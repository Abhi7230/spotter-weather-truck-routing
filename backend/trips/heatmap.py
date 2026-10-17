"""Weather heatmap over the trip corridor for every hour of the forecast slider.

The corridor is every grid cell within CORRIDOR_MILES of any route. The grid step
grows for long trips so the point count (and payload) stays bounded. All hours are
sent up front so the slider never waits on the network.
"""

import math
from datetime import datetime, timedelta

from trips import geo
from trips.geo import LatLon
from trips.risk import assess
from trips.services.routing import Route, point_at_mile
from trips.services.weather import WeatherProvider

CORRIDOR_MILES = 40
MAX_POINTS = 400
GRID_STEPS_DEG = (0.2, 0.3, 0.4, 0.5, 0.75, 1.0, 1.5)


def _grid_range(center: float, reach: float, step: float) -> range:
    return range(math.floor((center - reach) / step), math.ceil((center + reach) / step) + 1)


def corridor_cells(routes: list[Route], step: float) -> list[LatLon]:
    cells: set[tuple[int, int]] = set()
    for route in routes:
        n = max(2, int(route.distance_miles / 10))
        for i in range(n + 1):
            lat, lon = point_at_mile(route, route.distance_miles * i / n)
            lat_reach = CORRIDOR_MILES / 69.0
            lon_reach = lat_reach / max(math.cos(math.radians(lat)), 0.2)
            rows = _grid_range(lat, lat_reach, step)
            cols = _grid_range(lon, lon_reach, step)
            for gy in rows:
                for gx in cols:
                    if geo.approx_miles((lat, lon), (gy * step, gx * step)) <= CORRIDOR_MILES:
                        cells.add((gy, gx))
    return sorted((round(gy * step, 4), round(gx * step, 4)) for gy, gx in cells)


def build(
    routes: list[Route], provider: WeatherProvider, start: datetime, hours: int, load_lb: float
) -> dict:
    for step in GRID_STEPS_DEG:
        points = corridor_cells(routes, step)
        if len(points) <= MAX_POINTS:
            break

    series = provider.forecast(points, start, hours)
    frames = []
    for h in range(hours):
        t = start + timedelta(hours=h)
        frame = {"risk": [], "wind": [], "rain": [], "snow": []}
        for s in series:
            w = s.at(t)
            if w is None:
                frame["risk"].append(0)
                frame["wind"].append(0)
                frame["rain"].append(0)
                frame["snow"].append(0)
                continue
            frame["risk"].append(int(assess(w, load_lb).level))
            frame["wind"].append(round(w.wind_mph))
            frame["rain"].append(round(w.rain_in_hr, 2))
            frame["snow"].append(round(w.snow_in_hr, 2))
        frames.append(frame)

    return {
        "start": start.isoformat(),
        "step_deg": step,
        "points": [[lat, lon] for lat, lon in points],
        "frames": frames,
    }
