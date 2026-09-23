"""Safety Engine module for CAT Operator Decision Loop (§13).

Contains deterministic rule-based detectors for:
- Seatbelt compliance (seatbelt.py)
- Proximity hazard detection (proximity.py)
- Unified incident service (incident_service.py)
"""

from app.safety.incident_service import IncidentService
from app.safety.proximity import evaluate_proximity_hazard
from app.safety.seatbelt import evaluate_seatbelt_compliance

__all__ = [
    "evaluate_seatbelt_compliance",
    "evaluate_proximity_hazard",
    "IncidentService",
]
