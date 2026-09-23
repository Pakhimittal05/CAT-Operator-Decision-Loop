"""Statistical Anomaly Detection Engine (§11).

Evaluates task performance telemetry against reference expectations using the
shared deviation engine (compute_deviation). Classifies anomalies using statistical
thresholds, ranks Probable Contributing Factors, and strictly avoids causal claims
per project design principles.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.db.models import IncidentEvent, Machine, Operator, TaskCatalog, TaskInstance
from app.deviation_engine.deviation import DeviationResult, compute_deviation

logger = logging.getLogger("cat_decision_loop.anomaly")

# Anomaly threshold constants
COMPOSITE_ANOMALY_THRESHOLD: float = 2.0  # Composite magnitude >= 2.0 triggers anomaly
SINGLE_DIM_ANOMALY_THRESHOLD: float = 2.5  # Any |z| >= 2.5 triggers anomaly

DIMENSION_DISPLAY_NAMES: dict[str, str] = {
    "cycle_efficiency": "Cycle Efficiency",
    "idling": "Idling Duration",
    "duration": "Task Completion Time",
    "load_cycle": "Load Cycle Frequency",
    "safety": "Proximity Margin",
}


@dataclass(frozen=True)
class FactorAttribution:
    """Probable contributing dimension with attribution metrics."""

    dimension: str
    display_name: str
    z_score: float
    abs_z: float
    contribution_weight_pct: float
    description: str


@dataclass(frozen=True)
class AnomalyEvaluation:
    """Outcome of statistical anomaly evaluation on a deviation vector."""

    is_anomaly: bool
    composite_magnitude: float
    severity: Optional[str]  # medium | high | critical | None
    observed_pattern: str
    probable_factors: list[FactorAttribution]
    is_synthetic: bool = True


def evaluate_deviation_anomaly(
    deviation: DeviationResult,
    threshold: float = COMPOSITE_ANOMALY_THRESHOLD,
    single_dim_threshold: float = SINGLE_DIM_ANOMALY_THRESHOLD,
) -> AnomalyEvaluation:
    """Evaluate deviation vector for statistical anomalies without database side-effects.

    Parameters:
        deviation: Output from compute_deviation().
        threshold: Minimum composite magnitude to qualify as an anomaly.
        single_dim_threshold: Minimum absolute single z-score to qualify as an anomaly.

    Returns:
        AnomalyEvaluation with severity and non-causal probable contributing factors.
    """
    comp_mag = round(float(deviation.composite_magnitude), 2)
    z_scores = deviation.z_scores

    max_single_abs_z = max(abs(float(z)) for z in z_scores.values()) if z_scores else 0.0

    is_anomaly = (comp_mag >= threshold) or (max_single_abs_z >= single_dim_threshold)

    if not is_anomaly:
        return AnomalyEvaluation(
            is_anomaly=False,
            composite_magnitude=comp_mag,
            severity=None,
            observed_pattern="Normal operational variance within standard reference envelope.",
            probable_factors=[],
            is_synthetic=True,
        )

    # Classify severity
    if comp_mag >= 3.0 or max_single_abs_z >= 3.5:
        severity = "critical"
    elif comp_mag >= 2.5 or max_single_abs_z >= 2.8:
        severity = "high"
    else:
        severity = "medium"

    # Compute attribution weights based on absolute deviation magnitude
    total_abs_z = sum(abs(float(z)) for z in z_scores.values())
    if total_abs_z <= 1e-6:
        total_abs_z = 1.0

    factor_list: list[FactorAttribution] = []
    for dim, z_val in z_scores.items():
        z_float = round(float(z_val), 2)
        abs_z = abs(z_float)
        weight_pct = round((abs_z / total_abs_z) * 100.0, 1)
        display_name = DIMENSION_DISPLAY_NAMES.get(dim, dim.replace("_", " ").title())

        # Construct non-causal descriptive observation
        sign_str = f"+{z_float:.2f}σ" if z_float >= 0 else f"{z_float:.2f}σ"
        if dim == "idling":
            obs_detail = (
                f"Elevated idling ({sign_str}, {weight_pct}% contribution weight) "
                f"observed during this task"
            )
        elif dim == "cycle_efficiency":
            direction = "Elevated" if z_float >= 0 else "Lower"
            obs_detail = (
                f"{direction} cycle efficiency ({sign_str}, {weight_pct}% contribution weight) "
                f"associated with task execution"
            )
        elif dim == "duration":
            direction = "Extended" if z_float >= 0 else "Compressed"
            obs_detail = (
                f"{direction} duration ({sign_str}, {weight_pct}% contribution weight) "
                f"observed relative to reference baseline"
            )
        elif dim == "load_cycle":
            direction = "Higher" if z_float >= 0 else "Lower"
            obs_detail = (
                f"{direction} load cycle count ({sign_str}, {weight_pct}% contribution weight) "
                f"recorded during task operation"
            )
        elif dim == "safety":
            direction = "Ample" if z_float >= 0 else "Constrained"
            obs_detail = (
                f"{direction} proximity margin ({sign_str}, {weight_pct}% contribution weight) "
                f"observed relative to machine buffer"
            )
        else:
            obs_detail = (
                f"{display_name} variance ({sign_str}, {weight_pct}% contribution weight) "
                f"observed during task"
            )

        factor_list.append(
            FactorAttribution(
                dimension=dim,
                display_name=display_name,
                z_score=z_float,
                abs_z=abs_z,
                contribution_weight_pct=weight_pct,
                description=obs_detail,
            )
        )

    # Rank factors by absolute magnitude (highest contribution first)
    factor_list.sort(key=lambda f: f.abs_z, reverse=True)

    # Summary pattern text using strictly non-causal phrasing
    top_factor_names = [f"{f.display_name} ({f.z_score:+.1f}σ)" for f in factor_list[:2]]
    pattern_summary = (
        f"Observed Pattern: Multi-dimensional deviation ({comp_mag:.2f}σ magnitude, {severity} severity). "
        f"Probable Contributing Factors: {', '.join(top_factor_names)}."
    )

    return AnomalyEvaluation(
        is_anomaly=True,
        composite_magnitude=comp_mag,
        severity=severity,
        observed_pattern=pattern_summary,
        probable_factors=factor_list,
        is_synthetic=True,
    )


def detect_task_anomaly(
    db: Session,
    task: TaskInstance,
    auto_commit: bool = True,
) -> tuple[bool, Optional[IncidentEvent], AnomalyEvaluation]:
    """Run anomaly detection on a TaskInstance and persist incident event if anomalous.

    Includes deduplication against existing 'deviation_anomaly' incident events
    for the same task instance.
    """
    machine_age = task.machine.age_years if task.machine else 5.0
    task_name = task.task_type.name if task.task_type else "Excavation"

    telemetry = {
        "cycle_efficiency": task.efficiency_score,
        "idling": task.idle_seconds,
        "duration": task.duration_minutes,
        "load_cycle": task.load_cycles,
        "safety": task.min_proximity_distance,
    }
    context = {
        "task_type": task_name,
        "machine_age": machine_age,
        "weather": task.weather or "sunny",
    }

    try:
        deviation = compute_deviation(telemetry, context)
    except Exception as exc:
        logger.warning("compute_deviation failed for task #%d: %s", task.id, exc)
        return (
            False,
            None,
            AnomalyEvaluation(
                is_anomaly=False,
                composite_magnitude=0.0,
                severity=None,
                observed_pattern="Reference deviation calculation unavailable.",
                probable_factors=[],
                is_synthetic=True,
            ),
        )

    evaluation = evaluate_deviation_anomaly(deviation)
    incident: Optional[IncidentEvent] = None

    if evaluation.is_anomaly and evaluation.severity:
        # Check deduplication
        existing = (
            db.query(IncidentEvent)
            .filter(
                IncidentEvent.task_instance_id == task.id,
                IncidentEvent.source == "deviation_anomaly",
            )
            .first()
        )
        if existing:
            incident = existing
        else:
            incident = IncidentEvent(
                task_instance_id=task.id,
                operator_id=task.operator_id,
                machine_id=task.machine_id,
                source="deviation_anomaly",
                severity=evaluation.severity,
                description=evaluation.observed_pattern,
                created_at=task.completed_at or datetime.now(timezone.utc),
            )
            db.add(incident)
            if auto_commit:
                db.commit()
                db.refresh(incident)

    return evaluation.is_anomaly, incident, evaluation


def get_recent_anomalies(
    db: Session,
    operator_id: Optional[int] = None,
    severity: Optional[str] = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Retrieve anomaly incident records joined with detailed factors."""
    query = db.query(IncidentEvent).filter(IncidentEvent.source == "deviation_anomaly")

    if operator_id:
        query = query.filter(IncidentEvent.operator_id == operator_id)
    if severity:
        query = query.filter(IncidentEvent.severity == severity.lower().strip())

    incidents = query.order_by(IncidentEvent.created_at.desc()).limit(limit).all()

    results: list[dict[str, Any]] = []
    for inc in incidents:
        # Re-evaluate factors from linked task if available, or build from description
        factors: list[dict[str, Any]] = []
        comp_mag = 2.0
        pattern = inc.description or "Performance deviation anomaly."

        if inc.task_instance:
            task = inc.task_instance
            m_age = task.machine.age_years if task.machine else 5.0
            t_name = task.task_type.name if task.task_type else "Excavation"
            try:
                dev = compute_deviation(
                    {
                        "cycle_efficiency": task.efficiency_score,
                        "idling": task.idle_seconds,
                        "duration": task.duration_minutes,
                        "load_cycle": task.load_cycles,
                        "safety": task.min_proximity_distance,
                    },
                    {
                        "task_type": t_name,
                        "machine_age": m_age,
                        "weather": task.weather or "sunny",
                    },
                )
                eval_res = evaluate_deviation_anomaly(dev)
                comp_mag = eval_res.composite_magnitude
                pattern = eval_res.observed_pattern
                factors = [
                    {
                        "dimension": f.dimension,
                        "z_score": f.z_score,
                        "contribution_weight_pct": f.contribution_weight_pct,
                        "description": f.description,
                    }
                    for f in eval_res.probable_factors
                ]
            except Exception:
                pass

        results.append(
            {
                "id": inc.id,
                "task_instance_id": inc.task_instance_id or 0,
                "operator_id": inc.operator_id,
                "operator_name": inc.operator.name if inc.operator else f"Operator #{inc.operator_id}",
                "machine_id": inc.machine_id,
                "machine_name": inc.machine.name if inc.machine else None,
                "composite_magnitude": comp_mag,
                "severity": inc.severity,
                "observed_pattern": pattern,
                "probable_factors": factors,
                "created_at": inc.created_at,
                "is_synthetic": True,
            }
        )

    return results
