"""Deterministic Seatbelt Compliance Detector (§13).

Architecture Specification (§13):
- Telemetry field: `seatbelt_engaged` (bool).
- Event triggered if unengaged while machine in motion/operating for > threshold seconds.

Data Representation Note (§Data Constraint):
In task-level summary telemetry, continuous high-frequency time-slice streams are
aggregated. The field `seatbelt_engaged = False` indicates that the operator operated
the machine without seatbelt engagement. The task's active operating duration
`(duration_minutes * 60 - idle_seconds)` serves as the documented task-level proxy for
unengaged operating time exceeding the 5.0-second safety threshold. We explicitly document
this proxy rather than claiming continuous 5-second sensor sampling.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.config import settings


@dataclass(frozen=True)
class SeatbeltBreachResult:
    """Result of seatbelt compliance evaluation."""

    is_violation: bool
    severity: str  # low | medium | high | critical
    description: str
    threshold_seconds: float
    operating_seconds: float
    is_synthetic: bool = True


def evaluate_seatbelt_compliance(
    seatbelt_engaged: bool,
    duration_minutes: float,
    idle_seconds: float = 0.0,
    threshold_seconds: Optional[float] = None,
) -> Optional[SeatbeltBreachResult]:
    """Evaluate seatbelt compliance using existing task telemetry fields.

    Parameters:
        seatbelt_engaged: Whether seatbelt was engaged during the task.
        duration_minutes: Total task duration in minutes.
        idle_seconds: Idling duration in seconds during task.
        threshold_seconds: Safety threshold seconds (defaults to settings.seatbelt_unengaged_threshold_seconds = 5.0s).

    Returns:
        SeatbeltBreachResult if a violation occurred, None if compliant.
    """
    if seatbelt_engaged:
        return None

    threshold = (
        threshold_seconds
        if threshold_seconds is not None
        else settings.seatbelt_unengaged_threshold_seconds
    )

    # Documented proxy: active operating time = total task seconds - idle seconds
    active_operating_seconds = max(0.0, (duration_minutes * 60.0) - idle_seconds)

    if active_operating_seconds <= threshold:
        return None

    # Severity categorization based on active unlatched operating exposure
    if active_operating_seconds >= 600.0:  # >= 10 minutes active without seatbelt
        severity = "high"
    elif active_operating_seconds >= 60.0:  # >= 1 minute active without seatbelt
        severity = "medium"
    else:
        severity = "low"

    description = (
        f"Seatbelt unlatched during machine operation (task active time: "
        f"{active_operating_seconds:.1f}s, exceeding {threshold:.1f}s threshold proxy)."
    )

    return SeatbeltBreachResult(
        is_violation=True,
        severity=severity,
        description=description,
        threshold_seconds=threshold,
        operating_seconds=round(active_operating_seconds, 1),
        is_synthetic=True,
    )


def evaluate_seatbelt_unlatched_duration(
    seatbelt_engaged: bool,
    unlatched_motion_seconds: float,
    threshold_seconds: Optional[float] = None,
) -> Optional[SeatbeltBreachResult]:
    """Direct evaluation when explicit motion seconds are provided (e.g. unit tests or streaming slice)."""
    if seatbelt_engaged:
        return None

    threshold = (
        threshold_seconds
        if threshold_seconds is not None
        else settings.seatbelt_unengaged_threshold_seconds
    )

    if unlatched_motion_seconds <= threshold:
        return None

    if unlatched_motion_seconds >= 300.0:
        severity = "high"
    elif unlatched_motion_seconds >= 30.0:
        severity = "medium"
    else:
        severity = "low"

    description = (
        f"Seatbelt unengaged for {unlatched_motion_seconds:.1f}s while in motion "
        f"(exceeds {threshold:.1f}s threshold)."
    )

    return SeatbeltBreachResult(
        is_violation=True,
        severity=severity,
        description=description,
        threshold_seconds=threshold,
        operating_seconds=round(unlatched_motion_seconds, 1),
        is_synthetic=True,
    )
