"""FastAPI router for Anomaly Detection, Coaching, and Training (§11, §14, §C)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.anomaly.detector import detect_task_anomaly, get_recent_anomalies
from app.db.models import Operator, TaskInstance
from app.db.session import get_db
from app.schemas.training import (
    AnomalyItemResponse,
    AnomalyListResponse,
    BookingCreateRequest,
    ElearningModuleResponse,
    InstructorBookingResponse,
    InstructorSlotResponse,
    ProbableContributingFactor,
    TaskAnomalyEvaluationResponse,
    TrainingRecommendationResponse,
)
from app.training.recommendation import (
    SlotAlreadyBookedError,
    book_instructor_slot,
    evaluate_operator_training_needs,
    get_elearning_modules,
    get_instructor_slots,
    get_operator_bookings,
)

router = APIRouter(tags=["training-anomalies"])


@router.get("/anomalies", response_model=AnomalyListResponse)
def list_anomalies(
    operator_id: Optional[int] = Query(None, description="Filter by operator ID"),
    severity: Optional[str] = Query(None, description="Filter by severity (critical, high, medium)"),
    limit: int = Query(50, ge=1, le=500, description="Max results"),
    db: Session = Depends(get_db),
) -> AnomalyListResponse:
    """Retrieve performance anomaly events stream with non-causal contributing factors."""
    raw_anomalies = get_recent_anomalies(db, operator_id=operator_id, severity=severity, limit=limit)

    items: list[AnomalyItemResponse] = []
    for a in raw_anomalies:
        factors = [
            ProbableContributingFactor(
                dimension=f["dimension"],
                z_score=f["z_score"],
                contribution_weight_pct=f["contribution_weight_pct"],
                description=f["description"],
            )
            for f in a.get("probable_factors", [])
        ]
        items.append(
            AnomalyItemResponse(
                id=a.get("id"),
                task_instance_id=a["task_instance_id"],
                operator_id=a["operator_id"],
                operator_name=a["operator_name"],
                machine_id=a.get("machine_id"),
                machine_name=a.get("machine_name"),
                composite_magnitude=a["composite_magnitude"],
                severity=a["severity"],
                observed_pattern=a["observed_pattern"],
                probable_factors=factors,
                created_at=a["created_at"],
                is_synthetic=True,
            )
        )

    return AnomalyListResponse(anomalies=items, total_count=len(items), is_synthetic=True)


@router.post("/anomalies/detect/{task_id}", response_model=TaskAnomalyEvaluationResponse)
def evaluate_task_anomaly_endpoint(
    task_id: int,
    db: Session = Depends(get_db),
) -> TaskAnomalyEvaluationResponse:
    """Evaluate task telemetry against reference model and record anomaly incident if detected."""
    task = db.query(TaskInstance).filter(TaskInstance.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task instance #{task_id} not found.",
        )

    is_anomaly, incident, evaluation = detect_task_anomaly(db, task, auto_commit=True)

    factors = [
        ProbableContributingFactor(
            dimension=f.dimension,
            z_score=f.z_score,
            contribution_weight_pct=f.contribution_weight_pct,
            description=f.description,
        )
        for f in evaluation.probable_factors
    ]

    return TaskAnomalyEvaluationResponse(
        task_instance_id=task.id,
        is_anomaly=is_anomaly,
        composite_magnitude=evaluation.composite_magnitude,
        severity=evaluation.severity,
        observed_pattern=evaluation.observed_pattern,
        probable_factors=factors,
        incident_event_id=incident.id if incident else None,
        is_synthetic=True,
    )


@router.get("/training/recommendations/{operator_id}", response_model=list[TrainingRecommendationResponse])
def get_recommendations_for_operator(
    operator_id: int,
    db: Session = Depends(get_db),
) -> list[TrainingRecommendationResponse]:
    """Retrieve skill-gap training recommendations for an operator based on dynamic state."""
    try:
        recommendations = evaluate_operator_training_needs(db, operator_id, auto_commit=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    results: list[TrainingRecommendationResponse] = []
    for rec in recommendations:
        mod_resp = None
        if rec.elearning_module:
            mod_resp = ElearningModuleResponse.model_validate(rec.elearning_module)
        results.append(
            TrainingRecommendationResponse(
                id=rec.id,
                operator_id=rec.operator_id,
                operator_name=rec.operator.name if rec.operator else f"Operator #{rec.operator_id}",
                dimension=rec.dimension,
                elearning_module_id=rec.elearning_module_id,
                elearning_module=mod_resp,
                reason=rec.reason,
                status=rec.status,
                created_at=rec.created_at,
                is_synthetic=True,
            )
        )
    return results


@router.get("/training/modules", response_model=list[ElearningModuleResponse])
def list_elearning_modules(db: Session = Depends(get_db)) -> list[ElearningModuleResponse]:
    """List all available self-paced CAT E-Learning modules."""
    modules = get_elearning_modules(db)
    return [ElearningModuleResponse.model_validate(m) for m in modules]


@router.get("/training/slots", response_model=list[InstructorSlotResponse])
def list_instructor_slots(
    available_only: bool = Query(True, description="Filter for available slots only"),
    db: Session = Depends(get_db),
) -> list[InstructorSlotResponse]:
    """List 1-on-1 instructor coaching slots."""
    slots = get_instructor_slots(db, available_only=available_only)
    return [InstructorSlotResponse.model_validate(s) for s in slots]


@router.post(
    "/training/bookings",
    response_model=InstructorBookingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_instructor_booking(
    payload: BookingCreateRequest,
    db: Session = Depends(get_db),
) -> InstructorBookingResponse:
    """Reserve an instructor coaching slot with concurrency and double-booking protection."""
    try:
        booking = book_instructor_slot(
            db=db,
            operator_id=payload.operator_id,
            slot_id=payload.instructor_slot_id,
            topic=payload.topic,
        )
    except SlotAlreadyBookedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    return InstructorBookingResponse(
        id=booking.id,
        operator_id=booking.operator_id,
        operator_name=booking.operator.name if booking.operator else f"Operator #{booking.operator_id}",
        instructor_slot_id=booking.instructor_slot_id,
        instructor_name=booking.instructor_slot.instructor_name if booking.instructor_slot else None,
        slot_date=booking.instructor_slot.slot_date if booking.instructor_slot else None,
        start_time=booking.instructor_slot.start_time if booking.instructor_slot else None,
        end_time=booking.instructor_slot.end_time if booking.instructor_slot else None,
        topic=booking.topic,
        status=booking.status,
        created_at=booking.created_at,
        is_synthetic=True,
    )


@router.get("/training/bookings/{operator_id}", response_model=list[InstructorBookingResponse])
def list_operator_bookings(
    operator_id: int,
    db: Session = Depends(get_db),
) -> list[InstructorBookingResponse]:
    """Retrieve coaching bookings for a specific operator."""
    op = db.query(Operator).filter(Operator.id == operator_id).first()
    if not op:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Operator #{operator_id} not found.")

    bookings = get_operator_bookings(db, operator_id)
    return [
        InstructorBookingResponse(
            id=b.id,
            operator_id=b.operator_id,
            operator_name=b.operator.name if b.operator else f"Operator #{b.operator_id}",
            instructor_slot_id=b.instructor_slot_id,
            instructor_name=b.instructor_slot.instructor_name if b.instructor_slot else None,
            slot_date=b.instructor_slot.slot_date if b.instructor_slot else None,
            start_time=b.instructor_slot.start_time if b.instructor_slot else None,
            end_time=b.instructor_slot.end_time if b.instructor_slot else None,
            topic=b.topic,
            status=b.status,
            created_at=b.created_at,
            is_synthetic=True,
        )
        for b in bookings
    ]
