"""Graph wiring and failure routing.

Every case here corresponds to a bug that reached production:

- geocode failing while the concurrent intent branch pushed on into `fetch`,
  which then dereferenced coordinates that were never produced
- `handle_error` reachable from both branches and emitting two errors
- an unreadable profile still running the full analysis and presenting a
  generic result as a personalised one
- a run ending without a terminal event, leaving the UI spinning forever

The LLM and OpenStreetMap are stubbed: this exercises routing, not models or
the network.
"""
import pytest

from lib import llm, nodes
from lib.pipeline import analyse

POIS = [
    {"lat": 12.978, "lon": 77.640, "name": "A", "tags": {"amenity": "school"}},
    {"lat": 12.979, "lon": 77.641, "name": "B", "tags": {"amenity": "restaurant"}},
    {"lat": 12.980, "lon": 77.642, "name": "C", "tags": {"leisure": "park"}},
]

INTENT = {
    "profile_type": "family_with_kids",
    "priorities": ["schools"],
    "concerns": ["traffic"],
    "lifestyle": "",
    "selected_metrics": ["school_count", "park_count", "walkability_score"],
    "reasoning": "because",
    "degraded": False,
    "provider": "stub",
}


async def collect(*args, **kwargs):
    """Run the graph and bucket the events by type."""
    events = []
    async for event in analyse(*args, **kwargs):
        events.append(event)
    return events


def types(events):
    return [e["type"] for e in events]


def stages(events, status=None):
    return [
        e for e in events
        if e["type"] == "stage" and (status is None or e["status"] == status)
    ]


@pytest.fixture
def happy(monkeypatch):
    """A fully working world: geocoding, OSM and both LLM calls succeed."""
    async def fake_geocode(query, client):
        return {"lat": 12.9784, "lon": 77.6408, "address": "Indiranagar, Bengaluru"}

    async def fake_reverse(lat, lon, client):
        return "100 Feet Road, Indiranagar"

    async def fake_pois(lat, lon, radius, client):
        return [dict(p) for p in POIS]

    async def fake_area(lat, lon, radius, client):
        return 0.25

    async def fake_intent(profile, location):
        return dict(INTENT)

    async def fake_summary(*args, **kwargs):
        for chunk in ("Indiranagar ", "has 1 school. ", "Traffic is the trade-off."):
            yield chunk

    monkeypatch.setattr(nodes, "geocode", fake_geocode)
    monkeypatch.setattr(nodes, "reverse_geocode", fake_reverse)
    monkeypatch.setattr(nodes, "fetch_pois", fake_pois)
    monkeypatch.setattr(nodes, "fetch_park_area_km2", fake_area)
    monkeypatch.setattr(llm, "extract_intent", fake_intent)
    monkeypatch.setattr(llm, "stream_summary", fake_summary)


class TestHappyPath:
    async def test_all_six_stages_complete(self, happy):
        events = await collect("Indiranagar, Bangalore", "Family with kids")
        done = {e["id"] for e in stages(events, "done")}
        assert done == {"validate", "intent", "geocode", "fetch", "calculate", "summarize"}

    async def test_ends_with_a_done_event(self, happy):
        events = await collect("Indiranagar, Bangalore", "Family with kids")
        assert types(events)[-1] == "done"
        assert events[-1]["elapsed"] >= 0

    async def test_emits_the_payloads_the_ui_needs(self, happy):
        events = await collect("Indiranagar, Bangalore", "Family with kids")
        assert {"intent", "location", "pois", "stats"} <= set(types(events))

    async def test_summary_streams_as_tokens(self, happy):
        events = await collect("Indiranagar, Bangalore", "Family with kids")
        text = "".join(e["text"] for e in events if e["type"] == "token")
        assert "Indiranagar" in text

    async def test_no_error_on_the_happy_path(self, happy):
        events = await collect("Indiranagar, Bangalore", "Family with kids")
        assert "error" not in types(events)

    async def test_coordinate_input_skips_geocoding(self, happy):
        events = await collect("12.9784, 77.6408", "Student")
        validate = [e for e in stages(events, "done") if e["id"] == "validate"][0]
        assert "Coordinates" in validate["detail"]


class TestValidation:
    async def test_short_input_stops_with_one_error(self, happy):
        events = await collect("x", "Student")
        assert types(events).count("error") == 1
        assert "done" not in types(events)

    async def test_short_input_never_reaches_the_network(self, happy):
        events = await collect("", "Student")
        assert not [e for e in stages(events) if e["id"] == "fetch"]


class TestGeocodeFailure:
    @pytest.fixture
    def bad_geocode(self, happy, monkeypatch):
        async def boom(query, client):
            raise ValueError("Could not find a location matching 'Zzz'")

        monkeypatch.setattr(nodes, "geocode", boom)

    async def test_reports_exactly_one_error(self, bad_geocode):
        """`handle_error` is reachable from both branches; the client should
        be told once, not twice."""
        events = await collect("Zzz Nowhere", "Student")
        assert types(events).count("error") == 1

    async def test_does_not_claim_the_run_finished(self, bad_geocode):
        events = await collect("Zzz Nowhere", "Student")
        assert "done" not in types(events)

    async def test_fetch_never_runs_without_coordinates(self, bad_geocode):
        """The regression: intent's unconditional edge triggered the join and
        `fetch` dereferenced coordinates that did not exist."""
        events = await collect("Zzz Nowhere", "Student")
        assert not [e for e in stages(events) if e["id"] == "fetch"]
        assert "stats" not in types(events)


class TestOsmFailure:
    @pytest.fixture
    def bad_osm(self, happy, monkeypatch):
        async def boom(lat, lon, radius, client):
            raise RuntimeError("Overpass is rate-limiting or unavailable")

        monkeypatch.setattr(nodes, "fetch_pois", boom)

    async def test_surfaces_the_upstream_reason(self, bad_osm):
        events = await collect("Indiranagar, Bangalore", "Student")
        message = [e for e in events if e["type"] == "error"][0]["message"]
        assert "Overpass" in message

    async def test_stops_cleanly_without_done(self, bad_osm):
        events = await collect("Indiranagar, Bangalore", "Student")
        assert "done" not in types(events)
        assert "stats" not in types(events)


class TestUnreadableProfile:
    @pytest.fixture
    def unreadable(self, happy, monkeypatch):
        async def vague(profile, location):
            return {
                **INTENT,
                "selected_metrics": [],
                "degraded": True,
                "reason": "unreadable_profile",
                "hint": llm.UNREADABLE_HINT,
            }

        monkeypatch.setattr(llm, "extract_intent", vague)

    async def test_asks_for_a_rewording(self, unreadable):
        events = await collect("Indiranagar, Bangalore", "okay")
        rephrase = [e for e in events if e["type"] == "rephrase"]
        assert len(rephrase) == 1
        assert rephrase[0]["examples"]

    async def test_produces_no_analysis_at_all(self, unreadable):
        """Continuing would present a generic result as a personalised one -
        worse than saying plainly that the description did not land."""
        events = await collect("Indiranagar, Bangalore", "okay")
        assert "stats" not in types(events)
        assert "token" not in types(events)

    async def test_does_not_report_success(self, unreadable):
        events = await collect("Indiranagar, Bangalore", "okay")
        assert "done" not in types(events)


class TestSummaryFallback:
    async def test_llm_failure_still_yields_a_summary(self, happy, monkeypatch):
        """A dead summary model degrades to raw metrics rather than ending
        the run - the data gathered so far is still worth showing."""
        async def boom(*args, **kwargs):
            raise RuntimeError("provider exploded")
            yield  # pragma: no cover - makes this an async generator

        monkeypatch.setattr(llm, "stream_summary", boom)
        events = await collect("Indiranagar, Bangalore", "Family with kids")

        assert "token" in types(events)
        assert "notice" in types(events)
        assert types(events)[-1] == "done"


class TestTerminalEventContract:
    """The client treats a stream with no terminal event as a timeout, so
    every path must end in exactly one of done / error / rephrase."""

    TERMINAL = {"done", "error", "rephrase"}

    @pytest.mark.parametrize(
        "location,profile", [("Indiranagar, Bangalore", "Family with kids"), ("x", "Student")]
    )
    async def test_every_run_ends_on_a_terminal_event(self, happy, location, profile):
        events = await collect(location, profile)
        assert len(self.TERMINAL & set(types(events))) == 1
