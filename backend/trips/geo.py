"""Small geometry helpers. Coordinates are (lat, lon) tuples in degrees."""

import math

EARTH_RADIUS_MILES = 3958.8
METERS_PER_MILE = 1609.344

LatLon = tuple[float, float]


def haversine_miles(a: LatLon, b: LatLon) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(h))


def approx_miles(a: LatLon, b: LatLon) -> float:
    """Equirectangular distance: fast and accurate enough for short hops."""
    mean_lat = math.radians((a[0] + b[0]) / 2)
    dx = math.radians(b[1] - a[1]) * math.cos(mean_lat)
    dy = math.radians(b[0] - a[0])
    return EARTH_RADIUS_MILES * math.hypot(dx, dy)


def lerp(a: LatLon, b: LatLon, t: float) -> LatLon:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def offset_point(origin: LatLon, bearing_deg: float, miles: float) -> LatLon:
    """Point `miles` away from `origin` along `bearing_deg` (0 = north)."""
    lat1, lon1 = map(math.radians, origin)
    bearing = math.radians(bearing_deg)
    d = miles / EARTH_RADIUS_MILES
    lat2 = math.asin(
        math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(bearing)
    )
    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(d) * math.cos(lat1),
        math.cos(d) - math.sin(lat1) * math.sin(lat2),
    )
    return (math.degrees(lat2), math.degrees(lon2))


def bearing_deg(a: LatLon, b: LatLon) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    y = math.sin(lon2 - lon1) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def simplify(points: list[LatLon], tolerance_deg: float) -> list[LatLon]:
    """Ramer-Douglas-Peucker, iterative so long routes don't hit the recursion limit."""
    if len(points) < 3:
        return list(points)

    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        start, end = stack.pop()
        (y1, x1), (y2, x2) = points[start], points[end]
        dx, dy = x2 - x1, y2 - y1
        seg_len_sq = dx * dx + dy * dy
        max_dist, index = 0.0, start
        for i in range(start + 1, end):
            py, px = points[i]
            if seg_len_sq == 0:
                dist = math.hypot(px - x1, py - y1)
            else:
                t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / seg_len_sq))
                dist = math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))
            if dist > max_dist:
                max_dist, index = dist, i
        if max_dist > tolerance_deg:
            keep[index] = True
            stack.append((start, index))
            stack.append((index, end))
    return [p for p, k in zip(points, keep, strict=True) if k]
