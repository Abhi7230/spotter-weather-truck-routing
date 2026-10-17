import pytest

from trips.risk import (
    RiskLevel,
    Weather,
    assess,
    load_adjusted_wind_level,
    rain_level,
    snow_level,
    wind_level,
)

L, M, H, S, N = (
    RiskLevel.LOW,
    RiskLevel.MODERATE,
    RiskLevel.HIGH,
    RiskLevel.SEVERE,
    RiskLevel.NO_TRAVEL,
)


@pytest.mark.parametrize(
    ("mph", "expected"),
    [
        (0, L),
        (24.9, L),
        (25, M),
        (34.9, M),
        (35, H),
        (44.9, H),
        (45, S),
        (54.9, S),
        (55, N),
        (80, N),
    ],
)
def test_wind_bands(mph, expected):
    assert wind_level(mph) == expected


@pytest.mark.parametrize(
    ("rate", "expected"),
    [
        (0, L),
        (0.099, L),
        (0.10, M),
        (0.249, M),
        (0.25, H),
        (0.49, H),
        (0.50, S),
        (1.00, S),
        (1.01, N),
    ],
)
def test_rain_bands(rate, expected):
    assert rain_level(rate) == expected


@pytest.mark.parametrize(
    ("rate", "expected"),
    [(0, L), (0.49, L), (0.5, M), (0.99, M), (1.0, H), (1.99, H), (2.0, S), (3.0, S), (3.01, N)],
)
def test_snow_bands(rate, expected):
    assert snow_level(rate) == expected


@pytest.mark.parametrize(
    ("mph", "load", "expected"),
    [
        (55, 0, N),  # >=55 mph is No Travel for any load
        (50, 30_000, S),  # 45-54 mph at exactly 30,000 lb stays Severe
        (50, 30_001, N),  # ... and becomes No Travel above 30,000 lb
        (40, 40_000, H),  # 35-44 mph at exactly 40,000 lb stays High
        (40, 40_001, S),  # ... and becomes Severe above 40,000 lb
        (30, 80_000, M),  # load rules don't touch lighter wind
    ],
)
def test_load_rules(mph, load, expected):
    assert load_adjusted_wind_level(mph, load) == expected


def test_assess_takes_worst_condition():
    result = assess(Weather(wind_mph=26, rain_in_hr=0.3, snow_in_hr=0.6), load_lb=10_000)
    assert result.level == H
    assert len(result.reasons) == 3


def test_assess_explains_load_escalation():
    result = assess(Weather(wind_mph=40, rain_in_hr=0, snow_in_hr=0), load_lb=45_000)
    assert result.level == S
    assert "45,000 lb" in result.reasons[0]


def test_calm_weather_has_no_reasons():
    assert assess(Weather(5, 0, 0), 20_000).reasons == []


def test_reason_does_not_round_wind_across_a_threshold():
    # 54.6 mph is Severe; printing "55 mph (Severe)" would look like a bug.
    result = assess(Weather(wind_mph=54.6, rain_in_hr=0, snow_in_hr=0), load_lb=0)
    assert result.reasons == ["Wind 54.6 mph (Severe)"]
