"""Pydantic schemas for operator-related endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OperatorSummary(BaseModel):
    """Summary item for operator list view."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    legacy_skill_tier: str
    composite_score: float = Field(..., ge=0.0, le=100.0)
    derived_label: str
    trend_direction: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    sample_count: int
    is_synthetic: bool = True


class OperatorStateResponse(BaseModel):
    """Detailed dynamic operator state with all 5 dimension scores."""

    model_config = ConfigDict(from_attributes=True)

    operator_id: int
    task_type_id: int | None = None
    efficiency_score: float = Field(..., ge=0.0, le=100.0)
    idling_score: float = Field(..., ge=0.0, le=100.0)
    duration_score: float = Field(..., ge=0.0, le=100.0)
    load_cycle_score: float = Field(..., ge=0.0, le=100.0)
    safety_score: float = Field(..., ge=0.0, le=100.0)
    composite_score: float = Field(..., ge=0.0, le=100.0)
    trend_direction: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    derived_label: str
    sample_count: int
    is_synthetic: bool = True


class TaskHistoryItem(BaseModel):
    """An executed task instance with telemetry and standardized deviations."""

    model_config = ConfigDict(from_attributes=True)

    task_instance_id: int
    task_type: str
    machine_name: str
    weather: str
    completed_at: datetime
    duration_minutes: float
    idle_seconds: float
    load_cycles: int
    efficiency_score: float
    seatbelt_engaged: bool
    min_proximity_distance: float
    d_cycle_efficiency: float
    d_idling: float
    d_duration: float
    d_load_cycle: float
    d_safety: float
    composite_magnitude: float
    is_synthetic: bool = True


class OperatorHistoryResponse(BaseModel):
    """Response containing an operator's chronological task history."""

    operator_id: int
    operator_name: str
    total_tasks: int
    history: list[TaskHistoryItem]
    is_synthetic: bool = True
