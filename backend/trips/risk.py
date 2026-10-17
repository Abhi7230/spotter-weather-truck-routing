"""Weather risk rules from the assessment brief.

Each checkpoint is classified per condition (wind, rain, snow) using the threshold
table, the worst condition wins, and then the load-weight rules can escalate it.

Boundary handling: the brief's ranges touch at the edges (e.g. rain "0.10-0.25"
and "0.25-0.50"), so a value equal to a boundary goes to the higher band, except
where the brief is explicit (rain/snow "No Travel" starts strictly above 1.00/3.0).
"""

from dataclasses import dataclass, field
from enum import IntEnum


class RiskLevel(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()


# Lower bound (inclusive) of Moderate, High and Severe for each condition.
WIND_BANDS_MPH = (25, 35, 45)
WIND_NO_TRAVEL_MPH = 55  # >= 55 mph
RAIN_BANDS_IN_HR = (0.10, 0.25, 0.50)
RAIN_NO_TRAVEL_IN_HR = 1.00  # > 1.00 in/hr
SNOW_BANDS_IN_HR = (0.5, 1.0, 2.0)
SNOW_NO_TRAVEL_IN_HR = 3.0  # > 3.0 in/hr

HEAVY_LOAD_LB = 30_000
VERY_HEAVY_LOAD_LB = 40_000


@dataclass(frozen=True)
class Weather:
    wind_mph: float
    rain_in_hr: float
    snow_in_hr: float
    gust_mph: float | None = None
    temperature_f: float | None = None


@dataclass(frozen=True)
class RiskAssessment:
    level: RiskLevel
    reasons: list[str] = field(default_factory=list)


def _band(value: float, bands: tuple[float, float, float]) -> RiskLevel:
    moderate, high, severe = bands
    if value >= severe:
        return RiskLevel.SEVERE
    if value >= high:
        return RiskLevel.HIGH
    if value >= moderate:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def wind_level(mph: float) -> RiskLevel:
    if mph >= WIND_NO_TRAVEL_MPH:
        return RiskLevel.NO_TRAVEL
    return _band(mph, WIND_BANDS_MPH)


def rain_level(in_hr: float) -> RiskLevel:
    if in_hr > RAIN_NO_TRAVEL_IN_HR:
        return RiskLevel.NO_TRAVEL
    return _band(in_hr, RAIN_BANDS_IN_HR)


def snow_level(in_hr: float) -> RiskLevel:
    if in_hr > SNOW_NO_TRAVEL_IN_HR:
        return RiskLevel.NO_TRAVEL
    return _band(in_hr, SNOW_BANDS_IN_HR)


def load_adjusted_wind_level(mph: float, load_lb: float) -> RiskLevel:
    """Wind level after the load rules. Heavier trucks tolerate less wind."""
    level = wind_level(mph)
    if level == RiskLevel.SEVERE and load_lb > HEAVY_LOAD_LB:
        return RiskLevel.NO_TRAVEL
    if level == RiskLevel.HIGH and load_lb > VERY_HEAVY_LOAD_LB:
        return RiskLevel.SEVERE
    return level


def assess(weather: Weather, load_lb: float) -> RiskAssessment:
    """Overall risk at one point: the worst of wind (load-adjusted), rain and snow."""
    base_wind = wind_level(weather.wind_mph)
    wind = load_adjusted_wind_level(weather.wind_mph, load_lb)
    rain = rain_level(weather.rain_in_hr)
    snow = snow_level(weather.snow_in_hr)
    level = max(wind, rain, snow)

    reasons = []
    if wind > RiskLevel.LOW:
        text = f"Wind {weather.wind_mph:.0f} mph ({base_wind.label})"
        if wind != base_wind:
            text += f" → {wind.label} with {load_lb:,.0f} lb load"
        reasons.append(text)
    if rain > RiskLevel.LOW:
        reasons.append(f"Rain {weather.rain_in_hr:.2f} in/hr ({rain.label})")
    if snow > RiskLevel.LOW:
        reasons.append(f"Snow {weather.snow_in_hr:.2f} in/hr ({snow.label})")
    return RiskAssessment(level=level, reasons=reasons)
