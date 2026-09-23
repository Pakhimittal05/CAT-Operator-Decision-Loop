"""Unit tests for Task-Time Prediction, Uncertainty Bounds, and Risk Models (§10, §12, §24)."""

import pytest
from app.prediction.risk_model import (
    calculate_safety_risk,
    calculate_skill_fit,
    evaluate_training_need,
)
from app.prediction.task_time_model import (
    PredictionResult,
    load_task_time_artifacts,
    predict_task_time,
)


@pytest.fixture(scope="module")
def task_time_artifacts():
    """Load cached task-time models once for tests."""
    return load_task_time_artifacts()


def test_task_time_artifacts_exist_and_load(task_time_artifacts):
    """Verify task-time model artifacts contain required models, preprocessors, and metrics."""
    assert "point_model" in task_time_artifacts
    assert "p10_model" in task_time_artifacts
    assert "p90_model" in task_time_artifacts
    assert "metrics" in task_time_artifacts
    metrics = task_time_artifacts["metrics"]
    assert metrics["mae"] < 8.0  # MAE should be low on synthetic baselines
    assert metrics["interval_coverage"] > 0.60  # P10-P90 coverage reasonable


def test_p10_point_p90_monotonicity_constraint(task_time_artifacts):
    """CRITICAL CONSTRAINT TEST: P10 <= Point <= P90 must ALWAYS hold across all test scenarios."""
    scenarios = [
        # Standard scenario
        {
            "operator_composite_score": 50.0,
            "operator_duration_score": 50.0,
            "operator_efficiency_score": 50.0,
            "operator_confidence": 0.8,
            "baseline_duration_minutes": 35.0,
            "task_difficulty": 0.5,
            "machine_age_years": 3.0,
            "machine_wear_factor": 0.25,
            "task_type": "Hauling",
            "machine_type": "Hauler",
            "weather": "Clear",
        },
        # High skill operator in clear weather
        {
            "operator_composite_score": 90.0,
            "operator_duration_score": 88.0,
            "operator_efficiency_score": 92.0,
            "operator_confidence": 0.95,
            "baseline_duration_minutes": 50.0,
            "task_difficulty": 0.8,
            "machine_age_years": 1.0,
            "machine_wear_factor": 0.05,
            "task_type": "Excavation",
            "machine_type": "Excavator",
            "weather": "Clear",
        },
        # Low skill operator in severe weather with worn machine
        {
            "operator_composite_score": 25.0,
            "operator_duration_score": 20.0,
            "operator_efficiency_score": 30.0,
            "operator_confidence": 0.4,
            "baseline_duration_minutes": 25.0,
            "task_difficulty": 0.9,
            "machine_age_years": 8.0,
            "machine_wear_factor": 0.85,
            "task_type": "Trenching",
            "machine_type": "Dozer",
            "weather": "Snow/Ice",
        },
        # Edge scenario: Mud with wheel loader
        {
            "operator_composite_score": 60.0,
            "operator_duration_score": 55.0,
            "operator_efficiency_score": 65.0,
            "operator_confidence": 0.7,
            "baseline_duration_minutes": 20.0,
            "task_difficulty": 0.3,
            "machine_age_years": 4.5,
            "machine_wear_factor": 0.4,
            "task_type": "Loading",
            "machine_type": "Wheel Loader",
            "weather": "Mud",
        },
    ]

    for scenario in scenarios:
        res: PredictionResult = predict_task_time(scenario, artifacts=task_time_artifacts)
        # Assert strict monotonicity
        assert res.p10 <= res.predicted_duration, (
            f"Violation: P10 ({res.p10}) > Point ({res.predicted_duration}) for {scenario}"
        )
        assert res.predicted_duration <= res.p90, (
            f"Violation: Point ({res.predicted_duration}) > P90 ({res.p90}) for {scenario}"
        )
        assert res.uncertainty_range >= 0.0
        assert res.predicted_duration > 0.0


def test_probable_contributing_factors_non_causal_language(task_time_artifacts):
    """Verify explainability strictly uses 'Probable Contributing Factors' and no causal words."""
    scenario = {
        "operator_composite_score": 35.0,
        "operator_duration_score": 30.0,
        "operator_efficiency_score": 40.0,
        "operator_confidence": 0.8,
        "baseline_duration_minutes": 45.0,
        "task_difficulty": 0.75,
        "machine_age_years": 6.0,
        "machine_wear_factor": 0.7,
        "task_type": "Excavation",
        "machine_type": "Excavator",
        "weather": "Rain",
    }
    res = predict_task_time(scenario, artifacts=task_time_artifacts)
    assert len(res.probable_factors) > 0

    for factor in res.probable_factors:
        assert "factor_name" in factor
        assert factor["impact_direction"] in {"increases_duration", "decreases_duration"}
        assert 0.0 <= factor["impact_percentage"] <= 100.0
        assert 50.0 <= factor["confidence"] <= 100.0

        desc = factor["description"].lower()
        # Verify mandatory probabilistic phrasing
        assert "probable contributing factor" in desc
        # Strictly forbid causal dogmatism
        assert "caused by" not in desc
        assert "causes" not in desc
        assert "proves" not in desc


def test_skill_fit_calculation():
    """Verify skill fit appropriately rewards competence and scales with difficulty."""
    # High skill on high difficulty task
    fit_high, label_high = calculate_skill_fit(operator_task_score=85.0, task_difficulty=0.8)
    # Low skill on high difficulty task
    fit_low, label_low = calculate_skill_fit(operator_task_score=35.0, task_difficulty=0.8)

    assert fit_high > fit_low
    assert fit_high >= 70.0
    assert fit_low <= 45.0
    assert label_low in {"Skill Deficit", "Marginal Match"}


def test_safety_risk_calculation():
    """Verify safety risk escalates under adverse weather and worn machines."""
    # Safe operator in clear weather with new machine
    risk_safe, level_safe = calculate_safety_risk(
        operator_safety_score=85.0, machine_wear=0.1, task_difficulty=0.3, weather="Clear"
    )
    # Low safety score operator in snowy weather with worn machine
    risk_haz, level_haz = calculate_safety_risk(
        operator_safety_score=25.0, machine_wear=0.8, task_difficulty=0.8, weather="Snow/Ice"
    )

    assert risk_haz > risk_safe
    assert level_safe == "low"
    assert level_haz in {"moderate", "elevated"}


def test_training_recommendation_trigger():
    """Verify training flag triggers on low skill fit or elevated safety risk."""
    rec1, reason1 = evaluate_training_need(skill_fit=40.0, safety_risk=30.0)
    assert rec1 is True
    assert reason1 is not None

    rec2, reason2 = evaluate_training_need(skill_fit=80.0, safety_risk=75.0)
    assert rec2 is True
    assert reason2 is not None

    rec3, reason3 = evaluate_training_need(skill_fit=78.0, safety_risk=25.0)
    assert rec3 is False
    assert reason3 is None
