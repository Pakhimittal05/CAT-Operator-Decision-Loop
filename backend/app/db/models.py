"""SQLAlchemy ORM models — all 12 tables per ARCHITECTURE.md §B.

Every table carries ``is_synthetic`` (default True) where applicable.
``task_instances.source_process`` distinguishes Process-A from Process-B rows.
``incident_events.source`` distinguishes seatbelt / proximity / deviation_anomaly / manual.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import DeclarativeBase, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ── Core entities ──────────────────────────────────────────────────────────


class Operator(Base):
    """An equipment operator.

    ``skill_tier`` is the *static* legacy label (Expert / Intermediate / Beginner).
    The dynamic replacement lives in ``OperatorState``.
    ``latent_*`` columns store generation parameters for internal validation only.
    """

    __tablename__ = "operators"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    skill_tier = Column(String, nullable=False)  # Expert / Intermediate / Beginner
    is_synthetic = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    # Generation-only metadata (for backtest validation — never shown to judges)
    latent_efficiency_mean = Column(Float, nullable=True)
    latent_idle_tendency = Column(Float, nullable=True)
    latent_safety_tendency = Column(Float, nullable=True)

    task_instances = relationship("TaskInstance", back_populates="operator")
    states = relationship("OperatorState", back_populates="operator")


class Machine(Base):
    """A piece of heavy equipment."""

    __tablename__ = "machines"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    machine_type = Column(String, nullable=False)
    age_years = Column(Float, nullable=False)
    wear_factor = Column(Float, nullable=False)
    is_synthetic = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    task_instances = relationship("TaskInstance", back_populates="machine")


class TaskCatalog(Base):
    """A type of task (e.g. Excavation, Hauling)."""

    __tablename__ = "tasks_catalog"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    baseline_duration_minutes = Column(Float, nullable=False)
    baseline_load_cycles = Column(Integer, nullable=False)
    difficulty = Column(Float, nullable=False)  # 0–1 scale
    is_synthetic = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    task_instances = relationship("TaskInstance", back_populates="task_type")


# ── Telemetry ──────────────────────────────────────────────────────────────


class TaskInstance(Base):
    """A single executed task with full telemetry.

    ``source_process`` is 'A' (historical/training) or 'B' (live/demo actual).
    """

    __tablename__ = "task_instances"

    id = Column(Integer, primary_key=True)
    operator_id = Column(Integer, ForeignKey("operators.id"), nullable=False)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=False)
    task_type_id = Column(Integer, ForeignKey("tasks_catalog.id"), nullable=False)

    weather = Column(String, nullable=False)
    duration_minutes = Column(Float, nullable=False)
    idle_seconds = Column(Float, nullable=False)
    load_cycles = Column(Integer, nullable=False)
    efficiency_score = Column(Float, nullable=False)

    seatbelt_engaged = Column(Boolean, nullable=False)
    min_proximity_distance = Column(Float, nullable=False)

    is_synthetic = Column(Boolean, default=True, nullable=False)
    source_process = Column(String, nullable=False)  # 'A' or 'B'

    completed_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    operator = relationship("Operator", back_populates="task_instances")
    machine = relationship("Machine", back_populates="task_instances")
    task_type = relationship("TaskCatalog", back_populates="task_instances")
    deviation = relationship("DeviationVector", back_populates="task_instance", uselist=False)
    prediction = relationship("Prediction", back_populates="task_instance", uselist=False)


# ── Deviation / State ──────────────────────────────────────────────────────


class DeviationVector(Base):
    """Per-task deviation from reference (5 dimensions + composite)."""

    __tablename__ = "deviation_vectors"

    id = Column(Integer, primary_key=True)
    task_instance_id = Column(
        Integer, ForeignKey("task_instances.id"), nullable=False, unique=True
    )

    d_cycle_efficiency = Column(Float, nullable=False)
    d_idling = Column(Float, nullable=False)
    d_duration = Column(Float, nullable=False)
    d_load_cycle = Column(Float, nullable=False)
    d_safety = Column(Float, nullable=False)
    composite_magnitude = Column(Float, nullable=False)

    created_at = Column(DateTime, default=_utcnow, nullable=False)

    task_instance = relationship("TaskInstance", back_populates="deviation")


class OperatorState(Base):
    """Dynamic operator skill/performance state (EWMA-based).

    ``task_type_id = NULL`` represents the overall (cross-task) state.
    """

    __tablename__ = "operator_state"

    id = Column(Integer, primary_key=True)
    operator_id = Column(Integer, ForeignKey("operators.id"), nullable=False)
    task_type_id = Column(Integer, ForeignKey("tasks_catalog.id"), nullable=True)

    efficiency_score = Column(Float, nullable=False)
    idling_score = Column(Float, nullable=False)
    duration_score = Column(Float, nullable=False)
    load_cycle_score = Column(Float, nullable=False)
    safety_score = Column(Float, nullable=False)
    composite_score = Column(Float, nullable=False)

    trend_direction = Column(String, nullable=False)  # improving / stable / declining
    confidence = Column(Float, nullable=False)
    derived_label = Column(String, nullable=False)  # Expert / Intermediate / Beginner

    updated_at = Column(DateTime, default=_utcnow, nullable=False)

    operator = relationship("Operator", back_populates="states")


# ── Prediction ─────────────────────────────────────────────────────────────


class Prediction(Base):
    """Stored prediction (point estimate + uncertainty) for a task or simulation."""

    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True)
    task_instance_id = Column(
        Integer, ForeignKey("task_instances.id"), nullable=True
    )

    operator_id = Column(Integer, ForeignKey("operators.id"), nullable=False)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=False)
    task_type_id = Column(Integer, ForeignKey("tasks_catalog.id"), nullable=False)
    weather = Column(String, nullable=False)

    predicted_duration = Column(Float, nullable=False)
    p10 = Column(Float, nullable=False)
    p90 = Column(Float, nullable=False)
    risk_score = Column(Float, nullable=False)
    skill_fit = Column(Float, nullable=False)
    training_flag = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=_utcnow, nullable=False)

    task_instance = relationship("TaskInstance", back_populates="prediction")


# ── Incidents ──────────────────────────────────────────────────────────────


class IncidentEvent(Base):
    """Unified incident/event record.

    ``source`` enum: seatbelt | proximity | deviation_anomaly | manual.
    """

    __tablename__ = "incident_events"

    id = Column(Integer, primary_key=True)
    task_instance_id = Column(
        Integer, ForeignKey("task_instances.id"), nullable=True
    )
    operator_id = Column(Integer, ForeignKey("operators.id"), nullable=False)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=True)

    source = Column(String, nullable=False)
    severity = Column(String, nullable=False)  # low / medium / high / critical
    description = Column(String, nullable=True)

    created_at = Column(DateTime, default=_utcnow, nullable=False)

    operator = relationship("Operator")
    machine = relationship("Machine")
    task_instance = relationship("TaskInstance")


# ── Training ───────────────────────────────────────────────────────────────


class ElearningModule(Base):
    """A demo e-learning module mapped to a deviation dimension."""

    __tablename__ = "elearning_modules"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    dimension = Column(String, nullable=False)
    description = Column(String, nullable=True)
    content_url = Column(String, nullable=True)
    duration_minutes = Column(Integer, nullable=False)
    is_synthetic = Column(Boolean, default=True, nullable=False)


class TrainingRecommendation(Base):
    """A skill-gap-based training recommendation for an operator."""

    __tablename__ = "training_recommendations"

    id = Column(Integer, primary_key=True)
    operator_id = Column(Integer, ForeignKey("operators.id"), nullable=False)
    dimension = Column(String, nullable=False)
    elearning_module_id = Column(
        Integer, ForeignKey("elearning_modules.id"), nullable=True
    )
    reason = Column(String, nullable=False)
    status = Column(String, default="pending", nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    operator = relationship("Operator")
    elearning_module = relationship("ElearningModule")


class InstructorSlot(Base):
    """An available instructor time-slot for booking."""

    __tablename__ = "instructor_slots"

    id = Column(Integer, primary_key=True)
    instructor_name = Column(String, nullable=False)
    slot_date = Column(String, nullable=False)  # ISO date YYYY-MM-DD
    start_time = Column(String, nullable=False)  # HH:MM
    end_time = Column(String, nullable=False)  # HH:MM
    is_available = Column(Boolean, default=True, nullable=False)


class InstructorBooking(Base):
    """An operator's booking against an instructor slot."""

    __tablename__ = "instructor_bookings"

    id = Column(Integer, primary_key=True)
    operator_id = Column(Integer, ForeignKey("operators.id"), nullable=False)
    instructor_slot_id = Column(
        Integer, ForeignKey("instructor_slots.id"), nullable=False
    )
    topic = Column(String, nullable=False)
    status = Column(String, default="confirmed", nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    operator = relationship("Operator")
    instructor_slot = relationship("InstructorSlot")
