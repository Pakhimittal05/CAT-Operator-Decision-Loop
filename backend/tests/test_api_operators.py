"""Integration tests for Operator and Dashboard API Endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    """TestClient fixture that triggers FastAPI lifespan startup."""
    with TestClient(app) as c:
        yield c


def test_health_check_endpoint(client):
    """Verify health endpoint indicates models loaded and synthetic flag."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["models_loaded"] is True
    assert data["is_synthetic"] is True


def test_get_operators_list(client):
    """Verify GET /operators returns list of 30 operators with EWMA dynamic summary."""
    response = client.get("/operators")
    assert response.status_code == 200
    operators = response.json()
    assert len(operators) == 30

    for op in operators:
        assert "id" in op
        assert "name" in op
        assert "legacy_skill_tier" in op
        assert "composite_score" in op
        assert 0.0 <= op["composite_score"] <= 100.0
        assert op["derived_label"] in {"Expert", "Intermediate", "Beginner"}
        assert op["trend_direction"] in {"improving", "stable", "declining"}
        assert 0.0 <= op["confidence"] <= 1.0
        assert op["sample_count"] > 0
        assert op["is_synthetic"] is True


def test_get_operator_state(client):
    """Verify GET /operators/{id}/state returns detailed dynamic 5-dimension state."""
    response = client.get("/operators/1/state")
    assert response.status_code == 200
    state = response.json()

    assert state["operator_id"] == 1
    for dim_key in [
        "efficiency_score",
        "idling_score",
        "duration_score",
        "load_cycle_score",
        "safety_score",
        "composite_score",
    ]:
        assert dim_key in state
        assert 0.0 <= state[dim_key] <= 100.0

    assert state["trend_direction"] in {"improving", "stable", "declining"}
    assert 0.0 <= state["confidence"] <= 1.0
    assert state["derived_label"] in {"Expert", "Intermediate", "Beginner"}
    assert state["sample_count"] > 0
    assert state["is_synthetic"] is True


def test_get_operator_state_not_found(client):
    """Verify GET /operators/{id}/state returns 404 for nonexistent operator ID."""
    response = client.get("/operators/99999/state")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_operator_history(client):
    """Verify GET /operators/{id}/history returns chronological task history with deviations."""
    response = client.get("/operators/1/history?limit=10")
    assert response.status_code == 200
    data = response.json()

    assert data["operator_id"] == 1
    assert "history" in data
    assert len(data["history"]) > 0
    assert len(data["history"]) <= 10

    first_item = data["history"][0]
    required_fields = [
        "task_instance_id",
        "task_type",
        "machine_name",
        "weather",
        "completed_at",
        "duration_minutes",
        "idle_seconds",
        "load_cycles",
        "efficiency_score",
        "seatbelt_engaged",
        "min_proximity_distance",
        "d_cycle_efficiency",
        "d_idling",
        "d_duration",
        "d_load_cycle",
        "d_safety",
        "composite_magnitude",
        "is_synthetic",
    ]
    for f in required_fields:
        assert f in first_item, f"Missing field: {f}"

    assert first_item["composite_magnitude"] >= 0.0
    assert first_item["is_synthetic"] is True


def test_get_dashboard_daily_tasks(client):
    """Verify GET /dashboard/daily-tasks returns recent tasks and safety compliance summary."""
    response = client.get("/dashboard/daily-tasks?limit=15")
    assert response.status_code == 200
    data = response.json()

    assert "tasks" in data
    assert "compliance" in data
    assert "total_count" in data
    assert len(data["tasks"]) <= 15
    assert data["total_count"] >= 3000

    comp = data["compliance"]
    assert 0.0 <= comp["seatbelt_compliance_pct"] <= 100.0
    assert 0.0 <= comp["proximity_safe_pct"] <= 100.0
    assert comp["safety_violations_count"] >= 0
    assert comp["is_synthetic"] is True
