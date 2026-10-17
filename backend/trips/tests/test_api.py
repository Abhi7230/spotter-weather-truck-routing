from datetime import UTC, datetime, timedelta

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from trips import views
from trips.models import TripPlan
from trips.services.http import UpstreamError

pytestmark = pytest.mark.django_db

FAKE_RESULT = {"recommended_route_id": 0, "routes": [], "heatmap": {}}


@pytest.fixture
def client():
    return APIClient()


def payload(**overrides):
    body = {
        "origin": {"label": "Chicago", "lat": 41.88, "lon": -87.63},
        "destination": {"label": "Denver", "lat": 39.74, "lon": -104.99},
        "departure": (datetime.now(UTC) + timedelta(hours=2)).isoformat(),
        "load_lb": 42000,
        "interval_miles": 25,
    }
    body.update(overrides)
    return body


def test_create_plan_saves_and_returns_result(client, monkeypatch):
    captured = {}

    def fake_plan(req):
        captured["req"] = req
        return FAKE_RESULT

    monkeypatch.setattr(views, "plan_trip", fake_plan)
    response = client.post("/api/plans/", payload(), format="json")

    assert response.status_code == 201
    assert response.json()["result"] == FAKE_RESULT
    assert captured["req"].origin == (41.88, -87.63)
    assert captured["req"].load_lb == 42000

    plan_id = response.json()["id"]
    detail = client.get(f"/api/plans/{plan_id}/")
    assert detail.status_code == 200
    assert detail.json()["origin"]["label"] == "Chicago"
    assert "result" not in client.get("/api/plans/").json()[0]


@pytest.mark.parametrize(
    "overrides",
    [
        {"interval_miles": 30},
        {"load_lb": -1},
        {"departure": (datetime.now(UTC) - timedelta(days=1)).isoformat()},
        {"departure": (datetime.now(UTC) + timedelta(days=9)).isoformat()},
        {"destination": {"label": "Chicago", "lat": 41.88, "lon": -87.63}},
    ],
)
def test_invalid_requests_are_rejected(client, overrides):
    response = client.post("/api/plans/", payload(**overrides), format="json")
    assert response.status_code == 400
    assert TripPlan.objects.count() == 0


def test_upstream_failure_returns_502(client, monkeypatch):
    def boom(req):
        raise UpstreamError("OSRM is down")

    monkeypatch.setattr(views, "plan_trip", boom)
    response = client.post("/api/plans/", payload(), format="json")
    assert response.status_code == 502
    assert "OSRM is down" in response.json()["detail"]


def test_presets_are_seeded_idempotently(client):
    call_command("seed_presets")
    call_command("seed_presets")
    presets = client.get("/api/presets/").json()
    assert len(presets) == 6
    assert any(p["simulate_storm"] for p in presets)


def test_geocode_short_query_returns_empty(client):
    assert client.get("/api/geocode/?q=ab").json() == []


def test_health(client):
    assert client.get("/api/health/").json() == {"status": "ok"}
