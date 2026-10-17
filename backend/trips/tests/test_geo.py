import pytest

from trips import geo


def test_haversine_known_distance():
    chicago, denver = (41.8781, -87.6298), (39.7392, -104.9903)
    assert geo.haversine_miles(chicago, denver) == pytest.approx(920, abs=5)


def test_offset_point_round_trip():
    start = (40.0, -100.0)
    moved = geo.offset_point(start, 90, 50)
    assert geo.haversine_miles(start, moved) == pytest.approx(50, rel=1e-3)
    assert geo.bearing_deg(start, moved) == pytest.approx(90, abs=0.5)


def test_simplify_drops_collinear_points_and_keeps_corners():
    line = [(0.0, x / 10) for x in range(11)] + [(y / 10, 1.0) for y in range(1, 11)]
    simplified = geo.simplify(line, tolerance_deg=0.001)
    assert simplified == [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0)]
