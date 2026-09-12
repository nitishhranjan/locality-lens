"""Geometry and parsing - the deterministic layer.

`polygon_area_m2` is the headline case: v1 called GeoDataFrame.area on
EPSG:4326, which returns degrees squared, divided by 1e6, and reported every
park as 0.00 km². These tests pin the magnitude so that cannot recur.
"""
import math

import pytest

from lib.geo import (
    deduplicate,
    haversine_m,
    parse_coordinates,
    polygon_area_m2,
)

BLR = (12.9784, 77.6408)  # Indiranagar, the fixture location used throughout


def square_ring(lat: float, lon: float, side_m: float):
    """A roughly square ring of a known size, in (lat, lon) order."""
    dlat = side_m / 111_320.0
    dlon = side_m / (111_320.0 * math.cos(math.radians(lat)))
    return [
        (lat, lon),
        (lat, lon + dlon),
        (lat + dlat, lon + dlon),
        (lat + dlat, lon),
    ]


class TestPolygonArea:
    def test_known_square_is_correct_within_one_percent(self):
        ring = square_ring(*BLR, side_m=100.0)
        assert polygon_area_m2(ring) == pytest.approx(10_000.0, rel=0.01)

    def test_regression_result_is_metres_not_degrees(self):
        """The v1 bug: degrees squared is ~1e-10 of the true area.

        A 100 m square is 1e4 m². In degrees squared it is ~8e-7, which after
        the /1e6 conversion floored to 0.00 km². Asserting a sane order of
        magnitude catches any reintroduction of an unprojected calculation.
        """
        area = polygon_area_m2(square_ring(*BLR, side_m=100.0))
        assert area > 1_000, "area collapsed towards zero - is it still in degrees?"

    def test_scales_with_the_square_of_the_side(self):
        small = polygon_area_m2(square_ring(*BLR, side_m=100.0))
        large = polygon_area_m2(square_ring(*BLR, side_m=200.0))
        assert large == pytest.approx(4 * small, rel=0.02)

    def test_winding_order_does_not_change_sign(self):
        ring = square_ring(*BLR, side_m=150.0)
        assert polygon_area_m2(ring) == pytest.approx(polygon_area_m2(ring[::-1]))

    @pytest.mark.parametrize("ring", [[], [(1.0, 1.0)], [(1.0, 1.0), (1.0, 1.1)]])
    def test_degenerate_rings_are_zero(self, ring):
        assert polygon_area_m2(ring) == 0.0

    def test_works_far_from_the_equator(self):
        """The projection is anchored on the ring's own latitude, so a square
        in Oslo should measure the same as one in Bangalore."""
        oslo = polygon_area_m2(square_ring(59.91, 10.75, side_m=100.0))
        assert oslo == pytest.approx(10_000.0, rel=0.01)


class TestHaversine:
    def test_zero_distance(self):
        assert haversine_m(BLR, BLR) == pytest.approx(0.0, abs=1e-6)

    def test_one_degree_of_latitude_is_about_111km(self):
        assert haversine_m((0.0, 0.0), (1.0, 0.0)) == pytest.approx(111_195, rel=0.01)

    def test_symmetric(self):
        a, b = BLR, (12.99, 77.65)
        assert haversine_m(a, b) == pytest.approx(haversine_m(b, a))


class TestParseCoordinates:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("12.9784, 77.6408", (12.9784, 77.6408)),
            ("12.9784,77.6408", (12.9784, 77.6408)),
            ("  -33.86 , 151.21  ", (-33.86, 151.21)),
            ("0,0", (0.0, 0.0)),
            ("90,180", (90.0, 180.0)),
        ],
    )
    def test_accepts_coordinate_pairs(self, text, expected):
        assert parse_coordinates(text) == expected

    @pytest.mark.parametrize(
        "text",
        [
            "Indiranagar, Bangalore",  # an address with a comma
            "91, 0",                   # latitude out of range
            "0, 181",                  # longitude out of range
            "12.9784",                 # single number
            "",
            "12.9784, 77.6408, 5",     # too many parts
        ],
    )
    def test_rejects_everything_else(self, text):
        assert parse_coordinates(text) is None

    def test_an_address_is_not_mistaken_for_coordinates(self):
        """Guards the branch that decides between geocoding and using the
        numbers directly - a false positive here would search the wrong place."""
        assert parse_coordinates("Indiranagar, Bangalore") is None


class TestDeduplicate:
    def poi(self, lat, lon, name=None, category="restaurants"):
        return {"lat": lat, "lon": lon, "name": name, "category": category}

    def test_same_name_and_category_close_together_collapses(self):
        lat, lon = BLR
        pois = [
            self.poi(lat, lon, "Biryani Palace"),
            self.poi(lat + 0.0001, lon, "Biryani Palace"),  # ~11 m away
        ]
        assert len(deduplicate(pois)) == 1

    def test_same_name_far_apart_is_kept(self):
        """A chain with two branches is two places, not one."""
        lat, lon = BLR
        pois = [
            self.poi(lat, lon, "Cafe Chain"),
            self.poi(lat + 0.05, lon, "Cafe Chain"),  # ~5.5 km
        ]
        assert len(deduplicate(pois)) == 2

    def test_different_names_close_together_are_both_kept(self):
        lat, lon = BLR
        pois = [self.poi(lat, lon, "Alpha"), self.poi(lat + 0.00005, lon, "Beta")]
        assert len(deduplicate(pois)) == 2

    def test_different_categories_never_collapse(self):
        lat, lon = BLR
        pois = [
            self.poi(lat, lon, "Same Place", category="restaurants"),
            self.poi(lat, lon, "Same Place", category="cafes"),
        ]
        assert len(deduplicate(pois)) == 2

    def test_unnamed_features_collapse_on_proximity_alone(self):
        lat, lon = BLR
        pois = [self.poi(lat, lon), self.poi(lat + 0.00005, lon)]
        assert len(deduplicate(pois)) == 1

    def test_empty_input(self):
        assert deduplicate([]) == []

    def test_output_preserves_input_order(self):
        lat, lon = BLR
        pois = [self.poi(lat + i * 0.01, lon, f"P{i}") for i in range(5)]
        assert [p["name"] for p in deduplicate(pois)] == ["P0", "P1", "P2", "P3", "P4"]
