"""Unified Incident Service Layer (§13, §B).

Coordinates deterministic safety rule evaluation, incident logging into the
unified `incident_events` database table, deduplication, and historical backfill.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.db.models import IncidentEvent, Machine, Operator, TaskInstance
from app.safety.proximity import evaluate_proximity_hazard
from app.safety.seatbelt import evaluate_seatbelt_compliance

logger = logging.getLogger("cat_decision_loop.safety")

VALID_SOURCES = {"seatbelt", "proximity", "deviation_anomaly", "manual"}
VALID_SEVERITIES = {"low", "medium", "high", "critical"}


class IncidentService:
    """Service handling incident logging, evaluation, and retrieval."""

    @staticmethod
    def log_incident(
        db: Session,
        operator_id: int,
        source: str,
        severity: str,
        description: Optional[str] = None,
        machine_id: Optional[int] = None,
        task_instance_id: Optional[int] = None,
        created_at: Optional[datetime] = None,
    ) -> IncidentEvent:
        """Create and persist an incident event with strict validation and deduplication."""
        source_clean = source.lower().strip()
        severity_clean = severity.lower().strip()

        if source_clean not in VALID_SOURCES:
            raise ValueError(
                f"Invalid incident source '{source}'. Must be one of {sorted(VALID_SOURCES)}"
            )

        if severity_clean not in VALID_SEVERITIES:
            raise ValueError(
                f"Invalid incident severity '{severity}'. Must be one of {sorted(VALID_SEVERITIES)}"
            )

        # Operator existence validation
        op = db.query(Operator).filter(Operator.id == operator_id).first()
        if not op:
            raise ValueError(f"Operator #{operator_id} does not exist.")

        # Deduplication check for task-linked incidents
        if task_instance_id is not None:
            existing = (
                db.query(IncidentEvent)
                .filter(
                    IncidentEvent.task_instance_id == task_instance_id,
                    IncidentEvent.source == source_clean,
                )
                .first()
            )
            if existing:
                return existing

        incident = IncidentEvent(
            operator_id=operator_id,
            machine_id=machine_id,
            task_instance_id=task_instance_id,
            source=source_clean,
            severity=severity_clean,
            description=description,
            created_at=created_at or datetime.now(timezone.utc),
        )

        db.add(incident)
        db.commit()
        db.refresh(incident)
        return incident

    @classmethod
    def evaluate_task_instance(
        cls, db: Session, task: TaskInstance, auto_commit: bool = True
    ) -> list[IncidentEvent]:
        """Evaluate a TaskInstance against seatbelt and proximity detectors and record incidents.

        Deduplicates against existing incidents for the task instance.
        """
        created_incidents: list[IncidentEvent] = []
        machine_type = task.machine.machine_type if task.machine else None

        # 1. Seatbelt Compliance Rule
        seatbelt_res = evaluate_seatbelt_compliance(
            seatbelt_engaged=bool(task.seatbelt_engaged),
            duration_minutes=task.duration_minutes,
            idle_seconds=task.idle_seconds,
        )
        if seatbelt_res and seatbelt_res.is_violation:
            # Check deduplication
            existing = (
                db.query(IncidentEvent)
                .filter(
                    IncidentEvent.task_instance_id == task.id,
                    IncidentEvent.source == "seatbelt",
                )
                .first()
            )
            if not existing:
                inc = IncidentEvent(
                    task_instance_id=task.id,
                    operator_id=task.operator_id,
                    machine_id=task.machine_id,
                    source="seatbelt",
                    severity=seatbelt_res.severity,
                    description=seatbelt_res.description,
                    created_at=task.completed_at or datetime.now(timezone.utc),
                )
                db.add(inc)
                created_incidents.append(inc)
            else:
                created_incidents.append(existing)

        # 2. Proximity Hazard Rule
        prox_res = evaluate_proximity_hazard(
            min_proximity_distance=task.min_proximity_distance,
            machine_type=machine_type,
        )
        if prox_res and prox_res.is_violation:
            existing = (
                db.query(IncidentEvent)
                .filter(
                    IncidentEvent.task_instance_id == task.id,
                    IncidentEvent.source == "proximity",
                )
                .first()
            )
            if not existing:
                inc = IncidentEvent(
                    task_instance_id=task.id,
                    operator_id=task.operator_id,
                    machine_id=task.machine_id,
                    source="proximity",
                    severity=prox_res.severity,
                    description=prox_res.description,
                    created_at=task.completed_at or datetime.now(timezone.utc),
                )
                db.add(inc)
                created_incidents.append(inc)
            else:
                created_incidents.append(existing)

        if auto_commit and created_incidents:
            db.commit()
            for inc in created_incidents:
                db.refresh(inc)

        return created_incidents

    @staticmethod
    def get_incidents(
        db: Session,
        limit: int = 50,
        offset: int = 0,
        source: Optional[str] = None,
        severity: Optional[str] = None,
        operator_id: Optional[int] = None,
    ) -> tuple[list[IncidentEvent], int]:
        """Query unified incident events with filters and pagination."""
        query = db.query(IncidentEvent)

        if source:
            query = query.filter(IncidentEvent.source == source.lower().strip())
        if severity:
            query = query.filter(IncidentEvent.severity == severity.lower().strip())
        if operator_id:
            query = query.filter(IncidentEvent.operator_id == operator_id)

        total_count = query.count()
        incidents = (
            query.order_by(IncidentEvent.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return incidents, total_count

    @staticmethod
    def get_incident_statistics(db: Session) -> dict[str, Any]:
        """Aggregate incident totals and distribution breakdowns."""
        total = db.query(IncidentEvent).count()

        severities = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        sources = {"seatbelt": 0, "proximity": 0, "deviation_anomaly": 0, "manual": 0}

        all_events = db.query(IncidentEvent.severity, IncidentEvent.source).all()
        for sev, src in all_events:
            if sev in severities:
                severities[sev] += 1
            if src in sources:
                sources[src] += 1

        return {
            "total_incidents": total,
            "by_severity": severities,
            "by_source": sources,
            "is_synthetic": True,
        }

    @classmethod
    def sync_historical_task_incidents(cls, db: Session) -> int:
        """Idempotently backfill historical incident events from task telemetry.

        Does NOT modify the Process-A generator or regenerate data.
        Inspects existing task instances and creates incident records for any
        unlatched seatbelts or proximity breaches that are not yet logged.
        """
        # If historical task incidents are already backfilled, skip
        historical_task_incident_count = (
            db.query(IncidentEvent)
            .filter(IncidentEvent.task_instance_id.isnot(None))
            .count()
        )
        if historical_task_incident_count > 50:
            logger.info("Historical incidents already backfilled (%d events); skipping.", historical_task_incident_count)
            return 0

        logger.info("Performing idempotent historical incident backfill from task telemetry...")
        tasks_with_breaches = (
            db.query(TaskInstance)
            .filter(
                (TaskInstance.seatbelt_engaged == False)  # noqa: E712
                | (TaskInstance.min_proximity_distance < 7.0)
            )
            .all()
        )

        new_count = 0
        for task in tasks_with_breaches:
            created = cls.evaluate_task_instance(db, task, auto_commit=False)
            new_count += len(created)

        db.commit()
        logger.info("Backfill complete: recorded %d historical safety incident events.", new_count)
        return new_count
