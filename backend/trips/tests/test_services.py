import json
import re
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
import responses
from django.core.cache import cache

from trips.services import routing
from trips.services.weather import OpenMeteoProvider
from trips.tests.factories import straight_route


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


def osrm_route(route, seconds_scale=1.0):
    meters = [m * 1609.344 for m in route.segment_miles]
    return {
        "geometry": {"coordinates": [[lon, lat] for lat, lon in route.points]},
        "legs": [
            {
                "summary": route.summary,
                "annotation": {
                    "distance": meters,
                    "duration": [s * seconds_scale for s in route.segment_seconds],
                },
            }
        ],
    }


def test_osrm_parse_caps_speed_at_truck_limit(settings):
    settings.TRUCK_MAX_SPEED_MPH = 65
    fast_car = straight_route(miles=130, mph=80)
    parsed = routing._parse_osrm_route(osrm_route(fast_car), max_mph=65)
    assert parsed.distance_miles == pytest.approx(130, rel=1e-3)
    assert parsed.duration_seconds == pytest.approx(2 * 3600, rel=1e-3)


@responses.activate
def test_route_options_fill_up_to_three_with_detours(settings):
    settings.OSRM_BASE_URL = "https://osrm.test"
    main = straight_route(start=(40.0, -100.0), miles=200, mph=60, summary="I 80")
    north = straight_route(start=(41.0, -100.0), miles=210, mph=60, summary="US 30")
    south = straight_route(start=(39.0, -100.0), miles=220, mph=60, summary="US 50")

    def callback(request):
        coords = request.url.split("/driving/")[1].split("?")[0].split(";")
        if len(coords) == 2:  # direct request: OSRM gives just one route
            body = {"code": "Ok", "routes": [osrm_route(main)]}
        else:  # via-point request: pick the route on that side
            via_lat = float(coords[1].split(",")[1])
            detour = north if via_lat > 40.5 else south if via_lat < 39.5 else main
            body = {"code": "Ok", "routes": [osrm_route(detour)]}
        return 200, {}, json.dumps(body)

    responses.add_callback(
        responses.GET, re.compile(r"https://osrm\.test/route/v1/driving/.*"), callback=callback
    )

    options = routing.get_route_options((40.0, -100.0), (40.0, -96.2))
    assert [r.summary for r in options] == ["I 80", "US 30", "US 50"]


def test_overlap_detects_duplicates():
    a = straight_route(miles=100)
    assert routing.overlap_ratio(a, straight_route(miles=100)) == 1.0
    assert routing.overlap_ratio(a, straight_route(start=(41.0, -100.0), miles=100)) == 0.0


@responses.activate
def test_open_meteo_batches_snaps_and_caches(settings):
    settings.OPEN_METEO_URL = "https://meteo.test/forecast"
    start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(hours=3)
    days = (start + timedelta(hours=48)).date() - start.date()
    n_hours = (days.days + 1) * 24

    def callback(request):
        q = parse_qs(urlparse(request.url).query)
        count = len(q["latitude"][0].split(","))
        hourly = {
            "time": [f"t{i}" for i in range(n_hours)],
            "wind_speed_10m": list(range(n_hours)),  # wind == hours since 00:00 UTC
            "wind_gusts_10m": [None] * n_hours,
            "rain": [0.1] * n_hours,
            "showers": [0.05] * n_hours,
            "snowfall": [0.0] * n_hours,
            "temperature_2m": [50.0] * n_hours,
        }
        return 200, {}, json.dumps([{"hourly": hourly}] * count)

    responses.add_callback(responses.GET, "https://meteo.test/forecast", callback=callback)

    # 120 distinct cells → 3 batches of <=50; two points snap into one cell.
    points = [(30 + i * 0.2, -100.0) for i in range(120)] + [(30.01, -100.02)]
    series = OpenMeteoProvider().forecast(points, start, 49)

    assert len(responses.calls) == 3
    assert len(series) == 121
    first = series[0].at(start)
    assert first.wind_mph == start.hour  # sliced to start at `start`, not midnight
    assert first.rain_in_hr == pytest.approx(0.15)  # rain + showers
    assert series[-1].hours == series[0].hours

    OpenMeteoProvider().forecast(points, start, 49)
    assert len(responses.calls) == 3  # second call served from cache
