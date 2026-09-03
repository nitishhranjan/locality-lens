"""The LangGraph workflow, exposed as a stream of UI events.

The graph mirrors v1's structure - the same six stages with the same error
exits - but progress is emitted through LangGraph's custom stream writer as
each node runs, rather than only being available from the final state. That is
what lets the UI render a live agent trace instead of blocking on one response.
"""
from __future__ import annotations

import time
from typing import Any, AsyncIterator

import httpx
from langgraph.graph import END, StateGraph

from .nodes import (
    STAGES,
    calculate_statistics,
    extract_intent,
    fetch_osm,
    generate_summary,
    handle_error,
    resolve_location,
    validate_input,
)
from .state import LocalityState

__all__ = ["STAGES", "analyse", "build_graph"]


def build_graph() -> StateGraph:
    """Wire the nodes together.

        validate ─┬─▶ intent ──┐
                  │            ├─▶ fetch ─▶ calculate ─▶ summarize ─▶ END
                  └─▶ geocode ─┘
                  └─▶ handle_error ─▶ END

    `intent` and `geocode` fan out from `validate` and rejoin at `fetch`.
    They share no inputs - one calls the LLM, the other Nominatim - so running
    them concurrently takes a round trip off the critical path. LangGraph waits
    for both before `fetch` starts, since `fetch` needs coordinates from one
    and `selected_metrics` (downstream) from the other.
    """
    graph = StateGraph(LocalityState)

    graph.add_node("validate", validate_input)
    graph.add_node("intent", extract_intent)
    graph.add_node("geocode", resolve_location)
    graph.add_node("fetch", fetch_osm)
    graph.add_node("calculate", calculate_statistics)
    graph.add_node("summarize", generate_summary)
    graph.add_node("handle_error", handle_error)

    graph.set_entry_point("validate")

    # Fan out to both branches, or bail out. A router returning a *list* is
    # how LangGraph expresses fan-out; the third argument is the set of
    # reachable nodes, used for graph drawing and validation.
    def route_after_validate(state: LocalityState) -> str | list[str]:
        return "handle_error" if state.get("errors") else ["intent", "geocode"]

    graph.add_conditional_edges(
        "validate", route_after_validate, ["handle_error", "intent", "geocode"]
    )

    # Intent has no failure exit of its own: llm.extract_intent already
    # degrades to a default metric set rather than raising, so the run
    # continues with a visible "(fallback)" marker in the trace.
    graph.add_edge("intent", "fetch")

    graph.add_conditional_edges(
        "geocode",
        lambda s: "error" if s.get("errors") else "ok",
        {"error": "handle_error", "ok": "fetch"},
    )
    graph.add_conditional_edges(
        "fetch",
        lambda s: "error" if s.get("errors") else "ok",
        {"error": "handle_error", "ok": "calculate"},
    )
    graph.add_conditional_edges(
        "calculate",
        lambda s: "error" if s.get("errors") else "ok",
        {"error": "handle_error", "ok": "summarize"},
    )

    graph.add_edge("summarize", END)
    graph.add_edge("handle_error", END)
    return graph


# Compiled once at import. On a warm serverless instance this is reused
# across invocations instead of being rebuilt per request.
_COMPILED = build_graph().compile()


async def analyse(user_input: str, profile: str) -> AsyncIterator[dict[str, Any]]:
    """Run the graph, yielding UI events as they are produced."""
    started = time.perf_counter()

    initial: LocalityState = {
        "user_input": user_input or "",
        "user_profile": profile or "",
        "errors": [],
        "warnings": [],
    }

    async with httpx.AsyncClient(follow_redirects=True) as client:
        config = {
            "configurable": {"client": client, "t0": started},
            # One analysis is well inside this; it only guards against a
            # pathological loop, which this graph has no way to create.
            "recursion_limit": 25,
        }

        errored = False
        # stream_mode="custom" surfaces exactly what the nodes hand to their
        # stream writer - our own event dicts, not LangGraph's internal
        # state deltas.
        async for event in _COMPILED.astream(initial, config=config, stream_mode="custom"):
            if event.get("type") == "error":
                errored = True
            yield event

        if not errored:
            yield {"type": "done", "elapsed": round(time.perf_counter() - started, 2)}
