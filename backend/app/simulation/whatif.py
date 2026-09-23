"""What-If Simulation Engine (§12).

Connects:
  - Operator dynamic EWMA performance state
  - Task-time Gradient Boosting prediction model (Point, P10, P90)
  - Skill fit & Safety risk assessment models
  - Probabilistic explainability attribution ("Probable Contributing Factors")
  - SQLite predictions table persistence (ready for Phase 7 feedback loop)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import Machine, Operator, Prediction, TaskCatalog
from app.operator_state.state import get_operator_state
from app.prediction.risk_model import assess_risk_and_fit
from app.prediction.task_time_model import (
    PredictionResult,
    load_task_time_artifacts,
    predict_task_time,
)
from app.schemas.simulate import ContributingFactor, SimulationResponse

ALLOWED_WEATHER = {"Clear", "Rain", "Mud", "Snow/Ice"}


def run_whatif_simulation(
    session: Session,
    operator_id: int,
    machine_id: int,
    task_type_id: int,
    weather: str,
    artifacts: dict[str, Any] | None = None,
) -> SimulationResponse:
    """Execute a What-If task simulation and persist to SQLite predictions table."""
    # ── 1. Validation ────────────────────────────────────────────────────────
    if weather not in ALLOWED_WEATHER:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid weather '{weather}'. Allowed values: {sorted(ALLOWED_WEATHER)}",
        )

    operator = session.query(Operator).filter(Operator.id == operator_id).first()
    if not operator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operator with ID {operator_id} not found.",
        )

    machine = session.query(Machine).filter(Machine.id == machine_id).first()
    if not machine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Machine with ID {machine_id} not found.",
        )

    task_type = session.query(TaskCatalog).filter(TaskCatalog.id == task_type_id).first()
    if not task_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task type with ID {task_type_id} not found in catalog.",
        )

    # ── 2. Retrieve dynamic operator state (reusing shared intelligence) ──
    overall_state = get_operator_state(session, operator_id)

    # Try task-specific state for skill fit; fallback to overall if unobserved on this task
    task_state = get_operator_state(session, operator_id, task_type_id=task_type_id)
    relevant_skill_score = (
        task_state.composite_score if task_state.sample_count > 0 else overall_state.composite_score
    )

    # ── 3. Assemble prediction features ──────────────────────────────────────
    feature_row = {
        "operator_composite_score": overall_state.composite_score,
        "operator_duration_score": overall_state.duration_score,
        "operator_efficiency_score": overall_state.efficiency_score,
        "operator_confidence": overall_state.confidence,
        "baseline_duration_minutes": task_type.baseline_duration_minutes,
        "task_difficulty": task_type.difficulty,
        "machine_age_years": machine.age_years,
        "machine_wear_factor": machine.wear_factor,
        "task_type": task_type.name,
        "machine_type": machine.machine_type,
        "weather": weather,
    }

    # ── 4. Predict duration with uncertainty ────────────────────────────────
    pred_res: PredictionResult = predict_task_time(feature_row, artifacts=artifacts)

    # ── 5. Assess Skill Fit, Safety Risk & Training Trigger ──────────────────
    risk_res = assess_risk_and_fit(
        operator_score=relevant_skill_score,
        operator_safety_score=overall_state.safety_score,
        machine_wear=machine.wear_factor,
        task_difficulty=task_type.difficulty,
        weather=weather,
    )

    # ── 6. Persist to predictions table for Phase 7 feedback loop ───────────
    prediction_record = Prediction(
        task_instance_id=None,  # Not executed yet; linked after Process B outcome
        operator_id=operator.id,
        machine_id=machine.id,
        task_type_id=task_type.id,
        weather=weather,
        predicted_duration=pred_res.predicted_duration,
        p10=pred_res.p10,
        p90=pred_res.p90,
        risk_score=risk_res.safety_risk_score,
        skill_fit=risk_res.skill_fit_score,
        training_flag=risk_res.training_recommended,
        created_at=datetime.now(timezone.utc),
    )
    session.add(prediction_record)
    session.commit()
    session.refresh(prediction_record)

    factors = [
        ContributingFactor(
            factor_name=f["factor_name"],
            impact_direction=f["impact_direction"],
            impact_percentage=f["impact_percentage"],
            confidence=f["confidence"],
            description=f["description"],
        )
        for f in pred_res.probable_factors
    ]

    return SimulationResponse(
        prediction_id=prediction_record.id,
        operator_id=operator.id,
        operator_name=operator.name,
        machine_id=machine.id,
        machine_name=machine.name,
        task_type_id=task_type.id,
        task_type_name=task_type.name,
        weather=weather,
        predicted_duration_minutes=pred_res.predicted_duration,
        p10_minutes=pred_res.p10,
        p90_minutes=pred_res.p90,
        uncertainty_range_minutes=pred_res.uncertainty_range,
        skill_fit_score=risk_res.skill_fit_score,
        skill_fit_label=risk_res.skill_fit_label,
        safety_risk_score=risk_res.safety_risk_score,
        safety_risk_level=risk_res.safety_risk_level,
        training_recommended=risk_res.training_recommended,
        training_reason=risk_res.training_reason,
        probable_factors=factors,
        is_synthetic=True,
        created_at=prediction_record.created_at.isoformat(),
    )
