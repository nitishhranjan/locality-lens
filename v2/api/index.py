"""FastAPI entrypoint - deployed as a Vercel Python Function."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Vercel bundles from the project root, so make `lib` importable either way.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Local development only - on Vercel these come from project env vars.
if not os.getenv("VERCEL"):
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    except ImportError:
        pass

from lib.config import (  # noqa: E402
    APP_NAME,
    DEFAULT_LOCATION,
    FALLBACK_PROVIDER,
    SEARCH_RADIUS_M,
    provider_config,
)
from lib.metrics import CATALOG  # noqa: E402
from lib.pipeline import STAGES, analyse  # noqa: E402

from contextlib import asynccontextmanager  # noqa: E402

from lib import llm  # noqa: E402


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await llm.aclose_all()


app = FastAPI(title=APP_NAME, docs_url=None, redoc_url=None, lifespan=lifespan)


class AnalyseRequest(BaseModel):
    location: str
    profile: str = ""


@app.get("/api/health")
async def health() -> dict:
    """Report whether the configured provider actually has a key present."""
    try:
        cfg = provider_config()
        provider, has_key, error = cfg["name"], bool(cfg["api_key"]), None
        models = {"intent": cfg["intent_model"], "summary": cfg["summary_model"]}
    except ValueError as exc:
        provider, has_key, error, models = None, False, str(exc), {}

    # A usable fallback means the app still works even if the primary is out
    # of credits, so report readiness on either having a key.
    fallback, fallback_ok = FALLBACK_PROVIDER, False
    try:
        fallback_ok = bool(provider_config(FALLBACK_PROVIDER).get("api_key"))
    except ValueError:
        fallback = None

    return {
        "ok": has_key or fallback_ok,
        "provider": provider,
        "models": models,
        "key_present": has_key,
        "fallback": fallback if fallback != provider else None,
        "fallback_ready": fallback_ok if fallback != provider else None,
        "error": error,
        "radius_m": SEARCH_RADIUS_M,
    }


@app.get("/api/meta")
async def meta() -> dict:
    """Static metadata the UI needs to render before any analysis runs."""
    return {
        "app": APP_NAME,
        "default_location": DEFAULT_LOCATION,
        "stages": [{"id": sid, "label": label} for sid, label in STAGES],
        "catalog": CATALOG,
    }


@app.post("/api/analyse")
async def analyse_endpoint(body: AnalyseRequest) -> StreamingResponse:
    """Stream the analysis as newline-delimited JSON.

    NDJSON rather than SSE: the payload is consumed by fetch + a stream
    reader, so the event-type framing SSE adds would just be overhead.
    """

    async def generate():
        try:
            async for event in analyse(body.location, body.profile):
                yield json.dumps(event, separators=(",", ":")) + "\n"
        except Exception as exc:  # never leave the client hanging
            yield json.dumps({"type": "error", "message": str(exc)[:300]}) + "\n"

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
