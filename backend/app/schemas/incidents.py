"""Pydantic schemas for Incident Events and Safety Evaluation (§C, §13, §B)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

IncidentSource = Literal["seatbelt", "proximity", "deviation_anomaly", "manual"]
IncidentSeverity = Literal["low", "medium", "high", "critical"]


class IncidentCreateRequest(BaseModel):
    """Payload to log a manual safety or operations incident."""

    operator_id: int = Field(..., description="ID of the operator involved")
    machine_id: Optional[int] = Field(None, description="Optional ID of the machine involved")
    task_instance_id: Optional[int] = Field(None, description="Optional ID of associated task")
    source: IncidentSource = Field("manual", description="Incident source category")
    severity: IncidentSeverity = Field("medium", description="Severity classification")
    description: str = Field(..., min_length=3, max_length=500, description="Description of the incident")


class IncidentResponse(BaseModel):
    """Detailed unified incident event object."""

    id: int
    operator_id: int
    operator_name: str
    machine_id: Optional[int] = None
    machine_name: Optional[str] = None
    task_instance_id: Optional[int] = None
    source: str
    severity: str
    description: Optional[str] = None
    created_at: datetime
    is_synthetic: bool = True

    model_config = {"from_attributes": True}


class IncidentListResponse(BaseModel):
    """Paginated list of unified incident events."""

    incidents: list[IncidentResponse]
    total_count: int
    is_synthetic: bool = True


class IncidentStatsResponse(BaseModel):
    """Aggregate safety and incident statistics."""

    total_incidents: int
    by_severity: dict[str, int]
    by_source: dict[str, int]
    is_synthetic: bool = True


class TaskSafetyEvaluationResponse(BaseModel):
    """Outcome of evaluating a task against deterministic safety rules."""

    task_instance_id: int
    seatbelt_ok: bool
    proximity_ok: bool
    violations_count: int
    incidents: list[IncidentResponse]
    is_synthetic: bool = True
