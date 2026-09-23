"""Integration tests for Unified Incident Events and Safety Endpoints (§C, §13, §B)."""

import pytest
from fastapi.testclient import TestClient

from app.db.models import IncidentEvent, Operator, TaskInstance
from app.db.session import SessionLocal
from app.main import app


@pytest.fixture(scope="module")
def client():
    """TestClient fixture with app lifespan startup (triggers historical incident sync)."""
    with TestClient(app) as c:
        yield c


def test_get_incidents_list(client):
    """Verify GET /incidents returns unified incident timeline with proper schema."""
    response = client.get("/incidents?limit=20")
    assert response.status_code == 200
    data = response.json()

    assert "incidents" in data
    assert "total_count" in data
    assert data["is_synthetic"] is True
    assert data["total_count"] > 0
    assert len(data["incidents"]) > 0

    inc = data["incidents"][0]
    assert "id" in inc
    assert "operator_id" in inc
    assert "operator_name" in inc
    assert "source" in inc
    assert inc["source"] in {"seatbelt", "proximity", "deviation_anomaly", "manual"}
    assert "severity" in inc
    assert inc["severity"] in {"low", "medium", "high", "critical"}
    assert "created_at" in inc
    assert inc["is_synthetic"] is True


def test_get_incidents_source_and_severity_filters(client):
    """Verify filtering by incident source and severity."""
    # Source filter: seatbelt
    res_seatbelt = client.get("/incidents?source=seatbelt&limit=10")
    assert res_seatbelt.status_code == 200
    sb_data = res_seatbelt.json()
    for inc in sb_data["incidents"]:
        assert inc["source"] == "seatbelt"

    # Source filter: proximity
    res_prox = client.get("/incidents?source=proximity&limit=10")
    assert res_prox.status_code == 200
    px_data = res_prox.json()
    for inc in px_data["incidents"]:
        assert inc["source"] == "proximity"

    # Severity filter: critical or high
    res_high = client.get("/incidents?severity=high&limit=10")
    assert res_high.status_code == 200
    hi_data = res_high.json()
    for inc in hi_data["incidents"]:
        assert inc["severity"] == "high"


def test_post_manual_incident_success(client):
    """Verify POST /incidents creates a manual incident and persists in database."""
    payload = {
        "operator_id": 1,
        "machine_id": 1,
        "source": "manual",
        "severity": "high",
        "description": "Supervisor observation: Operator dismounted cab while engine was running.",
    }
    response = client.post("/incidents", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert data["operator_id"] == 1
    assert data["source"] == "manual"
    assert data["severity"] == "high"
    assert "dismounted cab" in data["description"]
    assert data["is_synthetic"] is True

    # Verify queryable via source filter
    list_res = client.get("/incidents?source=manual")
    assert list_res.status_code == 200
    manual_incidents = list_res.json()["incidents"]
    assert any(m["id"] == data["id"] for m in manual_incidents)


def test_post_manual_incident_validation_and_errors(client):
    """Verify 404 for missing entities and 422 for invalid payloads."""
    # Non-existent operator
    payload_bad_op = {
        "operator_id": 999999,
        "source": "manual",
        "severity": "medium",
        "description": "Invalid operator test description",
    }
    res_bad_op = client.post("/incidents", json=payload_bad_op)
    assert res_bad_op.status_code == 404

    # Invalid severity
    payload_bad_sev = {
        "operator_id": 1,
        "source": "manual",
        "severity": "catastrophic_extreme",
        "description": "Invalid severity test description",
    }
    res_bad_sev = client.post("/incidents", json=payload_bad_sev)
    assert res_bad_sev.status_code == 422


def test_get_incident_statistics(client):
    """Verify GET /incidents/stats aggregates totals, severity breakdown, and source breakdown."""
    response = client.get("/incidents/stats")
    assert response.status_code == 200
    stats = response.json()

    assert "total_incidents" in stats
    assert stats["total_incidents"] > 0
    assert "by_severity" in stats
    assert "by_source" in stats
    assert stats["is_synthetic"] is True

    assert "critical" in stats["by_severity"]
    assert "high" in stats["by_severity"]
    assert "medium" in stats["by_severity"]
    assert "low" in stats["by_severity"]

    assert "seatbelt" in stats["by_source"]
    assert "proximity" in stats["by_source"]
    assert "manual" in stats["by_source"]


def test_safety_evaluate_task_endpoint(client):
    """Verify POST /safety/evaluate-task/{task_id} evaluates telemetry and returns result."""
    # Find a task with known breach from database
    db = SessionLocal()
    task = db.query(TaskInstance).filter(TaskInstance.seatbelt_engaged == False).first()  # noqa: E712
    db.close()
    assert task is not None

    response = client.post(f"/safety/evaluate-task/{task.id}")
    assert response.status_code == 200
    data = response.json()

    assert data["task_instance_id"] == task.id
    assert data["seatbelt_ok"] is False
    assert "violations_count" in data
    assert "incidents" in data
    assert data["is_synthetic"] is True

    # 404 for non-existent task
    res_404 = client.post("/safety/evaluate-task/9999999")
    assert res_404.status_code == 404
