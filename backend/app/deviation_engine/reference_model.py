"""Reference Model Training for the Deviation Engine.

Trains five independent GradientBoostingRegressor reference models, one per dimension:
  - cycle_efficiency (efficiency_score)
  - idling (idle_seconds)
  - duration (duration_minutes)
  - load_cycle (load_cycles)
  - safety (min_proximity_distance)

Reference-model inputs:
  - task_type (categorical)
  - machine_age (numeric)
  - weather (categorical)

IMPORTANT - Prevent Holdout Leakage:
  - Data is split into 80% train / 20% holdout using a fixed random_state.
  - Reference models and residual standard deviations are fitted ONLY on the training split.
  - Residual standard deviations are frozen and saved with model artifacts.
  - The holdout split is used solely for evaluation (MAE, RMSE, calibration diagnostics).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db.models import Machine, TaskCatalog, TaskInstance
from app.db.session import get_engine

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# Reference Dimensions Configuration
# ═══════════════════════════════════════════════════════════════════════════

DIMENSION_MAPPINGS: dict[str, str] = {
    "cycle_efficiency": "efficiency_score",
    "idling": "idle_seconds",
    "duration": "duration_minutes",
    "load_cycle": "load_cycles",
    "safety": "min_proximity_distance",
}

FEATURE_COLUMNS: list[str] = ["task_type", "machine_age", "weather"]
CATEGORICAL_FEATURES: list[str] = ["task_type", "weather"]
NUMERICAL_FEATURES: list[str] = ["machine_age"]

RANDOM_STATE: int = 42
HOLDOUT_RATIO: float = 0.20


def build_pipeline(random_state: int = RANDOM_STATE) -> Pipeline:
    """Build an sklearn Pipeline for a single reference dimension.

    Encodes categoricals with OneHotEncoder and passes machine_age through,
    followed by a GradientBoostingRegressor.
    """
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "cat",
                OneHotEncoder(drop=None, sparse_output=False, handle_unknown="ignore"),
                CATEGORICAL_FEATURES,
            ),
            (
                "num",
                "passthrough",
                NUMERICAL_FEATURES,
            ),
        ]
    )

    regressor = GradientBoostingRegressor(
        n_estimators=100,
        max_depth=3,
        learning_rate=0.1,
        random_state=random_state,
    )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("regressor", regressor),
        ]
    )


def load_training_data(session: Session) -> pd.DataFrame:
    """Load historical Process A data joined with Machine and TaskCatalog."""
    query = (
        session.query(
            TaskInstance.id.label("task_instance_id"),
            TaskInstance.efficiency_score,
            TaskInstance.idle_seconds,
            TaskInstance.duration_minutes,
            TaskInstance.load_cycles,
            TaskInstance.min_proximity_distance,
            TaskCatalog.name.label("task_type"),
            Machine.age_years.label("machine_age"),
            TaskInstance.weather,
        )
        .join(TaskCatalog, TaskInstance.task_type_id == TaskCatalog.id)
        .join(Machine, TaskInstance.machine_id == Machine.id)
        .filter(TaskInstance.source_process == "A")
        .order_by(TaskInstance.id)
    )

    df = pd.read_sql(query.statement, session.bind)
    return df


def train_reference_models(
    df: pd.DataFrame,
    models_dir: Path | None = None,
    random_state: int = RANDOM_STATE,
    holdout_ratio: float = HOLDOUT_RATIO,
) -> dict[str, Any]:
    """Train reference models, evaluate on holdout, and save artifacts.

    Args:
        df: Dataframe with Process A historical data.
        models_dir: Directory to save .joblib artifacts.
        random_state: Random state for train_test_split and regressors.
        holdout_ratio: Proportion of data reserved for holdout evaluation.

    Returns:
        Dictionary containing trained models, residual_stds, and evaluation metrics.
    """
    save_dir = models_dir or settings.models_dir
    save_dir.mkdir(parents=True, exist_ok=True)

    # 1. Train / Holdout split
    train_df, holdout_df = train_test_split(
        df,
        test_size=holdout_ratio,
        random_state=random_state,
        shuffle=True,
    )

    X_train = train_df[FEATURE_COLUMNS]
    X_holdout = holdout_df[FEATURE_COLUMNS]

    models: dict[str, Pipeline] = {}
    residual_stds: dict[str, float] = {}
    metrics: dict[str, dict[str, float]] = {}

    for dim, col in DIMENSION_MAPPINGS.items():
        y_train = train_df[col].values
        y_holdout = holdout_df[col].values

        # 2. Fit model ONLY on training data
        pipeline = build_pipeline(random_state=random_state)
        pipeline.fit(X_train, y_train)
        models[dim] = pipeline

        # 3. Calculate residual standard deviation ONLY on training split
        y_train_pred = pipeline.predict(X_train)
        train_residuals = y_train - y_train_pred
        # Using unbiased estimator (ddof=1)
        res_std = float(np.std(train_residuals, ddof=1))
        # Guard against zero variance
        if res_std < 1e-6:
            res_std = 1.0
        residual_stds[dim] = res_std

        # 4. Evaluate ONLY on holdout split
        y_holdout_pred = pipeline.predict(X_holdout)
        holdout_residuals = y_holdout - y_holdout_pred

        mae = float(mean_absolute_error(y_holdout, y_holdout_pred))
        rmse = float(root_mean_squared_error(y_holdout, y_holdout_pred))

        # Standardize holdout residuals using TRAINING std
        holdout_z = holdout_residuals / res_std
        within_1sigma = float(np.mean(np.abs(holdout_z) <= 1.0))
        within_2sigma = float(np.mean(np.abs(holdout_z) <= 2.0))

        # Training calibration for comparison
        train_z = train_residuals / res_std
        train_within_1sigma = float(np.mean(np.abs(train_z) <= 1.0))
        train_within_2sigma = float(np.mean(np.abs(train_z) <= 2.0))

        metrics[dim] = {
            "mae": mae,
            "rmse": rmse,
            "training_residual_std": res_std,
            "holdout_within_1sigma": within_1sigma,
            "holdout_within_2sigma": within_2sigma,
            "train_within_1sigma": train_within_1sigma,
            "train_within_2sigma": train_within_2sigma,
        }

    # 5. Build metadata artifact
    metadata = {
        "dimensions": list(DIMENSION_MAPPINGS.keys()),
        "dimension_mappings": DIMENSION_MAPPINGS,
        "feature_columns": FEATURE_COLUMNS,
        "categorical_features": CATEGORICAL_FEATURES,
        "numerical_features": NUMERICAL_FEATURES,
        "residual_stds": residual_stds,
        "train_size": len(train_df),
        "holdout_size": len(holdout_df),
        "train_indices": train_df.index.tolist(),
        "holdout_indices": holdout_df.index.tolist(),
        "metrics": metrics,
        "random_state": random_state,
        "holdout_ratio": holdout_ratio,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }

    # 6. Save artifacts
    for dim, pipe in models.items():
        model_file = save_dir / f"reference_{dim}.joblib"
        joblib.dump(pipe, model_file)

    meta_file = save_dir / "reference_metadata.joblib"
    joblib.dump(metadata, meta_file)

    # Master bundle containing both models and metadata for convenient single-file load
    bundle_file = save_dir / "reference_models.joblib"
    joblib.dump({"models": models, "metadata": metadata}, bundle_file)

    logger.info("Saved reference model artifacts to %s", save_dir)

    return {
        "models": models,
        "metadata": metadata,
        "metrics": metrics,
        "residual_stds": residual_stds,
        "train_size": len(train_df),
        "holdout_size": len(holdout_df),
    }


def run_training():
    """Main training CLI entrypoint."""
    eng = get_engine()
    SessionClass = sessionmaker(bind=eng)
    session = SessionClass()
    try:
        df = load_training_data(session)
        print(f"Loaded {len(df)} Process A task instances for reference model training.")
        results = train_reference_models(df)
        print("\n--- Reference Models Training & Holdout Evaluation ---")
        print(f"Training split: {results['train_size']} records | Holdout split: {results['holdout_size']} records\n")
        print(f"{'Dimension':<18} | {'MAE':<10} | {'RMSE':<10} | {'Std (Train)':<12} | {'Within 1-std':<14} | {'Within 2-std':<14}")
        print("-" * 88)
        for dim, m in results["metrics"].items():
            print(
                f"{dim:<18} | {m['mae']:<10.4f} | {m['rmse']:<10.4f} | {m['training_residual_std']:<12.4f} | "
                f"{m['holdout_within_1sigma']*100:<13.1f}% | {m['holdout_within_2sigma']*100:<13.1f}%"
            )
        print("-" * 88)
        print(f"Artifacts successfully saved to: {settings.models_dir.resolve()}")
    finally:
        session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run_training()
