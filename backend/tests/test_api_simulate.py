"""Integration tests for What-If Simulator and Explainability Endpoints (§C, §12)."""

import pytest
from fastapi.testclient import TestClient

from app.db.models import Prediction
from app.db.session import SessionLocal
from app.main import app


@pytest.fixture(scope="module")
def client():
    """TestClient fixture with app lifespan startup."""
    with TestClient(app) as c:
        yield c


def test_get_simulation_options(client):
    """Verify GET /simulate/options returns valid operators, machines, tasks, and weather."""
    response = client.get("/simulate/options")
    assert response.status_code == 200
    data = response.json()

    assert "operators" in data
    assert "machines" in data
    assert "tasks" in data
    assert "weather_options" in data
    assert data["is_synthetic"] is True

    assert len(data["operators"]) == 30
    assert len(data["machines"]) == 10
    assert len(data["tasks"]) == 8
    assert set(data["weather_options"]) == {"Clear", "Rain", "Mud", "Snow/Ice"}

    op = data["operators"][0]
    assert "id" in op
    assert "name" in op
    assert "composite_score" in op
    assert "derived_label" in op

    mach = data["machines"][0]
    assert "id" in mach
    assert "name" in mach
    assert "machine_type" in mach
    assert "wear_factor" in mach


def test_post_simulate_whatif_success(client):
    """Verify POST /simulate/whatif returns valid prediction with uncertainty monotonicity."""
    payload = {
        "operator_id": 1,
        "machine_id": 1,
        "task_type_id": 1,
        "weather": "Rain",
    }
    response = client.post("/simulate/whatif", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "prediction_id" in data
    assert data["operator_id"] == 1
    assert data["weather"] == "Rain"
    assert data["is_synthetic"] is True

    # Check uncertainty bounds: P10 <= Point <= P90
    p10 = data["p10_minutes"]
    point = data["predicted_duration_minutes"]
    p90 = data["p90_minutes"]
    assert p10 <= point, f"Expected p10 ({p10}) <= point ({point})"
    assert point <= p90, f"Expected point ({point}) <= p90 ({p90})"
    assert data["uncertainty_range_minutes"] >= 0.0

    # Check skill and risk metrics
    assert 0.0 <= data["skill_fit_score"] <= 100.0
    assert data["skill_fit_label"] in {"High Match", "Acceptable Match", "Marginal Match", "Skill Deficit"}
    assert 0.0 <= data["safety_risk_score"] <= 100.0
    assert data["safety_risk_level"] in {"low", "moderate", "elevated"}
    assert isinstance(data["training_recommended"], bool)

    # Check explainability factors
    assert len(data["probable_factors"]) > 0
    for factor in data["probable_factors"]:
        assert "factor_name" in factor
        assert "impact_direction" in factor
        assert "impact_percentage" in factor
        assert "confidence" in factor
        assert "probable contributing factor" in factor["description"].lower()


def test_post_simulate_whatif_persists_to_predictions_table(client):
    """Verify simulation is persisted to SQLite predictions table with task_instance_id=None."""
    payload = {
        "operator_id": 2,
        "machine_id": 3,
        "task_type_id": 2,
        "weather": "Clear",
    }
    response = client.post("/simulate/whatif", json=payload)
    assert response.status_code == 200
    pred_id = response.json()["prediction_id"]

    session = SessionLocal()
    try:
        record = session.query(Prediction).filter(Prediction.id == pred_id).first()
        assert record is not None
        assert record.operator_id == 2
        assert record.machine_id == 3
        assert record.task_type_id == 2
        assert record.weather == "Clear"
        # task_instance_id must be None until Phase 7 Process B actual execution
        assert record.task_instance_id is None
        assert record.p10 <= record.predicted_duration <= record.p90
    finally:
        session.close()


def test_post_simulate_whatif_invalid_weather(client):
    """Verify 422 Unprocessable Entity when given an unsupported weather condition."""
    payload = {
        "operator_id": 1,
        "machine_id": 1,
        "task_type_id": 1,
        "weather": "Hurricane",
    }
    response = client.post("/simulate/whatif", json=payload)
    assert response.status_code == 422


def test_post_simulate_whatif_nonexistent_operator(client):
    """Verify 404 Not Found when operator does not exist."""
    payload = {
        "operator_id": 99999,
        "machine_id": 1,
        "task_type_id": 1,
        "weather": "Clear",
    }
    response = client.post("/simulate/whatif", json=payload)
    assert response.status_code == 404


def test_get_prediction_explanation(client):
    """Verify GET /models/explain/{prediction_id} retrieves stored prediction explanation."""
    # First create a prediction
    payload = {
        "operator_id": 3,
        "machine_id": 2,
        "task_type_id": 3,
        "weather": "Mud",
    }
    post_res = client.post("/simulate/whatif", json=payload)
    assert post_res.status_code == 200
    pred_id = post_res.json()["prediction_id"]

    # Now fetch explanation
    get_res = client.get(f"/models/explain/{pred_id}")
    assert get_res.status_code == 200
    data = get_res.json()

    assert data["prediction_id"] == pred_id
    assert "probable_contributing_factors" in data
    assert len(data["probable_contributing_factors"]) > 0
    assert "Probabilistic attribution" in data["note"]
