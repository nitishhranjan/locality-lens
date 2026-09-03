"""Geocoding and OpenStreetMap access over raw HTTP.

v1 used osmnx + geopandas for this, which pulled in ~460 MB of geospatial
wheels (GDAL bindings, PROJ, pandas, pyarrow, scipy). Everything here is
plain HTTP against the same upstream services plus a little trigonometry,
which keeps the deployed bundle small enough for a serverless function.
"""
from __future__ import annotations

import asyncio
import hashlib
import math
import re
import time
from collections import OrderedDict
from typing import Any, Iterable

import httpx

from .config import (
    HTTP_TIMEOUT,
    NOMINATIM_ENDPOINT,
    NOMINATIM_REVERSE_ENDPOINT,
    OVERPASS_ENDPOINTS,
    USER_AGENT,
)

_COORD_RE = re.compile(
    r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$"
)

EARTH_RADIUS_M = 6_371_000


# ---------------------------------------------------------------------------
# Input handling
# ---------------------------------------------------------------------------
def parse_coordinates(text: str) -> tuple[float, float] | None:
    """Return (lat, lon) if the input is a bare coordinate pair, else None."""
    match = _COORD_RE.match(text or "")
    if not match:
        return None
    lat, lon = float(match.group(1)), float(match.group(2))
    if -90 <= lat <= 90 and -180 <= lon <= 180:
        return lat, lon
    return None


async def geocode(query: str, client: httpx.AsyncClient) -> dict[str, Any]:
    """Resolve a free-text place name to coordinates via Nominatim."""
    response = await client.get(
        NOMINATIM_ENDPOINT,
        params={"q": query, "format": "json", "limit": 1},
        headers={"User-Agent": USER_AGENT},
        timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()
    results = response.json()
    if not results:
        raise ValueError(f"Could not find a location matching {query!r}")

    top = results[0]
    return {
        "lat": float(top["lat"]),
        "lon": float(top["lon"]),
        "address": top.get("display_name", query),
    }


async def reverse_geocode(
    lat: float, lon: float, client: httpx.AsyncClient
) -> str | None:
    """Name the place at a coordinate pair.

    Without this, a coordinate search reaches the summary model as bare
    digits, so it writes about "this location" with no idea where on earth
    it is. Failure is non-fatal - the caller keeps the numeric label.
    """
    try:
        response = await client.get(
            NOMINATIM_REVERSE_ENDPOINT,
            params={"lat": lat, "lon": lon, "format": "json", "zoom": 16},
            headers={"User-Agent": USER_AGENT},
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
        return response.json().get("display_name") or None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Overpass
# ---------------------------------------------------------------------------
# One consolidated query rather than a request per category. `out center`
# collapses ways and relations to a single point, which keeps the response
# small - we only need positions and tags to count and classify.
_POI_QUERY = """
[out:json][timeout:60];
(
  nwr["amenity"](around:{radius},{lat},{lon});
  nwr["shop"](around:{radius},{lat},{lon});
  nwr["leisure"](around:{radius},{lat},{lon});
  nwr["healthcare"](around:{radius},{lat},{lon});
  nwr["office"](around:{radius},{lat},{lon});
  nwr["tourism"](around:{radius},{lat},{lon});
  nwr["public_transport"="station"](around:{radius},{lat},{lon});
  nwr["railway"~"^(station|subway_entrance|halt|tram_stop)$"](around:{radius},{lat},{lon});
  node["highway"="bus_stop"](around:{radius},{lat},{lon});
);
out center tags;
"""

# Parks need real geometry to measure area, so they get a second, narrow query.
_PARK_QUERY = """
[out:json][timeout:60];
(
  way["leisure"~"^(park|garden|recreation_ground|nature_reserve)$"](around:{radius},{lat},{lon});
);
out geom;
"""


# Overpass is a free, shared, heavily rate-limited service. Repeat queries for
# the same place are common (reloads, profile switches on one location), so a
# small in-process cache spares the upstream and makes warm serverless
# instances answer instantly. Bounded so a long-lived instance cannot grow
# without limit.
_CACHE: "OrderedDict[str, tuple[float, dict[str, Any]]]" = OrderedDict()
_CACHE_TTL_S = 900
_CACHE_MAX = 32


def _cache_get(key: str) -> dict[str, Any] | None:
    hit = _CACHE.get(key)
    if not hit:
        return None
    stored_at, payload = hit
    if time.time() - stored_at > _CACHE_TTL_S:
        _CACHE.pop(key, None)
        return None
    _CACHE.move_to_end(key)
    return payload


def _cache_put(key: str, payload: dict[str, Any]) -> None:
    _CACHE[key] = (time.time(), payload)
    _CACHE.move_to_end(key)
    while len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)


async def _overpass(query: str, client: httpx.AsyncClient) -> dict[str, Any]:
    """POST a query to Overpass, with caching and mirror fallback."""
    key = hashlib.sha1(query.encode()).hexdigest()
    if (cached := _cache_get(key)) is not None:
        return cached

    errors: list[str] = []
    # Two passes over the mirrors: a mirror that answers 429 ("too many
    # requests") is usually willing a moment later, and the alternative is
    # failing the whole analysis over a transient quota.
    for attempt in range(2):
        for endpoint in OVERPASS_ENDPOINTS:
            try:
                response = await client.post(
                    endpoint,
                    data={"data": query},
                    headers={"User-Agent": USER_AGENT},
                    timeout=HTTP_TIMEOUT,
                )
                if response.status_code in (429, 504):
                    errors.append(f"{endpoint.split('/')[2]}: {response.status_code}")
                    continue
                response.raise_for_status()
                payload = response.json()
                _cache_put(key, payload)
                return payload
            except Exception as exc:
                errors.append(f"{endpoint.split('/')[2]}: {type(exc).__name__}")
        if attempt == 0:
            await asyncio.sleep(1.5)

    raise RuntimeError(
        "Overpass is rate-limiting or unavailable (" + "; ".join(errors[:4]) + "). Try again shortly."
    )


async def fetch_pois(
    lat: float, lon: float, radius_m: int, client: httpx.AsyncClient
) -> list[dict[str, Any]]:
    """Fetch and normalise POIs around a point."""
    query = _POI_QUERY.format(radius=radius_m, lat=lat, lon=lon)
    payload = await _overpass(query, client)

    pois: list[dict[str, Any]] = []
    for element in payload.get("elements", []):
        tags = element.get("tags") or {}
        if not tags:
            continue

        # Nodes carry lat/lon directly; ways and relations get a `center`.
        center = element.get("center") or element
        if "lat" not in center or "lon" not in center:
            continue

        pois.append(
            {
                "id": f"{element.get('type')}/{element.get('id')}",
                "lat": float(center["lat"]),
                "lon": float(center["lon"]),
                "name": tags.get("name"),
                "tags": tags,
            }
        )
    return pois


async def fetch_park_area_km2(
    lat: float, lon: float, radius_m: int, client: httpx.AsyncClient
) -> float:
    """Total park polygon area in km²."""
    query = _PARK_QUERY.format(radius=radius_m, lat=lat, lon=lon)
    try:
        payload = await _overpass(query, client)
    except Exception:
        return 0.0

    total_m2 = 0.0
    for element in payload.get("elements", []):
        geometry = element.get("geometry") or []
        ring = [(p["lat"], p["lon"]) for p in geometry if "lat" in p and "lon" in p]
        total_m2 += polygon_area_m2(ring)
    return round(total_m2 / 1e6, 3)


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------
def polygon_area_m2(ring: list[tuple[float, float]]) -> float:
    """Area of a lat/lon ring in m², via shoelace on a local projection.

    v1 called GeoDataFrame.area on EPSG:4326 and divided by 1e6, which
    silently produced degrees² and floored every park to 0.00 km². Projecting
    to local metres first is what makes the number mean anything.
    """
    if len(ring) < 3:
        return 0.0

    mean_lat = sum(lat for lat, _ in ring) / len(ring)
    scale = math.cos(math.radians(mean_lat))

    # Equirectangular projection about the ring's own latitude - accurate
    # well past the couple of kilometres we ever query.
    xs = [math.radians(lon) * EARTH_RADIUS_M * scale for _, lon in ring]
    ys = [math.radians(lat) * EARTH_RADIUS_M for lat, _ in ring]

    area2 = 0.0
    for i in range(len(ring)):
        j = (i + 1) % len(ring)
        area2 += xs[i] * ys[j] - xs[j] * ys[i]
    return abs(area2) / 2.0


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance between two (lat, lon) points, in metres."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def deduplicate(pois: Iterable[dict[str, Any]], distance_m: float = 60.0) -> list[dict[str, Any]]:
    """Collapse POIs that are the same place mapped twice.

    v1 used scipy's cKDTree (98 MB) for this. A grid hash gives the same
    answer in linear time with no dependency: bucket by a cell roughly
    `distance_m` across, then only compare within neighbouring cells.
    """
    # Degrees of latitude are ~111 km everywhere; longitude shrinks with cos(lat).
    cell_deg = distance_m / 111_000.0
    buckets: dict[tuple[int, int, str], list[dict[str, Any]]] = {}
    kept: list[dict[str, Any]] = []

    for poi in pois:
        # Same-name-and-kind duplicates are the ones worth collapsing; two
        # different shops 10 m apart are genuinely two shops.
        key_name = (poi.get("name") or "").strip().lower()
        kind = poi.get("category") or ""
        cell = (int(poi["lat"] / cell_deg), int(poi["lon"] / cell_deg), kind)

        duplicate = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for other in buckets.get((cell[0] + dx, cell[1] + dy, kind), ()):
                    other_name = (other.get("name") or "").strip().lower()
                    # Unnamed features are collapsed on proximity alone;
                    # named ones must also match by name.
                    if key_name and other_name and key_name != other_name:
                        continue
                    if haversine_m((poi["lat"], poi["lon"]), (other["lat"], other["lon"])) <= distance_m:
                        duplicate = True
                        break
                if duplicate:
                    break
            if duplicate:
                break

        if not duplicate:
            buckets.setdefault(cell, []).append(poi)
            kept.append(poi)

    return kept
