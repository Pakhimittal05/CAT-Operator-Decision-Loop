"""Deterministic Proximity Hazard Detector (§13).

Architecture Specification (§13):
- Telemetry field: `min_proximity_distance` (meters).
- Event triggered if below configured safe distance for the machine type / zone.
- Deterministic rule-based evaluation, no ML dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.config import settings

# Machine-specific safe proximity distance buffers (in meters)
MACHINE_PROXIMITY_BUFFERS: dict[str, float] = {
    "Crane": 7.0,
    "Excavator": 6.0,
    "Bulldozer": 5.5,
    "Dump Truck": 5.0,
    "Wheel Loader": 5.0,
    "Motor Grader": 5.0,
    "Compactor": 5.0,
}

DEFAULT_SAFE_DISTANCE: float = settings.proximity_safe_distance_meters  # 5.0m


@dataclass(frozen=True)
class ProximityBreachResult:
    """Result of proximity hazard evaluation."""

    is_violation: bool
    severity: str  # medium | high | critical
    description: str
    recorded_distance: float
    safe_distance_threshold: float
    machine_type: str
    is_synthetic: bool = True


def get_safe_distance_for_machine(machine_type: Optional[str]) -> float:
    """Return configured safe distance threshold for the given machine type."""
    if not machine_type:
        return DEFAULT_SAFE_DISTANCE
    return MACHINE_PROXIMITY_BUFFERS.get(machine_type, DEFAULT_SAFE_DISTANCE)


def evaluate_proximity_hazard(
    min_proximity_distance: float,
    machine_type: Optional[str] = None,
    custom_safe_distance: Optional[float] = None,
) -> Optional[ProximityBreachResult]:
    """Evaluate proximity telemetry against machine-specific safety buffers.

    Parameters:
        min_proximity_distance: Minimum recorded proximity distance in meters during task.
        machine_type: Type of machine (e.g. Crane, Excavator, Dump Truck).
        custom_safe_distance: Optional override for the safe buffer distance.

    Returns:
        ProximityBreachResult if a hazard occurred, None if within safe distance.
    """
    safe_distance = (
        custom_safe_distance
        if custom_safe_distance is not None
        else get_safe_distance_for_machine(machine_type)
    )

    machine_label = machine_type or "Heavy Equipment"

    if min_proximity_distance >= safe_distance:
        return None

    # Severity classification:
    # < 1.5m: critical (immediate blindspot / collision hazard)
    # 1.5m - 3.0m: high (severe exclusion zone violation)
    # 3.0m - safe_distance: medium (buffer breach)
    if min_proximity_distance < 1.5:
        severity = "critical"
        category_desc = "Critical collision hazard"
    elif min_proximity_distance < 3.0:
        severity = "high"
        category_desc = "Severe proximity zone breach"
    else:
        severity = "medium"
        category_desc = "Safety buffer margin breach"

    description = (
        f"{category_desc}: Min recorded distance was {min_proximity_distance:.2f}m "
        f"for {machine_label} (required safe buffer: {safe_distance:.1f}m)."
    )

    return ProximityBreachResult(
        is_violation=True,
        severity=severity,
        description=description,
        recorded_distance=round(min_proximity_distance, 2),
        safe_distance_threshold=round(safe_distance, 1),
        machine_type=machine_label,
        is_synthetic=True,
    )
