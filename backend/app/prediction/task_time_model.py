"""Task-Time Prediction Model using Gradient Boosting and Quantile Regression.

Architecture Specs (§10, §12, §24):
  - Point estimate: GradientBoostingRegressor(loss='squared_error')
  - Lower bound (P10): GradientBoostingRegressor(loss='quantile', alpha=0.10)
  - Upper bound (P90): GradientBoostingRegressor(loss='quantile', alpha=0.90)
  - Training Data: Process A historical data only (no Process B, zero data leakage)
  - Operator State Features: Prior EWMA state before the task (strictly zero data leakage)
  - Enforced Constraint: P10 <= Point Estimate <= P90 must always hold
  - Explainability: "Probable Contributing Factors" with percentage attribution (strictly non-causal)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.config import settings
from app.db.models import Machine, Operator, TaskCatalog, TaskInstance
from app.db.session import SessionLocal
from app.deviation_engine.deviation import compute_deviation
from app.operator_state.state import (
    DEFAULT_ALPHA,
    DEFAULT_CENTER,
    calculate_confidence,
    deviation_to_instant_scores,
)

logger = logging.getLogger("cat_decision_loop.prediction")

ARTIFACT_FILENAME = "task_time_models.joblib"

NUMERIC_FEATURES = [
    "operator_composite_score",
    "operator_duration_score",
    "operator_efficiency_score",
    "operator_confidence",
    "baseline_duration_minutes",
    "task_difficulty",
    "machine_age_years",
    "machine_wear_factor",
]

CATEGORICAL_FEATURES = [
    "task_type",
    "machine_type",
    "weather",
]

_CACHED_TASK_TIME_MODELS: dict[str, Any] | None = None


@dataclass(frozen=True)
class PredictionResult:
    """Task-time prediction result with strict uncertainty monotonicity."""

    predicted_duration: float
    p10: float
    p90: float
    uncertainty_range: float
    probable_factors: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "predicted_duration": self.predicted_duration,
            "p10": self.p10,
            "p90": self.p90,
            "uncertainty_range": self.uncertainty_range,
            "probable_factors": self.probable_factors,
        }


def extract_historical_training_data() -> pd.DataFrame:
    """Extract training features from Process A tasks with zero data leakage.

    For each operator, tasks are sorted chronologically. The operator's EWMA
    state is computed sequentially so that the features for task T_i reflect
    only tasks T_0 ... T_{i-1}.
    """
    session = SessionLocal()
    try:
        # Strictly filter by source_process == 'A'
        instances: list[TaskInstance] = (
            session.query(TaskInstance)
            .join(TaskCatalog, TaskInstance.task_type_id == TaskCatalog.id)
            .join(Machine, TaskInstance.machine_id == Machine.id)
            .filter(TaskInstance.source_process == "A")
            .order_by(TaskInstance.operator_id.asc(), TaskInstance.completed_at.asc())
            .all()
        )

        # Group by operator
        operator_tasks: dict[int, list[TaskInstance]] = {}
        for inst in instances:
            operator_tasks.setdefault(inst.operator_id, []).append(inst)

        rows = []
        alpha = DEFAULT_ALPHA

        for op_id, op_insts in operator_tasks.items():
            # Initial baseline before any tasks
            current_state = {
                "efficiency_score": DEFAULT_CENTER,
                "idling_score": DEFAULT_CENTER,
                "duration_score": DEFAULT_CENTER,
                "load_cycle_score": DEFAULT_CENTER,
                "safety_score": DEFAULT_CENTER,
                "composite_score": DEFAULT_CENTER,
            }

            for sample_idx, inst in enumerate(op_insts):
                # ── 1. Features BEFORE this task (zero data leakage) ──
                confidence = calculate_confidence(sample_idx)

                row = {
                    "instance_id": inst.id,
                    "operator_id": op_id,
                    "operator_composite_score": current_state["composite_score"],
                    "operator_duration_score": current_state["duration_score"],
                    "operator_efficiency_score": current_state["efficiency_score"],
                    "operator_confidence": confidence,
                    "baseline_duration_minutes": inst.task_type.baseline_duration_minutes,
                    "task_difficulty": inst.task_type.difficulty,
                    "machine_age_years": inst.machine.age_years,
                    "machine_wear_factor": inst.machine.wear_factor,
                    "task_type": inst.task_type.name,
                    "machine_type": inst.machine.machine_type,
                    "weather": inst.weather,
                    "duration_minutes": inst.duration_minutes,  # TARGET
                }
                rows.append(row)

                # ── 2. Update EWMA state AFTER task for next iterations ──
                telemetry = {
                    "efficiency_score": inst.efficiency_score,
                    "idle_seconds": inst.idle_seconds,
                    "duration_minutes": inst.duration_minutes,
                    "load_cycles": inst.load_cycles,
                    "min_proximity_distance": inst.min_proximity_distance,
                }
                context = {
                    "task_type": inst.task_type.name,
                    "machine_age": inst.machine.age_years,
                    "weather": inst.weather,
                }
                dev = compute_deviation(telemetry, context)
                instant = deviation_to_instant_scores(dev)

                if sample_idx == 0:
                    current_state = instant
                else:
                    for k in ["efficiency_score", "idling_score", "duration_score", "load_cycle_score", "safety_score"]:
                        current_state[k] = alpha * instant[k] + (1.0 - alpha) * current_state[k]
                    current_state["composite_score"] = (
                        current_state["efficiency_score"]
                        + current_state["idling_score"]
                        + current_state["duration_score"]
                        + current_state["load_cycle_score"]
                        + current_state["safety_score"]
                    ) / 5.0

        return pd.DataFrame(rows)
    finally:
        session.close()


def train_task_time_models(save_artifacts: bool = True) -> dict[str, Any]:
    """Train point estimate and quantile regression models on Process A data."""
    df = extract_historical_training_data()
    logger.info("Extracted %d historical training instances for task-time models.", len(df))

    feature_cols = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    X = df[feature_cols]
    y = df["duration_minutes"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), NUMERIC_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_FEATURES),
        ]
    )

    # 1. Point estimate model (GB with squared error)
    point_model = Pipeline([
        ("preprocessor", preprocessor),
        ("regressor", GradientBoostingRegressor(
            n_estimators=120,
            learning_rate=0.08,
            max_depth=4,
            random_state=42,
        )),
    ])
    point_model.fit(X_train, y_train)

    # 2. P10 Lower bound model (Quantile regression alpha=0.10)
    p10_model = Pipeline([
        ("preprocessor", preprocessor),
        ("regressor", GradientBoostingRegressor(
            loss="quantile",
            alpha=0.10,
            n_estimators=120,
            learning_rate=0.08,
            max_depth=4,
            random_state=42,
        )),
    ])
    p10_model.fit(X_train, y_train)

    # 3. P90 Upper bound model (Quantile regression alpha=0.90)
    p90_model = Pipeline([
        ("preprocessor", preprocessor),
        ("regressor", GradientBoostingRegressor(
            loss="quantile",
            alpha=0.90,
            n_estimators=120,
            learning_rate=0.08,
            max_depth=4,
            random_state=42,
        )),
    ])
    p90_model.fit(X_train, y_train)

    # Evaluate on held-out test split
    point_preds = point_model.predict(X_test)
    p10_preds = p10_model.predict(X_test)
    p90_preds = p90_model.predict(X_test)

    # Strictly enforce monotonicity for interval coverage metric
    adj_p10 = np.minimum(p10_preds, point_preds)
    adj_p90 = np.maximum(p90_preds, point_preds)

    mae = float(np.mean(np.abs(point_preds - y_test)))
    rmse = float(np.sqrt(np.mean((point_preds - y_test) ** 2)))
    interval_coverage = float(np.mean((y_test >= adj_p10) & (y_test <= adj_p90)))

    logger.info(
        "Task-Time Model Evaluation — MAE: %.2f min, RMSE: %.2f min, P10-P90 Coverage: %.1f%%",
        mae, rmse, interval_coverage * 100
    )

    # Feature statistics for explainability
    numeric_means = {col: float(df[col].mean()) for col in NUMERIC_FEATURES}
    numeric_stds = {col: float(max(df[col].std(), 1e-4)) for col in NUMERIC_FEATURES}

    # Extract transformed feature names and feature importances
    gb_regressor = point_model.named_steps["regressor"]
    feature_importances = gb_regressor.feature_importances_

    ohe = point_model.named_steps["preprocessor"].named_transformers_["cat"]
    cat_names = list(ohe.get_feature_names_out(CATEGORICAL_FEATURES))
    all_feature_names = NUMERIC_FEATURES + cat_names

    artifacts = {
        "point_model": point_model,
        "p10_model": p10_model,
        "p90_model": p90_model,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "numeric_means": numeric_means,
        "numeric_stds": numeric_stds,
        "all_feature_names": all_feature_names,
        "feature_importances": dict(zip(all_feature_names, feature_importances.tolist())),
        "metrics": {
            "mae": mae,
            "rmse": rmse,
            "interval_coverage": interval_coverage,
        },
    }

    if save_artifacts:
        models_dir = Path(settings.models_dir)
        models_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = models_dir / ARTIFACT_FILENAME
        joblib.dump(artifacts, artifact_path)
        logger.info("Saved task-time model artifacts to %s", artifact_path)

    global _CACHED_TASK_TIME_MODELS
    _CACHED_TASK_TIME_MODELS = artifacts
    return artifacts


def load_task_time_artifacts(models_dir: Path | str | None = None) -> dict[str, Any]:
    """Load cached task-time models or read from disk."""
    global _CACHED_TASK_TIME_MODELS
    if _CACHED_TASK_TIME_MODELS is not None:
        return _CACHED_TASK_TIME_MODELS

    target_dir = Path(models_dir or settings.models_dir)
    target_path = target_dir / ARTIFACT_FILENAME

    if not target_path.exists():
        raise FileNotFoundError(
            f"Task-time model artifact missing: {target_path}. "
            f"Run 'python -m app.prediction.task_time_model' first."
        )

    artifacts = joblib.load(target_path)
    _CACHED_TASK_TIME_MODELS = artifacts
    return artifacts


def extract_probable_contributing_factors(
    feature_row: dict[str, Any],
    artifacts: dict[str, Any],
    top_n: int = 4,
) -> list[dict[str, Any]]:
    """Generate probabilistic attribution factors for explainability (§24).

    Strict AI principle: Non-causal phrasing using 'Probable Contributing Factors'.
    """
    numeric_means = artifacts.get("numeric_means", {})
    numeric_stds = artifacts.get("numeric_stds", {})
    feature_importances = artifacts.get("feature_importances", {})

    candidates = []

    # 1. Weather impact
    weather_val = feature_row.get("weather", "Clear")
    weather_key = f"weather_{weather_val}"
    weather_imp = feature_importances.get(weather_key, 0.05)
    if weather_val in ["Rain", "Mud", "Snow/Ice"]:
        candidates.append({
            "name": f"Adverse Weather ({weather_val})",
            "direction": "increases_duration",
            "weight": weather_imp * 1.5,
            "description": f"Probable contributing factor: {weather_val} ground conditions associated with extended cycle times.",
        })
    else:
        candidates.append({
            "name": "Favorable Weather (Clear)",
            "direction": "decreases_duration",
            "weight": weather_imp * 0.8,
            "description": "Probable contributing factor: Clear operating conditions associated with standard cycle timing.",
        })

    # 2. Operator Duration & Efficiency Skill
    dur_score = float(feature_row.get("operator_duration_score", 50.0))
    dur_mean = numeric_means.get("operator_duration_score", 50.0)
    dur_std = numeric_stds.get("operator_duration_score", 15.0)
    z_dur = (dur_score - dur_mean) / dur_std
    dur_imp = feature_importances.get("operator_duration_score", 0.15)

    if z_dur > 0.4:
        candidates.append({
            "name": "Operator Speed Consistency",
            "direction": "decreases_duration",
            "weight": dur_imp * abs(z_dur),
            "description": f"Probable contributing factor: Operator dynamic speed score ({dur_score:.1f}/100) reflects higher demonstrated efficiency.",
        })
    elif z_dur < -0.4:
        candidates.append({
            "name": "Operator Speed Opportunity",
            "direction": "increases_duration",
            "weight": dur_imp * abs(z_dur),
            "description": f"Probable contributing factor: Operator dynamic speed score ({dur_score:.1f}/100) indicates cycle pacing below baseline.",
        })

    # 3. Machine Wear & Age
    wear = float(feature_row.get("machine_wear_factor", 0.0))
    wear_mean = numeric_means.get("machine_wear_factor", 0.3)
    wear_std = numeric_stds.get("machine_wear_factor", 0.2)
    z_wear = (wear - wear_mean) / wear_std
    wear_imp = feature_importances.get("machine_wear_factor", 0.10)

    if wear > 0.5:
        candidates.append({
            "name": f"Machine Age & Wear ({wear:.2f})",
            "direction": "increases_duration",
            "weight": wear_imp * max(1.0, z_wear),
            "description": f"Probable contributing factor: Equipment wear index ({wear:.2f}) associated with baseline mechanical efficiency drag.",
        })

    # 4. Task Difficulty
    diff = float(feature_row.get("task_difficulty", 0.5))
    task_name = str(feature_row.get("task_type", "Task"))
    diff_imp = feature_importances.get("task_difficulty", 0.20)
    if diff > 0.6:
        candidates.append({
            "name": f"High Task Complexity ({task_name})",
            "direction": "increases_duration",
            "weight": diff_imp * diff,
            "description": f"Probable contributing factor: {task_name} carries elevated operational difficulty rating ({diff:.2f}).",
        })
    elif diff < 0.4:
        candidates.append({
            "name": f"Standard Task Profile ({task_name})",
            "direction": "decreases_duration",
            "weight": diff_imp * (1.0 - diff),
            "description": f"Probable contributing factor: {task_name} baseline requirements represent low operational difficulty ({diff:.2f}).",
        })

    # Normalize weights into percentage attributions
    candidates.sort(key=lambda x: x["weight"], reverse=True)
    selected = candidates[:top_n]
    total_w = sum(c["weight"] for c in selected) or 1.0

    output = []
    for item in selected:
        pct = float(round((item["weight"] / total_w) * 100.0, 1))
        conf = float(round(min(96.0, 75.0 + (item["weight"] * 15.0)), 1))
        output.append({
            "factor_name": item["name"],
            "impact_direction": item["direction"],
            "impact_percentage": pct,
            "confidence": conf,
            "description": item["description"],
        })

    return output


def predict_task_time(
    feature_row: Mapping[str, Any],
    artifacts: dict[str, Any] | None = None,
) -> PredictionResult:
    """Predict task duration with uncertainty and strict P10 <= Point <= P90 constraint."""
    if artifacts is None:
        artifacts = load_task_time_artifacts()

    point_model: Pipeline = artifacts["point_model"]
    p10_model: Pipeline = artifacts["p10_model"]
    p90_model: Pipeline = artifacts["p90_model"]

    # Build input dataframe
    input_data = {
        col: [feature_row.get(col, 0.0)]
        for col in NUMERIC_FEATURES
    }
    for col in CATEGORICAL_FEATURES:
        input_data[col] = [str(feature_row.get(col, ""))]

    df_in = pd.DataFrame(input_data)

    raw_point = float(point_model.predict(df_in)[0])
    raw_p10 = float(p10_model.predict(df_in)[0])
    raw_p90 = float(p90_model.predict(df_in)[0])

    # ═══════════════════════════════════════════════════════════════════════
    # STRICT CONSTRAINT ENFORCEMENT: P10 <= Point <= P90 must always hold
    # ═══════════════════════════════════════════════════════════════════════
    # Prevent crossing and ensure positive durations
    point_est = max(1.0, raw_point)
    p10_est = max(0.5, min(raw_p10, point_est))
    p90_est = max(point_est, max(raw_p90, point_est + 0.5))

    uncertainty_range = float(round(p90_est - p10_est, 2))

    # Explainability breakdown
    factors = extract_probable_contributing_factors(dict(feature_row), artifacts)

    return PredictionResult(
        predicted_duration=float(round(point_est, 2)),
        p10=float(round(p10_est, 2)),
        p90=float(round(p90_est, 2)),
        uncertainty_range=uncertainty_range,
        probable_factors=factors,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    print("=" * 60)
    print("Training Task-Time Prediction Models (Process A only)...")
    print("=" * 60)
    train_task_time_models(save_artifacts=True)
    print("Done!")
