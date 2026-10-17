"""Test helpers: straight-line fake routes and a constant-weather provider."""

from datetime import datetime, timedelta

from trips import geo
from trips.risk import Weather
from trips.services.routing import Route
from trips.services.weather import HourlySeries, floor_hour


def straight_route(
    start=(40.0, -100.0), miles=100.0, step_miles=1.0, mph=50.0, bearing=90.0, summary="I 99"
) -> Route:
    """A route heading `bearing` from `start`, `miles` long, at a constant speed."""
    n = int(miles / step_miles)
    points = [geo.offset_point(start, bearing, i * step_miles) for i in range(n + 1)]
    segment_miles = [geo.haversine_miles(a, b) for a, b in zip(points, points[1:], strict=False)]
    return Route(
        points=points,
        segment_miles=segment_miles,
        segment_seconds=[m / mph * 3600 for m in segment_miles],
        summary=summary,
    )


class ConstantWeather:
    """Same weather everywhere, or per-point via `by_lon` (lon threshold → weather)."""

    def __init__(self, weather: Weather, by_lon=None):
        self.weather = weather
        self.by_lon = by_lon or []
        self.calls = 0

    def _weather_for(self, point):
        for min_lon, weather in self.by_lon:
            if point[1] >= min_lon:
                return weather
        return self.weather

    def forecast(self, points, start: datetime, hours: int):
        self.calls += 1
        start = floor_hour(start)
        return [HourlySeries(start, [self._weather_for(p)] * hours) for p in points]


CALM = Weather(wind_mph=5, rain_in_hr=0, snow_in_hr=0)


def hours(n: float) -> timedelta:
    return timedelta(hours=n)
