# Evals

Two separate things live in this repository, and conflating them is the usual
mistake:

| | `tests/` | `evals/` |
|---|---|---|
| Subject | deterministic code | model behaviour |
| Assertion | exact equality | rates across a dataset |
| Cost | free, ~1s | tokens and minutes |
| A red result means | the code broke | quality moved, *or* the provider did |

`polygon_area_m2` and `_scaled` belong in `tests/` — the two worst bugs this
project had lived there and each died to a three-line assertion. Model output
cannot be asserted that way: the same input yields different words each call,
so every case is run several times and scored as a rate.

## Running

```bash
python -m evals.run                  # all suites, 3 runs per case
python -m evals.run --suite usable   # one suite
python -m evals.run --runs 5         # tighter estimate, slower
python -m evals.run --save-baseline  # record today's scores as the bar
```

Reports land in `evals/results/<timestamp>.{json,md}`. `evals/baseline.json`
is the comparison point; the runner prints any metric that has moved by 2+
points since.

Exit codes: `0` pass, `1` below threshold, `2` inconclusive (see coverage).

## Suites

**`usable`** — the gate that decides whether a free-text profile carries
enough signal to work from. A binary classifier, so precision and recall are
reported separately, because the two errors cost very different things:

- *false reject* — a real description is refused and the user is told to
  reword something that was fine. Infuriating.
- *false accept* — "okay" produces a full analysis. A generic result is
  presented as a personalised one.

Cases are grouped by failure mode (greeting, single word, punctuation,
keyboard mash, affirmation, meta-question, injection, placeholder) so a
regression points at *which kind* of input broke.

**`relevance`** — given a readable description, are the selected metrics
sensible? Several sets are defensible for one profile, so each case asserts
only the weakest defensible claim: at least one obviously relevant metric is
present, and nothing plainly wrong for that person is.

**`faithfulness`** — does the written summary invent figures? Synthetic stats
go in, prose comes out, and every number in the prose must be one that was
supplied. No network is involved. This is the grader that matters most for
credibility: v1's output claimed Indiranagar was *"far above the city average
of 15-20 schools per comparable zone"* — two numbers nobody gave it, stated
as fact.

## Graders

All programmatic. Nothing depends on a second model, so a red result means
the system moved rather than a judge having an off day. An LLM judge is worth
adding only for what these cannot express — *is the trade-off substantive, or
just the word "however"?* — and it would need calibrating against human
labels before its number counts for anything.

## Coverage, and why it exists

The first version of this runner reported **10% recall on empty inputs** and
looked like a catastrophic model regression. It was not. Groq was rate
limiting, `extract_intent` degrades on a provider fault rather than raising,
and the grader counted every 429 as *"the model accepted this input"* — which
is accidentally right for real descriptions and wrong for every empty one,
producing exactly the misleading split.

So the runner now separates **"the model decided X"** from **"the model never
answered"**. Failed calls are retried with backoff, then recorded as
inconclusive rather than scored. If fewer than `MIN_COVERAGE` of runs return a
verdict the run exits `2` and refuses to publish scores at all — a quality
number computed from the handful of calls that survived is worse than no
number, because it reads as a regression.

If you see exit code 2, the provider was throttling. Re-run, or lower
`--rpm`.

## Budget

Groq's free tier caps requests **per day** as well as per minute. A full
sweep at 3 repeats is ~174 calls, which is more than a day's budget once
you have also been developing against it.

Pacing (`--rpm`) fixes per-minute throttling. It cannot fix a daily cap, and
retrying into an exhausted quota is worse than useless - an early version of
this runner spent 3.9 hours backing off and produced nothing. The runner now
aborts after 8 consecutive provider failures and says so.

Practical options when the budget is tight:

- run one suite at a time (`--suite relevance`)
- `--runs 1` for a smoke check, `--runs 3+` only for a baseline
- point `LLM_PROVIDER` at a paid OpenAI key for baseline runs

## Thresholds

`THRESHOLDS` in `run.py` are **placeholders**. Where the bar sits is a product
judgement, not a technical one: how often is it acceptable to wrongly tell
someone to reword a perfectly good description? Look at a few runs before
setting them.

## Adding held-out cases

`intent_usable.yaml` was written by the same author as the prompt it grades,
which is a real conflict of interest — it is easy to unconsciously pick cases
the implementation already handles. Add your own, ideally ones you have seen
confuse it in real use. Anything you add is scored the same way; keeping a
slice that was never tuned against is what makes the number trustworthy.

## Known gaps

- **No OSM fixtures yet.** The `usable` and `relevance` suites need no
  network beyond the LLM, and `faithfulness` uses synthetic stats, so nothing
  here touches Overpass. A future end-to-end suite would need recorded
  fixtures, or a failure becomes ambiguous between a model regression and
  Overpass throttling.
- **No LLM judge**, deliberately — see Graders.
- **Rate limits dominate wall-clock.** A full run at 3 repeats is minutes,
  almost all of it backoff on Groq's free tier.
