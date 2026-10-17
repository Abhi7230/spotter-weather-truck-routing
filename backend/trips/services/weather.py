"""Hourly weather forecasts for many points at once.

`OpenMeteoProvider` is the real source. `SimulatedStormProvider` produces a
deterministic storm so the risk logic can be demoed (and tested) on a calm day.
Both return one `HourlySeries` per requested point, starting at `start`.
"""

import logging
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from django.conf import settings
from django.core.cache import cache

from trips import geo
from trips.geo import LatLon
from trips.risk import Weather
from trips.services.http import UpstreamError, get_json

logger = logging.getLogger(__name__)

HOUR = timedelta(hours=1)
OPEN_METEO_BATCH = 50  # locations per request
OPEN_METEO_MAX_FORECAST_DAYS = 16


def floor_hour(t: datetime) -> datetime:
    return t.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


@dataclass
class HourlySeries:
    start: datetime  # UTC, on the hour
    hours: list[Weather]

    def at(self, t: datetime) -> Weather | None:
        """Forecast for the hour nearest to `t`, or None outside the series."""
        index = round((t - self.start) / HOUR)
        if 0 <= index < len(self.hours):
            return self.hours[index]
        return None


class WeatherProvider(Protocol):
    def forecast(self, points: list[LatLon], start: datetime, hours: int) -> list[HourlySeries]: ...


class OpenMeteoProvider:
    """https://open-meteo.com – free, keyless, supports many locations per call.

    Points are snapped to a grid (`precision` degrees) so nearby checkpoints share
    one forecast and repeat requests hit the cache. Open-Meteo's model resolution
    is a few km, so 0.1° (~7 mi) snapping loses nothing meaningful.
    """

    VARIABLES = "wind_speed_10m,wind_gusts_10m,rain,showers,snowfall,temperature_2m"

    def __init__(self, precision: float = 0.1):
        self.precision = precision

    def _snap(self, p: LatLon) -> LatLon:
        q = self.precision
        return (round(round(p[0] / q) * q, 4), round(round(p[1] / q) * q, 4))

    def forecast(self, points: list[LatLon], start: datetime, hours: int) -> list[HourlySeries]:
        start = floor_hour(start)
        first_day = start.date()
        last_day = (start + hours * HOUR).date()
        if (last_day - datetime.now(UTC).date()).days >= OPEN_METEO_MAX_FORECAST_DAYS:
            raise UpstreamError("Departure is too far in the future for a forecast.")

        snapped = [self._snap(p) for p in points]
        key = f"{first_day}:{last_day}"
        daily: dict[LatLon, list[Weather]] = {}
        missing = []
        for cell in dict.fromkeys(snapped):
            if (hit := cache.get(_cache_key(cell, key))) is not None:
                daily[cell] = hit
            else:
                missing.append(cell)

        size = OPEN_METEO_BATCH
        batches = [missing[i : i + size] for i in range(0, len(missing), size)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            for result in pool.map(lambda b: self._fetch(b, first_day, last_day), batches):
                for cell, series in result.items():
                    daily[cell] = series
                    cache.set(_cache_key(cell, key), series, settings.WEATHER_CACHE_SECONDS)

        # Series from Open-Meteo start at 00:00 UTC of the first day; slice to `start`.
        day_start = datetime.combine(first_day, datetime.min.time(), tzinfo=UTC)
        offset = round((start - day_start) / HOUR)
        return [HourlySeries(start, daily[cell][offset : offset + hours]) for cell in snapped]

    def _fetch(self, cells: list[LatLon], first_day, last_day) -> dict[LatLon, list[Weather]]:
        data = get_json(
            settings.OPEN_METEO_URL,
            params={
                "latitude": ",".join(f"{lat}" for lat, _ in cells),
                "longitude": ",".join(f"{lon}" for _, lon in cells),
                "hourly": self.VARIABLES,
                "wind_speed_unit": "mph",
                "precipitation_unit": "inch",
                "temperature_unit": "fahrenheit",
                "timezone": "GMT",
                "start_date": first_day.isoformat(),
                "end_date": last_day.isoformat(),
            },
        )
        locations = data if isinstance(data, list) else [data]
        if len(locations) != len(cells):
            raise UpstreamError("Weather API returned an unexpected number of locations.")
        return {
            cell: _parse_hourly(loc["hourly"]) for cell, loc in zip(cells, locations, strict=True)
        }


def _cache_key(cell: LatLon, days: str) -> str:
    return f"wx:{cell[0]},{cell[1]}:{days}"


def _parse_hourly(hourly: dict) -> list[Weather]:
    def values(name):
        return [v or 0.0 for v in hourly[name]]  # Open-Meteo uses null for "no data"

    return [
        Weather(
            wind_mph=wind,
            gust_mph=gust,
            rain_in_hr=rain + showers,
            snow_in_hr=snow,
            temperature_f=temp,
        )
        for wind, gust, rain, showers, snow, temp in zip(
            values("wind_speed_10m"),
            values("wind_gusts_10m"),
            values("rain"),
            values("showers"),
            values("snowfall"),
            values("temperature_2m"),
            strict=True,
        )
    ]


class SimulatedStormProvider:
    """A single storm cell drifting east, peaking at `center` at `peak_time`.

    Strength falls off with distance from the cell's core, so routes that pass
    through the core see No Travel / Severe conditions and routes further away see
    milder weather. North of `snow_latitude` precipitation falls as snow.
    """

    def __init__(
        self,
        center: LatLon,
        peak_time: datetime,
        radius_miles: float = 90,
        speed_mph: float = 20,
        snow_latitude: float = 41.0,
    ):
        self.center = center
        self.peak_time = peak_time
        self.radius_miles = radius_miles
        self.speed_mph = speed_mph
        self.snow_latitude = snow_latitude

    def weather_at(self, p: LatLon, t: datetime) -> Weather:
        drift_miles = (t - self.peak_time) / HOUR * self.speed_mph
        core = geo.offset_point(self.center, 90, drift_miles)
        distance = geo.haversine_miles(p, core)
        strength = math.exp(-((distance / self.radius_miles) ** 2))
        precip = 1.3 * strength
        snowing = p[0] >= self.snow_latitude
        return Weather(
            wind_mph=round(10 + 50 * strength, 1),
            gust_mph=round(15 + 65 * strength, 1),
            rain_in_hr=0.0 if snowing else round(precip, 3),
            snow_in_hr=round(precip * 2.6, 3) if snowing else 0.0,
            temperature_f=28.0 if snowing else 55.0,
        )

    def forecast(self, points: list[LatLon], start: datetime, hours: int) -> list[HourlySeries]:
        start = floor_hour(start)
        times = [start + i * HOUR for i in range(hours)]
        return [HourlySeries(start, [self.weather_at(p, t) for t in times]) for p in points]
