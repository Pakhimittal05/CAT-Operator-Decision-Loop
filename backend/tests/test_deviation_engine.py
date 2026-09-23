"""Tests for Phase 2: Deviation Engine and Reference Models."""

import math
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pytest
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db.session import get_engine
from app.deviation_engine.deviation import (
    DeviationResult,
    compute_deviation,
    load_reference_artifacts,
)
from app.deviation_engine.reference_model import (
    DIMENSION_MAPPINGS,
    FEATURE_COLUMNS,
    load_training_data,
)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Known-Input Test with Manually Calculated Expected Z-Scores
# ═══════════════════════════════════════════════════════════════════════════

class FixedValueModel:
    """Mock model that returns a predetermined constant expectation."""

    def __init__(self, value: float):
        self.value = value

    def predict(self, X: Any) -> np.ndarray:
        return np.array([self.value])


def test_known_input_manually_calculated_z_scores():
    """Verify that compute_deviation matches exact manual arithmetic.

    Known expected values:
      cycle_efficiency: 0.80
      idling: 120.0
      duration: 40.0
      load_cycle: 20.0
      safety: 10.0

    Known training residual standard deviations:
      cycle_efficiency: 0.05
      idling: 25.0
      duration: 5.0
      load_cycle: 2.0
      safety: 2.0

    Known observed values:
      cycle_efficiency: 0.70  -> z = (0.70 - 0.80) / 0.05 = -2.0
      idling: 170.0          -> z = (170.0 - 120.0) / 25.0 = +2.0
      duration: 50.0         -> z = (50.0 - 40.0) / 5.0   = +2.0
      load_cycle: 24.0       -> z = (24.0 - 20.0) / 2.0   = +2.0
      safety: 6.0            -> z = (6.0 - 10.0) / 2.0    = -2.0

    Composite magnitude:
      sqrt((-2)^2 + 2^2 + 2^2 + 2^2 + (-2)^2) = sqrt(20) ~ 4.472136
    """
    mock_models = {
        "cycle_efficiency": FixedValueModel(0.80),
        "idling": FixedValueModel(120.0),
        "duration": FixedValueModel(40.0),
        "load_cycle": FixedValueModel(20.0),
        "safety": FixedValueModel(10.0),
    }

    mock_metadata = {
        "dimensions": list(mock_models.keys()),
        "residual_stds": {
            "cycle_efficiency": 0.05,
            "idling": 25.0,
            "duration": 5.0,
            "load_cycle": 2.0,
            "safety": 2.0,
        },
    }

    mock_artifacts = {"models": mock_models, "metadata": mock_metadata}

    telemetry = {
        "efficiency_score": 0.70,
        "idle_seconds": 170.0,
        "duration_minutes": 50.0,
        "load_cycles": 24,
        "min_proximity_distance": 6.0,
    }

    context = {
        "task_type": "Excavation",
        "machine_age": 5.0,
        "weather": "sunny",
    }

    result = compute_deviation(telemetry, context, artifacts=mock_artifacts)

    # Assert exact manually calculated z-scores
    assert result.d_cycle_efficiency == pytest.approx(-2.0, abs=1e-3)
    assert result.d_idling == pytest.approx(2.0, abs=1e-3)
    assert result.d_duration == pytest.approx(2.0, abs=1e-3)
    assert result.d_load_cycle == pytest.approx(2.0, abs=1e-3)
    assert result.d_safety == pytest.approx(-2.0, abs=1e-3)

    # Assert composite magnitude: sqrt(20) ~ 4.4721
    expected_magnitude = math.sqrt(20.0)
    assert result.composite_magnitude == pytest.approx(expected_magnitude, abs=1e-3)


# ═══════════════════════════════════════════════════════════════════════════
# 2. Return Structure, Five Dimensions & Determinism
# ═══════════════════════════════════════════════════════════════════════════

def test_compute_deviation_returns_all_five_dimensions():
    """Verify that compute_deviation returns all five dimensions and composite magnitude."""
    artifacts = load_reference_artifacts()

    telemetry = {
        "cycle_efficiency": 0.75,
        "idling": 300.0,
        "duration": 45.0,
        "load_cycle": 20,
        "safety": 8.0,
    }

    context = {
        "task_type": "Grading",
        "machine_age": 4.0,
        "weather": "cloudy",
    }

    res = compute_deviation(telemetry, context, artifacts=artifacts)

    assert isinstance(res, DeviationResult)
    expected_dims = {"cycle_efficiency", "idling", "duration", "load_cycle", "safety"}
    assert set(res.z_scores.keys()) == expected_dims
    assert set(res.expected_values.keys()) == expected_dims
    assert set(res.observed_values.keys()) == expected_dims

    for dim in expected_dims:
        assert isinstance(res[f"d_{dim}"], float)
        assert not math.isnan(res[f"d_{dim}"])

    assert isinstance(res.composite_magnitude, float)
    assert res.composite_magnitude >= 0.0


def test_composite_deviation_magnitude_formula():
    """Verify composite magnitude is exactly the Euclidean norm of the 5 z-scores."""
    artifacts = load_reference_artifacts()

    telemetry = {
        "efficiency_score": 0.65,
        "idle_seconds": 450.0,
        "duration_minutes": 55.0,
        "load_cycles": 18,
        "min_proximity_distance": 9.2,
    }

    context = {
        "task_type": "Excavation",
        "machine_age": 6.5,
        "weather": "rainy",
    }

    res = compute_deviation(telemetry, context, artifacts=artifacts)

    manual_mag = math.sqrt(
        res.d_cycle_efficiency**2
        + res.d_idling**2
        + res.d_duration**2
        + res.d_load_cycle**2
        + res.d_safety**2
    )

    assert res.composite_magnitude == pytest.approx(manual_mag, abs=1e-3)


def test_compute_deviation_is_deterministic():
    """Verify compute_deviation produces identical outputs for identical inputs."""
    artifacts = load_reference_artifacts()

    telemetry = {
        "efficiency_score": 0.82,
        "idle_seconds": 150.0,
        "duration_minutes": 38.0,
        "load_cycles": 26,
        "min_proximity_distance": 11.0,
    }

    context = {
        "task_type": "Hauling",
        "machine_age": 2.0,
        "weather": "sunny",
    }

    run1 = compute_deviation(telemetry, context, artifacts=artifacts)
    run2 = compute_deviation(telemetry, context, artifacts=artifacts)

    assert run1.to_dict() == run2.to_dict()


# ═══════════════════════════════════════════════════════════════════════════
# 3. Prevent Holdout Leakage Verification
# ═══════════════════════════════════════════════════════════════════════════

def test_standardization_statistics_from_training_split_only():
    """Verify that residual standard deviations came ONLY from the training split."""
    artifacts = load_reference_artifacts()
    metadata = artifacts["metadata"]

    eng = get_engine()
    SessionClass = sessionmaker(bind=eng)
    session = SessionClass()
    try:
        df = load_training_data(session)
    finally:
        session.close()

    train_indices = metadata["train_indices"]
    holdout_indices = metadata["holdout_indices"]

    # Assert train and holdout splits are disjoint
    train_set = set(train_indices)
    holdout_set = set(holdout_indices)
    assert train_set.isdisjoint(holdout_set), "Train and holdout sets must not overlap!"

    assert len(train_set) + len(holdout_set) == len(df)
    assert len(holdout_set) == pytest.approx(len(df) * 0.20, abs=2)

    # Reconstruct training data and holdout data using indices
    train_df = df.loc[train_indices]
    holdout_df = df.loc[holdout_indices]
    X_train = train_df[FEATURE_COLUMNS]

    for dim, col in DIMENSION_MAPPINGS.items():
        model = artifacts["models"][dim]
        train_pred = model.predict(X_train)
        train_residuals = train_df[col].values - train_pred
        recalculated_train_std = float(np.std(train_residuals, ddof=1))

        saved_std = metadata["residual_stds"][dim]

        # The saved residual std must match recalculated training residual std
        assert saved_std == pytest.approx(recalculated_train_std, abs=1e-5), (
            f"Dimension '{dim}' residual std mismatch with training split!"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 4. Holdout Evaluation, MAE/RMSE Reporting, and Calibration Coverage
# ═══════════════════════════════════════════════════════════════════════════

def test_holdout_evaluation_metrics_and_calibration():
    """Verify and report holdout evaluation metrics and calibration coverage."""
    artifacts = load_reference_artifacts()
    metadata = artifacts["metadata"]
    metrics = metadata["metrics"]

    print("\n" + "=" * 80)
    print("PHASE 2 REFERENCE MODELS HOLDOUT EVALUATION & CALIBRATION REPORT")
    print("=" * 80)
    print(f"Total Process A instances: {metadata['train_size'] + metadata['holdout_size']}")
    print(f"Training split: {metadata['train_size']} records | Holdout split: {metadata['holdout_size']} records\n")
    print(f"{'Dimension':<18} | {'MAE':<10} | {'RMSE':<10} | {'Std (Train)':<12} | {'Holdout 1-std':<14} | {'Holdout 2-std':<14}")
    print("-" * 84)

    for dim in metadata["dimensions"]:
        m = metrics[dim]
        print(
            f"{dim:<18} | {m['mae']:<10.4f} | {m['rmse']:<10.4f} | {m['training_residual_std']:<12.4f} | "
            f"{m['holdout_within_1sigma']*100:<11.1f}% | {m['holdout_within_2sigma']*100:<11.1f}%"
        )

        # Sanity assertions on errors
        assert m["mae"] > 0, f"MAE for {dim} must be positive"
        assert m["rmse"] >= m["mae"], f"RMSE must be >= MAE for {dim}"
        assert m["training_residual_std"] > 0

        # Calibration diagnostics (diagnostic check: non-zero reasonable coverage)
        assert 0.40 <= m["holdout_within_1sigma"] <= 0.90, (
            f"Holdout 1-sigma coverage unexpected: {m['holdout_within_1sigma']}"
        )
        assert 0.80 <= m["holdout_within_2sigma"] <= 1.00, (
            f"Holdout 2-sigma coverage unexpected: {m['holdout_within_2sigma']}"
        )

    print("=" * 80)


def test_model_artifacts_files_exist():
    """Verify all expected .joblib files exist in backend/models/."""
    models_dir = settings.models_dir
    expected_files = [
        "reference_cycle_efficiency.joblib",
        "reference_idling.joblib",
        "reference_duration.joblib",
        "reference_load_cycle.joblib",
        "reference_safety.joblib",
        "reference_metadata.joblib",
        "reference_models.joblib",
    ]

    for fname in expected_files:
        p = models_dir / fname
        assert p.exists(), f"Expected model artifact missing: {p.resolve()}"
        assert p.stat().st_size > 0, f"Model artifact is empty: {p.resolve()}"
