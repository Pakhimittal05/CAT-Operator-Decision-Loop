"""Training and Coaching Recommendation Module for CAT Operator Decision Loop (§14)."""

from app.training.recommendation import (
    SlotAlreadyBookedError,
    book_instructor_slot,
    evaluate_operator_training_needs,
    get_elearning_modules,
    get_instructor_slots,
    get_operator_bookings,
    seed_default_modules_and_slots,
)

__all__ = [
    "evaluate_operator_training_needs",
    "get_elearning_modules",
    "get_instructor_slots",
    "book_instructor_slot",
    "get_operator_bookings",
    "seed_default_modules_and_slots",
    "SlotAlreadyBookedError",
]
