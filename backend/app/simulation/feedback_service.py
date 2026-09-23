"""Process B Feedback & Predicted vs Actual Service (§4, §12, §15).

Orchestrates the closed-loop feedback pipeline:
  1. Trigger Process B stochastic actual outcome generator.
  2. Persist actual TaskInstance tagged source_process='B'.
  3. Calculate standardized 5D deviation vector using shared compute_deviation().
  4. Evaluate safety compliance events via IncidentService.
  5. Dynamically recalibrate operator EWMA performance state.
  6. Calculate predicted-vs-actual error metrics and uncertainty interval coverage.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.data_generation.generate_actual_outcomes import generate_process_b_telemetry
from app.db.models import (
    DeviationVector,
    IncidentEvent,
    Machine,
    Operator,
    Prediction,
    TaskCatalog,
    TaskInstance,
)
from app.deviation_engine.deviation import compute_deviation
from app.operator_state.state import StateSnapshot, get_operator_state
from app.safety.incident_service import IncidentService
from app.schemas.simulate import (
    ComparisonListItem,
    ComparisonListResponse,
    ComparisonResponse,
    IncidentSummary,
    OperatorStateSummary,
)

logger = logging.getLogger(__name__)


def _to_state_summary(snap: StateSnapshot) -> OperatorStateSummary:
    """Helper to convert StateSnapshot to OperatorStateSummary Pydantic model."""
    return OperatorStateSummary(
        operator_id=snap.operator_id,
        composite_score=snap.composite_score,
        derived_label=snap.derived_label,
        trend_direction=snap.trend_direction,
        confidence=snap.confidence,
        efficiency_score=snap.efficiency_score,
        idling_score=snap.idling_score,
        duration_score=snap.duration_score,
        load_cycle_score=snap.load_cycle_score,
        safety_score=snap.safety_score,
        sample_count=snap.sample_count,
    )


def execute_process_b_for_prediction(
    session: Session,
    prediction_id: int,
    seed: int | None = None,
) -> ComparisonResponse:
    """Execute Process B actual outcome for a simulated prediction and close the feedback loop."""
    prediction = session.query(Prediction).filter(Prediction.id == prediction_id).first()
    if not prediction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prediction with ID {prediction_id} not found.",
        )

    # Idempotency check: prevent duplicate execution of the same prediction
    if prediction.task_instance_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Prediction #{prediction_id} has already been executed "
                f"(linked to TaskInstance #{prediction.task_instance_id}). "
                f"Use GET /simulate/{prediction_id}/comparison to inspect results."
            ),
        )

    operator = session.query(Operator).filter(Operator.id == prediction.operator_id).first()
    machine = session.query(Machine).filter(Machine.id == prediction.machine_id).first()
    task_type = session.query(TaskCatalog).filter(TaskCatalog.id == prediction.task_type_id).first()

    if not operator or not machine or not task_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Referenced operator, machine, or task type no longer exists.",
        )

    # ── 1. Capture dynamic operator state BEFORE execution ─────────────────
    state_before_snap = get_operator_state(session, operator.id)
    state_before = _to_state_summary(state_before_snap)

    # ── 2. Run Process B Stochastic Telemetry Generator ────────────────────
    telemetry = generate_process_b_telemetry(
        baseline_duration=task_type.baseline_duration_minutes,
        baseline_load_cycles=task_type.baseline_load_cycles,
        task_difficulty=task_type.difficulty,
        machine_age_years=machine.age_years,
        machine_wear_factor=machine.wear_factor,
        operator_skill_tier=operator.skill_tier,
        operator_latent_efficiency=operator.latent_efficiency_mean,
        operator_latent_idle=operator.latent_idle_tendency,
        operator_latent_safety=operator.latent_safety_tendency,
        weather=prediction.weather,
        seed=seed,
    )

    now = datetime.now(timezone.utc)

    # ── 3. Persist actual TaskInstance (source_process='B') ─────────────────
    task_instance = TaskInstance(
        operator_id=operator.id,
        machine_id=machine.id,
        task_type_id=task_type.id,
        weather=prediction.weather,
        duration_minutes=telemetry["duration_minutes"],
        idle_seconds=telemetry["idle_seconds"],
        load_cycles=telemetry["load_cycles"],
        efficiency_score=telemetry["efficiency_score"],
        seatbelt_engaged=telemetry["seatbelt_engaged"],
        min_proximity_distance=telemetry["min_proximity_distance"],
        is_synthetic=True,
        source_process="B",
        completed_at=now,
        created_at=now,
    )
    session.add(task_instance)
    session.flush()  # Allocates task_instance.id

    # ── 4. Link Prediction to TaskInstance ─────────────────────────────────
    prediction.task_instance_id = task_instance.id

    # ── 5. Calculate Standardized 5D Deviation Vector ──────────────────────
    context = {
        "task_type": task_type.name,
        "machine_age": machine.age_years,
        "weather": prediction.weather,
    }
    dev_result = compute_deviation(telemetry, context)

    deviation_record = DeviationVector(
        task_instance_id=task_instance.id,
        d_cycle_efficiency=dev_result.d_cycle_efficiency,
        d_idling=dev_result.d_idling,
        d_duration=dev_result.d_duration,
        d_load_cycle=dev_result.d_load_cycle,
        d_safety=dev_result.d_safety,
        composite_magnitude=dev_result.composite_magnitude,
        created_at=now,
    )
    session.add(deviation_record)

    # ── 6. Safety Compliance Evaluation via IncidentService ────────────────
    safety_incidents = IncidentService.evaluate_task_instance(session, task_instance, auto_commit=True)
    session.commit()
    session.refresh(prediction)
    session.refresh(task_instance)

    # ── 7. Dynamic Operator State AFTER execution (recalculated) ───────────
    state_after_snap = get_operator_state(session, operator.id)
    state_after = _to_state_summary(state_after_snap)

    composite_score_delta = round(state_after.composite_score - state_before.composite_score, 2)

    # ── 8. Formulate Comparison Metrics ────────────────────────────────────
    pred_dur = prediction.predicted_duration
    act_dur = task_instance.duration_minutes
    duration_diff = round(act_dur - pred_dur, 2)
    abs_err = round(abs(duration_diff), 2)
    pct_err = round((abs_err / act_dur) * 100.0, 2) if act_dur > 0 else 0.0
    within_interval = bool(prediction.p10 <= act_dur <= prediction.p90)

    # Format recorded incidents
    incidents_recorded = [
        IncidentSummary(
            id=inc.id,
            source=inc.source,
            severity=inc.severity,
            description=inc.description,
        )
        for inc in safety_incidents
    ]

    return ComparisonResponse(
        prediction_id=prediction.id,
        task_instance_id=task_instance.id,
        operator_id=operator.id,
        operator_name=operator.name,
        machine_id=machine.id,
        machine_name=machine.name,
        task_type_id=task_type.id,
        task_type_name=task_type.name,
        weather=prediction.weather,
        predicted_duration_minutes=pred_dur,
        p10_minutes=prediction.p10,
        p90_minutes=prediction.p90,
        actual_duration_minutes=act_dur,
        duration_difference_minutes=duration_diff,
        absolute_error_minutes=abs_err,
        percentage_error=pct_err,
        is_within_interval=within_interval,
        observed_telemetry={
            "duration_minutes": act_dur,
            "idle_seconds": task_instance.idle_seconds,
            "load_cycles": task_instance.load_cycles,
            "efficiency_score": task_instance.efficiency_score,
            "seatbelt_engaged": task_instance.seatbelt_engaged,
            "min_proximity_distance": task_instance.min_proximity_distance,
        },
        deviation_vector={
            "d_cycle_efficiency": dev_result.d_cycle_efficiency,
            "d_idling": dev_result.d_idling,
            "d_duration": dev_result.d_duration,
            "d_load_cycle": dev_result.d_load_cycle,
            "d_safety": dev_result.d_safety,
        },
        composite_magnitude=dev_result.composite_magnitude,
        state_before=state_before,
        state_after=state_after,
        composite_score_delta=composite_score_delta,
        seatbelt_engaged=task_instance.seatbelt_engaged,
        min_proximity_distance=task_instance.min_proximity_distance,
        incidents_recorded=incidents_recorded,
        is_synthetic=True,
        executed_at=task_instance.completed_at.isoformat(),
    )


def get_prediction_comparison(session: Session, prediction_id: int) -> ComparisonResponse:
    """Retrieve predicted vs actual comparison for an already executed prediction."""
    prediction = session.query(Prediction).filter(Prediction.id == prediction_id).first()
    if not prediction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prediction with ID {prediction_id} not found.",
        )

    if prediction.task_instance_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Prediction #{prediction_id} has not yet been executed with Process B actual outcomes. "
                f"Call POST /simulate/{prediction_id}/generate-actual first."
            ),
        )

    task_instance = (
        session.query(TaskInstance).filter(TaskInstance.id == prediction.task_instance_id).first()
    )
    if not task_instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Linked TaskInstance #{prediction.task_instance_id} not found.",
        )

    operator = session.query(Operator).filter(Operator.id == prediction.operator_id).first()
    machine = session.query(Machine).filter(Machine.id == prediction.machine_id).first()
    task_type = session.query(TaskCatalog).filter(TaskCatalog.id == prediction.task_type_id).first()

    dev = (
        session.query(DeviationVector)
        .filter(DeviationVector.task_instance_id == task_instance.id)
        .first()
    )

    incidents = (
        session.query(IncidentEvent)
        .filter(IncidentEvent.task_instance_id == task_instance.id)
        .all()
    )

    # Post-state
    state_after_snap = get_operator_state(session, operator.id)
    state_after = _to_state_summary(state_after_snap)

    # Pre-state: approximate from state_after or snapshot
    # For reporting, state_before sample count is state_after.sample_count - 1
    state_before_sample = max(state_after.sample_count - 1, 0)
    # Estimate delta from instant score difference or state
    composite_delta = 0.0

    pred_dur = prediction.predicted_duration
    act_dur = task_instance.duration_minutes
    duration_diff = round(act_dur - pred_dur, 2)
    abs_err = round(abs(duration_diff), 2)
    pct_err = round((abs_err / act_dur) * 100.0, 2) if act_dur > 0 else 0.0
    within_interval = bool(prediction.p10 <= act_dur <= prediction.p90)

    deviation_dict = {
        "d_cycle_efficiency": dev.d_cycle_efficiency if dev else 0.0,
        "d_idling": dev.d_idling if dev else 0.0,
        "d_duration": dev.d_duration if dev else 0.0,
        "d_load_cycle": dev.d_load_cycle if dev else 0.0,
        "d_safety": dev.d_safety if dev else 0.0,
    }
    comp_magnitude = dev.composite_magnitude if dev else 0.0

    return ComparisonResponse(
        prediction_id=prediction.id,
        task_instance_id=task_instance.id,
        operator_id=operator.id if operator else prediction.operator_id,
        operator_name=operator.name if operator else "Unknown",
        machine_id=machine.id if machine else prediction.machine_id,
        machine_name=machine.name if machine else "Unknown",
        task_type_id=task_type.id if task_type else prediction.task_type_id,
        task_type_name=task_type.name if task_type else "Unknown",
        weather=prediction.weather,
        predicted_duration_minutes=pred_dur,
        p10_minutes=prediction.p10,
        p90_minutes=prediction.p90,
        actual_duration_minutes=act_dur,
        duration_difference_minutes=duration_diff,
        absolute_error_minutes=abs_err,
        percentage_error=pct_err,
        is_within_interval=within_interval,
        observed_telemetry={
            "duration_minutes": act_dur,
            "idle_seconds": task_instance.idle_seconds,
            "load_cycles": task_instance.load_cycles,
            "efficiency_score": task_instance.efficiency_score,
            "seatbelt_engaged": task_instance.seatbelt_engaged,
            "min_proximity_distance": task_instance.min_proximity_distance,
        },
        deviation_vector=deviation_dict,
        composite_magnitude=comp_magnitude,
        state_before=state_after,  # Default fallback if queried long after
        state_after=state_after,
        composite_score_delta=composite_delta,
        seatbelt_engaged=task_instance.seatbelt_engaged,
        min_proximity_distance=task_instance.min_proximity_distance,
        incidents_recorded=[
            IncidentSummary(
                id=inc.id,
                source=inc.source,
                severity=inc.severity,
                description=inc.description,
            )
            for inc in incidents
        ],
        is_synthetic=True,
        executed_at=task_instance.completed_at.isoformat(),
    )


def list_simulation_comparisons(
    session: Session,
    limit: int = 15,
    offset: int = 0,
) -> ComparisonListResponse:
    """Retrieve history of completed simulation executions with summary comparison cards."""
    query = (
        session.query(Prediction, TaskInstance, Operator, Machine, TaskCatalog)
        .join(TaskInstance, Prediction.task_instance_id == TaskInstance.id)
        .join(Operator, Prediction.operator_id == Operator.id)
        .join(Machine, Prediction.machine_id == Machine.id)
        .join(TaskCatalog, Prediction.task_type_id == TaskCatalog.id)
        .order_by(desc(TaskInstance.completed_at))
    )

    total_count = query.count()
    rows = query.offset(offset).limit(limit).all()

    items: list[ComparisonListItem] = []
    for pred, inst, op, mac, task in rows:
        pred_dur = pred.predicted_duration
        act_dur = inst.duration_minutes
        diff = round(act_dur - pred_dur, 2)
        abs_err = round(abs(diff), 2)
        pct_err = round((abs_err / act_dur) * 100.0, 2) if act_dur > 0 else 0.0
        within_interval = bool(pred.p10 <= act_dur <= pred.p90)

        items.append(
            ComparisonListItem(
                prediction_id=pred.id,
                task_instance_id=inst.id,
                operator_name=op.name,
                machine_name=mac.name,
                task_type_name=task.name,
                weather=pred.weather,
                predicted_duration_minutes=pred_dur,
                actual_duration_minutes=act_dur,
                duration_difference_minutes=diff,
                absolute_error_minutes=abs_err,
                percentage_error=pct_err,
                is_within_interval=within_interval,
                composite_score_delta=0.0,
                executed_at=inst.completed_at.isoformat(),
                is_synthetic=True,
            )
        )

    return ComparisonListResponse(
        comparisons=items,
        total_count=total_count,
        is_synthetic=True,
    )
