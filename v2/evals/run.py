"""Eval runner.

    python -m evals.run                     # every suite, 3 runs per case
    python -m evals.run --suite usable      # one suite
    python -m evals.run --runs 5            # more repeats, tighter estimate
    python -m evals.run --save-baseline     # record today's scores as the bar

Each case is run several times because the models are sampled, not
deterministic: a single pass tells you almost nothing about a case that
passes four times in five. Scores are therefore rates, and the gate is a
rate too.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from lib import llm  # noqa: E402
from lib.config import provider_config  # noqa: E402
from evals import graders  # noqa: E402

DATASETS = Path(__file__).resolve().parent / "datasets"
RESULTS = Path(__file__).resolve().parent / "results"
BASELINE = Path(__file__).resolve().parent / "baseline.json"

# Gate thresholds.
#
# THESE ARE PLACEHOLDERS. Where the bar sits is a product judgement, not a
# technical one - "how often is it acceptable to wrongly tell someone to
# reword a perfectly good description?" Look at a few runs, then set them.
THRESHOLDS = {
    "usable.recall_real": 0.95,      # real descriptions accepted (avoid false rejects)
    "usable.recall_empty": 0.90,     # empty descriptions rejected (avoid hollow output)
    "relevance.pass_rate": 0.85,
    "faithfulness.no_invented": 0.95,
    "faithfulness.cites_metrics": 0.90,
}

# Groq's free tier is rate limited. Keep the pool small and back off hard:
# a 429 scored as a model decision is worse than a slow run. The first
# version of this file used a pool of 3 and reported 10% recall on the
# usable gate - every rate-limited call had been counted as "accepted".
# Groq's free tier is a requests-per-minute budget. Bursting into it and
# retrying makes things worse: the retries are themselves requests. Pacing
# every call to stay under the budget is what actually works, so requests are
# serialised and spaced rather than run in parallel.
DEFAULT_RPM = 26
RETRIES = 5
MIN_COVERAGE = 0.8  # refuse to report a score computed on less data than this


@dataclass
class CaseResult:
    suite: str
    case_id: str
    taxonomy: str = ""
    checks: dict[str, list[bool]] = field(default_factory=lambda: defaultdict(list))
    details: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    attempted: int = 0
    inconclusive: int = 0

    @property
    def coverage(self) -> float:
        """Fraction of attempted runs that produced an actual verdict."""
        if not self.attempted:
            return 0.0
        return (self.attempted - self.inconclusive) / self.attempted

    def record(self, name: str, result: graders.Result) -> None:
        self.checks[name].append(result.passed)
        if not result.passed:
            self.details.append(f"{name}: {result.detail}")

    def rate(self, name: str) -> float:
        runs = self.checks.get(name) or []
        return sum(runs) / len(runs) if runs else 0.0


class Throttle:
    """Serialise calls and hold them at most `rpm` per minute.

    A semaphore alone caps concurrency but not rate: two workers looping
    freely still burst well past a per-minute budget. This spaces the *start*
    of every request instead.
    """

    def __init__(self, rpm: int):
        self.interval = 60.0 / max(rpm, 1)
        self._lock = asyncio.Lock()
        self._next = 0.0

    async def __aenter__(self):
        await self._lock.acquire()
        now = asyncio.get_running_loop().time()
        if now < self._next:
            await asyncio.sleep(self._next - now)
        self._next = asyncio.get_running_loop().time() + self.interval
        return self

    async def __aexit__(self, *exc):
        self._lock.release()
        return False

    def penalise(self, seconds: float) -> None:
        """After a 429, push the next slot out - we are over budget."""
        loop = asyncio.get_running_loop()
        self._next = max(self._next, loop.time() + seconds)


# ---------------------------------------------------------------------------
# Talking to the provider
# ---------------------------------------------------------------------------
# A provider fault is not a verdict. `extract_intent` deliberately degrades
# rather than raising, so a 429 comes back as reason="provider_error" - which
# looks exactly like "the model accepted this input" unless it is handled
# explicitly. Retry it, and if it still fails, record the run as inconclusive
# instead of scoring it.
async def intent_with_retry(profile: str, location: str, throttle: "Throttle") -> dict:
    delay = 5.0
    intent: dict = {}
    for attempt in range(RETRIES):
        async with throttle:
            intent = await llm.extract_intent(profile, location)
        if intent.get("reason") != "provider_error":
            return intent
        if attempt < RETRIES - 1:
            wait = delay + random.random()
            throttle.penalise(wait)
            await asyncio.sleep(wait)
            delay *= 2
    return intent


async def summary_with_retry(address, profile, intent, stats, counts, throttle: "Throttle") -> str:
    delay = 5.0
    last: Exception | None = None
    for attempt in range(RETRIES):
        try:
            async with throttle:
                return "".join(
                    [c async for c in llm.stream_summary(address, profile, intent, stats, counts)]
                )
        except Exception as exc:
            last = exc
            if attempt < RETRIES - 1:
                wait = delay + random.random()
                throttle.penalise(wait)
                await asyncio.sleep(wait)
                delay *= 2
    raise last if last else RuntimeError("summary failed")


# ---------------------------------------------------------------------------
# Suites
# ---------------------------------------------------------------------------
async def run_usable(runs: int, sem: asyncio.Semaphore) -> list[CaseResult]:
    data = yaml.safe_load((DATASETS / "intent_usable.yaml").read_text())
    cases = (
        [(c, False, "unusable") for c in data["unusable"]]
        + [(c, True, "usable") for c in data["usable"]]
        + [(c, c.get("expect_usable", True), "advisory") for c in data.get("advisory", [])]
    )

    async def one(case, expect_usable, group):
        out = CaseResult("usable", case["id"], case.get("taxonomy", ""))
        out.checks = defaultdict(list)
        out.details = []
        for _ in range(runs):
            out.attempted += 1
            intent = await intent_with_retry(case["input"], "Indiranagar, Bangalore", sem)
            if intent.get("reason") == "provider_error":
                out.inconclusive += 1
                out.errors.append((intent.get("error") or "provider error")[:120])
                continue
            out.record("classified_correctly", graders.graded_usable(intent, expect_usable))
            if expect_usable and intent.get("reason") != "unreadable_profile":
                out.record("metric_validity", graders.graded_metric_validity(intent))
                out.record("metric_count", graders.graded_metric_count(intent))
        out.taxonomy = f"{group}/{case.get('taxonomy', '')}"
        return out

    return list(await asyncio.gather(*(one(c, e, g) for c, e, g in cases)))


async def run_relevance(runs: int, sem: asyncio.Semaphore) -> list[CaseResult]:
    data = yaml.safe_load((DATASETS / "intent_relevance.yaml").read_text())

    async def one(case):
        out = CaseResult("relevance", case["id"])
        out.checks = defaultdict(list)
        out.details = []
        for _ in range(runs):
            out.attempted += 1
            intent = await intent_with_retry(case["input"], "Indiranagar, Bangalore", sem)
            if intent.get("reason") == "provider_error":
                out.inconclusive += 1
                out.errors.append((intent.get("error") or "provider error")[:120])
                continue
            out.record(
                "relevant",
                graders.graded_relevance(intent, case["require_any"], case.get("forbid", [])),
            )
            out.record("metric_validity", graders.graded_metric_validity(intent))
        return out

    return list(await asyncio.gather(*(one(c) for c in data["cases"])))


async def run_faithfulness(runs: int, sem: asyncio.Semaphore) -> list[CaseResult]:
    """No network: synthetic stats in, prose out, checked against the inputs."""
    data = yaml.safe_load((DATASETS / "summary_faithfulness.yaml").read_text())

    async def one(case):
        out = CaseResult("faithfulness", case["id"])
        out.checks = defaultdict(list)
        out.details = []
        stats = {k: {"key": k, **v} for k, v in case["metrics"].items()}
        intent = {"priorities": case.get("priorities", []), "concerns": case.get("concerns", [])}
        counts = {"total": case["total_pois"]}

        for _ in range(runs):
            out.attempted += 1
            try:
                text = await summary_with_retry(
                    case["address"], case["profile"], intent, stats, counts, sem
                )
            except Exception as exc:
                out.inconclusive += 1
                out.errors.append(str(exc)[:200])
                continue
            out.record("no_invented", graders.graded_faithfulness(text, stats, case["total_pois"]))
            out.record("cites_metrics", graders.graded_cites_metrics(text, stats))
            out.record("names_tradeoff", graders.graded_names_a_tradeoff(text))
            out.record("shape", graders.graded_shape(text))
        return out

    return list(await asyncio.gather(*(one(c) for c in data["cases"])))


SUITES = {"usable": run_usable, "relevance": run_relevance, "faithfulness": run_faithfulness}


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def score(results: list[CaseResult]) -> dict[str, float]:
    """Headline numbers, keyed to match THRESHOLDS."""
    out: dict[str, float] = {}

    usable = [r for r in results if r.suite == "usable" and not r.taxonomy.startswith("advisory")]
    if usable:
        real = [r for r in usable if r.taxonomy.startswith("usable")]
        empty = [r for r in usable if r.taxonomy.startswith("unusable")]
        if real:
            out["usable.recall_real"] = statistics.mean(r.rate("classified_correctly") for r in real)
        if empty:
            out["usable.recall_empty"] = statistics.mean(r.rate("classified_correctly") for r in empty)

    relevance = [r for r in results if r.suite == "relevance"]
    if relevance:
        out["relevance.pass_rate"] = statistics.mean(r.rate("relevant") for r in relevance)

    faith = [r for r in results if r.suite == "faithfulness"]
    if faith:
        for check in ("no_invented", "cites_metrics", "names_tradeoff", "shape"):
            out[f"faithfulness.{check}"] = statistics.mean(r.rate(check) for r in faith)

    out["_coverage"] = (
        statistics.mean(r.coverage for r in results if r.attempted) if results else 0.0
    )

    advisory = [r for r in results if r.taxonomy.startswith("advisory")]
    if advisory:
        out["advisory.non_english"] = statistics.mean(
            r.rate("classified_correctly") for r in advisory
        )
    return out


def report(results: list[CaseResult], scores: dict[str, float], meta: dict) -> str:
    lines = [
        "# Eval report",
        "",
        f"- **When** {meta['when']}",
        f"- **Provider** `{meta['provider']}` · intent `{meta['intent_model']}` · summary `{meta['summary_model']}`",
        f"- **Runs per case** {meta['runs']} · **cases** {len(results)} · **duration** {meta['duration']:.0f}s",
        f"- **Coverage** {scores.get('_coverage', 0):.0%} of runs returned a verdict"
        + ("" if scores.get("_coverage", 0) >= MIN_COVERAGE
           else f"  ⚠️ **below {MIN_COVERAGE:.0%} — scores below are unreliable, the provider was failing**"),
        "",
        "## Headline",
        "",
        "| Metric | Score | Threshold | |",
        "|---|---:|---:|---|",
    ]
    for key in sorted(k for k in scores if not k.startswith("_")):
        value = scores[key]
        threshold = THRESHOLDS.get(key)
        if threshold is None:
            mark = "advisory" if key.startswith("advisory") else "—"
            bar = "—"
        else:
            mark = "PASS" if value >= threshold else "**FAIL**"
            bar = f"{threshold:.0%}"
        lines.append(f"| `{key}` | {value:.0%} | {bar} | {mark} |")

    failures = [r for r in results if r.details or r.errors]
    lines += ["", "## Cases needing attention", ""]
    if not failures:
        lines.append("None — every case passed on every run.")
    else:
        lines += ["| Suite | Case | Group | Detail |", "|---|---|---|---|"]
        for r in sorted(failures, key=lambda r: (r.suite, r.case_id)):
            detail = "; ".join(dict.fromkeys(r.details + [f"ERROR {e}" for e in r.errors]))
            lines.append(f"| {r.suite} | `{r.case_id}` | {r.taxonomy} | {detail[:160]} |")

    by_group: dict[str, list[float]] = defaultdict(list)
    for r in results:
        if r.suite == "usable" and r.checks.get("classified_correctly"):
            by_group[r.taxonomy].append(r.rate("classified_correctly"))
    if by_group:
        lines += ["", "## Usable gate by failure mode", "", "| Group | Cases | Correct |", "|---|---:|---:|"]
        for group in sorted(by_group):
            rates = by_group[group]
            lines.append(f"| {group} | {len(rates)} | {statistics.mean(rates):.0%} |")

    return "\n".join(lines) + "\n"


def compare(scores: dict[str, float]) -> list[str]:
    if not BASELINE.exists():
        return []
    base = json.loads(BASELINE.read_text()).get("scores", {})
    notes = []
    for key, value in sorted(scores.items()):
        if key in base:
            delta = value - base[key]
            if abs(delta) >= 0.02:
                notes.append(f"{key}: {base[key]:.0%} -> {value:.0%} ({delta:+.0%})")
    return notes


# ---------------------------------------------------------------------------
async def main() -> int:
    parser = argparse.ArgumentParser(description="Run Locality Lens evals")
    parser.add_argument("--suite", choices=[*SUITES, "all"], default="all")
    parser.add_argument("--runs", type=int, default=3, help="repeats per case")
    parser.add_argument("--save-baseline", action="store_true")
    parser.add_argument("--rpm", type=int, default=DEFAULT_RPM,
                        help="requests per minute budget (Groq free tier is tight)")
    args = parser.parse_args()

    cfg = provider_config()
    if not cfg.get("api_key"):
        print(f"No API key for provider {cfg['name']!r}. Set it in .env.", file=sys.stderr)
        return 2

    chosen = list(SUITES) if args.suite == "all" else [args.suite]
    sem = Throttle(args.rpm)
    started = time.perf_counter()

    results: list[CaseResult] = []
    for name in chosen:
        print(f"running {name}…", file=sys.stderr)
        results += await SUITES[name](args.runs, sem)

    # Let in-flight stream teardown finish before closing the pools,
    # otherwise httpcore logs 'generator didn't stop after athrow()'.
    await asyncio.sleep(0.25)
    await llm.aclose_all()
    duration = time.perf_counter() - started
    scores = score(results)
    meta = {
        "when": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "provider": cfg["name"],
        "intent_model": cfg["intent_model"],
        "summary_model": cfg["summary_model"],
        "runs": args.runs,
        "duration": duration,
    }

    RESULTS.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    payload = {
        "meta": meta,
        "scores": scores,
        "cases": [
            {
                "suite": r.suite,
                "id": r.case_id,
                "group": r.taxonomy,
                "rates": {k: r.rate(k) for k in r.checks},
                "details": r.details,
                "errors": r.errors,
            }
            for r in results
        ],
    }
    (RESULTS / f"{stamp}.json").write_text(json.dumps(payload, indent=2))
    markdown = report(results, scores, meta)
    (RESULTS / f"{stamp}.md").write_text(markdown)

    print(markdown)

    drift = compare(scores)
    if drift:
        print("## Change since baseline\n")
        for note in drift:
            print(f"- {note}")
        print()

    if args.save_baseline:
        BASELINE.write_text(json.dumps(
            {"meta": meta, "scores": {k: v for k, v in scores.items() if not k.startswith("_")}},
            indent=2,
        ))
        print(f"baseline written to {BASELINE.relative_to(ROOT)}")

    coverage = scores.get("_coverage", 0.0)
    if coverage < MIN_COVERAGE:
        # Reporting a quality score computed from a handful of surviving runs
        # is worse than reporting nothing: it looks like a model regression.
        inconclusive = sum(r.inconclusive for r in results)
        print(
            f"INCONCLUSIVE: only {coverage:.0%} of runs returned a verdict "
            f"({inconclusive} failed). The provider was rate-limiting or down; "
            f"scores are not meaningful. Re-run, or lower --rpm.",
            file=sys.stderr,
        )
        return 2

    failed = [k for k, v in scores.items() if k in THRESHOLDS and v < THRESHOLDS[k]]
    if failed:
        print(f"BELOW THRESHOLD: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
