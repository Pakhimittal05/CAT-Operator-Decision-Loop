"""Dynamic Operator State Calculation using Exponentially Weighted Moving Average (EWMA).

Aggregates task deviation vectors over an operator's task history into a dynamic
performance/skill state:
  - 5 per-dimension skill scores (0–100 scale)
  - overall composite score (0–100 scale)
  - trend direction (improving, stable, declining)
  - confidence based on sample count
  - derived UI label (Expert, Intermediate, Beginner)

CRITICAL RULE:
  Consumes the existing shared compute_deviation() function from
  app.deviation_engine.deviation. Zero duplicate deviation logic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

from sqlalchemy.orm import Session

from app.db.models import Machine, Operator, OperatorState, TaskCatalog, TaskInstance
from app.deviation_engine.deviation import DeviationResult, compute_deviation

# ═══════════════════════════════════════════════════════════════════════════
# Configuration Constants
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_ALPHA: float = 0.20  # EWMA smoothing factor (higher = more recency weight)
DEFAULT_CENTER: float = 50.0  # Center score for z=0
DEFAULT_SCALE: float = 15.0  # Multiplier per 1 sigma deviation

EXPERT_THRESHOLD: float = 75.0
INTERMEDIATE_THRESHOLD: float = 50.0
TREND_THRESHOLD: float = 1.0  # Points difference to qualify as improving/declining


@dataclass(frozen=True)
class StateSnapshot:
    """In-memory snapshot of dynamic operator state."""

    operator_id: int
    task_type_id: int | None
    efficiency_score: float
    idling_score: float
    duration_score: float
    load_cycle_score: float
    safety_score: float
    composite_score: float
    trend_direction: str
    confidence: float
    derived_label: str
    sample_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator_id": self.operator_id,
            "task_type_id": self.task_type_id,
            "efficiency_score": self.efficiency_score,
            "idling_score": self.idling_score,
            "duration_score": self.duration_score,
            "load_cycle_score": self.load_cycle_score,
            "safety_score": self.safety_score,
            "composite_score": self.composite_score,
            "trend_direction": self.trend_direction,
            "confidence": self.confidence,
            "derived_label": self.derived_label,
            "sample_count": self.sample_count,
        }


def z_to_score(z: float, positive_is_good: bool = True) -> float:
    """Map a z-score deviation into a continuous 0-100 skill score.

    For efficiency, load_cycles, and proximity: higher observed is better (z > 0 is good).
    For idling and duration: lower observed is better (z < 0 is good, z > 0 is penalized).
    """
    effective_z = z if positive_is_good else -z
    raw_score = DEFAULT_CENTER + DEFAULT_SCALE * effective_z
    return float(max(0.0, min(100.0, raw_score)))


def get_derived_label(composite_score: float) -> str:
    """Derive UI categorical label from continuous composite score."""
    if composite_score >= EXPERT_THRESHOLD:
        return "Expert"
    elif composite_score >= INTERMEDIATE_THRESHOLD:
        return "Intermediate"
    return "Beginner"


def calculate_confidence(sample_count: int) -> float:
    """Calculate confidence based on sample count.

    Reaches ~0.63 at 10 samples, ~0.86 at 20 samples, ~0.95 at 30 samples.
    """
    if sample_count <= 0:
        return 0.0
    conf = 1.0 - math.exp(-sample_count / 10.0)
    return float(round(min(1.0, conf), 4))


def deviation_to_instant_scores(dev: DeviationResult) -> dict[str, float]:
    """Convert a 5D DeviationResult into instant 0-100 dimension scores."""
    eff = z_to_score(dev.d_cycle_efficiency, positive_is_good=True)
    idl = z_to_score(dev.d_idling, positive_is_good=False)
    dur = z_to_score(dev.d_duration, positive_is_good=False)
    load = z_to_score(dev.d_load_cycle, positive_is_good=True)
    saf = z_to_score(dev.d_safety, positive_is_good=True)
    comp = float(round((eff + idl + dur + load + saf) / 5.0, 4))
    return {
        "efficiency_score": float(round(eff, 4)),
        "idling_score": float(round(idl, 4)),
        "duration_score": float(round(dur, 4)),
        "load_cycle_score": float(round(load, 4)),
        "safety_score": float(round(saf, 4)),
        "composite_score": comp,
    }


def compute_ewma_state_from_instances(
    operator_id: int,
    instances: Sequence[TaskInstance],
    task_type_id: int | None = None,
    alpha: float = DEFAULT_ALPHA,
    artifacts: dict[str, Any] | None = None,
) -> StateSnapshot:
    """Compute deterministic EWMA state for an operator from task instances.

    Consumes the shared compute_deviation() function for every instance.
    """
    # Filter by task_type if task-specific state requested
    if task_type_id is not None:
        filtered = [inst for inst in instances if inst.task_type_id == task_type_id]
    else:
        filtered = list(instances)

    # Sort deterministically by completed_at ascending
    sorted_instances = sorted(filtered, key=lambda x: x.completed_at)

    if not sorted_instances:
        # Default unobserved baseline state
        return StateSnapshot(
            operator_id=operator_id,
            task_type_id=task_type_id,
            efficiency_score=DEFAULT_CENTER,
            idling_score=DEFAULT_CENTER,
            duration_score=DEFAULT_CENTER,
            load_cycle_score=DEFAULT_CENTER,
            safety_score=DEFAULT_CENTER,
            composite_score=DEFAULT_CENTER,
            trend_direction="stable",
            confidence=0.0,
            derived_label=get_derived_label(DEFAULT_CENTER),
            sample_count=0,
        )

    current_scores: dict[str, float] = {}
    prev_composite: float = DEFAULT_CENTER

    for i, inst in enumerate(sorted_instances):
        # Build telemetry and context dicts
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

        # SHARED DEVIATION ENGINE CALL
        dev = compute_deviation(telemetry, context, artifacts=artifacts)
        instant = deviation_to_instant_scores(dev)

        if i == 0:
            current_scores = instant
        else:
            prev_composite = current_scores["composite_score"]
            for k in ["efficiency_score", "idling_score", "duration_score", "load_cycle_score", "safety_score"]:
                current_scores[k] = alpha * instant[k] + (1.0 - alpha) * current_scores[k]
            current_scores["composite_score"] = (
                current_scores["efficiency_score"]
                + current_scores["idling_score"]
                + current_scores["duration_score"]
                + current_scores["load_cycle_score"]
                + current_scores["safety_score"]
            ) / 5.0

    # Trend calculation: compare current composite with previous step
    delta = current_scores["composite_score"] - prev_composite
    if delta > TREND_THRESHOLD:
        trend = "improving"
    elif delta < -TREND_THRESHOLD:
        trend = "declining"
    else:
        trend = "stable"

    comp_score = float(round(current_scores["composite_score"], 2))
    confidence = calculate_confidence(len(sorted_instances))
    derived_label = get_derived_label(comp_score)

    return StateSnapshot(
        operator_id=operator_id,
        task_type_id=task_type_id,
        efficiency_score=float(round(current_scores["efficiency_score"], 2)),
        idling_score=float(round(current_scores["idling_score"], 2)),
        duration_score=float(round(current_scores["duration_score"], 2)),
        load_cycle_score=float(round(current_scores["load_cycle_score"], 2)),
        safety_score=float(round(current_scores["safety_score"], 2)),
        composite_score=comp_score,
        trend_direction=trend,
        confidence=confidence,
        derived_label=derived_label,
        sample_count=len(sorted_instances),
    )


def get_operator_state(
    session: Session,
    operator_id: int,
    task_type_id: int | None = None,
    artifacts: dict[str, Any] | None = None,
) -> StateSnapshot:
    """Retrieve or compute dynamic operator state from database."""
    # Query all historical tasks for this operator with joined relations
    instances = (
        session.query(TaskInstance)
        .join(TaskCatalog, TaskInstance.task_type_id == TaskCatalog.id)
        .join(Machine, TaskInstance.machine_id == Machine.id)
        .filter(TaskInstance.operator_id == operator_id)
        .order_by(TaskInstance.completed_at.asc())
        .all()
    )

    return compute_ewma_state_from_instances(
        operator_id=operator_id,
        instances=instances,
        task_type_id=task_type_id,
        artifacts=artifacts,
    )
