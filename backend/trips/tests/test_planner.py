from datetime import UTC, datetime

import pytest

from trips import planner
from trips.planner import PlanRequest, build_checkpoints, explain, ranking_key
from trips.risk import RiskLevel, Weather
from trips.tests.factories import CALM, ConstantWeather, hours, straight_route

DEPARTURE = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize("interval", [10, 25, 50])
def test_checkpoints_every_interval_with_eta(interval):
    route = straight_route(miles=120, mph=60)
    cps = build_checkpoints(route, interval, DEPARTURE)

    expected_miles = [m for m in range(0, 121, interval)]
    if expected_miles[-1] != 120:
        expected_miles.append(120)
    assert [round(cp.mile) for cp in cps] == expected_miles
    for cp in cps:  # 60 mph → one hour per 60 miles
        assert (cp.eta - DEPARTURE).total_seconds() == pytest.approx(cp.mile * 60, abs=1)
    assert sum(cp.owned_miles for cp in cps) == pytest.approx(route.distance_miles)


def test_checkpoint_owns_half_of_each_neighbouring_gap():
    cps = build_checkpoints(straight_route(miles=100), 25, DEPARTURE)
    assert [round(cp.owned_miles, 1) for cp in cps] == [12.5, 25.0, 25.0, 25.0, 12.5]


def option(name="Route A", duration_h=10.0, avg=0.0, **miles):
    by_risk = {"Low": 0, "Moderate": 0, "High": 0, "Severe": 0, "No Travel": 0}
    by_risk.update({k.replace("_", " ").title(): v for k, v in miles.items()})
    return {
        "name": name,
        "miles_by_risk": by_risk,
        "average_risk": avg,
        "duration_seconds": duration_h * 3600,
    }


def best_of(*options):
    return min(options, key=ranking_key)["name"]


def test_ranking_follows_brief_order():
    # 1. fewest Severe miles beats everything below it
    assert best_of(option("A", severe=10, duration_h=5), option("B", high=200, avg=2)) == "B"
    # 2. then fewest High miles
    assert best_of(option("A", high=30), option("B", high=10, avg=1.5)) == "B"
    # 3. then lowest average risk
    assert best_of(option("A", avg=0.4, duration_h=5), option("B", avg=0.2, duration_h=9)) == "B"
    assert best_of(option("A", avg=0.09, duration_h=5), option("B", avg=0.0, duration_h=9)) == "B"
    # 4. then shortest travel time
    assert best_of(option("A", duration_h=9), option("B", duration_h=8)) == "B"


def test_no_travel_miles_are_worse_than_severe():
    assert best_of(option("A", no_travel=5), option("B", severe=100)) == "B"


def test_tiny_differences_fall_through_to_travel_time():
    a = option("A", severe=10.2, avg=0.32, duration_h=8)
    b = option("B", severe=9.9, avg=0.28, duration_h=10)
    assert best_of(a, b) == "A"


def test_a_few_moderate_miles_do_not_justify_a_much_longer_route():
    # 20 Moderate miles on an 800-mile trip → average risk 0.02.
    fast = option("A", moderate=20, avg=0.02, duration_h=13)
    slow = option("B", avg=0.0, duration_h=17.5)
    assert best_of(fast, slow) == "A"


def test_explain_names_the_deciding_criterion():
    best, other = option("A", high=0), option("B", high=50)
    assert (
        explain(best, other)
        == "Tied on No Travel miles, Severe miles; fewest High miles (0 mi vs 50 mi on B)."
    )


def make_plan(monkeypatch, provider, routes=None, load_lb=20_000, interval=25):
    routes = routes or [
        straight_route(miles=100, mph=60, summary="fast"),
        straight_route(start=(41.0, -100.0), miles=130, mph=60, summary="slow"),
    ]
    monkeypatch.setattr(planner, "get_route_options", lambda o, d: routes)
    return planner.plan_trip(
        PlanRequest(
            origin=(40.0, -100.0),
            destination=(40.0, -98.0),
            departure=DEPARTURE,
            load_lb=load_lb,
            interval_miles=interval,
        ),
        provider=provider,
    )


def test_calm_weather_recommends_fastest_route(monkeypatch):
    result = make_plan(monkeypatch, ConstantWeather(CALM))
    assert result["recommended_route_id"] == 0
    assert "shortest travel time" in result["recommendation_reason"]
    first = result["routes"][0]
    assert first["worst_risk"] == "Low"
    assert first["checkpoints"][1]["eta"] == (DEPARTURE + hours(25 / 60)).isoformat()


def test_storm_on_fast_route_recommends_safer_route(monkeypatch):
    storm = Weather(wind_mph=50, rain_in_hr=0, snow_in_hr=0)  # Severe; No Travel when heavy
    fast = straight_route(miles=100, mph=60)  # stays south of 40.5°
    safe = straight_route(start=(42.0, -100.0), miles=130, mph=60)

    class SouthernStorm(ConstantWeather):
        def _weather_for(self, point):
            return storm if point[0] < 41 else CALM

    light = make_plan(monkeypatch, SouthernStorm(CALM), routes=[fast, safe], load_lb=20_000)
    assert light["routes"][0]["miles_by_risk"]["Severe"] == pytest.approx(100, abs=1)
    assert light["recommended_route_id"] == 1

    heavy = make_plan(monkeypatch, SouthernStorm(CALM), routes=[fast, safe], load_lb=35_000)
    assert heavy["routes"][0]["worst_risk"] == "No Travel"
    assert heavy["recommended_route_id"] == 1


def test_heatmap_has_a_frame_per_slider_hour(monkeypatch):
    result = make_plan(monkeypatch, ConstantWeather(CALM))
    heat = result["heatmap"]
    assert len(heat["frames"]) == 49
    assert 0 < len(heat["points"]) <= 400
    assert all(len(f["risk"]) == len(heat["points"]) for f in heat["frames"])
    assert set(heat["frames"][0]["risk"]) == {"0"}


def test_simulated_storm_creates_risk_on_fastest_route(monkeypatch):
    routes = [straight_route(miles=400, mph=60), straight_route(start=(44.0, -100.0), miles=420)]
    monkeypatch.setattr(planner, "get_route_options", lambda o, d: routes)
    result = planner.plan_trip(
        PlanRequest((40.0, -100.0), (40.0, -95.0), DEPARTURE, 45_000, 25, simulate_storm=True)
    )
    fastest = result["routes"][0]
    assert RiskLevel[fastest["worst_risk"].upper().replace(" ", "_")] >= RiskLevel.SEVERE
    assert result["recommended_route_id"] == 1
