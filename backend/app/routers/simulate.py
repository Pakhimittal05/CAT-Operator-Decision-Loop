"""What-If Simulation and Explainability API Router (§C, §12, §24).

Endpoints:
  - POST /simulate/whatif: Execute simulation and store prediction
  - GET  /simulate/options: Retrieve operators, machines, tasks, and weather for UI
  - GET  /models/explain/{prediction_id}: Retrieve explanation details for a prediction
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import Machine, Operator, Prediction, TaskCatalog
from app.db.session import get_db
from app.operator_state.state import get_operator_state
from app.prediction.task_time_model import (
    extract_probable_contributing_factors,
    load_task_time_artifacts,
)
from app.schemas.simulate import (
    ComparisonListResponse,
    ComparisonResponse,
    ContributingFactor,
    MachineOption,
    OperatorOption,
    ProcessBTriggerRequest,
    SimulationOptionsResponse,
    SimulationRequest,
    SimulationResponse,
    TaskCatalogOption,
)
from app.simulation.feedback_service import (
    execute_process_b_for_prediction,
    get_prediction_comparison,
    list_simulation_comparisons,
)
from app.simulation.whatif import ALLOWED_WEATHER, run_whatif_simulation

router = APIRouter(tags=["simulation"])


@router.get("/simulate/options", response_model=SimulationOptionsResponse)
def get_simulation_options(db: Session = Depends(get_db)) -> SimulationOptionsResponse:
    """Retrieve dropdown selector options for the What-If Simulator interface."""
    # Operators
    operators = db.query(Operator).order_by(Operator.name.asc()).all()
    operator_options = []
    for op in operators:
        op_state = get_operator_state(db, op.id)
        operator_options.append(
            OperatorOption(
                id=op.id,
                name=op.name,
                composite_score=op_state.composite_score,
                derived_label=op_state.derived_label,
            )
        )

    # Machines
    machines = db.query(Machine).order_by(Machine.name.asc()).all()
    machine_options = [
        MachineOption(
            id=m.id,
            name=m.name,
            machine_type=m.machine_type,
            age_years=m.age_years,
            wear_factor=m.wear_factor,
        )
        for m in machines
    ]

    # Task catalog
    tasks = db.query(TaskCatalog).order_by(TaskCatalog.name.asc()).all()
    task_options = [
        TaskCatalogOption(
            id=t.id,
            name=t.name,
            baseline_duration_minutes=t.baseline_duration_minutes,
            difficulty=t.difficulty,
        )
        for t in tasks
    ]

    return SimulationOptionsResponse(
        operators=operator_options,
        machines=machine_options,
        tasks=task_options,
        weather_options=sorted(ALLOWED_WEATHER),
        is_synthetic=True,
    )


@router.post("/simulate/whatif", response_model=SimulationResponse)
def simulate_task(
    payload: SimulationRequest,
    db: Session = Depends(get_db),
) -> SimulationResponse:
    """Run What-If simulation for an operator/machine/task/weather combination.

    Predicts duration with uncertainty interval (P10 <= Point <= P90),
    computes skill fit and safety risk, and persists result to predictions table.
    """
    artifacts = load_task_time_artifacts()
    return run_whatif_simulation(
        session=db,
        operator_id=payload.operator_id,
        machine_id=payload.machine_id,
        task_type_id=payload.task_type_id,
        weather=payload.weather,
        artifacts=artifacts,
    )


@router.get("/models/explain/{prediction_id}")
def get_prediction_explanation(
    prediction_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve probabilistic model explainability attribution for a prediction (§24)."""
    pred = db.query(Prediction).filter(Prediction.id == prediction_id).first()
    if not pred:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prediction with ID {prediction_id} not found.",
        )

    operator = db.query(Operator).filter(Operator.id == pred.operator_id).first()
    machine = db.query(Machine).filter(Machine.id == pred.machine_id).first()
    task_type = db.query(TaskCatalog).filter(TaskCatalog.id == pred.task_type_id).first()

    artifacts = load_task_time_artifacts()
    op_state = get_operator_state(db, pred.operator_id)

    feature_row = {
        "operator_composite_score": op_state.composite_score,
        "operator_duration_score": op_state.duration_score,
        "operator_efficiency_score": op_state.efficiency_score,
        "operator_confidence": op_state.confidence,
        "baseline_duration_minutes": task_type.baseline_duration_minutes if task_type else 30.0,
        "task_difficulty": task_type.difficulty if task_type else 0.5,
        "machine_age_years": machine.age_years if machine else 3.0,
        "machine_wear_factor": machine.wear_factor if machine else 0.3,
        "task_type": task_type.name if task_type else "Task",
        "machine_type": machine.machine_type if machine else "Machine",
        "weather": pred.weather,
    }

    factors = extract_probable_contributing_factors(feature_row, artifacts)

    return {
        "prediction_id": pred.id,
        "operator_id": pred.operator_id,
        "operator_name": operator.name if operator else "Unknown",
        "machine_name": machine.name if machine else "Unknown",
        "task_type_name": task_type.name if task_type else "Unknown",
        "weather": pred.weather,
        "predicted_duration": pred.predicted_duration,
        "p10": pred.p10,
        "p90": pred.p90,
        "skill_fit": pred.skill_fit,
        "risk_score": pred.risk_score,
        "training_flag": pred.training_flag,
        "probable_contributing_factors": factors,
        "note": "Probabilistic attribution based on gradient boosting feature importances. Never implies causality.",
        "is_synthetic": True,
    }


# ── Phase 7: Closed Loop & Predicted vs Actual Endpoints (§C, §15) ─────────


@router.post(
    "/simulate/{prediction_id}/generate-actual",
    response_model=ComparisonResponse,
    status_code=status.HTTP_200_OK,
)
def generate_actual_outcome(
    prediction_id: int,
    payload: ProcessBTriggerRequest | None = None,
    db: Session = Depends(get_db),
) -> ComparisonResponse:
    """Trigger Process B independent stochastic actual outcome for a simulated prediction.

    Executes closed loop:
      - Process B telemetry generation (log-normal duration noise, hidden fatigue factor)
      - Creates actual TaskInstance (source_process='B')
      - Computes standardized 5D deviation vector
      - Evaluates safety events via IncidentService
      - Recalibrates operator EWMA performance state
      - Returns complete Predicted vs Actual comparison
    """
    seed = payload.seed if payload else None
    return execute_process_b_for_prediction(session=db, prediction_id=prediction_id, seed=seed)


@router.get(
    "/simulate/{prediction_id}/comparison",
    response_model=ComparisonResponse,
)
def get_comparison(
    prediction_id: int,
    db: Session = Depends(get_db),
) -> ComparisonResponse:
    """Retrieve predicted vs actual comparison for an already executed prediction."""
    return get_prediction_comparison(session=db, prediction_id=prediction_id)


@router.get(
    "/simulate/comparisons",
    response_model=ComparisonListResponse,
)
def list_comparisons(
    limit: int = 15,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> ComparisonListResponse:
    """Retrieve history of completed simulation executions with summary comparison cards."""
    return list_simulation_comparisons(session=db, limit=limit, offset=offset)
