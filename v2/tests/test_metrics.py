"""Classification and scoring.

The `_scaled` tests exist because v1 scored with `min(100, count * k)`, which
pinned every dense urban area to exactly 100 - Walkability and Accessibility
both read 100 for Indiranagar and the numbers could not tell one
neighbourhood from another. Saturation must stay gradual.
"""
import pytest

from lib.metrics import (
    CATALOG,
    _scaled,
    calculate,
    catalog_for_prompt,
    classify,
    default_metrics,
    validate,
)


class TestScaled:
    def test_zero_and_negative_score_zero(self):
        assert _scaled(0, 30) == 0
        assert _scaled(-5, 30) == 0

    def test_full_marks_scores_about_seventy_five(self):
        """`full_marks` is documented as the value that scores ~75."""
        assert _scaled(30, 30) == pytest.approx(75, abs=1)

    def test_never_exceeds_one_hundred(self):
        assert _scaled(10_000, 30) <= 100

    def test_monotonic_non_decreasing(self):
        values = [_scaled(v, 40) for v in range(0, 200, 5)]
        assert values == sorted(values)

    def test_regression_discriminates_across_the_realistic_range(self):
        """The v1 bug in one assertion.

        With `min(100, count * k)` any two moderately dense areas both clipped
        to 100 and became indistinguishable. A saturating curve has to keep
        separating them well past `full_marks`.
        """
        modest, busy, dense = _scaled(20, 40), _scaled(40, 40), _scaled(70, 40)
        assert modest < busy < dense
        assert dense - modest > 20, "curve saturates too fast to compare areas"

    def test_scores_stay_inside_the_stated_bounds(self):
        for value in (0, 1, 15, 40, 100, 5_000):
            assert 0 <= _scaled(value, 40) <= 100


class TestClassify:
    def test_specific_amenity_wins_over_generic_shop(self):
        """Rules are ordered most-specific-first: a pharmacy that also carries
        a shop tag must classify as healthcare, not retail."""
        poi = {"tags": {"amenity": "pharmacy", "shop": "chemist"}}
        assert classify(poi) == "pharmacies"

    @pytest.mark.parametrize(
        "tags,expected",
        [
            ({"amenity": "school"}, "schools"),
            ({"amenity": "kindergarten"}, "kindergartens"),
            ({"amenity": "hospital"}, "hospitals"),
            ({"amenity": "restaurant"}, "restaurants"),
            ({"amenity": "cafe"}, "cafes"),
            ({"leisure": "park"}, "parks"),
            ({"leisure": "playground"}, "playgrounds"),
            ({"railway": "station"}, "metro_stations"),
            ({"highway": "bus_stop"}, "bus_stops"),
            ({"shop": "bakery"}, "shops"),
            ({"tourism": "hotel"}, "hotels"),
        ],
    )
    def test_known_tags_map_to_categories(self, tags, expected):
        assert classify({"tags": tags}) == expected

    def test_unmatched_tags_return_none(self):
        assert classify({"tags": {"barrier": "fence"}}) is None
        assert classify({"tags": {}}) is None
        assert classify({}) is None

    def test_open_ended_rule_accepts_any_value(self):
        """`healthcare` has no value allowlist, so any value should match."""
        assert classify({"tags": {"healthcare": "physiotherapist"}}) == "healthcare"


class TestValidate:
    def test_drops_keys_outside_the_catalog(self):
        assert validate(["school_count", "not_a_metric"]) == ["school_count"]

    def test_removes_duplicates_but_keeps_first_position(self):
        assert validate(["park_count", "school_count", "park_count"]) == [
            "park_count",
            "school_count",
        ]

    def test_empty_and_all_invalid(self):
        assert validate([]) == []
        assert validate(["nope", "also_nope"]) == []


class TestDefaultMetrics:
    @pytest.mark.parametrize(
        "profile,expected",
        [
            ("Family with kids", "school_count"),
            ("family", "school_count"),
            ("Student", "library_count"),
            ("Senior citizen", "hospital_count"),
        ],
    )
    def test_profile_keywords_pick_a_sensible_set(self, profile, expected):
        assert expected in default_metrics(profile)

    def test_unknown_profile_falls_back_to_general(self):
        assert default_metrics("something unmapped") == default_metrics(None)

    def test_every_default_is_a_real_catalog_key(self):
        """A default set containing a typo would silently produce no metric."""
        for profile in [None, "", "family", "student", "senior", "profession", "xyz"]:
            for key in default_metrics(profile):
                assert key in CATALOG, f"{key!r} is not in the catalog"


class TestCalculate:
    COUNTS = {
        "schools": 85,
        "hospitals": 126,
        "restaurants": 400,
        "parks": 69,
        "playgrounds": 30,
        "metro_stations": 12,
        "bus_stops": 56,
    }

    def test_returns_only_the_selected_metrics(self):
        stats = calculate(self.COUNTS, 0.25, 2000, ["school_count", "park_count"])
        assert set(stats) == {"school_count", "park_count"}

    def test_counts_pass_through_untouched(self):
        stats = calculate(self.COUNTS, 0.25, 2000, ["school_count"])
        assert stats["school_count"]["value"] == 85

    def test_park_area_passes_through_rounded(self):
        stats = calculate(self.COUNTS, 0.2567, 2000, ["park_area_km2"])
        assert stats["park_area_km2"]["value"] == 0.26

    def test_unknown_selection_is_skipped_not_fatal(self):
        stats = calculate(self.COUNTS, 0.25, 2000, ["school_count", "bogus_metric"])
        assert set(stats) == {"school_count"}

    def test_missing_category_reads_zero_rather_than_raising(self):
        stats = calculate({}, 0.0, 2000, ["school_count", "walkability_score"])
        assert stats["school_count"]["value"] == 0
        assert stats["walkability_score"]["value"] == 0

    def test_all_score_metrics_are_bounded(self):
        keys = [k for k, v in CATALOG.items() if v["unit"] == "score"]
        stats = calculate(self.COUNTS, 0.25, 2000, keys)
        for key, metric in stats.items():
            assert 0 <= metric["value"] <= 100, f"{key} out of range"

    def test_each_metric_carries_its_catalog_metadata(self):
        """The UI renders label and unit straight from here."""
        stats = calculate(self.COUNTS, 0.25, 2000, ["walkability_score"])
        metric = stats["walkability_score"]
        assert metric["label"] == CATALOG["walkability_score"]["label"]
        assert metric["unit"] == "score"
        assert metric["key"] == "walkability_score"

    def test_a_richer_area_outscores_a_sparser_one(self):
        """End-to-end version of the saturation regression."""
        sparse = calculate({"parks": 2, "bus_stops": 3}, 0.02, 2000, ["walkability_score"])
        rich = calculate(self.COUNTS, 0.25, 2000, ["walkability_score"])
        assert rich["walkability_score"]["value"] > sparse["walkability_score"]["value"]


def test_catalog_prompt_lists_every_metric():
    """The model may only choose keys it was shown."""
    prompt = catalog_for_prompt()
    for key in CATALOG:
        assert key in prompt
