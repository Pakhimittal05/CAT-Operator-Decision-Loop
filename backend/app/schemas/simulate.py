"""Pydantic schemas for What-If Simulation and Prediction API (§C, §12, §24)."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SimulationRequest(BaseModel):
    """Parameters for running a What-If task simulation."""

    operator_id: int = Field(..., description="ID of the operator to assign")
    machine_id: int = Field(..., description="ID of the machine to use")
    task_type_id: int = Field(..., description="ID of the task from catalog")
    weather: str = Field(..., description="Weather condition (Clear, Rain, Mud, Snow/Ice)")


class ContributingFactor(BaseModel):
    """Probabilistic attribution factor explaining prediction (§24)."""

    factor_name: str
    impact_direction: str  # "increases_duration" | "decreases_duration"
    impact_percentage: float
    confidence: float
    description: str


class SimulationResponse(BaseModel):
    """Complete response returned from a What-If simulation run."""

    model_config = ConfigDict(from_attributes=True)

    prediction_id: int
    operator_id: int
    operator_name: str
    machine_id: int
    machine_name: str
    task_type_id: int
    task_type_name: str
    weather: str

    predicted_duration_minutes: float
    p10_minutes: float
    p90_minutes: float
    uncertainty_range_minutes: float

    skill_fit_score: float
    skill_fit_label: str
    safety_risk_score: float
    safety_risk_level: str
    training_recommended: bool
    training_reason: Optional[str] = None

    probable_factors: List[ContributingFactor]
    is_synthetic: bool = True
    created_at: str


class OperatorOption(BaseModel):
    """Lightweight operator option for simulator selector."""

    id: int
    name: str
    composite_score: float
    derived_label: str


class MachineOption(BaseModel):
    """Machine option with wear factor for simulator selector."""

    id: int
    name: str
    machine_type: str
    age_years: float
    wear_factor: float


class TaskCatalogOption(BaseModel):
    """Task catalog option with difficulty for simulator selector."""

    id: int
    name: str
    baseline_duration_minutes: float
    difficulty: float


class SimulationOptionsResponse(BaseModel):
    """Available entities for configuring a What-If simulation in the UI."""

    operators: List[OperatorOption]
    machines: List[MachineOption]
    tasks: List[TaskCatalogOption]
    weather_options: List[str]
    is_synthetic: bool = True
