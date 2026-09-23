"""Process A — Historical Synthetic Data Generator.

Generates the *training corpus* using Stochastic Process A:
  - ~30 operators with latent skill parameters drawn per tier
  - ~10 machines with age-based wear factors
  - ~8 task types with baseline duration / load-cycle profiles
  - ~3 000+ task instances with Gaussian noise + Bernoulli safety-event injection
  - Weather sampled from a categorical distribution

ALL rows are tagged ``is_synthetic=True``, ``source_process='A'``.

This module has NO imports from ``generate_actual_outcomes`` (Process B).
They share only the database schema contract.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import numpy as np
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base, Machine, Operator, TaskCatalog, TaskInstance

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# Constants — Process A parameters
# ═══════════════════════════════════════════════════════════════════════════

SKILL_TIERS: dict[str, dict] = {
    "Expert": {
        "n": 10,
        "efficiency": (0.85, 0.04),   # (mean, std)
        "idle":       (0.08, 0.03),
        "safety":     (0.03, 0.012),
    },
    "Intermediate": {
        "n": 12,
        "efficiency": (0.68, 0.05),
        "idle":       (0.22, 0.05),
        "safety":     (0.10, 0.03),
    },
    "Beginner": {
        "n": 8,
        "efficiency": (0.52, 0.06),
        "idle":       (0.38, 0.06),
        "safety":     (0.18, 0.04),
    },
}

MACHINE_SPECS: list[dict] = [
    {"name": "EX-001", "machine_type": "Excavator",    "age_years": 2.0},
    {"name": "EX-002", "machine_type": "Excavator",    "age_years": 8.0},
    {"name": "BD-001", "machine_type": "Bulldozer",    "age_years": 5.0},
    {"name": "WL-001", "machine_type": "Wheel Loader", "age_years": 3.0},
    {"name": "WL-002", "machine_type": "Wheel Loader", "age_years": 12.0},
    {"name": "CR-001", "machine_type": "Crane",        "age_years": 7.0},
    {"name": "DT-001", "machine_type": "Dump Truck",   "age_years": 1.0},
    {"name": "DT-002", "machine_type": "Dump Truck",   "age_years": 10.0},
    {"name": "MG-001", "machine_type": "Motor Grader",  "age_years": 6.0},
    {"name": "CP-001", "machine_type": "Compactor",     "age_years": 4.0},
]

TASK_TYPES: list[dict] = [
    {"name": "Excavation",  "baseline_duration": 45.0, "baseline_load_cycles": 25, "difficulty": 0.60},
    {"name": "Grading",     "baseline_duration": 30.0, "baseline_load_cycles": 15, "difficulty": 0.40},
    {"name": "Hauling",     "baseline_duration": 60.0, "baseline_load_cycles": 10, "difficulty": 0.30},
    {"name": "Loading",     "baseline_duration": 20.0, "baseline_load_cycles": 40, "difficulty": 0.50},
    {"name": "Trenching",   "baseline_duration": 50.0, "baseline_load_cycles": 20, "difficulty": 0.70},
    {"name": "Demolition",  "baseline_duration": 40.0, "baseline_load_cycles": 30, "difficulty": 0.80},
    {"name": "Compaction",  "baseline_duration": 35.0, "baseline_load_cycles": 12, "difficulty": 0.35},
    {"name": "Drilling",    "baseline_duration": 55.0, "baseline_load_cycles": 18, "difficulty": 0.75},
]

WEATHER_CATEGORIES: dict[str, dict] = {
    "sunny":  {"prob": 0.30, "duration_mult": 1.00, "risk_mult": 1.00},
    "cloudy": {"prob": 0.25, "duration_mult": 1.02, "risk_mult": 1.00},
    "rainy":  {"prob": 0.15, "duration_mult": 1.15, "risk_mult": 1.30},
    "windy":  {"prob": 0.10, "duration_mult": 1.05, "risk_mult": 1.20},
    "hot":    {"prob": 0.12, "duration_mult": 1.10, "risk_mult": 1.10},
    "cold":   {"prob": 0.08, "duration_mult": 1.08, "risk_mult": 1.15},
}

# Simulation span
SIM_START = datetime(2025, 1, 1, tzinfo=timezone.utc)
SIM_DAYS = 180  # ~6 months

# Each operator completes 0–3 tasks per day (sampled via Poisson λ≈0.6)
TASKS_PER_DAY_LAMBDA = 0.6


# ═══════════════════════════════════════════════════════════════════════════
# Helper: wear factor from machine age
# ═══════════════════════════════════════════════════════════════════════════

def _wear_factor(age_years: float) -> float:
    """Linear wear factor: older machines → slightly worse performance."""
    return 1.0 + 0.015 * age_years


# ═══════════════════════════════════════════════════════════════════════════
# Entity generators
# ═══════════════════════════════════════════════════════════════════════════

def _create_operators(rng: np.random.Generator) -> list[dict]:
    """Return a list of operator dicts with latent parameters."""
    operators: list[dict] = []
    op_idx = 0
    for tier, cfg in SKILL_TIERS.items():
        for _ in range(cfg["n"]):
            op_idx += 1
            eff = float(np.clip(rng.normal(*cfg["efficiency"]), 0.15, 0.99))
            idl = float(np.clip(rng.normal(*cfg["idle"]), 0.0, 0.80))
            saf = float(np.clip(rng.normal(*cfg["safety"]), 0.0, 0.50))
            operators.append(
                {
                    "name": f"Operator-{op_idx:03d}",
                    "skill_tier": tier,
                    "latent_efficiency_mean": round(eff, 4),
                    "latent_idle_tendency": round(idl, 4),
                    "latent_safety_tendency": round(saf, 4),
                    "is_synthetic": True,
                }
            )
    return operators


def _create_machines() -> list[dict]:
    """Return machine dicts with computed wear factors."""
    return [
        {
            "name": spec["name"],
            "machine_type": spec["machine_type"],
            "age_years": spec["age_years"],
            "wear_factor": round(_wear_factor(spec["age_years"]), 4),
            "is_synthetic": True,
        }
        for spec in MACHINE_SPECS
    ]


def _create_task_catalog() -> list[dict]:
    """Return task-type dicts."""
    return [
        {
            "name": t["name"],
            "baseline_duration_minutes": t["baseline_duration"],
            "baseline_load_cycles": t["baseline_load_cycles"],
            "difficulty": t["difficulty"],
            "is_synthetic": True,
        }
        for t in TASK_TYPES
    ]


# ═══════════════════════════════════════════════════════════════════════════
# Task-instance telemetry generation (Process A)
# ═══════════════════════════════════════════════════════════════════════════

def _generate_telemetry(
    operator: Operator,
    machine: Machine,
    task: TaskCatalog,
    weather: str,
    rng: np.random.Generator,
    task_index_today: int,
    total_tasks_today: int,
) -> dict:
    """Produce a single task-instance telemetry row under Process A.

    Uses Gaussian noise for continuous values and Bernoulli injection for
    safety events.  The exact formulas here must NOT be imported by
    ``generate_actual_outcomes.py`` (Process B).
    """
    winfo = WEATHER_CATEGORIES[weather]

    # ── Duration (minutes) ─────────────────────────────────────────────
    base_dur = task.baseline_duration_minutes
    machine_mult = machine.wear_factor
    weather_mult = winfo["duration_mult"]
    # Higher efficiency → shorter duration
    operator_mult = 1.30 - 0.40 * operator.latent_efficiency_mean
    # Harder tasks amplify operator-skill differences
    difficulty_adj = 1.0 + 0.20 * (task.difficulty - 0.5)

    expected_dur = base_dur * machine_mult * weather_mult * operator_mult * difficulty_adj
    duration = expected_dur + rng.normal(0, expected_dur * 0.10)  # Gaussian noise
    duration = max(duration, base_dur * 0.30)

    # ── Idle seconds ───────────────────────────────────────────────────
    base_idle = duration * 60.0 * 0.05  # 5 % of duration as baseline
    idle_mult = 1.0 + 2.0 * operator.latent_idle_tendency
    expected_idle = base_idle * idle_mult
    idle_seconds = expected_idle + rng.normal(0, expected_idle * 0.20)
    idle_seconds = max(idle_seconds, 0.0)

    # ── Load cycles ────────────────────────────────────────────────────
    expected_cycles = task.baseline_load_cycles * (1.0 + 0.01 * machine.age_years)
    expected_cycles *= 1.10 - 0.15 * operator.latent_efficiency_mean
    load_cycles = int(expected_cycles + rng.normal(0, expected_cycles * 0.08))
    load_cycles = max(load_cycles, 1)

    # ── Efficiency score (0–1) ─────────────────────────────────────────
    base_eff = operator.latent_efficiency_mean
    machine_pen = 0.01 * machine.age_years
    weather_pen = (weather_mult - 1.0) * 0.30
    diff_pen = task.difficulty * 0.10
    efficiency = base_eff - machine_pen - weather_pen - diff_pen
    efficiency += rng.normal(0, 0.05)
    efficiency = float(np.clip(efficiency, 0.05, 1.0))

    # ── Safety events (Bernoulli — Process A) ──────────────────────────
    fatigue_proxy = task_index_today / max(total_tasks_today, 1)
    safety_risk = (
        operator.latent_safety_tendency
        * (1.0 + 0.5 * fatigue_proxy)
        * winfo["risk_mult"]
    )

    # Seatbelt: probability of being unengaged
    seatbelt_engaged = not (rng.random() < safety_risk * 0.15)

    # Proximity: higher risk operators get closer
    prox_base = rng.normal(12.0, 3.0)
    prox_offset = -operator.latent_safety_tendency * 8.0 * winfo["risk_mult"]
    min_proximity = max(prox_base + prox_offset, 0.5)

    return {
        "duration_minutes": round(float(duration), 2),
        "idle_seconds": round(float(idle_seconds), 1),
        "load_cycles": int(load_cycles),
        "efficiency_score": round(float(efficiency), 4),
        "seatbelt_engaged": bool(seatbelt_engaged),
        "min_proximity_distance": round(float(min_proximity), 2),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Main generation pipeline
# ═══════════════════════════════════════════════════════════════════════════

def generate_historical_data(engine, *, seed: int = 42) -> dict[str, int]:
    """Generate all Process-A synthetic data into the database.

    Args:
        engine: SQLAlchemy engine (tables are created if absent).
        seed: RNG seed for reproducibility within Process A.

    Returns:
        Dict with counts: operators, machines, task_types, task_instances.
    """
    rng = np.random.default_rng(seed)

    # Ensure tables exist
    Base.metadata.create_all(engine)
    DBSession = sessionmaker(bind=engine)
    session: Session = DBSession()

    try:
        # ── 1. Operators ───────────────────────────────────────────────
        op_dicts = _create_operators(rng)
        db_operators: list[Operator] = []
        for d in op_dicts:
            op = Operator(**d)
            session.add(op)
            db_operators.append(op)
        session.flush()  # assigns IDs

        # ── 2. Machines ────────────────────────────────────────────────
        m_dicts = _create_machines()
        db_machines: list[Machine] = []
        for d in m_dicts:
            m = Machine(**d)
            session.add(m)
            db_machines.append(m)
        session.flush()

        # ── 3. Task catalog ────────────────────────────────────────────
        t_dicts = _create_task_catalog()
        db_tasks: list[TaskCatalog] = []
        for d in t_dicts:
            tc = TaskCatalog(**d)
            session.add(tc)
            db_tasks.append(tc)
        session.flush()

        # ── 4. Weather probability array ───────────────────────────────
        weather_names = list(WEATHER_CATEGORIES.keys())
        weather_probs = np.array(
            [WEATHER_CATEGORIES[w]["prob"] for w in weather_names]
        )
        weather_probs = weather_probs / weather_probs.sum()  # normalise

        # ── 5. Task instances ──────────────────────────────────────────
        instances: list[TaskInstance] = []

        for day_offset in range(SIM_DAYS):
            current_date = SIM_START + timedelta(days=day_offset)

            # Sample daily weather (one per day for the whole site)
            weather = str(rng.choice(weather_names, p=weather_probs))

            for op in db_operators:
                # Poisson-sampled number of tasks this operator does today
                n_tasks = int(rng.poisson(TASKS_PER_DAY_LAMBDA))
                if n_tasks == 0:
                    continue

                for t_idx in range(n_tasks):
                    machine = db_machines[int(rng.integers(len(db_machines)))]
                    task_type = db_tasks[int(rng.integers(len(db_tasks)))]

                    telemetry = _generate_telemetry(
                        operator=op,
                        machine=machine,
                        task=task_type,
                        weather=weather,
                        rng=rng,
                        task_index_today=t_idx,
                        total_tasks_today=n_tasks,
                    )

                    # Timestamp: morning start + offset per task index
                    completed_at = current_date + timedelta(
                        hours=7 + t_idx * 2,
                        minutes=int(rng.integers(0, 60)),
                    )

                    inst = TaskInstance(
                        operator_id=op.id,
                        machine_id=machine.id,
                        task_type_id=task_type.id,
                        weather=weather,
                        is_synthetic=True,
                        source_process="A",
                        completed_at=completed_at,
                        **telemetry,
                    )
                    instances.append(inst)

        session.add_all(instances)
        session.commit()

        counts = {
            "operators": len(db_operators),
            "machines": len(db_machines),
            "task_types": len(db_tasks),
            "task_instances": len(instances),
        }
        logger.info("Process A generation complete: %s", counts)
        return counts

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ═══════════════════════════════════════════════════════════════════════════
# CLI entry point
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    from app.config import settings
    from app.db.session import get_engine

    eng = get_engine(settings.database_url)
    result = generate_historical_data(eng)
    print(f"Generated {result['task_instances']} task instances "
          f"for {result['operators']} operators across "
          f"{result['machines']} machines and {result['task_types']} task types.")
    sys.exit(0)
