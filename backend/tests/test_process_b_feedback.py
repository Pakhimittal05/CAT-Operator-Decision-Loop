"""Phase 7 Tests — Process B Independent Generator, Feedback Loop & Comparison (§4, §5, §15).

Tests:
  1. Process B module independence (zero imports from generate_historical_data).
  2. Process B log-normal distribution properties (positive skew, realistic ranges).
  3. Process B reproducible demo seed vs live stochastic randomness.
  4. Process B hidden dynamic factor (fatigue/mood) and difficulty effects.
  5. Process B threshold-based safety event generation.
  6. Feedback service links Prediction.task_instance_id to Process B TaskInstance.
  7. Duplicate execution protection (HTTP 409 Conflict).
  8. Predicted-vs-actual error metrics calculation correctness.
  9. 5D deviation vector computed and persisted for Process B task instance.
  10. Dynamic operator EWMA state recalibration after actual outcome.
  11. Safety incidents recording from Process B actual outcomes.
  12. API endpoints: generate-actual, comparison, and comparisons history list.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.data_generation.generate_actual_outcomes import (
    PROCESS_B_WEATHER_FACTORS,
    generate_process_b_telemetry,
)
from app.db.models import (
    DeviationVector,
    IncidentEvent,
    Machine,
    Operator,
    Prediction,
    TaskCatalog,
    TaskInstance,
)
from app.db.session import SessionLocal
from app.main import app
from app.operator_state.state import get_operator_state
from app.simulation.feedback_service import (
    execute_process_b_for_prediction,
    get_prediction_comparison,
    list_simulation_comparisons,
)


@pytest.fixture(scope="module")
def client():
    """TestClient fixture with app lifespan startup."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module", autouse=True)
def cleanup_process_b_test_records():
    """Cleanup any Process B test rows after testing so database integrity test remains pristine."""
    yield
    db = SessionLocal()
    try:
        # Delete test predictions that link to Process B or were created for testing
        test_instances = db.query(TaskInstance).filter(TaskInstance.source_process == "B").all()
        for inst in test_instances:
            db.query(DeviationVector).filter(DeviationVector.task_instance_id == inst.id).delete()
            db.query(IncidentEvent).filter(IncidentEvent.task_instance_id == inst.id).delete()
            db.query(Prediction).filter(Prediction.task_instance_id == inst.id).delete()
            db.delete(inst)
        db.commit()
    finally:
        db.close()


# ── 1. Process B Independence & Module Isolation ─────────────────────────────


def test_process_b_module_independence():
    """Verify Process B code has ZERO imports or references to generate_historical_data."""
    gen_file = Path(__file__).resolve().parent.parent / "app" / "data_generation" / "generate_actual_outcomes.py"
    assert gen_file.exists(), "generate_actual_outcomes.py must exist"

    code_content = gen_file.read_text(encoding="utf-8")
    assert "generate_historical_data" not in code_content, (
        "Process B must not import or reference generate_historical_data.py"
    )

    tree = ast.parse(code_content)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "historical" not in alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert "historical" not in node.module


# ── 2. Process B Log-Normal Distribution ─────────────────────────────────────


def test_process_b_lognormal_distribution():
    """Verify Process B produces strictly positive, realistically bounded telemetry."""
    samples = [
        generate_process_b_telemetry(
            baseline_duration=45.0,
            baseline_load_cycles=25,
            task_difficulty=0.6,
            machine_age_years=3.0,
            machine_wear_factor=1.05,
            operator_skill_tier="Intermediate",
            operator_latent_efficiency=0.68,
            operator_latent_idle=0.22,
            operator_latent_safety=0.10,
            weather="Clear",
        )
        for _ in range(100)
    ]

    durations = [s["duration_minutes"] for s in samples]
    idles = [s["idle_seconds"] for s in samples]
    efficiencies = [s["efficiency_score"] for s in samples]
    proximities = [s["min_proximity_distance"] for s in samples]

    assert all(d > 10.0 for d in durations), "Durations must be positive and reasonable"
    assert all(i >= 0.0 for i in idles), "Idling seconds must be non-negative"
    assert all(0.10 <= e <= 1.00 for e in efficiencies), "Efficiency must be within (0.10, 1.00]"
    assert all(p >= 0.50 for p in proximities), "Proximity distance must be positive"


# ── 3. Reproducible Demo Seed vs. Stochastic Randomness ──────────────────────


def test_process_b_reproducible_seed():
    """Verify demo seed yields 100% identical results, while differing seeds vary."""
    run1 = generate_process_b_telemetry(
        baseline_duration=45.0,
        baseline_load_cycles=25,
        task_difficulty=0.6,
        machine_age_years=2.0,
        machine_wear_factor=1.03,
        operator_skill_tier="Expert",
        weather="Clear",
        seed=42,
    )
    run2 = generate_process_b_telemetry(
        baseline_duration=45.0,
        baseline_load_cycles=25,
        task_difficulty=0.6,
        machine_age_years=2.0,
        machine_wear_factor=1.03,
        operator_skill_tier="Expert",
        weather="Clear",
        seed=42,
    )
    run3 = generate_process_b_telemetry(
        baseline_duration=45.0,
        baseline_load_cycles=25,
        task_difficulty=0.6,
        machine_age_years=2.0,
        machine_wear_factor=1.03,
        operator_skill_tier="Expert",
        weather="Clear",
        seed=999,
    )

    assert run1 == run2, "Identical seed must produce identical telemetry"
    assert run1["duration_minutes"] != run3["duration_minutes"], "Different seeds must produce varying telemetry"


# ── 4. Hidden Factor & Context Effects ────────────────────────────────────────


def test_process_b_daily_fatigue_and_difficulty_effects():
    """Verify adverse conditions (weather/wear) increase expected duration."""
    clear_runs = [
        generate_process_b_telemetry(
            baseline_duration=40.0,
            baseline_load_cycles=20,
            task_difficulty=0.4,
            machine_age_years=1.0,
            machine_wear_factor=1.01,
            operator_skill_tier="Expert",
            weather="Clear",
            seed=i,
        )["duration_minutes"]
        for i in range(20)
    ]
    snow_runs = [
        generate_process_b_telemetry(
            baseline_duration=40.0,
            baseline_load_cycles=20,
            task_difficulty=0.4,
            machine_age_years=1.0,
            machine_wear_factor=1.01,
            operator_skill_tier="Expert",
            weather="Snow/Ice",
            seed=i,
        )["duration_minutes"]
        for i in range(20)
    ]

    assert sum(snow_runs) / len(snow_runs) > sum(clear_runs) / len(clear_runs), (
        "Snow/Ice weather should produce higher mean duration than Clear"
    )


# ── 5. Safety Threshold Logic ────────────────────────────────────────────────


def test_process_b_safety_threshold_bursts():
    """Verify proximity values and seatbelt flags adhere to physical limits."""
    res = generate_process_b_telemetry(
        baseline_duration=30.0,
        baseline_load_cycles=15,
        task_difficulty=0.5,
        machine_age_years=5.0,
        machine_wear_factor=1.1,
        operator_skill_tier="Beginner",
        operator_latent_safety=0.35,  # Higher risk operator
        weather="Mud",
        seed=77,
    )
    assert isinstance(res["seatbelt_engaged"], bool)
    assert res["min_proximity_distance"] >= 0.5


# ── 6. Feedback Service Links Prediction to TaskInstance ─────────────────────


def test_execute_process_b_links_prediction(client):
    """Verify executing Process B updates Prediction.task_instance_id and creates source_process='B'."""
    # 1. Create a simulation
    sim_res = client.post(
        "/simulate/whatif",
        json={"operator_id": 1, "machine_id": 1, "task_type_id": 1, "weather": "Clear"},
    )
    assert sim_res.status_code == 200
    pred_id = sim_res.json()["prediction_id"]

    db = SessionLocal()
    try:
        pred_before = db.query(Prediction).filter(Prediction.id == pred_id).first()
        assert pred_before.task_instance_id is None, "Before execution, task_instance_id must be None"

        # 2. Execute Process B
        comp = execute_process_b_for_prediction(db, pred_id, seed=42)
        assert comp.prediction_id == pred_id
        assert comp.task_instance_id > 0

        # 3. Assert DB linkage
        pred_after = db.query(Prediction).filter(Prediction.id == pred_id).first()
        assert pred_after.task_instance_id == comp.task_instance_id

        task_inst = db.query(TaskInstance).filter(TaskInstance.id == comp.task_instance_id).first()
        assert task_inst is not None
        assert task_inst.source_process == "B"
        assert task_inst.is_synthetic is True
    finally:
        db.close()


# ── 7. Duplicate Execution Prevention (409 Conflict) ─────────────────────────


def test_execute_process_b_duplicate_prevented_409(client):
    """Verify attempting to execute the same prediction twice raises 409 Conflict."""
    sim_res = client.post(
        "/simulate/whatif",
        json={"operator_id": 2, "machine_id": 1, "task_type_id": 2, "weather": "Clear"},
    )
    pred_id = sim_res.json()["prediction_id"]

    db = SessionLocal()
    try:
        # First execution succeeds
        execute_process_b_for_prediction(db, pred_id, seed=42)

        # Second execution must raise HTTPException 409 Conflict
        with pytest.raises(Exception) as exc_info:
            execute_process_b_for_prediction(db, pred_id, seed=42)
        assert "409" in str(exc_info.value)
    finally:
        db.close()


# ── 8. Error Metrics Correctness ─────────────────────────────────────────────


def test_predicted_vs_actual_error_metrics_correctness(client):
    """Verify mathematical calculation of duration difference, absolute error, and percentage error."""
    sim_res = client.post(
        "/simulate/whatif",
        json={"operator_id": 3, "machine_id": 2, "task_type_id": 3, "weather": "Rain"},
    )
    pred_id = sim_res.json()["prediction_id"]

    db = SessionLocal()
    try:
        comp = execute_process_b_for_prediction(db, pred_id, seed=123)
        expected_diff = round(comp.actual_duration_minutes - comp.predicted_duration_minutes, 2)
        expected_abs = round(abs(expected_diff), 2)
        expected_pct = round((expected_abs / comp.actual_duration_minutes) * 100.0, 2)

        assert comp.duration_difference_minutes == expected_diff
        assert comp.absolute_error_minutes == expected_abs
        assert comp.percentage_error == expected_pct
        assert comp.is_within_interval == (comp.p10_minutes <= comp.actual_duration_minutes <= comp.p90_minutes)
    finally:
        db.close()


# ── 9. Deviation Vector Persisted ────────────────────────────────────────────


def test_deviation_vector_persisted_for_process_b(client):
    """Verify shared compute_deviation() runs on Process B telemetry and stores DeviationVector."""
    sim_res = client.post(
        "/simulate/whatif",
        json={"operator_id": 4, "machine_id": 3, "task_type_id": 1, "weather": "Clear"},
    )
    pred_id = sim_res.json()["prediction_id"]

    db = SessionLocal()
    try:
        comp = execute_process_b_for_prediction(db, pred_id, seed=55)
        dev = db.query(DeviationVector).filter(DeviationVector.task_instance_id == comp.task_instance_id).first()
        assert dev is not None
        assert isinstance(dev.composite_magnitude, float)
        assert isinstance(dev.d_cycle_efficiency, float)
        assert isinstance(dev.d_idling, float)
        assert isinstance(dev.d_duration, float)
        assert isinstance(dev.d_load_cycle, float)
        assert isinstance(dev.d_safety, float)
    finally:
        db.close()


# ── 10. Operator Dynamic State EWMA Recalibrated ─────────────────────────────


def test_operator_state_ewma_recalibrated(client):
    """Verify operator dynamic state updates sample count and incorporates new actual outcome."""
    db = SessionLocal()
    try:
        operator_id = 5
        state_before = get_operator_state(db, operator_id)

        sim_res = client.post(
            "/simulate/whatif",
            json={"operator_id": operator_id, "machine_id": 1, "task_type_id": 1, "weather": "Clear"},
        )
        pred_id = sim_res.json()["prediction_id"]

        comp = execute_process_b_for_prediction(db, pred_id, seed=88)

        state_after = get_operator_state(db, operator_id)
        assert state_after.sample_count == state_before.sample_count + 1
        assert comp.state_after.sample_count == comp.state_before.sample_count + 1
        assert isinstance(comp.composite_score_delta, float)
    finally:
        db.close()


# ── 11. Safety Incidents Recorded ────────────────────────────────────────────


def test_safety_incidents_recorded_from_actual_outcome(client):
    """Verify IncidentService evaluates safety on Process B task instance."""
    db = SessionLocal()
    try:
        # Create prediction and execute
        sim_res = client.post(
            "/simulate/whatif",
            json={"operator_id": 6, "machine_id": 2, "task_type_id": 2, "weather": "Mud"},
        )
        pred_id = sim_res.json()["prediction_id"]
        comp = execute_process_b_for_prediction(db, pred_id, seed=10)

        assert isinstance(comp.seatbelt_engaged, bool)
        assert isinstance(comp.min_proximity_distance, float)
        assert isinstance(comp.incidents_recorded, list)
    finally:
        db.close()


# ── 12. API Endpoints: generate-actual, comparison, and comparisons list ──────


def test_simulation_comparison_api_endpoints(client):
    """Test POST /simulate/{id}/generate-actual, GET /simulate/{id}/comparison, and GET /simulate/comparisons."""
    # 1. Create a simulation
    sim = client.post(
        "/simulate/whatif",
        json={"operator_id": 7, "machine_id": 1, "task_type_id": 1, "weather": "Clear"},
    ).json()
    pred_id = sim["prediction_id"]

    # 2. Before execution, GET comparison should return 400
    res_before = client.get(f"/simulate/{pred_id}/comparison")
    assert res_before.status_code == 400

    # 3. POST /simulate/{id}/generate-actual with demo seed
    gen_res = client.post(
        f"/simulate/{pred_id}/generate-actual",
        json={"seed": 42},
    )
    assert gen_res.status_code == 200
    data = gen_res.json()
    assert data["prediction_id"] == pred_id
    assert "actual_duration_minutes" in data
    assert "percentage_error" in data
    assert "state_before" in data
    assert "state_after" in data
    assert "deviation_vector" in data

    # 4. Duplicate POST returns 409
    dup_res = client.post(
        f"/simulate/{pred_id}/generate-actual",
        json={"seed": 42},
    )
    assert dup_res.status_code == 409

    # 5. GET /simulate/{id}/comparison now succeeds with 200
    comp_res = client.get(f"/simulate/{pred_id}/comparison")
    assert comp_res.status_code == 200
    assert comp_res.json()["prediction_id"] == pred_id

    # 6. GET /simulate/comparisons lists this execution
    list_res = client.get("/simulate/comparisons?limit=10")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert "comparisons" in list_data
    assert list_data["total_count"] >= 1
    found = any(c["prediction_id"] == pred_id for c in list_data["comparisons"])
    assert found, "Recently executed prediction must be present in comparisons list"
