# Locality Lens v2

A Vercel-deployable rebuild of Locality Lens: a Next.js frontend over a lean
FastAPI backend, streaming a live agent trace as it works.

The v1 Streamlit app lives in the repository root and still runs. This is a
parallel version, not a replacement.

---

## Why a rewrite

Streamlit cannot run on Vercel. It is a stateful, long-lived server that keeps
per-session state in process memory behind a WebSocket; Vercel Functions are
ephemeral and scale to zero, and a session would die at the duration cap. The
Python *pipeline* runs on Vercel perfectly well - only the UI layer had to go.

So v2 splits the app: a Next.js frontend and a Python function, in one project.

## What changed

### Dependencies: 639 MB → 83 MB

v1 pulled in the full geospatial stack to make what are, underneath, two HTTP
calls to public APIs. v2 makes those calls directly.

| Removed | Size | Replaced with |
|---|---|---|
| `osmnx`, `geopandas`, `pyogrio`, `pyproj` | ~110 MB | Raw Overpass + Nominatim over `httpx` |
| `pandas` + `pyarrow` | ~197 MB | Plain dicts and lists |
| `scipy` (only used for `cKDTree`) | 98 MB | Grid-hash dedupe, linear time, ~30 lines |
| `numpy`, `networkx` | ~52 MB | stdlib `math` |
| `streamlit`, `pydeck`, `altair`, `PIL` | ~72 MB | Next.js + MapLibre |
| `langchain`, `langchain-groq` | — | `openai` SDK directly (LangGraph kept) |

Everything deployed now fits in six packages. Both LLM providers speak the
OpenAI wire protocol, so **one SDK serves both** - Groq is reached by pointing
`base_url` at its OpenAI-compatible endpoint.

### LangGraph is kept

The orchestration is still a LangGraph `StateGraph` — same six stages and the
same error exits as v1. It adds ~30 MB (83 MB total, against Vercel's 500 MB
Python limit) and every binary dependency has Linux wheels, so it deploys
without trouble.

The one thing worth knowing: `invoke()` returns only a final state, which
would kill the live trace. Nodes therefore emit progress through
`get_stream_writer()`, consumed with `astream(stream_mode="custom")` — so the
graph structure and the streaming UI coexist rather than trading off.

### Bugs fixed along the way

- **Park area always read 0.00 km².** v1 called `.area` on an EPSG:4326
  GeoDataFrame, which returns *degrees²*, then divided by 1e6. 97 park polygons
  summed to `2.29e-05`, floored to zero. v2 projects to local metres first.
- **Every score pinned to exactly 100.** v1 used `min(100, count * k)`, so any
  dense urban area maxed out and the scores could not distinguish anywhere from
  anywhere else. v2 uses a saturating curve, so the range stays usable.
- **Silent LLM failures.** v1 swallowed model errors into a default metric set
  with no signal, so a dead model looked like a working app. v2 surfaces every
  fallback in the trace *and* says why.

---

## Running it

Two processes: Next.js on :3000, FastAPI on :8000. Next proxies `/api/*` to the
Python server in development.

```bash
npm install
python3 -m venv .venv-api && .venv-api/bin/pip install -r requirements-dev.txt
```

Create `.env`:

```
GROQ_API_KEY=gsk_...
LLM_PROVIDER=groq
FALLBACK_PROVIDER=groq

# Optional - only needed if you switch LLM_PROVIDER to openai
OPENAI_API_KEY=sk-...
```

Then, in two terminals:

```bash
npm run api
```

```bash
npm run dev
```

`GET /api/health` reports which provider is live and whether its key is present.

## Profiles

Six presets, plus **Describe yourself** — a free-text box, as v1's "Custom"
option had. The backend takes any string: the model reads it, infers
priorities and concerns, and selects metrics to match. Free text is the richer
input, not a lesser one:

| Input | Metrics selected |
|---|---|
| *Family with kids* (preset) | schools, kindergartens, parks, playgrounds, hospitals, bus stops, walkability |
| *"fitness enthusiast, loves parks and gyms, needs connectivity, quiet morning runs"* | gyms, parks, park area, walkability, transit, green score |
| *"wheelchair user, step-free access, pharmacies and hospitals close, doesn't drive"* | pharmacies, hospitals, bus stops, metro & rail, walkability, transit |

## Providers

**Groq is the default and runs everything.** OpenAI stays fully wired: set
`LLM_PROVIDER=openai` to use it.

| Provider | Intent | Summary |
|---|---|---|
| `groq` (default) | `openai/gpt-oss-20b` | `openai/gpt-oss-120b` |
| `openai` | `gpt-4o-mini` | `gpt-4o` |

`FALLBACK_PROVIDER` (default `groq`) is retried automatically when the primary
fails at request time — an OpenAI account out of credits 429s on every call,
and falling through to Groq beats degrading the analysis to canned defaults.
For summaries the switch only happens **before the first token**; once text has
reached the client, restarting on another model would splice two different
answers together. `GET /api/health` reports the active provider and whether the
fallback is ready.

Models are overridable with `INTENT_MODEL` and `SUMMARY_MODEL` — worth knowing,
because **Groq retires models regularly**; v1 broke exactly this way when
`llama-3.1-8b-instant` was decommissioned. A retirement is now a one-line env
change, not a code hunt.

## Deploying to Vercel

Set the project **Root Directory** to `v2`, add `GROQ_API_KEY` as an
environment variable, and deploy. `vercel.json` already excludes
`node_modules`, `.next` and the local venv from the Python bundle.

No map key is needed: OpenFreeMap serves vector tiles without signup. CARTO's
dark tiles look similar but now watermark anonymous requests.

## Architecture

```
Browser ──POST /api/analyse──▶ FastAPI (Vercel Python Function)
   ▲                                │
   └────── NDJSON event stream ◀─────┘

validate → intent ─┐
                   ├─▶ fetch OSM → metrics → summary
        geocode ───┘
   (intent and geocode run concurrently)
```

Events are newline-delimited JSON rather than SSE — the client reads them with
`fetch` and a stream reader, so SSE's event framing would be pure overhead.
Stage updates, intent, POIs, metrics and summary tokens all arrive on the one
stream, which is what lets the UI fill in progressively instead of blocking on
a single response.

## Layout

```
v2/
├── api/index.py        FastAPI entrypoint (the Vercel function)
├── lib/
│   ├── config.py       Provider + model resolution
│   ├── geo.py          Nominatim, Overpass, dedupe, polygon area
│   ├── metrics.py      POI classification + metric catalog
│   ├── llm.py          Intent extraction + streaming summary
│   ├── state.py        LocalityState (graph schema)
│   ├── nodes.py        One function per stage
│   └── pipeline.py     StateGraph wiring + event stream
├── app/                Next.js App Router + design tokens
└── components/         Agent trace, metric grid, map
```

## Troubleshooting

**`Cannot find module './NNN.js'`** — a stale `.next` cache, usually from
running `next build` while `next dev` was live (they share the directory).
Stop both, then:

```bash
rm -rf .next && npm run dev
```

Never run `npm run build` while the dev server is up.

## Known limits

- **Overpass is a free, shared, rate-limited service.** Heavy use returns 429s.
  There is a 15-minute in-process cache and a mirror-plus-retry fallback, but a
  cold serverless instance can still be throttled. A persistent cache (Vercel
  KV, Redis) is the real fix if this ever sees traffic.
- The map filter and popups are client-side; filtering uses MapLibre
  `setFilter` so toggling stays instant at a few thousand points.
- POI counts reflect **mapping density, not ground truth**. A high count can
  mean a well-mapped area as much as a well-served one; OSM coverage varies
  enormously between cities.
- Scores are heuristics over amenity counts. They are useful for comparing
  areas within one city, and much weaker across countries.
