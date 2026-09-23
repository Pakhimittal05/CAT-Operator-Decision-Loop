"""Shared Deviation Engine.

Calculates the standardized 5-dimensional deviation vector and composite
deviation magnitude:
    D = [d_cycle_efficiency, d_idling, d_duration, d_load_cycle, d_safety]
    d_i = (observed_i - expected_i) / training_residual_std_i

This pure function is the single shared evidence-based core used by:
  - operator state calculation (EWMA)
  - anomaly detection
  - what-if simulation & post-task comparison

Zero database writes, zero side effects.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import joblib
import numpy as np
import pandas as pd
import scipy.sparse  # Ensure sparse matrix classes are loaded for joblib unpickling

from app.config import settings
from app.deviation_engine.reference_model import (
    DIMENSION_MAPPINGS,
    FEATURE_COLUMNS,
)

# Global in-memory cache for loaded model artifacts
_CACHED_ARTIFACTS: dict[str, Any] | None = None


# Alternative telemetry key synonyms for developer convenience
TELEMETRY_KEYS: dict[str, list[str]] = {
    "cycle_efficiency": ["efficiency_score", "cycle_efficiency", "efficiency"],
    "idling": ["idle_seconds", "idling", "idle_time"],
    "duration": ["duration_minutes", "duration"],
    "load_cycle": ["load_cycles", "load_cycle", "cycles"],
    "safety": ["min_proximity_distance", "safety", "proximity_distance"],
}

CONTEXT_KEYS: dict[str, list[str]] = {
    "task_type": ["task_type", "task_name", "name"],
    "machine_age": ["machine_age", "age_years", "machine_age_years", "age"],
    "weather": ["weather", "weather_condition"],
}


@dataclass(frozen=True)
class DeviationResult:
    """Standardized 5-dimensional deviation result and composite magnitude."""

    d_cycle_efficiency: float
    d_idling: float
    d_duration: float
    d_load_cycle: float
    d_safety: float
    composite_magnitude: float
    expected_values: dict[str, float]
    observed_values: dict[str, float]
    z_scores: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary representation."""
        return {
            "d_cycle_efficiency": self.d_cycle_efficiency,
            "d_idling": self.d_idling,
            "d_duration": self.d_duration,
            "d_load_cycle": self.d_load_cycle,
            "d_safety": self.d_safety,
            "composite_magnitude": self.composite_magnitude,
            "expected_values": dict(self.expected_values),
            "observed_values": dict(self.observed_values),
            "z_scores": dict(self.z_scores),
        }

    def __getitem__(self, item: str) -> Any:
        """Allow dict-style key access."""
        if hasattr(self, item):
            return getattr(self, item)
        if item in self.z_scores:
            return self.z_scores[item]
        raise KeyError(item)


def load_reference_artifacts(
    models_dir: Path | None = None,
    force_reload: bool = False,
) -> dict[str, Any]:
    """Load reference models and metadata from disk, cached in memory.

    Args:
        models_dir: Directory containing .joblib files.
        force_reload: If True, bypass cache and reload from disk.

    Returns:
        Dict with 'models' (dict of Pipelines) and 'metadata' (dict).
    """
    global _CACHED_ARTIFACTS
    if _CACHED_ARTIFACTS is not None and not force_reload:
        return _CACHED_ARTIFACTS

    target_dir = models_dir or settings.models_dir
    bundle_path = target_dir / "reference_models.joblib"

    if bundle_path.exists():
        bundle = joblib.load(bundle_path)
        _CACHED_ARTIFACTS = bundle
        return bundle

    # Fallback to individual files
    meta_path = target_dir / "reference_metadata.joblib"
    if not meta_path.exists():
        raise FileNotFoundError(
            f"Reference model artifacts not found in {target_dir}. "
            "Please run 'python -m app.deviation_engine.reference_model' first."
        )

    metadata = joblib.load(meta_path)
    models = {}
    for dim in metadata["dimensions"]:
        model_path = target_dir / f"reference_{dim}.joblib"
        models[dim] = joblib.load(model_path)

    bundle = {"models": models, "metadata": metadata}
    _CACHED_ARTIFACTS = bundle
    return bundle


def _extract_field(obj: Any, candidate_keys: list[str], default: Any = None) -> Any:
    """Extract a value from a dict, object attributes, or Mapping."""
    if isinstance(obj, Mapping):
        for k in candidate_keys:
            if k in obj:
                return obj[k]
    else:
        for k in candidate_keys:
            if hasattr(obj, k):
                return getattr(obj, k)
    return default


def compute_deviation(
    task_telemetry: Any,
    task_context: Any,
    artifacts: dict[str, Any] | None = None,
) -> DeviationResult:
    """Compute standardized 5-dim deviation vector and composite magnitude.

    Pure function: zero DB writes, zero side effects.

    Args:
        task_telemetry: Observed task metrics (dict or object with efficiency,
            idling, duration, load cycles, proximity).
        task_context: Context features (dict or object with task_type,
            machine_age, weather).
        artifacts: Optional pre-loaded reference artifacts dict with 'models'
            and 'metadata'. If None, loaded from cached artifacts on disk.

    Returns:
        DeviationResult containing the 5 standardized deviations and composite magnitude.
    """
    loaded = artifacts or load_reference_artifacts()
    models = loaded["models"]
    metadata = loaded.get("metadata", loaded)
    residual_stds = metadata["residual_stds"]

    # 1. Parse context into single-row dataframe for model prediction
    task_type = _extract_field(task_context, CONTEXT_KEYS["task_type"])
    machine_age = _extract_field(task_context, CONTEXT_KEYS["machine_age"])
    weather = _extract_field(task_context, CONTEXT_KEYS["weather"])

    if task_type is None or machine_age is None or weather is None:
        raise ValueError(
            f"task_context missing required fields {FEATURE_COLUMNS}. "
            f"Received: task_type={task_type}, machine_age={machine_age}, weather={weather}"
        )

    X_context = pd.DataFrame(
        [
            {
                "task_type": str(task_type),
                "machine_age": float(machine_age),
                "weather": str(weather),
            }
        ]
    )

    # 2. Extract observed values, predict expected values, calculate z-scores
    expected_values: dict[str, float] = {}
    observed_values: dict[str, float] = {}
    z_scores: dict[str, float] = {}

    for dim in ["cycle_efficiency", "idling", "duration", "load_cycle", "safety"]:
        # Expected value from reference model
        model = models[dim]
        pred_val = float(model.predict(X_context)[0])
        expected_values[dim] = round(pred_val, 4)

        # Observed value from telemetry
        obs_val = _extract_field(task_telemetry, TELEMETRY_KEYS[dim])
        if obs_val is None:
            raise ValueError(
                f"task_telemetry missing dimension '{dim}' (checked keys: {TELEMETRY_KEYS[dim]})"
            )
        obs_float = float(obs_val)
        observed_values[dim] = round(obs_float, 4)

        # Standardized deviation: (observed - expected) / training_residual_std
        std_val = float(residual_stds[dim])
        if std_val <= 0:
            std_val = 1.0

        z = (obs_float - pred_val) / std_val
        z_scores[dim] = round(float(z), 4)

    # 3. Composite deviation magnitude: Euclidean norm ||D||_2
    magnitude = math.sqrt(sum(z**2 for z in z_scores.values()))
    composite_magnitude = round(float(magnitude), 4)

    return DeviationResult(
        d_cycle_efficiency=z_scores["cycle_efficiency"],
        d_idling=z_scores["idling"],
        d_duration=z_scores["duration"],
        d_load_cycle=z_scores["load_cycle"],
        d_safety=z_scores["safety"],
        composite_magnitude=composite_magnitude,
        expected_values=expected_values,
        observed_values=observed_values,
        z_scores=z_scores,
    )
