"""Trip planning: routes → checkpoints with ETAs → weather → risk → recommendation.

This module is pure orchestration over the routing and weather services, so the
whole pipeline can be tested with fake providers.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from trips import geo, heatmap
from trips.geo import LatLon
from trips.risk import RiskLevel, assess
from trips.services.routing import Route, get_route_options, point_at_mile
from trips.services.weather import (
    OpenMeteoProvider,
    SimulatedStormProvider,
    WeatherProvider,
    floor_hour,
)

SAMPLE_INTERVALS_MILES = (10, 25, 50)
HEATMAP_HOURS = 49  # slider covers +0h … +48h from departure
DISPLAY_TOLERANCE_DEG = 0.0008  # ~90 m; keeps polylines light for the map


@dataclass
class Checkpoint:
    mile: float
    point: LatLon
    eta: datetime
    owned_miles: float = 0.0  # stretch of road this checkpoint represents
    weather: dict | None = None
    risk: RiskLevel = RiskLevel.LOW
    reasons: list[str] = field(default_factory=list)


@dataclass
class PlanRequest:
    origin: LatLon
    destination: LatLon
    departure: datetime  # timezone-aware
    load_lb: float
    interval_miles: int = 25
    simulate_storm: bool = False


def build_checkpoints(route: Route, interval_miles: float, departure: datetime) -> list[Checkpoint]:
    """A checkpoint at mile 0, every `interval_miles`, and at the destination.

    ETA is departure + truck-adjusted driving time to that point (no rest stops).
    """
    checkpoints = []
    target = 0.0
    travelled_miles = travelled_seconds = 0.0
    for i, (miles, seconds) in enumerate(
        zip(route.segment_miles, route.segment_seconds, strict=True)
    ):
        while miles > 0 and target <= travelled_miles + miles:
            t = (target - travelled_miles) / miles
            checkpoints.append(
                Checkpoint(
                    mile=target,
                    point=geo.lerp(route.points[i], route.points[i + 1], t),
                    eta=departure + timedelta(seconds=travelled_seconds + t * seconds),
                )
            )
            target += interval_miles
        travelled_miles += miles
        travelled_seconds += seconds

    if not checkpoints or travelled_miles - checkpoints[-1].mile > 0.5:
        checkpoints.append(
            Checkpoint(
                mile=travelled_miles,
                point=route.points[-1],
                eta=departure + timedelta(seconds=travelled_seconds),
            )
        )

    # Each checkpoint stands for the road halfway to its neighbours.
    for i, cp in enumerate(checkpoints):
        start = (checkpoints[i - 1].mile + cp.mile) / 2 if i > 0 else cp.mile
        end = (cp.mile + checkpoints[i + 1].mile) / 2 if i < len(checkpoints) - 1 else cp.mile
        cp.owned_miles = end - start
    return checkpoints


def summarize(checkpoints: list[Checkpoint]) -> dict:
    miles = {level: 0.0 for level in RiskLevel}
    for cp in checkpoints:
        miles[cp.risk] += cp.owned_miles
    total = sum(miles.values()) or 1.0
    return {
        "miles_by_risk": {level.label: round(m, 1) for level, m in miles.items()},
        "average_risk": round(sum(level * m for level, m in miles.items()) / total, 3),
        "worst_risk": max((cp.risk for cp in checkpoints), default=RiskLevel.LOW),
    }


def ranking_key(option: dict) -> tuple:
    """Lower is better. Order follows the brief, with No Travel miles ranked first
    because a route that crosses No Travel weather is worse than any Severe one.

    Miles are compared to the nearest mile. Average risk (0-4 scale) is compared to
    one decimal: a difference under ~0.05 means only a few miles of Moderate weather,
    which shouldn't send a driver on a route that is hours longer.
    """
    by_risk = option["miles_by_risk"]
    return (
        round(by_risk["No Travel"]),
        round(by_risk["Severe"]),
        round(by_risk["High"]),
        round(option["average_risk"], 1),
        option["duration_seconds"],
    )


CRITERIA = (
    ("No Travel miles", lambda o: f"{o['miles_by_risk']['No Travel']:.0f} mi"),
    ("Severe miles", lambda o: f"{o['miles_by_risk']['Severe']:.0f} mi"),
    ("High miles", lambda o: f"{o['miles_by_risk']['High']:.0f} mi"),
    ("average risk", lambda o: f"{o['average_risk']:.2f}"),
    ("travel time", lambda o: f"{o['duration_seconds'] / 3600:.1f} h"),
)


def explain(best: dict, runner_up: dict | None) -> str:
    if runner_up is None:
        return "Only one route was available."
    for i, (a, b) in enumerate(zip(ranking_key(best), ranking_key(runner_up), strict=True)):
        if a != b:
            name, fmt = CRITERIA[i]
            tied = [c[0] for c in CRITERIA[:i]]
            prefix = f"Tied on {', '.join(tied)}; " if tied else ""
            adjective = ("fewest", "fewest", "fewest", "lowest", "shortest")[i]
            return (
                f"{prefix}{adjective} {name} "
                f"({fmt(best)} vs {fmt(runner_up)} on {runner_up['name']})."
            )
    return "All routes scored the same; picked the fastest."


def _storm_for(routes: list[Route], departure: datetime) -> SimulatedStormProvider:
    """Park a storm on the fastest route's midpoint, timed to meet the truck."""
    fastest = routes[0]
    mid = fastest.distance_miles / 2
    cps = build_checkpoints(fastest, mid, departure)
    return SimulatedStormProvider(center=point_at_mile(fastest, mid), peak_time=cps[1].eta)


def plan_trip(req: PlanRequest, provider: WeatherProvider | None = None) -> dict:
    routes = get_route_options(req.origin, req.destination)
    if provider is None:
        provider = _storm_for(routes, req.departure) if req.simulate_storm else OpenMeteoProvider()

    all_checkpoints = [build_checkpoints(r, req.interval_miles, req.departure) for r in routes]
    longest_hours = max(r.duration_seconds for r in routes) / 3600
    hours = max(HEATMAP_HOURS, math.ceil(longest_hours) + 2)
    start = floor_hour(req.departure)

    flat = [cp for cps in all_checkpoints for cp in cps]
    series = provider.forecast([cp.point for cp in flat], start, hours)
    for cp, s in zip(flat, series, strict=True):
        weather = s.at(cp.eta)
        if weather is None:  # should not happen: the window covers the longest trip
            continue
        result = assess(weather, req.load_lb)
        cp.weather = {
            "wind_mph": round(weather.wind_mph, 1),
            "gust_mph": round(weather.gust_mph or 0, 1),
            "rain_in_hr": round(weather.rain_in_hr, 3),
            "snow_in_hr": round(weather.snow_in_hr, 3),
            "temperature_f": round(weather.temperature_f or 0, 1),
        }
        cp.risk, cp.reasons = result.level, result.reasons

    options = []
    for index, (route, cps) in enumerate(zip(routes, all_checkpoints, strict=True)):
        stats = summarize(cps)
        options.append(
            {
                "id": index,
                "name": f"Route {chr(65 + index)}",
                "summary": route.summary,
                "distance_miles": round(route.distance_miles, 1),
                "duration_seconds": round(route.duration_seconds),
                "arrival": cps[-1].eta.isoformat(),
                "miles_by_risk": stats["miles_by_risk"],
                "average_risk": stats["average_risk"],
                "worst_risk": stats["worst_risk"].label,
                "geometry": [
                    [round(lat, 5), round(lon, 5)]
                    for lat, lon in geo.simplify(route.points, DISPLAY_TOLERANCE_DEG)
                ],
                "checkpoints": [_checkpoint_json(cp) for cp in cps],
            }
        )

    ranked = sorted(options, key=ranking_key)
    best = ranked[0]
    for rank, option in enumerate(ranked, start=1):
        option["rank"] = rank
    return {
        "recommended_route_id": best["id"],
        "recommendation_reason": explain(best, ranked[1] if len(ranked) > 1 else None),
        "routes": options,
        "heatmap": heatmap.build(routes, provider, req.departure, HEATMAP_HOURS, req.load_lb),
        "risk_levels": [level.label for level in RiskLevel],
    }


def _checkpoint_json(cp: Checkpoint) -> dict:
    return {
        "mile": round(cp.mile, 1),
        "lat": round(cp.point[0], 5),
        "lon": round(cp.point[1], 5),
        "eta": cp.eta.isoformat(),
        "weather": cp.weather,
        "risk": cp.risk.label,
        "risk_score": int(cp.risk),
        "reasons": cp.reasons,
    }
