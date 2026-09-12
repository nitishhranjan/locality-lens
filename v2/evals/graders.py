"""Graders: score one model output, deterministically where possible.

Every grader here is programmatic. Nothing depends on a second model, so a
red result means the system under test moved, not that a judge had an off
day. An LLM judge is only worth adding for qualities these cannot express -
and it would need calibrating against human labels before its number counts.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from lib.metrics import CATALOG


@dataclass
class Result:
    passed: bool
    detail: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Intent: the usable gate
# ---------------------------------------------------------------------------
def graded_usable(intent: dict[str, Any], expect_usable: bool) -> Result:
    """Did the gate agree with the label?

    `reason == "unreadable_profile"` is how the pipeline signals a stop, so
    that - not the raw model field - is what the product actually acts on.
    """
    stopped = intent.get("reason") == "unreadable_profile"
    judged_usable = not stopped

    if judged_usable == expect_usable:
        return Result(True, "accepted" if judged_usable else "rejected")

    if expect_usable:
        return Result(False, "FALSE REJECT - a real description was refused")
    return Result(False, "FALSE ACCEPT - an empty description produced metrics")


# ---------------------------------------------------------------------------
# Intent: metric selection
# ---------------------------------------------------------------------------
def graded_metric_validity(intent: dict[str, Any]) -> Result:
    """Every selected key must exist, or the UI renders nothing for it."""
    keys = intent.get("selected_metrics") or []
    unknown = [k for k in keys if k not in CATALOG]
    if unknown:
        return Result(False, f"not in catalog: {', '.join(unknown)}")
    return Result(True, f"{len(keys)} valid keys")


def graded_metric_count(intent: dict[str, Any], low: int = 5, high: int = 7) -> Result:
    """The prompt asks for 5-7. Fewer starves the UI, more clutters it."""
    n = len(intent.get("selected_metrics") or [])
    if low <= n <= high:
        return Result(True, f"{n} metrics")
    return Result(False, f"{n} metrics, expected {low}-{high}")


def graded_relevance(
    intent: dict[str, Any], require_any: Iterable[str], forbid: Iterable[str]
) -> Result:
    """The weakest defensible claim: something obviously relevant is present,
    and nothing plainly wrong for this person is."""
    keys = set(intent.get("selected_metrics") or [])
    require_any, forbid = list(require_any), list(forbid)

    missing = not (set(require_any) & keys) if require_any else False
    wrong = sorted(keys & set(forbid))

    if missing and wrong:
        return Result(False, f"none of {require_any}; and picked {wrong}")
    if missing:
        return Result(False, f"none of {require_any} selected")
    if wrong:
        return Result(False, f"selected irrelevant: {wrong}")
    return Result(True, "relevant")


# ---------------------------------------------------------------------------
# Summary: faithfulness to the supplied figures
# ---------------------------------------------------------------------------
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")

# Numbers that legitimately appear without being a metric value: the 0-100
# scale, the 2 km search radius, and small numbers that read as prose
# ("two kilometres", "a handful of 3 or 4"). Only figures at or above this
# threshold are treated as claims about the data.
_PROSE_CEILING = 10


def _numbers_in(text: str) -> set[float]:
    found = set()
    for raw in _NUMBER.findall(text):
        try:
            found.add(float(raw.replace(",", "")))
        except ValueError:
            continue
    return found


def allowed_numbers(metrics: dict[str, Any], total_pois: int) -> set[float]:
    """Every figure the model was actually given."""
    allowed: set[float] = {100.0, float(total_pois), 2.0, 2000.0}
    for metric in metrics.values():
        value = metric["value"] if isinstance(metric, dict) else metric
        try:
            allowed.add(float(value))
        except (TypeError, ValueError):
            continue
    # Percentages of the scale read naturally and are derivable, e.g. "83 out
    # of 100"; nothing else is.
    return allowed


def graded_faithfulness(
    summary: str, metrics: dict[str, Any], total_pois: int
) -> Result:
    """Flag any figure the model was not given.

    This is the grader that matters most for credibility. v1's output claimed
    Indiranagar sat "far above the city average of 15-20 schools per
    comparable zone" - two numbers nobody supplied, stated as fact.
    """
    allowed = allowed_numbers(metrics, total_pois)
    invented = sorted(
        n for n in _numbers_in(summary) if n >= _PROSE_CEILING and n not in allowed
    )
    if invented:
        pretty = ", ".join(f"{n:g}" for n in invented)
        return Result(False, f"figures not supplied: {pretty}", {"invented": invented})
    return Result(True, "all figures supplied")


def graded_cites_metrics(summary: str, metrics: dict[str, Any], minimum: int = 3) -> Result:
    """A summary that names no numbers is generic prose, not an analysis."""
    present = _numbers_in(summary)
    cited = [
        key
        for key, metric in metrics.items()
        if float(metric["value"] if isinstance(metric, dict) else metric) in present
    ]
    if len(cited) >= minimum:
        return Result(True, f"cited {len(cited)}/{len(metrics)} metrics")
    return Result(False, f"cited only {len(cited)}/{len(metrics)}, want >= {minimum}")


_HEDGE = re.compile(
    r"\b(however|but|although|though|trade-?off|downside|drawback|on the other hand"
    r"|the catch|less|weak|lack|limited|scarce|short of|worth noting|caveat)\b",
    re.I,
)


def graded_names_a_tradeoff(summary: str) -> Result:
    """The prompt requires an honest weakness in the closing paragraph.

    Keyword presence is a proxy, not proof - it can be fooled by a sentence
    that uses "however" without conceding anything. It is here to catch the
    obvious failure (pure marketing copy); judging whether the trade-off is
    *substantive* is the job an LLM judge would take on.
    """
    tail = summary[len(summary) // 2 :]
    hit = _HEDGE.search(tail)
    if hit:
        return Result(True, f"hedge term {hit.group(0)!r} in second half")
    return Result(False, "no trade-off language in the second half")


def graded_shape(summary: str, min_chars: int = 400, max_chars: int = 3000) -> Result:
    """Three short paragraphs of prose - no bullets, no headings."""
    if not (min_chars <= len(summary) <= max_chars):
        return Result(False, f"{len(summary)} chars, want {min_chars}-{max_chars}")
    if re.search(r"^\s*[-*•]\s+", summary, re.M):
        return Result(False, "contains bullet points")
    if re.search(r"^\s*#{1,6}\s+", summary, re.M):
        return Result(False, "contains markdown headings")
    return Result(True, f"{len(summary)} chars, prose")
