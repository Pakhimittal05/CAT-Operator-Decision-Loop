"""Deterministic Training and Coaching Recommendation Engine (§14).

Provides:
  - Deterministic mapping from 5 deviation dimensions to targeted E-Learning modules
  - Skill-gap detection from operator dynamic state (EWMA) and anomaly history
  - Idempotent initial seed of modules and instructor coaching slots
  - Thread-safe / transactional instructor slot booking with double-booking prevention (HTTP 409)
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.db.models import (
    ElearningModule,
    InstructorBooking,
    InstructorSlot,
    Operator,
    OperatorState,
    TrainingRecommendation,
)
from app.operator_state.state import get_operator_state

logger = logging.getLogger("cat_decision_loop.training")


class SlotAlreadyBookedError(Exception):
    """Raised when attempting to reserve an instructor slot that is already booked."""
    pass


# Deterministic mapping from 5 deviation dimensions to CAT E-Learning modules
ELEARNING_CATALOG: list[dict[str, Any]] = [
    {
        "name": "CAT Hydraulic Optimization & Cycle Efficiency",
        "dimension": "cycle_efficiency",
        "description": (
            "Techniques for optimizing hydraulic pressure modulation, bucket curl timing, "
            "and swing-to-dump cycle efficiency across varied soil densities."
        ),
        "content_url": "https://learn.cat.com/modules/hydraulic-cycle-opt",
        "duration_minutes": 45,
    },
    {
        "name": "Eco-Operating: Idle Reduction & Duty Cycle Management",
        "dimension": "idling",
        "description": (
            "Operational protocols for reducing non-productive engine idling, staged warm-up, "
            "and auto-shutdown protocol compliance to reduce fuel consumption."
        ),
        "content_url": "https://learn.cat.com/modules/eco-idle-reduction",
        "duration_minutes": 30,
    },
    {
        "name": "Task Pacing & Haul Route Optimization",
        "dimension": "duration",
        "description": (
            "Methods for grade assessment, gear selection, and smooth pass sequencing "
            "to achieve consistent, repeatable task cycle times."
        ),
        "content_url": "https://learn.cat.com/modules/route-pacing",
        "duration_minutes": 35,
    },
    {
        "name": "Payload Distribution & Truck Spotting Efficiency",
        "dimension": "load_cycle",
        "description": (
            "Best practices for target payload distribution, bucket fill factors, and optimal "
            "excavator-to-haul-truck spotting positioning."
        ),
        "content_url": "https://learn.cat.com/modules/payload-spotting",
        "duration_minutes": 40,
    },
    {
        "name": "Proximity Awareness & Blind-Spot Navigation",
        "dimension": "safety",
        "description": (
            "Defensive machine maneuvering, exclusion zone compliance, and blind-spot "
            "clearance procedures for heavy equipment site safety."
        ),
        "content_url": "https://learn.cat.com/modules/proximity-blindspot",
        "duration_minutes": 50,
    },
]

INITIAL_INSTRUCTOR_SLOTS: list[dict[str, Any]] = [
    {
        "instructor_name": "Sarah Jenkins (Master Certified Trainer)",
        "slot_date": "2025-07-15",
        "start_time": "09:00",
        "end_time": "10:00",
    },
    {
        "instructor_name": "Sarah Jenkins (Master Certified Trainer)",
        "slot_date": "2025-07-15",
        "start_time": "10:30",
        "end_time": "11:30",
    },
    {
        "instructor_name": "Marcus Vance (Heavy Equipment Safety Specialist)",
        "slot_date": "2025-07-16",
        "start_time": "13:00",
        "end_time": "14:00",
    },
    {
        "instructor_name": "Marcus Vance (Heavy Equipment Safety Specialist)",
        "slot_date": "2025-07-16",
        "start_time": "14:30",
        "end_time": "15:30",
    },
    {
        "instructor_name": "Elena Rostova (Earthmoving & Grading Specialist)",
        "slot_date": "2025-07-17",
        "start_time": "09:30",
        "end_time": "10:30",
    },
    {
        "instructor_name": "Elena Rostova (Earthmoving & Grading Specialist)",
        "slot_date": "2025-07-17",
        "start_time": "11:00",
        "end_time": "12:00",
    },
    {
        "instructor_name": "David Chen (Fleet Efficiency & Operations Coach)",
        "slot_date": "2025-07-18",
        "start_time": "13:30",
        "end_time": "14:30",
    },
    {
        "instructor_name": "David Chen (Fleet Efficiency & Operations Coach)",
        "slot_date": "2025-07-18",
        "start_time": "15:00",
        "end_time": "16:00",
    },
]


def seed_default_modules_and_slots(db: Session) -> tuple[int, int]:
    """Idempotently seed default e-learning modules and instructor slots if absent.

    Returns:
        (modules_added, slots_added)
    """
    modules_added = 0
    if db.query(ElearningModule).count() == 0:
        for item in ELEARNING_CATALOG:
            mod = ElearningModule(
                name=item["name"],
                dimension=item["dimension"],
                description=item["description"],
                content_url=item["content_url"],
                duration_minutes=item["duration_minutes"],
                is_synthetic=True,
            )
            db.add(mod)
            modules_added += 1
        db.commit()
        logger.info("Seeded %d default E-Learning modules.", modules_added)

    slots_added = 0
    if db.query(InstructorSlot).count() == 0:
        for slot in INITIAL_INSTRUCTOR_SLOTS:
            s = InstructorSlot(
                instructor_name=slot["instructor_name"],
                slot_date=slot["slot_date"],
                start_time=slot["start_time"],
                end_time=slot["end_time"],
                is_available=True,
            )
            db.add(s)
            slots_added += 1
        db.commit()
        logger.info("Seeded %d default instructor coaching slots.", slots_added)

    return modules_added, slots_added


def get_elearning_modules(db: Session) -> list[ElearningModule]:
    """Retrieve all available e-learning modules."""
    return db.query(ElearningModule).order_by(ElearningModule.id.asc()).all()


def get_module_for_dimension(db: Session, dimension: str) -> Optional[ElearningModule]:
    """Find the specific e-learning module associated with a deviation dimension."""
    return db.query(ElearningModule).filter(ElearningModule.dimension == dimension).first()


def evaluate_operator_training_needs(
    db: Session,
    operator_id: int,
    auto_commit: bool = True,
) -> list[TrainingRecommendation]:
    """Evaluate an operator's dynamic performance state and generate skill-gap recommendations.

    A skill-gap is triggered when an operator's dimension score is below 50.0.
    All recommendation reasons strictly use non-causal coaching advice.
    """
    op = db.query(Operator).filter(Operator.id == operator_id).first()
    if not op:
        raise ValueError(f"Operator #{operator_id} not found.")

    # Retrieve overall dynamic state
    state = get_operator_state(db, operator_id, task_type_id=None)

    # Check each of the 5 dimension scores
    dimension_scores = {
        "cycle_efficiency": state.efficiency_score,
        "idling": state.idling_score,
        "duration": state.duration_score,
        "load_cycle": state.load_cycle_score,
        "safety": state.safety_score,
    }

    dimension_reasons = {
        "cycle_efficiency": (
            f"Observed cycle efficiency score ({state.efficiency_score:.1f}/100) indicates "
            f"potential benefit from hydraulic pressure modulation and bucket curl refresher."
        ),
        "idling": (
            f"Observed pattern of elevated idling ({state.idling_score:.1f}/100) suggests "
            f"refresher on staged shutdown protocols and duty cycle eco-operating."
        ),
        "duration": (
            f"Extended task duration trend ({state.duration_score:.1f}/100) associated with "
            f"route pacing and grade transition variance."
        ),
        "load_cycle": (
            f"Load cycle score ({state.load_cycle_score:.1f}/100) indicates opportunity "
            f"to refine truck spotting angles and bucket payload distribution."
        ),
        "safety": (
            f"Proximity buffer score ({state.safety_score:.1f}/100) indicates benefit "
            f"from blind-spot clearance and exclusion zone protocol coaching."
        ),
    }

    created_or_existing: list[TrainingRecommendation] = []

    for dim, score in dimension_scores.items():
        if score < 50.0:  # Persistent skill deficit threshold
            # Check if active recommendation already exists
            existing = (
                db.query(TrainingRecommendation)
                .filter(
                    TrainingRecommendation.operator_id == operator_id,
                    TrainingRecommendation.dimension == dim,
                    TrainingRecommendation.status.in_(["pending", "in_progress"]),
                )
                .first()
            )
            if existing:
                created_or_existing.append(existing)
            else:
                mod = get_module_for_dimension(db, dim)
                rec = TrainingRecommendation(
                    operator_id=operator_id,
                    dimension=dim,
                    elearning_module_id=mod.id if mod else None,
                    reason=dimension_reasons.get(dim, f"Targeted coaching recommended for {dim}."),
                    status="pending",
                    created_at=datetime.now(timezone.utc),
                )
                db.add(rec)
                created_or_existing.append(rec)

    if auto_commit:
        db.commit()
        for r in created_or_existing:
            db.refresh(r)

    return created_or_existing


def get_instructor_slots(db: Session, available_only: bool = True) -> list[InstructorSlot]:
    """Retrieve instructor coaching slots."""
    query = db.query(InstructorSlot)
    if available_only:
        query = query.filter(InstructorSlot.is_available == True)  # noqa: E712
    return query.order_by(InstructorSlot.slot_date.asc(), InstructorSlot.start_time.asc()).all()


def book_instructor_slot(
    db: Session,
    operator_id: int,
    slot_id: int,
    topic: str,
) -> InstructorBooking:
    """Safely reserve an instructor coaching session with transactional concurrency protection.

    Raises:
        ValueError: If operator or slot does not exist.
        SlotAlreadyBookedError: If slot is already reserved (yields HTTP 409).
    """
    op = db.query(Operator).filter(Operator.id == operator_id).first()
    if not op:
        raise ValueError(f"Operator #{operator_id} not found.")

    # Transactional check on slot availability
    slot = (
        db.query(InstructorSlot)
        .filter(InstructorSlot.id == slot_id)
        .with_for_update()
        .first()
    )
    if not slot:
        raise ValueError(f"Instructor slot #{slot_id} not found.")

    if not slot.is_available:
        raise SlotAlreadyBookedError(
            f"Instructor slot #{slot_id} on {slot.slot_date} at {slot.start_time} "
            f"is already reserved by another operator."
        )

    # Mark slot unavailable and create booking record
    slot.is_available = False

    booking = InstructorBooking(
        operator_id=operator_id,
        instructor_slot_id=slot_id,
        topic=topic.strip(),
        status="confirmed",
        created_at=datetime.now(timezone.utc),
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    # Advance any pending training recommendation for this operator on this topic to in_progress
    pending_rec = (
        db.query(TrainingRecommendation)
        .filter(
            TrainingRecommendation.operator_id == operator_id,
            TrainingRecommendation.status == "pending",
        )
        .first()
    )
    if pending_rec:
        pending_rec.status = "in_progress"
        db.commit()

    return booking


def get_operator_bookings(db: Session, operator_id: int) -> list[InstructorBooking]:
    """Retrieve all confirmed coaching bookings for an operator."""
    return (
        db.query(InstructorBooking)
        .filter(InstructorBooking.operator_id == operator_id)
        .order_by(InstructorBooking.created_at.desc())
        .all()
    )
