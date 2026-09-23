"""Integration tests for Anomaly, Coaching, and Training Endpoints (§11, §14, §C)."""

import pytest
from fastapi.testclient import TestClient

from app.db.models import InstructorSlot, Operator, TaskInstance
from app.db.session import SessionLocal
from app.main import app


@pytest.fixture(scope="module")
def client():
    """TestClient fixture with app lifespan startup."""
    with TestClient(app) as c:
        yield c


def test_get_anomalies_endpoint(client):
    """Verify GET /anomalies returns the anomaly feed timeline with non-causal contributing factors."""
    response = client.get("/anomalies?limit=20")
    assert response.status_code == 200
    data = response.json()

    assert "anomalies" in data
    assert "total_count" in data
    assert data["is_synthetic"] is True
    assert isinstance(data["anomalies"], list)

    if data["anomalies"]:
        anomaly = data["anomalies"][0]
        assert "composite_magnitude" in anomaly
        assert "severity" in anomaly
        assert anomaly["severity"] in {"medium", "high", "critical"}
        assert "observed_pattern" in anomaly
        assert "probable_factors" in anomaly
        assert anomaly["is_synthetic"] is True


def test_post_detect_anomaly_endpoint(client):
    """Verify POST /anomalies/detect/{task_id} evaluates task telemetry and returns result."""
    db = SessionLocal()
    task = db.query(TaskInstance).first()
    db.close()
    assert task is not None

    response = client.post(f"/anomalies/detect/{task.id}")
    assert response.status_code == 200
    data = response.json()

    assert data["task_instance_id"] == task.id
    assert "is_anomaly" in data
    assert "composite_magnitude" in data
    assert "probable_factors" in data
    assert data["is_synthetic"] is True

    # 404 for non-existent task
    res_404 = client.post("/anomalies/detect/9999999")
    assert res_404.status_code == 404


def test_get_training_recommendations_endpoint(client):
    """Verify GET /training/recommendations/{operator_id} returns skill-gap recommendations."""
    db = SessionLocal()
    op = db.query(Operator).first()
    db.close()
    assert op is not None

    response = client.get(f"/training/recommendations/{op.id}")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

    for rec in data:
        assert rec["operator_id"] == op.id
        assert "dimension" in rec
        assert "reason" in rec
        assert rec["status"] in {"pending", "in_progress", "completed"}
        assert rec["is_synthetic"] is True
        if rec["elearning_module"]:
            assert "name" in rec["elearning_module"]
            assert "content_url" in rec["elearning_module"]

    # 404 for non-existent operator
    res_404 = client.get("/training/recommendations/9999999")
    assert res_404.status_code == 404


def test_get_elearning_modules_endpoint(client):
    """Verify GET /training/modules returns the 5 seeded CAT training courses."""
    response = client.get("/training/modules")
    assert response.status_code == 200
    modules = response.json()

    assert len(modules) >= 5
    dims = {m["dimension"] for m in modules}
    assert {"cycle_efficiency", "idling", "duration", "load_cycle", "safety"}.issubset(dims)
    for m in modules:
        assert m["duration_minutes"] > 0
        assert m["is_synthetic"] is True


def test_instructor_booking_full_api_workflow(client):
    """Verify full booking lifecycle: query slots -> book -> verify listed in operator bookings."""
    # Use API endpoints instead of direct DB queries to avoid WAL connection isolation
    ops_response = client.get("/operators")
    assert ops_response.status_code == 200
    operators = ops_response.json()
    assert len(operators) > 0
    op_id = operators[0]["id"]

    # Find an open slot via API
    slots_response = client.get("/training/slots?available_only=true")
    assert slots_response.status_code == 200
    slots = slots_response.json()
    assert len(slots) > 0, "Expected at least one available instructor slot"
    slot_id = slots[0]["id"]

    # Book slot
    payload = {
        "operator_id": op_id,
        "instructor_slot_id": slot_id,
        "topic": "Cycle Pacing & Pass Sequencing Coaching",
    }
    response = client.post("/training/bookings", json=payload)
    assert response.status_code == 201
    booking_data = response.json()

    assert booking_data["operator_id"] == op_id
    assert booking_data["instructor_slot_id"] == slot_id
    assert booking_data["status"] == "confirmed"
    assert booking_data["topic"] == "Cycle Pacing & Pass Sequencing Coaching"
    assert booking_data["is_synthetic"] is True

    # Verify queryable under operator bookings
    res_list = client.get(f"/training/bookings/{op_id}")
    assert res_list.status_code == 200
    bookings = res_list.json()
    assert any(b["id"] == booking_data["id"] for b in bookings)


def test_book_instructor_slot_double_booking_and_validation(client):
    """Verify 409 Conflict when attempting to book an already-reserved slot, and 404 on invalid IDs."""
    # Use API endpoints instead of direct DB queries to avoid WAL connection isolation
    ops_response = client.get("/operators")
    assert ops_response.status_code == 200
    operators = ops_response.json()
    assert len(operators) > 0
    op_id = operators[0]["id"]

    # Find an unavailable (already-booked) slot via API
    all_slots_response = client.get("/training/slots?available_only=false")
    assert all_slots_response.status_code == 200
    all_slots = all_slots_response.json()
    booked_slots = [s for s in all_slots if not s["is_available"]]
    assert len(booked_slots) > 0, "Expected at least one booked slot from previous test"
    slot_id = booked_slots[0]["id"]

    # Attempt double-booking
    payload = {
        "operator_id": op_id,
        "instructor_slot_id": slot_id,
        "topic": "Conflict attempt on reserved slot",
    }
    res_conflict = client.post("/training/bookings", json=payload)
    assert res_conflict.status_code == 409
    assert "already reserved" in res_conflict.json()["detail"].lower()

    # 404 for non-existent operator
    bad_op = {"operator_id": 999999, "instructor_slot_id": slot_id, "topic": "Bad op"}
    assert client.post("/training/bookings", json=bad_op).status_code == 404

    # 404 for non-existent slot
    bad_slot = {"operator_id": op_id, "instructor_slot_id": 999999, "topic": "Bad slot"}
    assert client.post("/training/bookings", json=bad_slot).status_code == 404
