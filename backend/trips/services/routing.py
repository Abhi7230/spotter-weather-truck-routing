"""Route options from OSRM.

OSRM's `alternatives` often returns fewer than three routes, so missing options are
filled by forcing the route through a via-point offset to either side of the
fastest route's midpoint. Near-duplicates and silly detours are discarded.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache

from trips import geo
from trips.geo import LatLon
from trips.services.http import UpstreamError, get_json

logger = logging.getLogger(__name__)

ROUTE_CACHE_SECONDS = 6 * 3600
MAX_DETOUR_RATIO = 1.6  # reject detours this much slower than the fastest route
MAX_OVERLAP = 0.8  # routes sharing more than 80% of their path are "the same"
DETOUR_OFFSETS = (0.18, -0.18, 0.35, -0.35)  # fraction of straight-line distance


@dataclass
class Route:
    points: list[LatLon]
    segment_miles: list[float]  # len(points) - 1
    segment_seconds: list[float]  # truck-adjusted, len(points) - 1
    summary: str

    @property
    def distance_miles(self) -> float:
        return sum(self.segment_miles)

    @property
    def duration_seconds(self) -> float:
        return sum(self.segment_seconds)


def _parse_osrm_route(data: dict, max_mph: float) -> Route:
    points = [(lat, lon) for lon, lat in data["geometry"]["coordinates"]]
    meters, seconds = [], []
    for leg in data["legs"]:
        meters += leg["annotation"]["distance"]
        seconds += leg["annotation"]["duration"]
    if len(meters) != len(points) - 1:
        raise UpstreamError("OSRM annotation does not match geometry")

    segment_miles = [m / geo.METERS_PER_MILE for m in meters]
    # OSRM's public server only has a car profile; cap speed to a truck's governor.
    segment_seconds = [
        max(s, miles / max_mph * 3600) for s, miles in zip(seconds, segment_miles, strict=True)
    ]
    names = ", ".join(leg.get("summary", "") for leg in data["legs"]).replace(";", ",")
    summary = ", ".join(dict.fromkeys(n.strip() for n in names.split(",") if n.strip()))
    return Route(points, segment_miles, segment_seconds, summary)


def _osrm(waypoints: list[LatLon], alternatives: int = 0) -> list[Route]:
    coords = ";".join(f"{lon:.5f},{lat:.5f}" for lat, lon in waypoints)
    cache_key = f"osrm:{coords}:{alternatives}:{settings.TRUCK_MAX_SPEED_MPH}"
    if (cached := cache.get(cache_key)) is not None:
        return cached

    data = get_json(
        f"{settings.OSRM_BASE_URL}/route/v1/driving/{coords}",
        service="The routing service (OSRM)",
        params={
            "alternatives": alternatives or "false",
            "overview": "full",
            "geometries": "geojson",
            "annotations": "distance,duration",
            "steps": "true",  # needed for leg summaries ("I 80, I 76")
        },
    )
    if data.get("code") != "Ok":
        raise UpstreamError(f"Routing failed: {data.get('message') or data.get('code')}")
    routes = [_parse_osrm_route(r, settings.TRUCK_MAX_SPEED_MPH) for r in data["routes"]]
    cache.set(cache_key, routes, ROUTE_CACHE_SECONDS)
    return routes


def point_at_mile(route: Route, target_mile: float) -> LatLon:
    travelled = 0.0
    for i, miles in enumerate(route.segment_miles):
        if travelled + miles >= target_mile and miles > 0:
            return geo.lerp(route.points[i], route.points[i + 1], (target_mile - travelled) / miles)
        travelled += miles
    return route.points[-1]


def _sample(route: Route, every_miles: float) -> list[LatLon]:
    count = max(2, int(route.distance_miles / every_miles))
    return [point_at_mile(route, route.distance_miles * i / count) for i in range(count + 1)]


def overlap_ratio(a: Route, b: Route, tolerance_miles: float = 3.0) -> float:
    """Share of route `a` (sampled every ~5 mi) that runs within tolerance of route `b`."""
    cell = 0.1  # degrees, ~7 miles; bigger than the tolerance so neighbours suffice
    grid: dict[tuple[int, int], list[LatLon]] = {}
    for p in _sample(b, 1.0):
        grid.setdefault((int(p[0] // cell), int(p[1] // cell)), []).append(p)

    samples = _sample(a, 5.0)
    hits = 0
    for p in samples:
        cx, cy = int(p[0] // cell), int(p[1] // cell)
        neighbours = (
            q for dx in (-1, 0, 1) for dy in (-1, 0, 1) for q in grid.get((cx + dx, cy + dy), ())
        )
        if any(geo.approx_miles(p, q) <= tolerance_miles for q in neighbours):
            hits += 1
    return hits / len(samples)


def _is_distinct(candidate: Route, chosen: list[Route]) -> bool:
    return all(
        overlap_ratio(candidate, r) < MAX_OVERLAP and overlap_ratio(r, candidate) < MAX_OVERLAP
        for r in chosen
    )


def _detour_candidates(origin: LatLon, destination: LatLon, base: Route) -> list[Route]:
    straight = geo.haversine_miles(origin, destination)
    mid = point_at_mile(base, base.distance_miles / 2)
    heading = geo.bearing_deg(origin, destination)
    vias = [
        geo.offset_point(mid, heading + (90 if frac > 0 else -90), abs(frac) * straight)
        for frac in DETOUR_OFFSETS
    ]

    def fetch(via: LatLon) -> Route | None:
        try:
            return _osrm([origin, via, destination])[0]
        except UpstreamError as exc:
            logger.info("Detour via %s failed: %s", via, exc)
            return None

    with ThreadPoolExecutor(max_workers=len(vias)) as pool:
        return [r for r in pool.map(fetch, vias) if r is not None]


def get_route_options(origin: LatLon, destination: LatLon, count: int = 3) -> list[Route]:
    """Up to `count` distinct routes, fastest first."""
    routes = _osrm([origin, destination], alternatives=count)
    if not routes:
        raise UpstreamError("No route found between these points.")

    chosen = [routes[0]]
    for route in routes[1:]:
        if len(chosen) < count and _is_distinct(route, chosen):
            chosen.append(route)

    if len(chosen) < count:
        fastest = chosen[0].duration_seconds
        for route in _detour_candidates(origin, destination, chosen[0]):
            if len(chosen) == count:
                break
            if route.duration_seconds <= fastest * MAX_DETOUR_RATIO and _is_distinct(route, chosen):
                chosen.append(route)

    return sorted(chosen, key=lambda r: r.duration_seconds)
