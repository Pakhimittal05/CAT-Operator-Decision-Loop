"""API router for dashboard views: daily tasks and safety compliance summary."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Machine, Operator, TaskCatalog, TaskInstance
from app.db.session import get_db
from app.schemas.dashboard import (
    DailyTaskItem,
    DashboardDailyTasksResponse,
    SafetyComplianceSummary,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/daily-tasks", response_model=DashboardDailyTasksResponse)
def get_daily_tasks(
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(25, ge=1, le=200, description="Number of recent tasks to display"),
) -> DashboardDailyTasksResponse:
    """Retrieve daily tasks feed along with site safety compliance summary."""
    # Query most recent completed tasks joined with entities
    tasks_query = (
        db.query(TaskInstance)
        .join(Operator, TaskInstance.operator_id == Operator.id)
        .join(Machine, TaskInstance.machine_id == Machine.id)
        .join(TaskCatalog, TaskInstance.task_type_id == TaskCatalog.id)
        .order_by(TaskInstance.completed_at.desc())
    )

    total_count = tasks_query.count()
    recent_tasks = tasks_query.limit(limit).all()

    items: list[DailyTaskItem] = []
    seatbelt_ok = 0
    proximity_ok = 0
    violations_count = 0

    safe_dist = settings.proximity_safe_distance_meters

    for t in recent_tasks:
        is_seatbelt_ok = bool(t.seatbelt_engaged)
        is_prox_ok = bool(t.min_proximity_distance >= safe_dist)

        if is_seatbelt_ok:
            seatbelt_ok += 1
        else:
            violations_count += 1

        if is_prox_ok:
            proximity_ok += 1
        else:
            violations_count += 1

        items.append(
            DailyTaskItem(
                id=t.id,
                operator_id=t.operator_id,
                operator_name=t.operator.name,
                machine_name=t.machine.name,
                task_type=t.task_type.name,
                weather=t.weather,
                completed_at=t.completed_at,
                duration_minutes=t.duration_minutes,
                idle_seconds=t.idle_seconds,
                load_cycles=t.load_cycles,
                efficiency_score=t.efficiency_score,
                seatbelt_engaged=t.seatbelt_engaged,
                min_proximity_distance=t.min_proximity_distance,
                status="Completed",
                is_synthetic=True,
            )
        )

    n = len(recent_tasks)
    seatbelt_pct = round((seatbelt_ok / n * 100.0), 1) if n > 0 else 100.0
    prox_pct = round((proximity_ok / n * 100.0), 1) if n > 0 else 100.0

    compliance = SafetyComplianceSummary(
        total_tasks=n,
        seatbelt_compliance_pct=seatbelt_pct,
        proximity_safe_pct=prox_pct,
        safety_violations_count=violations_count,
        is_synthetic=True,
    )

    return DashboardDailyTasksResponse(
        tasks=items,
        compliance=compliance,
        total_count=total_count,
        is_synthetic=True,
    )
