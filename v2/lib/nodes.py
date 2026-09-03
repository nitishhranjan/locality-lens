"""Graph nodes.

Each node does one stage of work and reports on it through LangGraph's custom
stream writer, which is what lets the UI render a live agent trace while the
graph is still running.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer

from . import llm
from .config import SEARCH_RADIUS_M
from .geo import (
    deduplicate,
    fetch_park_area_km2,
    fetch_pois,
    geocode,
    parse_coordinates,
    reverse_geocode,
)
from .metrics import calculate, classify
from .state import LocalityState

STAGES = [
    ("validate", "Validating input"),
    ("intent", "Reading intent & selecting metrics"),
    ("geocode", "Resolving location"),
    ("fetch", "Querying OpenStreetMap"),
    ("calculate", "Computing metrics"),
    ("summarize", "Writing analysis"),
]


def _client(config: RunnableConfig) -> httpx.AsyncClient:
    """The shared HTTP client, handed in by the caller via config."""
    return config["configurable"]["client"]


def _elapsed(config: RunnableConfig) -> float:
    return round(time.perf_counter() - config["configurable"]["t0"], 2)


def _stage(config: RunnableConfig, stage_id: str, status: str, detail: str | None = None) -> None:
    event: dict[str, Any] = {"type": "stage", "id": stage_id, "status": status}
    if detail:
        event["detail"] = detail
    if status in ("done", "error"):
        event["elapsed"] = _elapsed(config)
    get_stream_writer()(event)


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------
async def validate_input(state: LocalityState, config: RunnableConfig) -> dict[str, Any]:
    _stage(config, "validate", "running")
    text = (state.get("user_input") or "").strip()

    if len(text) < 2:
        _stage(config, "validate", "error", "Input too short")
        return {"errors": ["Enter a location - an address or 'lat, lon'."]}

    coords = parse_coordinates(text)
    _stage(config, "validate", "done", "Coordinates supplied" if coords else "Address supplied")
    return {"user_input": text, "coordinates": coords}


async def extract_intent(state: LocalityState, config: RunnableConfig) -> dict[str, Any]:
    """Runs concurrently with `resolve_location` - they share no inputs."""
    _stage(config, "intent", "running")
    writer = get_stream_writer()

    intent = await llm.extract_intent(state.get("user_profile") or "", state["user_input"])

    # An unreadable description stops the run. Continuing would produce a
    # generic analysis presented as a personalised one, which is worse than
    # saying plainly that the description did not land.
    if intent.get("reason") == "unreadable_profile":
        _stage(config, "intent", "error", "Could not read the description")
        writer(
            {
                "type": "rephrase",
                "message": llm.UNREADABLE_HINT,
                "examples": llm.UNREADABLE_EXAMPLES,
            }
        )
        return {"needs_rephrase": True}

    writer({"type": "intent", "data": intent})

    detail = f"{len(intent['selected_metrics'])} metrics selected"
    warnings: list[str] = []
    if intent.get("degraded"):
        detail += " (fallback)"
        # v1 hid LLM failures behind default metrics with no signal, so a dead
        # model looked like a working app. Always say when we fell back, and why.
        writer(
            {
                "type": "notice",
                "message": intent.get("hint")
                or "Metric selection fell back to a standard set for this profile.",
            }
        )
        if intent.get("error"):
            warnings.append(intent["error"])

    _stage(config, "intent", "done", detail)
    return {
        "user_intent": intent,
        "selected_metrics": intent["selected_metrics"],
        "warnings": warnings,
    }


async def resolve_location(state: LocalityState, config: RunnableConfig) -> dict[str, Any]:
    _stage(config, "geocode", "running")
    writer = get_stream_writer()
    coords = state.get("coordinates")

    try:
        if coords:
            # Name the spot so the summary model gets real context instead of
            # a pair of numbers. Falls back to the numeric label.
            label = await reverse_geocode(coords[0], coords[1], _client(config))
            location = {
                "lat": coords[0],
                "lon": coords[1],
                "address": label or f"{coords[0]:.5f}, {coords[1]:.5f}",
            }
        else:
            location = await geocode(state["user_input"], _client(config))
    except Exception as exc:
        _stage(config, "geocode", "error", str(exc)[:160])
        return {"errors": [str(exc)[:200]]}

    writer({"type": "location", "data": location})
    _stage(config, "geocode", "done", location["address"][:60])
    return {
        "coordinates": (location["lat"], location["lon"]),
        "address": location["address"],
    }


async def fetch_osm(state: LocalityState, config: RunnableConfig) -> dict[str, Any]:
    """Join point: both parallel branches must finish before this runs.

    `intent` reaches here unconditionally, so if `geocode` failed this node
    still gets scheduled - with no coordinates to work from. Bail out and let
    the router hand off to handle_error rather than dereferencing None.
    """
    if state.get("errors") or state.get("needs_rephrase") or not state.get("coordinates"):
        return {}

    _stage(config, "fetch", "running")
    writer = get_stream_writer()

    lat, lon = state["coordinates"]
    try:
        raw_pois, park_area = await asyncio.gather(
            fetch_pois(lat, lon, SEARCH_RADIUS_M, _client(config)),
            fetch_park_area_km2(lat, lon, SEARCH_RADIUS_M, _client(config)),
        )
    except Exception as exc:
        _stage(config, "fetch", "error", str(exc)[:160])
        return {"errors": [f"OpenStreetMap query failed: {str(exc)[:160]}"]}

    for poi in raw_pois:
        poi["category"] = classify(poi)
    pois = deduplicate([p for p in raw_pois if p["category"]])

    counts: dict[str, int] = {}
    for poi in pois:
        counts[poi["category"]] = counts.get(poi["category"], 0) + 1

    _stage(
        config,
        "fetch",
        "done",
        f"{len(raw_pois)} features, {len(pois)} after dedupe, {len(counts)} categories",
    )
    # Trimmed payload for the map - full tag dictionaries would multiply the
    # response size for no client-side benefit.
    writer(
        {
            "type": "pois",
            "data": [
                {"lat": round(p["lat"], 6), "lon": round(p["lon"], 6), "c": p["category"], "n": p.get("name")}
                for p in pois
            ],
            "counts": counts,
        }
    )
    return {"pois": pois, "counts": counts, "park_area_km2": park_area, "raw_feature_count": len(raw_pois)}


async def calculate_statistics(state: LocalityState, config: RunnableConfig) -> dict[str, Any]:
    _stage(config, "calculate", "running")
    stats = calculate(
        state["counts"],
        state.get("park_area_km2", 0.0),
        SEARCH_RADIUS_M,
        state["selected_metrics"],
    )
    get_stream_writer()({"type": "stats", "data": stats})
    _stage(config, "calculate", "done", f"{len(stats)} metrics computed")
    return {"statistics": stats}


async def generate_summary(state: LocalityState, config: RunnableConfig) -> dict[str, Any]:
    _stage(config, "summarize", "running")
    writer = get_stream_writer()

    parts: list[str] = []
    try:
        async for token in llm.stream_summary(
            state.get("address") or "",
            state.get("user_profile") or "",
            state.get("user_intent") or {},
            state["statistics"],
            state["counts"],
        ):
            parts.append(token)
            writer({"type": "token", "text": token})
    except Exception as exc:
        if not parts:
            text = llm.fallback_summary(state.get("address") or "", state["statistics"], state["counts"])
            parts.append(text)
            writer({"type": "token", "text": text})
            writer({"type": "notice", "message": f"Summary fell back to raw metrics: {str(exc)[:140]}"})

    _stage(config, "summarize", "done")
    return {"summary": "".join(parts)}


async def handle_error(state: LocalityState, config: RunnableConfig) -> dict[str, Any]:
    # Reachable from either branch, so report the first failure only.
    if state.get("reported"):
        return {}
    errors = state.get("errors") or ["Unknown error"]
    get_stream_writer()({"type": "error", "message": errors[0]})
    return {"reported": True}
