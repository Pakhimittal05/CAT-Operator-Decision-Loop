"""Unit tests for deterministic Seatbelt, Proximity, and Incident rules (§13)."""

import pytest
from app.db.models import Machine, Operator, TaskCatalog, TaskInstance
from app.db.session import SessionLocal
from app.safety.incident_service import IncidentService
from app.safety.proximity import (
    MACHINE_PROXIMITY_BUFFERS,
    evaluate_proximity_hazard,
    get_safe_distance_for_machine,
)
from app.safety.seatbelt import (
    evaluate_seatbelt_compliance,
    evaluate_seatbelt_unlatched_duration,
)


def test_seatbelt_detector_compliance_and_threshold_boundaries():
    """Verify that engaged seatbelt or operating time below/equal to threshold returns no violation."""
    # Engaged seatbelt -> None
    result = evaluate_seatbelt_compliance(
        seatbelt_engaged=True,
        duration_minutes=45.0,
        idle_seconds=120.0,
    )
    assert result is None

    # Active operating seconds = 0.05 * 60 - 0 = 3.0s (<= 5.0s threshold) -> None
    result_under_thresh = evaluate_seatbelt_compliance(
        seatbelt_engaged=False,
        duration_minutes=0.05,
        idle_seconds=0.0,
        threshold_seconds=5.0,
    )
    assert result_under_thresh is None

    # Direct motion seconds detector boundary check
    assert evaluate_seatbelt_unlatched_duration(False, 4.0, threshold_seconds=5.0) is None
    res_direct = evaluate_seatbelt_unlatched_duration(False, 10.0, threshold_seconds=5.0)
    assert res_direct is not None
    assert res_direct.is_violation is True


def test_seatbelt_detector_unlatched_in_motion():
    """Verify that unlatched seatbelt with active operating time triggers violation with severity."""
    # Active operating seconds = 30 * 60 - 60 = 1740s (> 600s -> high)
    result = evaluate_seatbelt_compliance(
        seatbelt_engaged=False,
        duration_minutes=30.0,
        idle_seconds=60.0,
        threshold_seconds=5.0,
    )
    assert result is not None
    assert result.is_violation is True
    assert result.severity == "high"
    assert result.threshold_seconds == 5.0
    assert result.operating_seconds == 1740.0
    assert "threshold proxy" in result.description
    assert result.is_synthetic is True

    # Moderate duration (90s active operating -> medium)
    result_med = evaluate_seatbelt_compliance(
        seatbelt_engaged=False,
        duration_minutes=2.0,
        idle_seconds=30.0,
    )
    assert result_med is not None
    assert result_med.severity == "medium"


def test_proximity_detector_safe_distance():
    """Verify distance above safe buffer produces no hazard."""
    assert evaluate_proximity_hazard(8.0, machine_type="Crane") is None
    assert evaluate_proximity_hazard(6.5, machine_type="Excavator") is None
    assert evaluate_proximity_hazard(5.5, machine_type="Dump Truck") is None


def test_proximity_machine_specific_thresholds():
    """Verify machine-specific safety buffers (e.g. Crane 7.0m vs Excavator 6.0m)."""
    assert get_safe_distance_for_machine("Crane") == 7.0
    assert get_safe_distance_for_machine("Excavator") == 6.0
    assert get_safe_distance_for_machine("Bulldozer") == 5.5
    assert get_safe_distance_for_machine("Dump Truck") == 5.0

    # 6.5m is safe for an Excavator (buffer 6.0m), but a hazard for a Crane (buffer 7.0m)
    assert evaluate_proximity_hazard(6.5, machine_type="Excavator") is None
    crane_hazard = evaluate_proximity_hazard(6.5, machine_type="Crane")
    assert crane_hazard is not None
    assert crane_hazard.is_violation is True
    assert crane_hazard.safe_distance_threshold == 7.0


def test_proximity_severity_tiers():
    """Verify proximity severity tiers: critical (<1.5m), high (<3.0m), medium (>=3.0m)."""
    crit = evaluate_proximity_hazard(1.2, machine_type="Bulldozer")
    assert crit is not None
    assert crit.severity == "critical"
    assert "Critical collision hazard" in crit.description

    high = evaluate_proximity_hazard(2.4, machine_type="Bulldozer")
    assert high is not None
    assert high.severity == "high"
    assert "Severe proximity zone breach" in high.description

    med = evaluate_proximity_hazard(4.2, machine_type="Bulldozer")
    assert med is not None
    assert med.severity == "medium"
    assert "Safety buffer margin breach" in med.description


def test_incident_service_deduplication():
    """Verify incident evaluation deduplicates on repeated runs for the same task."""
    db = SessionLocal()
    try:
        # Find a task with unengaged seatbelt or proximity hazard
        task = db.query(TaskInstance).filter(TaskInstance.seatbelt_engaged == False).first()  # noqa: E712
        assert task is not None, "Expected historical tasks to exist"

        # Evaluate once
        first_run = IncidentService.evaluate_task_instance(db, task, auto_commit=True)
        count_first = len(first_run)
        assert count_first >= 1

        first_id = first_run[0].id

        # Evaluate second time — must return the existing record and not create a duplicate
        second_run = IncidentService.evaluate_task_instance(db, task, auto_commit=True)
        assert len(second_run) == count_first
        assert second_run[0].id == first_id
    finally:
        db.close()
