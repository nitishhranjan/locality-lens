"""Configuration for Locality Lens v2.

Reads from environment only - on Vercel these come from project env vars,
locally from a .env file loaded by the caller.
"""
import os

# ---------------------------------------------------------------------------
# LLM provider
# ---------------------------------------------------------------------------
# Both providers speak the OpenAI wire protocol, so a single SDK serves both.
# Groq exposes an OpenAI-compatible endpoint, which keeps the bundle at one SDK.
PROVIDERS = {
    "openai": {
        "base_url": None,  # SDK default
        "key_env": "OPENAI_API_KEY",
        "intent_model": "gpt-4o-mini",
        "summary_model": "gpt-4o",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "intent_model": "openai/gpt-oss-20b",
        "summary_model": "openai/gpt-oss-120b",
    },
}

# Groq is the default: it is what the project actually runs on. OpenAI stays
# fully wired and can be selected with LLM_PROVIDER=openai.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()

# When the selected provider fails at request time, retry once on this one.
FALLBACK_PROVIDER = os.getenv("FALLBACK_PROVIDER", "groq").lower()


def provider_config(name: str | None = None) -> dict:
    """Resolve provider settings, allowing per-field env overrides."""
    name = (name or LLM_PROVIDER).lower()
    if name not in PROVIDERS:
        raise ValueError(f"Unknown LLM_PROVIDER {name!r}. Use one of: {', '.join(PROVIDERS)}")

    cfg = dict(PROVIDERS[name])
    cfg["name"] = name
    cfg["api_key"] = os.getenv(cfg["key_env"])
    cfg["intent_model"] = os.getenv("INTENT_MODEL", cfg["intent_model"])
    cfg["summary_model"] = os.getenv("SUMMARY_MODEL", cfg["summary_model"])
    return cfg


# ---------------------------------------------------------------------------
# Analysis settings
# ---------------------------------------------------------------------------
APP_NAME = "Locality Lens"
DEFAULT_LOCATION = "Indiranagar, Bangalore"
SEARCH_RADIUS_M = int(os.getenv("SEARCH_RADIUS_M", "2000"))

# Overpass mirrors - tried in order, so one dead mirror doesn't sink a request.
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
NOMINATIM_ENDPOINT = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE_ENDPOINT = "https://nominatim.openstreetmap.org/reverse"

# Nominatim's usage policy requires a identifying User-Agent.
USER_AGENT = os.getenv("USER_AGENT", "locality-lens/2.0 (github.com/nitishhranjan/locality-lens)")

HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "60"))
