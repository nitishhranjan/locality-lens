"""LLM access for intent extraction and summary generation.

Both OpenAI and Groq speak the OpenAI wire protocol, so one SDK covers both
providers - selected with LLM_PROVIDER. That keeps the bundle to a single
client library instead of one per vendor.
"""
from __future__ import annotations

import json
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from .config import FALLBACK_PROVIDER, provider_config
from .metrics import catalog_for_prompt, default_metrics, validate

_INTENT_SYSTEM = """You analyse what someone needs from a neighbourhood.

Given a user profile, infer their priorities and pick the metrics that matter \
most to them from the catalog.

Return ONLY a JSON object with this exact shape:
{
  "profile_type": "short_snake_case_label",
  "priorities": ["3-6 short phrases"],
  "concerns": ["2-4 short phrases"],
  "lifestyle": "one short sentence",
  "selected_metrics": ["5-7 metric keys from the catalog"],
  "reasoning": "one sentence on why these metrics"
}

Available metrics:
{catalog}

Choose metric keys EXACTLY as written above. Pick 5-7."""

_SUMMARY_SYSTEM = """You are a location analyst writing for someone deciding \
where to live.

Write 3 short paragraphs of flowing prose:
1. What this area is like in character and feel.
2. How it scores against what this person specifically cares about - cite the \
actual numbers you were given.
3. An honest verdict, including at least one genuine trade-off or weakness.

Rules:
- Reference the real figures provided. Never invent a number.
- Scores are 0-100 where higher is better. Counts are within a ~2 km radius.
- Be specific and grounded. No marketing language, no bullet points, no headings.
- If a number looks weak, say so plainly rather than spinning it."""


# Clients are cached per provider: each one owns an HTTP connection pool, so
# reusing it across invocations keeps warm connections on a warm serverless
# instance instead of paying TLS setup every request.
_CLIENTS: dict[str, AsyncOpenAI] = {}


def _client(cfg: dict) -> AsyncOpenAI:
    if not cfg.get("api_key"):
        raise RuntimeError(
            f"{cfg['key_env']} is not set - required for LLM_PROVIDER={cfg['name']}"
        )
    if cfg["name"] not in _CLIENTS:
        _CLIENTS[cfg["name"]] = AsyncOpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])
    return _CLIENTS[cfg["name"]]


UNREADABLE_HINT = (
    "Could not read that description well enough to pick metrics for you. "
    "Try a sentence or two about how you live - who is moving, what you need "
    "nearby, what you want to avoid."
)

UNREADABLE_EXAMPLES = [
    "Family of four, need good schools and parks within walking distance",
    "I work from home and cycle everywhere; cafes and quiet streets matter",
    "Retired, no car, want pharmacies and a doctor close by",
]

# Providers reject a malformed structured response with a 400 rather than
# returning the text, so the failure has to be recognised from the message.
_JSON_FAILURE_MARKERS = (
    "failed to generate json",
    "json_validate_failed",
    "failed_generation",
    "response_format",
)


def _is_json_failure(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in _JSON_FAILURE_MARKERS)


def _provider_chain() -> list[dict]:
    """The provider to try, then the fallback if it is a different, usable one.

    An OpenAI account out of credits returns 429 on every call. Rather than
    degrading the whole analysis to canned defaults, fall through to Groq.
    """
    chain = [provider_config()]
    if FALLBACK_PROVIDER and FALLBACK_PROVIDER != chain[0]["name"]:
        try:
            fallback = provider_config(FALLBACK_PROVIDER)
            if fallback.get("api_key"):
                chain.append(fallback)
        except ValueError:
            pass
    return chain


async def aclose_all() -> None:
    """Close pooled clients. Called from the app's shutdown hook."""
    while _CLIENTS:
        _, client = _CLIENTS.popitem()
        try:
            await client.close()
        except Exception:
            pass


async def extract_intent(profile: str, location: str) -> dict[str, Any]:
    """Infer user intent and select metrics in a single call.

    Falls back to a profile-matched default set if the call or the parse
    fails, so a bad LLM response degrades the analysis rather than ending it.
    """
    fallback = {
        "profile_type": (profile or "general").lower().replace(" ", "_")[:40],
        "priorities": [],
        "concerns": [],
        "lifestyle": "",
        "selected_metrics": default_metrics(profile),
        "reasoning": "Default metric set for this profile.",
        "degraded": True,
    }

    if not profile:
        return fallback

    system = _INTENT_SYSTEM.replace("{catalog}", catalog_for_prompt())
    user = f"Profile: {profile}\nLocation of interest: {location}"

    parsed, errors, used, unreadable = None, [], None, False
    for cfg in _provider_chain():
        # Two passes: a terse or unusual description can make the model emit
        # something that is not valid JSON, which the provider rejects with a
        # 400 rather than returning text. Retrying once with an explicit
        # reminder recovers most of those before anyone sees an error.
        for attempt in range(2):
            messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
            if attempt:
                messages.append(
                    {
                        "role": "system",
                        "content": "The previous attempt did not return valid JSON. Respond with "
                        "the JSON object only - no prose, no code fences. If the profile is "
                        "vague, infer reasonable priorities rather than asking for more detail.",
                    }
                )
            try:
                response = await _client(cfg).chat.completions.create(
                    model=cfg["intent_model"],
                    temperature=0.4 if not attempt else 0.1,
                    max_tokens=700,
                    response_format={"type": "json_object"},
                    messages=messages,
                )
                parsed = json.loads(response.choices[0].message.content or "{}")
                used = cfg["name"]
                break
            except Exception as exc:
                text = str(exc)
                if _is_json_failure(text):
                    unreadable = True
                    continue  # retry is worth a shot
                errors.append(f"{cfg['name']}: {text[:120]}")
                break  # a real provider fault - move to the next provider
        if parsed is not None:
            break

    if parsed is None:
        fallback["reason"] = "unreadable_profile" if unreadable else "provider_error"
        fallback["hint"] = (
            UNREADABLE_HINT
            if unreadable
            else "The language model could not be reached, so a standard metric set was used."
        )
        fallback["error"] = " | ".join(errors)[:240] or "model could not produce a usable response"
        return fallback

    metrics = validate(parsed.get("selected_metrics") or [])
    if not metrics:
        metrics = default_metrics(profile)

    return {
        "profile_type": parsed.get("profile_type") or fallback["profile_type"],
        "priorities": parsed.get("priorities") or [],
        "concerns": parsed.get("concerns") or [],
        "lifestyle": parsed.get("lifestyle") or "",
        "selected_metrics": metrics,
        "reasoning": parsed.get("reasoning") or "",
        "degraded": False,
        "provider": used,
    }


async def stream_summary(
    address: str,
    profile: str,
    intent: dict[str, Any],
    stats: dict[str, Any],
    counts: dict[str, int],
) -> AsyncIterator[str]:
    """Yield the summary token by token so the UI can render it live."""
    lines = [f"{m['label']}: {m['value']} ({m['unit']})" for m in stats.values()]
    context = "\n".join(
        [
            f"Location: {address}",
            f"Person: {profile or 'unspecified'}",
            f"Their priorities: {', '.join(intent.get('priorities') or []) or 'unspecified'}",
            f"Their concerns: {', '.join(intent.get('concerns') or []) or 'unspecified'}",
            "",
            "Metrics selected for this person:",
            *lines,
            "",
            f"Total amenities mapped nearby: {sum(counts.values())}",
        ]
    )

    # Try the configured provider, then the fallback. Only safe to switch
    # before the first token: once text has reached the client, restarting on
    # another model would splice two different answers together.
    errors = []
    for cfg in _provider_chain():
        try:
            stream = await _client(cfg).chat.completions.create(
                model=cfg["summary_model"],
                temperature=0.6,
                max_tokens=900,
                stream=True,
                messages=[
                    {"role": "system", "content": _SUMMARY_SYSTEM},
                    {"role": "user", "content": context},
                ],
            )
        except Exception as exc:
            errors.append(f"{cfg['name']}: {str(exc)[:120]}")
            continue

        # `async with` releases the underlying HTTP connection even if the
        # caller stops consuming partway through - otherwise an abandoned
        # stream leaves the pool's byte-iterator to be torn down at exit.
        async with stream:
            async for chunk in stream:
                if chunk.choices and (delta := chunk.choices[0].delta.content):
                    yield delta
        return

    raise RuntimeError(" | ".join(errors) or "No usable LLM provider configured")


def fallback_summary(address: str, stats: dict[str, Any], counts: dict[str, int]) -> str:
    """Deterministic summary used when the LLM is unreachable."""
    top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:4]
    highlights = ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in top if v)
    scores = [m for m in stats.values() if m["unit"] == "score"]
    score_text = ", ".join(f"{m['label']} {m['value']}/100" for m in scores)

    parts = [
        f"{address} has {sum(counts.values())} amenities mapped within a 2 km radius"
        + (f", led by {highlights}." if highlights else "."),
    ]
    if score_text:
        parts.append(f"Scores for this profile: {score_text}.")
    parts.append(
        "This is a generated fallback - the language model was unavailable, "
        "so these are the raw measurements without interpretation."
    )
    return " ".join(parts)
