"""Pydantic schemas for dashboard endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DailyTaskItem(BaseModel):
    """A task instance displayed on the dashboard."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    operator_id: int
    operator_name: str
    machine_name: str
    task_type: str
    weather: str
    completed_at: datetime
    duration_minutes: float
    idle_seconds: float
    load_cycles: int
    efficiency_score: float
    seatbelt_engaged: bool
    min_proximity_distance: float
    status: str = "Completed"
    is_synthetic: bool = True


class SafetyComplianceSummary(BaseModel):
    """Aggregate safety indicators for the dashboard view."""

    total_tasks: int
    seatbelt_compliance_pct: float = Field(..., ge=0.0, le=100.0)
    proximity_safe_pct: float = Field(..., ge=0.0, le=100.0)
    safety_violations_count: int
    is_synthetic: bool = True


class DashboardDailyTasksResponse(BaseModel):
    """Response payload for GET /dashboard/daily-tasks."""

    tasks: list[DailyTaskItem]
    compliance: SafetyComplianceSummary
    total_count: int
    is_synthetic: bool = True
