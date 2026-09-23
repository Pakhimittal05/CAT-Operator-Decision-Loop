"""Unit tests for Anomaly Detection Engine and Training/Coaching Service (§11, §14)."""

import pytest

from app.anomaly.detector import (
    AnomalyEvaluation,
    detect_task_anomaly,
    evaluate_deviation_anomaly,
)
from app.db.models import IncidentEvent, InstructorSlot, Operator, TaskInstance
from app.db.session import SessionLocal
from app.deviation_engine.deviation import DeviationResult
from app.training.recommendation import (
    SlotAlreadyBookedError,
    book_instructor_slot,
    evaluate_operator_training_needs,
    get_elearning_modules,
    get_instructor_slots,
    seed_default_modules_and_slots,
)


def _make_dummy_deviation(
    d_eff: float = 0.2,
    d_idle: float = -0.1,
    d_dur: float = 0.3,
    d_load: float = 0.1,
    d_safe: float = 0.2,
    comp_mag: float = 0.45,
) -> DeviationResult:
    """Helper to construct synthetic DeviationResult for unit testing."""
    return DeviationResult(
        d_cycle_efficiency=d_eff,
        d_idling=d_idle,
        d_duration=d_dur,
        d_load_cycle=d_load,
        d_safety=d_safe,
        composite_magnitude=comp_mag,
        expected_values={},
        observed_values={},
        z_scores={
            "cycle_efficiency": d_eff,
            "idling": d_idle,
            "duration": d_dur,
            "load_cycle": d_load,
            "safety": d_safe,
        },
    )


def test_anomaly_detection_thresholds():
    """Verify statistical anomaly thresholds (composite >= 2.0 or single |z| >= 2.5) and severity tiers."""
    # 1. Normal variation (magnitude < 2.0 and all |z| < 2.5) -> Not an anomaly
    normal_dev = _make_dummy_deviation(d_eff=0.5, d_idle=0.8, comp_mag=1.1)
    res_normal = evaluate_deviation_anomaly(normal_dev)
    assert res_normal.is_anomaly is False
    assert res_normal.severity is None
    assert "Normal operational variance" in res_normal.observed_pattern

    # 2. Moderate anomaly (composite >= 2.0, < 2.5) -> Medium severity
    med_dev = _make_dummy_deviation(d_idle=2.1, d_dur=1.0, comp_mag=2.15)
    res_med = evaluate_deviation_anomaly(med_dev)
    assert res_med.is_anomaly is True
    assert res_med.severity == "medium"

    # 3. High anomaly (composite >= 2.5 or |z| >= 2.8) -> High severity
    high_dev = _make_dummy_deviation(d_idle=2.9, d_dur=1.5, comp_mag=2.65)
    res_high = evaluate_deviation_anomaly(high_dev)
    assert res_high.is_anomaly is True
    assert res_high.severity == "high"

    # 4. Critical anomaly (composite >= 3.0 or |z| >= 3.5) -> Critical severity
    crit_dev = _make_dummy_deviation(d_idle=3.6, d_dur=2.0, comp_mag=3.2)
    res_crit = evaluate_deviation_anomaly(crit_dev)
    assert res_crit.is_anomaly is True
    assert res_crit.severity == "critical"


def test_probable_contributing_factors_non_causal_phrasing():
    """Verify ranking by |z|, percentage contribution math, and strict non-causal language."""
    # Deviation where idling has the largest absolute z-score
    dev = _make_dummy_deviation(
        d_eff=-1.2,
        d_idle=3.0,
        d_dur=1.8,
        d_load=0.5,
        d_safe=-0.8,
        comp_mag=2.85,
    )
    res = evaluate_deviation_anomaly(dev)
    assert res.is_anomaly is True
    assert len(res.probable_factors) == 5

    # Top factor must be idling
    top_factor = res.probable_factors[0]
    assert top_factor.dimension == "idling"
    assert top_factor.z_score == 3.0

    # Weights must sum to approximately 100%
    total_pct = sum(f.contribution_weight_pct for f in res.probable_factors)
    assert 99.0 <= total_pct <= 101.0

    # Strict non-causal language verification:
    forbidden_terms = ["caused by", "causes", "proves", "responsible for", "operator fault"]
    for factor in res.probable_factors:
        desc_lower = factor.description.lower()
        for forbidden in forbidden_terms:
            assert forbidden not in desc_lower, f"Forbidden causal phrase '{forbidden}' found in description"

    # Must contain required non-causal descriptors
    assert "observed during this task" in top_factor.description
    assert "Observed Pattern" in res.observed_pattern
    assert "Probable Contributing Factors" in res.observed_pattern


def test_anomaly_persists_incident_event():
    """Verify that detect_task_anomaly persists an IncidentEvent with source='deviation_anomaly'."""
    db = SessionLocal()
    try:
        task = db.query(TaskInstance).first()
        assert task is not None, "Expected historical tasks to exist"

        # Force high idle seconds to ensure anomaly trigger
        original_idle = task.idle_seconds
        task.idle_seconds = 2400.0  # 40 minutes idle -> extreme deviation
        db.commit()

        is_anomaly, inc, eval_res = detect_task_anomaly(db, task, auto_commit=True)
        assert is_anomaly is True
        assert inc is not None
        assert inc.source == "deviation_anomaly"
        assert inc.severity in {"medium", "high", "critical"}
        assert inc.task_instance_id == task.id
        assert inc.operator_id == task.operator_id
        assert "Observed Pattern" in inc.description

        # Clean up modified idle seconds
        task.idle_seconds = original_idle
        db.commit()
    finally:
        db.close()


def test_anomaly_incident_deduplication():
    """Verify running anomaly detection on the same task multiple times does not duplicate incidents."""
    db = SessionLocal()
    try:
        task = db.query(TaskInstance).first()
        assert task is not None

        # First run
        _, inc1, _ = detect_task_anomaly(db, task, auto_commit=True)
        assert inc1 is not None

        # Second run on same task
        _, inc2, _ = detect_task_anomaly(db, task, auto_commit=True)
        assert inc2 is not None
        assert inc1.id == inc2.id

        # Verify count in database
        dup_count = (
            db.query(IncidentEvent)
            .filter(
                IncidentEvent.task_instance_id == task.id,
                IncidentEvent.source == "deviation_anomaly",
            )
            .count()
        )
        assert dup_count == 1
    finally:
        db.close()


def test_dimension_to_elearning_mapping():
    """Verify all 5 deviation dimensions map to designated CAT E-Learning modules."""
    db = SessionLocal()
    try:
        seed_default_modules_and_slots(db)
        modules = get_elearning_modules(db)
        assert len(modules) >= 5

        dimensions_present = {m.dimension for m in modules}
        expected_dimensions = {"cycle_efficiency", "idling", "duration", "load_cycle", "safety"}
        assert expected_dimensions.issubset(dimensions_present)

        for m in modules:
            assert m.duration_minutes > 0
            assert m.content_url.startswith("https://")
            assert len(m.description) > 10
            assert m.is_synthetic is True
    finally:
        db.close()


def test_instructor_booking_state_transition_and_concurrency():
    """Verify slot reservation sets is_available=False, creates confirmed booking, and prevents double-booking."""
    db = SessionLocal()
    try:
        seed_default_modules_and_slots(db)
        op = db.query(Operator).first()
        assert op is not None

        # Find an available slot
        slot = db.query(InstructorSlot).filter(InstructorSlot.is_available == True).first()  # noqa: E712
        assert slot is not None

        # Reserve slot
        booking = book_instructor_slot(
            db=db,
            operator_id=op.id,
            slot_id=slot.id,
            topic="Hydraulic Pressure Modulation Coaching",
        )
        assert booking.id is not None
        assert booking.operator_id == op.id
        assert booking.status == "confirmed"

        # Verify slot is no longer available
        db.refresh(slot)
        assert slot.is_available is False

        # Attempt to double-book must raise SlotAlreadyBookedError
        with pytest.raises(SlotAlreadyBookedError) as exc_info:
            book_instructor_slot(
                db=db,
                operator_id=op.id,
                slot_id=slot.id,
                topic="Second attempt on reserved slot",
            )
        assert "already reserved" in str(exc_info.value)
    finally:
        db.close()
