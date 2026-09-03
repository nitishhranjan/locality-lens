"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import AgentTrace from "@/components/AgentTrace";
import MetricGrid from "@/components/MetricGrid";
import MapPanel from "@/components/MapPanel";
import {
  PROFILES,
  type Intent,
  type LocationInfo,
  type Metric,
  type Poi,
  type Stage,
  type StreamEvent,
} from "@/components/types";

const STAGE_LABELS: [string, string][] = [
  ["validate", "Validating input"],
  ["intent", "Reading intent & selecting metrics"],
  ["geocode", "Resolving location"],
  ["fetch", "Querying OpenStreetMap"],
  ["calculate", "Computing metrics"],
  ["summarize", "Writing analysis"],
];

const freshStages = (): Stage[] =>
  STAGE_LABELS.map(([id, label]) => ({ id, label, status: "idle" as const }));

export default function Page() {
  const [location, setLocation] = useState("Indiranagar, Bangalore");
  const [profile, setProfile] = useState<string>(PROFILES[0]);
  // Free-text profile, as v1's "Custom" option had. The backend takes any
  // string here - the model infers priorities and picks metrics from it - so
  // this is a richer input than the presets, not a lesser one.
  const [custom, setCustom] = useState(false);
  const [customText, setCustomText] = useState("");
  const [running, setRunning] = useState(false);

  const [stages, setStages] = useState<Stage[]>(freshStages);
  const [intent, setIntent] = useState<Intent | null>(null);
  const [resolved, setResolved] = useState<LocationInfo | null>(null);
  const [pois, setPois] = useState<Poi[]>([]);
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [summary, setSummary] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rephrase, setRephrase] = useState<{ message: string; examples: string[] } | null>(null);
  const customRef = useRef<HTMLTextAreaElement>(null);
  const [elapsed, setElapsed] = useState<number | null>(null);
  const [provider, setProvider] = useState<{ provider: string; ok: boolean } | null>(null);

  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then((d) => setProvider({ provider: d.provider ?? "unset", ok: Boolean(d.ok) }))
      .catch(() => setProvider({ provider: "offline", ok: false }));
  }, []);

  const apply = useCallback((event: StreamEvent) => {
    switch (event.type) {
      case "stage":
        setStages((prev) =>
          prev.map((s) =>
            s.id === event.id
              ? { ...s, status: event.status, detail: event.detail ?? s.detail, elapsed: event.elapsed ?? s.elapsed }
              : s
          )
        );
        break;
      case "intent":
        setIntent(event.data);
        break;
      case "location":
        setResolved(event.data);
        break;
      case "pois":
        setPois(event.data);
        break;
      case "stats":
        setMetrics(Object.values(event.data));
        break;
      case "token":
        setSummary((prev) => prev + event.text);
        break;
      case "notice":
        setNotice(event.message);
        break;
      case "rephrase":
        setRephrase({ message: event.message, examples: event.examples });
        // Put the cursor back where the fix has to happen.
        setTimeout(() => customRef.current?.focus(), 60);
        break;
      case "error":
        setError(event.message);
        break;
      case "done":
        setElapsed(event.elapsed);
        break;
    }
  }, []);

  // What actually gets sent: the typed description when custom mode is on,
  // otherwise the selected preset.
  const effectiveProfile = custom ? customText.trim() : profile;

  const run = useCallback(async () => {
    if (!location.trim() || running) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setRunning(true);
    setStages(freshStages());
    setIntent(null);
    setResolved(null);
    setPois([]);
    setMetrics([]);
    setSummary("");
    setNotice(null);
    setError(null);
    setRephrase(null);
    setElapsed(null);

    try {
      const response = await fetch("/api/analyse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ location, profile: effectiveProfile }),
        signal: controller.signal,
      });

      if (!response.ok || !response.body) {
        throw new Error(`Server returned ${response.status}`);
      }

      // NDJSON: decode incrementally and dispatch on each complete line.
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop() ?? ""; // keep the trailing partial line
        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            apply(JSON.parse(line) as StreamEvent);
          } catch {
            /* ignore a malformed line rather than killing the stream */
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setError((err as Error).message || "Analysis failed");
      }
    } finally {
      setRunning(false);
    }
  }, [location, effectiveProfile, running, apply]);

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden>
              <circle cx="7" cy="7" r="4.4" stroke="#fff" strokeWidth="1.6" />
              <path d="M10.4 10.4 14 14" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
          </span>
          <span className="brand-name">Locality Lens</span>
        </div>

        <span className="pill">
          <span className={`dot ${provider?.ok ? "live" : "warn"}`} />
          {provider ? `${provider.provider}${provider.ok ? "" : " · no key"}` : "connecting…"}
        </span>
      </header>

      <section className="hero">
        <h1>
          Know a neighbourhood<br />
          <span className="grad">before you live in it.</span>
        </h1>
        <p>
          Every amenity within 2 km, pulled live from OpenStreetMap. A language model reads your
          situation, picks the metrics that actually matter to you, and writes the verdict.
        </p>
      </section>

      <div className="composer">
        <div className="composer-row">
          <input
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && run()}
            placeholder="Any address, or 12.9784, 77.6408"
            aria-label="Location"
            spellCheck={false}
          />
          <button
            className="go"
            onClick={run}
            disabled={running || !location.trim() || (custom && !customText.trim())}
          >
            {running ? "Analysing…" : "Analyse"}
            {!running && (
              <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden>
                <path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
          </button>
        </div>

        <div className="profiles">
          {PROFILES.map((p) => (
            <button
              key={p}
              className="chip"
              aria-pressed={!custom && profile === p}
              onClick={() => {
                setCustom(false);
                setProfile(profile === p ? "" : p);
              }}
            >
              {p}
            </button>
          ))}

          <button
            className="chip custom"
            aria-pressed={custom}
            onClick={() => setCustom((v) => !v)}
            title="Describe your situation in your own words"
          >
            <svg width="11" height="11" viewBox="0 0 16 16" fill="none" aria-hidden>
              <path
                d="M11.5 2.5a1.6 1.6 0 0 1 2.3 2.3L6 12.6l-3 .7.7-3 7.8-7.8Z"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinejoin="round"
              />
            </svg>
            Describe yourself
          </button>
        </div>

        {custom && (
          <div className="custom-wrap">
            <textarea
              ref={customRef}
              value={customText}
              onChange={(e) => setCustomText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) run();
              }}
              placeholder="e.g. I'm a fitness enthusiast who loves parks and gyms, work from home three days a week, and need good connectivity plus somewhere quiet to run in the mornings."
              aria-label="Describe your needs"
              maxLength={600}
            />
            <div className="custom-hint">
              <span>The model reads this and picks the metrics that fit — ⌘⏎ to run</span>
              <span>{customText.length}/600</span>
            </div>
          </div>
        )}
      </div>

      {rephrase && (
        <div className="rephrase" role="status">
          <div className="rephrase-head">
            <span className="rephrase-icon" aria-hidden>
              <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
                <path
                  d="M11.5 2.5a1.6 1.6 0 0 1 2.3 2.3L6 12.6l-3 .7.7-3 7.8-7.8Z"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinejoin="round"
                />
              </svg>
            </span>
            <div>
              <strong>Could you put that another way?</strong>
              <p>{rephrase.message}</p>
            </div>
          </div>

          <div className="rephrase-examples">
            {rephrase.examples.map((example) => (
              <button
                key={example}
                className="chip"
                onClick={() => {
                  // Load the example straight into the box so it can be
                  // edited rather than retyped from scratch.
                  setCustom(true);
                  setCustomText(example);
                  setRephrase(null);
                  setTimeout(() => customRef.current?.focus(), 60);
                }}
              >
                {example}
              </button>
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="notice err" style={{ marginTop: 18 }}>
          <span>⚠</span>
          <span>{error}</span>
        </div>
      )}
      {notice && !error && (
        <div className="notice warn" style={{ marginTop: 18 }}>
          <span>⚠</span>
          <span>{notice}</span>
        </div>
      )}

      <div className="grid">
        <div className="stack">
          <AgentTrace stages={stages} totalElapsed={elapsed} />

          {intent && (
            <section className="panel">
              <div className="panel-head">
                <div className="panel-title">
                  <span className="dot live" />
                  Understood intent
                </div>
                <span className="mono-sm">{intent.degraded ? "fallback" : intent.profile_type}</span>
              </div>
              <div className="panel-body">
                {intent.priorities.length > 0 && (
                  <div className="tag-group">
                    <div className="tag-group-label">Priorities</div>
                    <div className="tags">
                      {intent.priorities.map((p) => (
                        <span className="tag accent" key={p}>{p}</span>
                      ))}
                    </div>
                  </div>
                )}
                {intent.concerns.length > 0 && (
                  <div className="tag-group">
                    <div className="tag-group-label">Concerns</div>
                    <div className="tags">
                      {intent.concerns.map((c) => (
                        <span className="tag" key={c}>{c}</span>
                      ))}
                    </div>
                  </div>
                )}
                {intent.reasoning && (
                  <p style={{ margin: "14px 0 0", fontSize: 12.5, lineHeight: 1.6, color: "var(--text-dim)" }}>
                    {intent.reasoning}
                  </p>
                )}
              </div>
            </section>
          )}

          <MetricGrid metrics={metrics} />
        </div>

        <div className="stack">
          <MapPanel location={resolved} pois={pois} />

          <section className="panel">
            <div className="panel-head">
              <div className="panel-title">
                <span className={`dot ${summary ? "live" : ""}`} />
                Analysis
              </div>
              {resolved && (
                <span className="mono-sm" title={resolved.address}>
                  {resolved.lat.toFixed(4)}, {resolved.lon.toFixed(4)}
                </span>
              )}
            </div>
            <div className="panel-body">
              <div className="summary">
                {summary}
                {running && summary && <span className="caret" />}
              </div>
            </div>
          </section>
        </div>
      </div>

      <footer className="footer">
        <span>
          Data © OpenStreetMap contributors · Geocoding by Nominatim
        </span>
        <a href="https://github.com/nitishhranjan/locality-lens" target="_blank" rel="noreferrer">
          github.com/nitishhranjan/locality-lens
        </a>
      </footer>
    </main>
  );
}
