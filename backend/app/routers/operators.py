"""API router for operator endpoints: list, dynamic state, and history."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.models import Machine, Operator, TaskCatalog, TaskInstance
from app.db.session import get_db
from app.deviation_engine.deviation import compute_deviation
from app.operator_state.state import get_operator_state
from app.schemas.operators import (
    OperatorHistoryResponse,
    OperatorStateResponse,
    OperatorSummary,
    TaskHistoryItem,
)

router = APIRouter(prefix="/operators", tags=["operators"])


@router.get("", response_model=list[OperatorSummary])
def list_operators(
    db: Annotated[Session, Depends(get_db)],
) -> list[OperatorSummary]:
    """Retrieve all operators with their dynamic EWMA state summary."""
    operators = db.query(Operator).order_by(Operator.id).all()
    results: list[OperatorSummary] = []

    for op in operators:
        state = get_operator_state(db, op.id)
        results.append(
            OperatorSummary(
                id=op.id,
                name=op.name,
                legacy_skill_tier=op.skill_tier,
                composite_score=state.composite_score,
                derived_label=state.derived_label,
                trend_direction=state.trend_direction,
                confidence=state.confidence,
                sample_count=state.sample_count,
                is_synthetic=op.is_synthetic,
            )
        )

    return results


@router.get("/{operator_id}/state", response_model=OperatorStateResponse)
def get_operator_state_endpoint(
    operator_id: int,
    db: Annotated[Session, Depends(get_db)],
    task_type_id: int | None = Query(None, description="Optional task type filter"),
) -> OperatorStateResponse:
    """Retrieve dynamic EWMA state and 5 dimension scores for an operator."""
    operator = db.query(Operator).filter(Operator.id == operator_id).first()
    if not operator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operator with id {operator_id} not found",
        )

    state = get_operator_state(db, operator_id, task_type_id=task_type_id)
    return OperatorStateResponse(
        operator_id=state.operator_id,
        task_type_id=state.task_type_id,
        efficiency_score=state.efficiency_score,
        idling_score=state.idling_score,
        duration_score=state.duration_score,
        load_cycle_score=state.load_cycle_score,
        safety_score=state.safety_score,
        composite_score=state.composite_score,
        trend_direction=state.trend_direction,
        confidence=state.confidence,
        derived_label=state.derived_label,
        sample_count=state.sample_count,
        is_synthetic=True,
    )


@router.get("/{operator_id}/history", response_model=OperatorHistoryResponse)
def get_operator_history(
    operator_id: int,
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(50, ge=1, le=500, description="Max history items to return"),
) -> OperatorHistoryResponse:
    """Retrieve chronological task history with standardized deviations for an operator."""
    operator = db.query(Operator).filter(Operator.id == operator_id).first()
    if not operator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operator with id {operator_id} not found",
        )

    instances = (
        db.query(TaskInstance)
        .join(TaskCatalog, TaskInstance.task_type_id == TaskCatalog.id)
        .join(Machine, TaskInstance.machine_id == Machine.id)
        .filter(TaskInstance.operator_id == operator_id)
        .order_by(TaskInstance.completed_at.desc())
        .limit(limit)
        .all()
    )

    history_items: list[TaskHistoryItem] = []
    for inst in instances:
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

        history_items.append(
            TaskHistoryItem(
                task_instance_id=inst.id,
                task_type=inst.task_type.name,
                machine_name=inst.machine.name,
                weather=inst.weather,
                completed_at=inst.completed_at,
                duration_minutes=inst.duration_minutes,
                idle_seconds=inst.idle_seconds,
                load_cycles=inst.load_cycles,
                efficiency_score=inst.efficiency_score,
                seatbelt_engaged=inst.seatbelt_engaged,
                min_proximity_distance=inst.min_proximity_distance,
                d_cycle_efficiency=dev.d_cycle_efficiency,
                d_idling=dev.d_idling,
                d_duration=dev.d_duration,
                d_load_cycle=dev.d_load_cycle,
                d_safety=dev.d_safety,
                composite_magnitude=dev.composite_magnitude,
                is_synthetic=True,
            )
        )

    return OperatorHistoryResponse(
        operator_id=operator.id,
        operator_name=operator.name,
        total_tasks=len(history_items),
        history=history_items,
        is_synthetic=True,
    )
