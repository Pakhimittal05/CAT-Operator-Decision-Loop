"""Unit and integration tests for Phase 1: Schema, Database, and Process A Data Generation."""

import math
import numpy as np
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import (
    Base,
    Operator,
    Machine,
    TaskCatalog,
    TaskInstance,
    DeviationVector,
    OperatorState,
    Prediction,
    IncidentEvent,
    ElearningModule,
    TrainingRecommendation,
    InstructorSlot,
    InstructorBooking,
)
from app.data_generation.generate_historical_data import (
    generate_historical_data,
    SKILL_TIERS,
    WEATHER_CATEGORIES,
    MACHINE_SPECS,
    TASK_TYPES,
)


EXPECTED_TABLES = {
    "operators",
    "machines",
    "tasks_catalog",
    "task_instances",
    "deviation_vectors",
    "operator_state",
    "predictions",
    "incident_events",
    "elearning_modules",
    "training_recommendations",
    "instructor_slots",
    "instructor_bookings",
}


def test_schema_has_all_twelve_tables():
    """Verify that all 12 tables defined in ARCHITECTURE.md §B are present in the ORM schema."""
    table_names = set(Base.metadata.tables.keys())
    assert table_names == EXPECTED_TABLES, f"Missing tables: {EXPECTED_TABLES - table_names}"


def test_database_table_creation():
    """Verify that all 12 tables can be created in a SQLite database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    created_tables = set(inspector.get_table_names())
    assert EXPECTED_TABLES.issubset(created_tables)


def test_process_a_data_generation_counts_and_constraints():
    """Test Process A generation end-to-end against an in-memory SQLite database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    # Run Process A generation
    counts = generate_historical_data(engine, seed=42)

    assert counts["operators"] == 30, f"Expected 30 operators, got {counts['operators']}"
    assert counts["machines"] == len(MACHINE_SPECS), f"Expected {len(MACHINE_SPECS)} machines, got {counts['machines']}"
    assert counts["task_types"] == len(TASK_TYPES), f"Expected {len(TASK_TYPES)} task types, got {counts['task_types']}"
    assert counts["task_instances"] >= 3000, f"Expected >= 3000 task instances, got {counts['task_instances']}"

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Check operators
        operators = session.query(Operator).all()
        assert len(operators) == 30
        op_ids = {op.id for op in operators}
        for op in operators:
            assert op.is_synthetic is True
            assert op.skill_tier in SKILL_TIERS
            assert op.latent_efficiency_mean is not None
            assert 0.0 <= op.latent_efficiency_mean <= 1.0
            assert op.latent_idle_tendency is not None
            assert op.latent_idle_tendency >= 0.0
            assert op.latent_safety_tendency is not None
            assert op.latent_safety_tendency >= 0.0

        # Check machines
        machines = session.query(Machine).all()
        assert len(machines) == len(MACHINE_SPECS)
        machine_ids = {m.id for m in machines}
        for m in machines:
            assert m.is_synthetic is True
            assert m.wear_factor >= 1.0
            assert m.age_years >= 0.0

        # Check task catalog
        tasks = session.query(TaskCatalog).all()
        assert len(tasks) == len(TASK_TYPES)
        task_ids = {t.id for t in tasks}
        for t in tasks:
            assert t.is_synthetic is True
            assert t.baseline_duration_minutes > 0
            assert t.baseline_load_cycles > 0
            assert 0.0 <= t.difficulty <= 1.0

        # Check task instances
        instances = session.query(TaskInstance).all()
        assert len(instances) >= 3000

        valid_weathers = set(WEATHER_CATEGORIES.keys())

        for inst in instances:
            # Synthetic label and source process
            assert inst.is_synthetic is True
            assert inst.source_process == "A"

            # Foreign key integrity
            assert inst.operator_id in op_ids
            assert inst.machine_id in machine_ids
            assert inst.task_type_id in task_ids

            # Categorical validation
            assert inst.weather in valid_weathers

            # Numeric telemetry constraints (no NaNs, within bounds)
            assert not math.isnan(inst.duration_minutes), "duration_minutes is NaN"
            assert inst.duration_minutes > 0, f"duration_minutes must be > 0, got {inst.duration_minutes}"

            assert not math.isnan(inst.idle_seconds), "idle_seconds is NaN"
            assert inst.idle_seconds >= 0, f"idle_seconds must be >= 0, got {inst.idle_seconds}"

            assert not math.isnan(inst.load_cycles), "load_cycles is NaN"
            assert inst.load_cycles > 0, f"load_cycles must be > 0, got {inst.load_cycles}"

            assert not math.isnan(inst.efficiency_score), "efficiency_score is NaN"
            assert 0.0 <= inst.efficiency_score <= 1.0, f"efficiency_score must be in [0, 1], got {inst.efficiency_score}"

            assert isinstance(inst.seatbelt_engaged, bool), "seatbelt_engaged must be boolean"

            assert not math.isnan(inst.min_proximity_distance), "min_proximity_distance is NaN"
            assert inst.min_proximity_distance >= 0.0, f"min_proximity_distance must be >= 0, got {inst.min_proximity_distance}"

            # Completed timestamp validity
            assert inst.completed_at is not None

    finally:
        session.close()


def test_process_a_reproducibility():
    """Verify that two runs with the same seed generate identical records."""
    engine1 = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    engine2 = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    c1 = generate_historical_data(engine1, seed=123)
    c2 = generate_historical_data(engine2, seed=123)

    assert c1 == c2

    s1 = sessionmaker(bind=engine1)()
    s2 = sessionmaker(bind=engine2)()

    try:
        first1 = s1.query(TaskInstance).first()
        first2 = s2.query(TaskInstance).first()
        assert first1.duration_minutes == first2.duration_minutes
        assert first1.idle_seconds == first2.idle_seconds
        assert first1.efficiency_score == first2.efficiency_score
    finally:
        s1.close()
        s2.close()


def test_sqlite_file_database_integrity():
    """Verify that the generated cat_decision_loop.db file has all 12 tables and populated records."""
    from pathlib import Path
    from app.config import settings

    # Derive the real DB path from the config URL (sqlite:///path/to/file)
    db_url = settings.database_url
    db_path = Path(db_url.replace("sqlite:///", ""))
    assert db_path.exists(), f"Database file does not exist at {db_path.resolve()}"

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert EXPECTED_TABLES.issubset(tables)

    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        op_count = session.query(Operator).count()
        m_count = session.query(Machine).count()
        t_count = session.query(TaskCatalog).count()
        inst_count = session.query(TaskInstance).count()

        assert op_count == 30, f"Expected 30 operators, got {op_count}"
        assert m_count == 10, f"Expected 10 machines, got {m_count}"
        assert t_count == 8, f"Expected 8 task types, got {t_count}"
        assert inst_count >= 3000, f"Expected >= 3000 instances, got {inst_count}"

        # Spot check all instances in the real DB
        non_synth = session.query(TaskInstance).filter(TaskInstance.is_synthetic != True).count()
        assert non_synth == 0, f"Found {non_synth} non-synthetic instances"

        non_process_a = session.query(TaskInstance).filter(TaskInstance.source_process != "A").count()
        assert non_process_a == 0, f"Found {non_process_a} non-Process-A instances"

        invalid_dur = session.query(TaskInstance).filter(TaskInstance.duration_minutes <= 0).count()
        assert invalid_dur == 0, f"Found {invalid_dur} instances with duration <= 0"

        invalid_idle = session.query(TaskInstance).filter(TaskInstance.idle_seconds < 0).count()
        assert invalid_idle == 0, f"Found {invalid_idle} instances with idle_seconds < 0"

        invalid_eff = session.query(TaskInstance).filter(
            (TaskInstance.efficiency_score < 0.0) | (TaskInstance.efficiency_score > 1.0)
        ).count()
        assert invalid_eff == 0, f"Found {invalid_eff} instances with efficiency not in [0, 1]"
    finally:
        session.close()

