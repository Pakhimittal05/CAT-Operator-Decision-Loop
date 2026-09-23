"""Unified Incident Events and Safety Evaluation API Router (§C, §13, §B).

Endpoints:
  - GET  /incidents: Retrieve incident events with filtering and pagination
  - POST /incidents: Log a manual safety incident event
  - GET  /incidents/stats: Aggregate incident statistics by severity and source
  - POST /safety/evaluate-task/{task_id}: Evaluate task against safety rules
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.models import IncidentEvent, Machine, Operator, TaskInstance
from app.db.session import get_db
from app.safety.incident_service import IncidentService
from app.schemas.incidents import (
    IncidentCreateRequest,
    IncidentListResponse,
    IncidentResponse,
    IncidentStatsResponse,
    TaskSafetyEvaluationResponse,
)

router = APIRouter(tags=["incidents"])


def _to_incident_response(inc: IncidentEvent) -> IncidentResponse:
    """Format an ORM IncidentEvent to IncidentResponse schema with joined names."""
    return IncidentResponse(
        id=inc.id,
        operator_id=inc.operator_id,
        operator_name=inc.operator.name if inc.operator else f"Operator #{inc.operator_id}",
        machine_id=inc.machine_id,
        machine_name=inc.machine.name if inc.machine else None,
        task_instance_id=inc.task_instance_id,
        source=inc.source,
        severity=inc.severity,
        description=inc.description,
        created_at=inc.created_at,
        is_synthetic=True,
    )


@router.get("/incidents", response_model=IncidentListResponse)
def get_incidents(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=500, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    source: Optional[str] = Query(None, description="Filter by source (seatbelt, proximity, manual)"),
    severity: Optional[str] = Query(None, description="Filter by severity (critical, high, medium, low)"),
    operator_id: Optional[int] = Query(None, description="Filter by operator ID"),
) -> IncidentListResponse:
    """Retrieve the unified incident feed timeline."""
    incidents, total_count = IncidentService.get_incidents(
        db=db,
        limit=limit,
        offset=offset,
        source=source,
        severity=severity,
        operator_id=operator_id,
    )

    items = [_to_incident_response(inc) for inc in incidents]
    return IncidentListResponse(incidents=items, total_count=total_count, is_synthetic=True)


@router.post("/incidents", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
def create_manual_incident(
    payload: IncidentCreateRequest,
    db: Session = Depends(get_db),
) -> IncidentResponse:
    """Manually log a safety or operational incident event."""
    op = db.query(Operator).filter(Operator.id == payload.operator_id).first()
    if not op:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operator #{payload.operator_id} not found.",
        )

    if payload.machine_id:
        mach = db.query(Machine).filter(Machine.id == payload.machine_id).first()
        if not mach:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Machine #{payload.machine_id} not found.",
            )

    if payload.task_instance_id:
        task = db.query(TaskInstance).filter(TaskInstance.id == payload.task_instance_id).first()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task instance #{payload.task_instance_id} not found.",
            )

    try:
        incident = IncidentService.log_incident(
            db=db,
            operator_id=payload.operator_id,
            source=payload.source,
            severity=payload.severity,
            description=payload.description,
            machine_id=payload.machine_id,
            task_instance_id=payload.task_instance_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    return _to_incident_response(incident)


@router.get("/incidents/stats", response_model=IncidentStatsResponse)
def get_incident_stats(db: Session = Depends(get_db)) -> IncidentStatsResponse:
    """Aggregate statistics for unified incident events."""
    stats = IncidentService.get_incident_statistics(db)
    return IncidentStatsResponse(**stats)


@router.post("/safety/evaluate-task/{task_id}", response_model=TaskSafetyEvaluationResponse)
def evaluate_task_safety(
    task_id: int,
    db: Session = Depends(get_db),
) -> TaskSafetyEvaluationResponse:
    """Evaluate task telemetry against deterministic seatbelt and proximity rules."""
    task = db.query(TaskInstance).filter(TaskInstance.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task instance #{task_id} not found.",
        )

    incidents = IncidentService.evaluate_task_instance(db, task, auto_commit=True)
    items = [_to_incident_response(inc) for inc in incidents]

    seatbelt_ok = bool(task.seatbelt_engaged)
    # Check if proximity satisfies safe buffer for machine
    safe_buffer = (
        task.machine.machine_type
        if task.machine
        else None
    )
    from app.safety.proximity import get_safe_distance_for_machine
    safe_dist = get_safe_distance_for_machine(safe_buffer)
    proximity_ok = bool(task.min_proximity_distance >= safe_dist)

    return TaskSafetyEvaluationResponse(
        task_instance_id=task.id,
        seatbelt_ok=seatbelt_ok,
        proximity_ok=proximity_ok,
        violations_count=len(items),
        incidents=items,
        is_synthetic=True,
    )
