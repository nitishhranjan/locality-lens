"""POI classification and metric calculation.

Pure Python - no pandas, no geopandas. The whole job is bucketing tag
dictionaries and doing arithmetic on the counts.
"""
from __future__ import annotations

import math
from typing import Any

# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------
# Ordered most-specific first: the first rule that matches wins, so a
# "pharmacy" is healthcare rather than falling through to generic shop.
_RULES: list[tuple[str, str, set[str] | None]] = [
    ("schools",        "amenity",          {"school", "college", "university"}),
    ("kindergartens",  "amenity",          {"kindergarten", "childcare"}),
    ("hospitals",      "amenity",          {"hospital", "clinic", "doctors"}),
    ("pharmacies",     "amenity",          {"pharmacy"}),
    ("restaurants",    "amenity",          {"restaurant", "fast_food", "food_court"}),
    ("cafes",          "amenity",          {"cafe", "ice_cream"}),
    ("bars",           "amenity",          {"bar", "pub", "nightclub"}),
    ("banks",          "amenity",          {"bank", "atm", "bureau_de_change"}),
    ("fuel",           "amenity",          {"fuel", "charging_station"}),
    ("worship",        "amenity",          {"place_of_worship"}),
    ("libraries",      "amenity",          {"library"}),
    ("bus_stops",      "highway",          {"bus_stop"}),
    ("metro_stations", "railway",          {"station", "subway_entrance", "halt", "tram_stop"}),
    ("metro_stations", "public_transport", {"station"}),
    ("parks",          "leisure",          {"park", "garden", "nature_reserve", "recreation_ground"}),
    ("playgrounds",    "leisure",          {"playground"}),
    ("gyms",           "leisure",          {"fitness_centre", "sports_centre", "pitch", "stadium"}),
    ("hotels",         "tourism",          {"hotel", "hostel", "guest_house", "apartment"}),
    ("attractions",    "tourism",          {"attraction", "museum", "artwork", "viewpoint"}),
    ("healthcare",     "healthcare",       None),
    ("offices",        "office",           None),
    ("shops",          "shop",             None),
]


def classify(poi: dict[str, Any]) -> str | None:
    """Assign a POI to a single category, or None if nothing matches."""
    tags = poi.get("tags", {})
    for category, key, values in _RULES:
        value = tags.get(key)
        if value is None:
            continue
        if values is None or value in values:
            return category
    return None


# ---------------------------------------------------------------------------
# Metric catalog - what the LLM is allowed to choose from
# ---------------------------------------------------------------------------
CATALOG: dict[str, dict[str, str]] = {
    "school_count":        {"label": "Schools",            "unit": "count",  "about": "Schools, colleges and universities"},
    "kindergarten_count":  {"label": "Kindergartens",      "unit": "count",  "about": "Childcare and pre-school"},
    "hospital_count":      {"label": "Hospitals & Clinics","unit": "count",  "about": "Hospitals, clinics and doctors"},
    "pharmacy_count":      {"label": "Pharmacies",         "unit": "count",  "about": "Chemists and pharmacies"},
    "restaurant_count":    {"label": "Restaurants",        "unit": "count",  "about": "Restaurants and fast food"},
    "cafe_count":          {"label": "Cafes",              "unit": "count",  "about": "Cafes and dessert shops"},
    "bar_count":           {"label": "Bars & Nightlife",   "unit": "count",  "about": "Bars, pubs and nightclubs"},
    "shop_count":          {"label": "Shops",              "unit": "count",  "about": "Retail of all kinds"},
    "bank_count":          {"label": "Banks & ATMs",       "unit": "count",  "about": "Banking access"},
    "gym_count":           {"label": "Gyms & Sports",      "unit": "count",  "about": "Fitness and sports facilities"},
    "park_count":          {"label": "Parks",              "unit": "count",  "about": "Parks and gardens"},
    "park_area_km2":       {"label": "Park Area",          "unit": "km2",    "about": "Total mapped green space"},
    "playground_count":    {"label": "Playgrounds",        "unit": "count",  "about": "Children's playgrounds"},
    "metro_station_count": {"label": "Metro & Rail",       "unit": "count",  "about": "Rail and metro access points"},
    "bus_stop_count":      {"label": "Bus Stops",          "unit": "count",  "about": "Bus stops"},
    "hotel_count":         {"label": "Hotels",             "unit": "count",  "about": "Hotels and guest houses"},
    "worship_count":       {"label": "Places of Worship",  "unit": "count",  "about": "Religious buildings"},
    "library_count":       {"label": "Libraries",          "unit": "count",  "about": "Public libraries"},
    "poi_density":         {"label": "POI Density",        "unit": "per_km2","about": "Amenities per km² - how built-up the area is"},
    "amenity_diversity":   {"label": "Amenity Diversity",  "unit": "score",  "about": "0-100, how many distinct amenity types are present"},
    "walkability_score":   {"label": "Walkability",        "unit": "score",  "about": "0-100, daily needs reachable on foot"},
    "transit_score":       {"label": "Transit Access",     "unit": "score",  "about": "0-100, public transport availability"},
    "green_score":         {"label": "Green Space",        "unit": "score",  "about": "0-100, parks and playground provision"},
    "nightlife_score":     {"label": "Nightlife",          "unit": "score",  "about": "0-100, evening economy density"},
}

_COUNT_SOURCE = {
    "school_count": "schools",
    "kindergarten_count": "kindergartens",
    "hospital_count": "hospitals",
    "pharmacy_count": "pharmacies",
    "restaurant_count": "restaurants",
    "cafe_count": "cafes",
    "bar_count": "bars",
    "shop_count": "shops",
    "bank_count": "banks",
    "gym_count": "gyms",
    "park_count": "parks",
    "playground_count": "playgrounds",
    "metro_station_count": "metro_stations",
    "bus_stop_count": "bus_stops",
    "hotel_count": "hotels",
    "worship_count": "worship",
    "library_count": "libraries",
}

DEFAULTS_BY_PROFILE: dict[str, list[str]] = {
    "family":     ["school_count", "kindergarten_count", "playground_count", "hospital_count", "park_area_km2", "green_score", "walkability_score"],
    "bachelor":   ["restaurant_count", "cafe_count", "bar_count", "gym_count", "nightlife_score", "transit_score", "walkability_score"],
    "student":    ["school_count", "cafe_count", "library_count", "transit_score", "restaurant_count", "walkability_score", "shop_count"],
    "senior":     ["hospital_count", "pharmacy_count", "park_count", "worship_count", "walkability_score", "green_score", "bank_count"],
    "profession": ["transit_score", "cafe_count", "gym_count", "restaurant_count", "walkability_score", "poi_density", "shop_count"],
    "general":    ["poi_density", "walkability_score", "transit_score", "restaurant_count", "school_count", "park_count", "green_score"],
}


def default_metrics(profile: str | None) -> list[str]:
    """Fallback metric set when the LLM is unavailable or returns junk."""
    text = (profile or "").lower()
    for key in DEFAULTS_BY_PROFILE:
        if key in text:
            return DEFAULTS_BY_PROFILE[key]
    if "kid" in text or "child" in text:
        return DEFAULTS_BY_PROFILE["family"]
    if "work" in text:
        return DEFAULTS_BY_PROFILE["profession"]
    return DEFAULTS_BY_PROFILE["general"]


def validate(keys: list[str]) -> list[str]:
    """Keep only keys that exist in the catalog, preserving order."""
    seen, out = set(), []
    for key in keys:
        if key in CATALOG and key not in seen:
            seen.add(key)
            out.append(key)
    return out


# ---------------------------------------------------------------------------
# Calculation
# ---------------------------------------------------------------------------
def _scaled(value: float, full_marks: float) -> int:
    """Map a raw count onto 0-100 with diminishing returns.

    v1 used `min(100, count * k)`, which pinned every dense urban area to
    exactly 100 and made the scores useless for comparison. A saturating
    curve keeps the whole range in play: `full_marks` is the value that
    scores ~75, and the curve approaches but never reaches 100.
    """
    if value <= 0:
        return 0
    return round(100 * (1 - math.exp(-1.386 * value / full_marks)))


def calculate(
    counts: dict[str, int],
    park_area_km2: float,
    radius_m: int,
    selected: list[str],
) -> dict[str, Any]:
    """Compute the selected metrics from category counts."""
    area_km2 = math.pi * (radius_m / 1000.0) ** 2
    total_pois = sum(counts.values())

    density = total_pois / area_km2 if area_km2 else 0.0
    distinct = sum(1 for v in counts.values() if v > 0)

    # Component scores, each saturating rather than clipping.
    transit = _scaled(counts.get("metro_stations", 0) * 4 + counts.get("bus_stops", 0), 40)
    green = _scaled(counts.get("parks", 0) * 2 + counts.get("playgrounds", 0) * 3 + park_area_km2 * 40, 30)
    nightlife = _scaled(counts.get("bars", 0) * 2 + counts.get("restaurants", 0) * 0.4 + counts.get("cafes", 0) * 0.4, 45)
    diversity = _scaled(distinct, 14)

    # Walkability blends errand density with transit and greenery, so a
    # dense-but-transitless area and a leafy suburb land in different places.
    walk = round(0.5 * _scaled(density, 260) + 0.3 * transit + 0.2 * green)

    computed: dict[str, Any] = {
        "poi_density": round(density, 1),
        "amenity_diversity": diversity,
        "walkability_score": walk,
        "transit_score": transit,
        "green_score": green,
        "nightlife_score": nightlife,
        "park_area_km2": round(park_area_km2, 2),
    }
    for metric_key, category in _COUNT_SOURCE.items():
        computed[metric_key] = counts.get(category, 0)

    results: dict[str, Any] = {}
    for key in selected:
        if key not in CATALOG:
            continue
        results[key] = {
            "key": key,
            "value": computed.get(key, 0),
            **CATALOG[key],
        }
    return results


def catalog_for_prompt() -> str:
    """Compact catalog listing for the metric-selection prompt."""
    return "\n".join(f"- {key}: {meta['about']}" for key, meta in CATALOG.items())
