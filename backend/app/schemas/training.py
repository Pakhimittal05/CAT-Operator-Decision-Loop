"""Pydantic schemas for Anomaly Detection, Coaching, and Training (§11, §14, §C)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

AnomalySeverity = Literal["medium", "high", "critical"]
RecommendationStatus = Literal["pending", "in_progress", "completed"]


class ProbableContributingFactor(BaseModel):
    """Ranked probable contributing dimension explaining deviation anomaly."""

    dimension: str = Field(..., description="Deviation dimension name")
    z_score: float = Field(..., description="Standardized z-score relative to global reference")
    contribution_weight_pct: float = Field(
        ..., description="Normalized contribution weight percentage (0-100%)"
    )
    description: str = Field(..., description="Non-causal descriptive observation")


class AnomalyItemResponse(BaseModel):
    """Performance deviation anomaly event."""

    id: Optional[int] = None
    task_instance_id: int
    operator_id: int
    operator_name: str
    machine_id: Optional[int] = None
    machine_name: Optional[str] = None
    composite_magnitude: float
    severity: str
    observed_pattern: str
    probable_factors: list[ProbableContributingFactor]
    created_at: datetime
    is_synthetic: bool = True

    model_config = {"from_attributes": True}


class AnomalyListResponse(BaseModel):
    """List of detected performance anomalies."""

    anomalies: list[AnomalyItemResponse]
    total_count: int
    is_synthetic: bool = True


class TaskAnomalyEvaluationResponse(BaseModel):
    """Result of running anomaly detection against a specific task instance."""

    task_instance_id: int
    is_anomaly: bool
    composite_magnitude: float
    severity: Optional[str] = None
    observed_pattern: Optional[str] = None
    probable_factors: list[ProbableContributingFactor] = []
    incident_event_id: Optional[int] = None
    is_synthetic: bool = True


class ElearningModuleResponse(BaseModel):
    """Self-paced training module mapped to deviation skill gap."""

    id: int
    name: str
    dimension: str
    description: Optional[str] = None
    content_url: Optional[str] = None
    duration_minutes: int
    is_synthetic: bool = True

    model_config = {"from_attributes": True}


class TrainingRecommendationResponse(BaseModel):
    """Skill-gap coaching and training recommendation for an operator."""

    id: int
    operator_id: int
    operator_name: Optional[str] = None
    dimension: str
    elearning_module_id: Optional[int] = None
    elearning_module: Optional[ElearningModuleResponse] = None
    reason: str
    status: str
    created_at: datetime
    is_synthetic: bool = True

    model_config = {"from_attributes": True}


class InstructorSlotResponse(BaseModel):
    """Instructor availability slot for 1-on-1 coaching."""

    id: int
    instructor_name: str
    slot_date: str
    start_time: str
    end_time: str
    is_available: bool
    is_synthetic: bool = True

    model_config = {"from_attributes": True}


class BookingCreateRequest(BaseModel):
    """Payload to reserve an instructor coaching session."""

    operator_id: int = Field(..., description="Operator ID booking the slot")
    instructor_slot_id: int = Field(..., description="Slot ID to reserve")
    topic: str = Field(..., min_length=3, max_length=200, description="Coaching focus topic")


class InstructorBookingResponse(BaseModel):
    """Confirmed instructor coaching session."""

    id: int
    operator_id: int
    operator_name: Optional[str] = None
    instructor_slot_id: int
    instructor_name: Optional[str] = None
    slot_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    topic: str
    status: str
    created_at: datetime
    is_synthetic: bool = True

    model_config = {"from_attributes": True}
