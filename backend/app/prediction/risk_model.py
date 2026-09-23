"""Risk and Skill Fit Evaluation Models (§12).

Calculates:
  - Skill Fit Score (0-100) comparing operator competence vs task difficulty
  - Behavioral/Safety Risk Indicator (%) derived from operator safety history,
    machine wear, task complexity, and environmental conditions
  - Training Recommendation trigger
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

WEATHER_RISK_FACTORS: dict[str, float] = {
    "Clear": 0.05,
    "Rain": 0.16,
    "Mud": 0.22,
    "Snow/Ice": 0.28,
}


@dataclass(frozen=True)
class RiskFitResult:
    """Skill fit and safety risk assessment result."""

    skill_fit_score: float
    skill_fit_label: str
    safety_risk_score: float
    safety_risk_level: str
    training_recommended: bool
    training_reason: str | None


def calculate_skill_fit(operator_task_score: float, task_difficulty: float) -> tuple[float, str]:
    """Calculate continuous skill fit score (0-100) and descriptive label.

    Higher operator performance on a high difficulty task yields high fit.
    Low performance on high difficulty yields low fit.
    """
    # Baseline adjustment: difficulty > 0.5 penalizes lower skilled operators more
    diff_penalty = (task_difficulty - 0.5) * 35.0
    raw_fit = operator_task_score - diff_penalty
    fit_score = float(max(10.0, min(99.0, round(raw_fit, 1))))

    if fit_score >= 80.0:
        label = "High Match"
    elif fit_score >= 60.0:
        label = "Acceptable Match"
    elif fit_score >= 45.0:
        label = "Marginal Match"
    else:
        label = "Skill Deficit"

    return fit_score, label


def calculate_safety_risk(
    operator_safety_score: float,
    machine_wear: float,
    task_difficulty: float,
    weather: str,
) -> tuple[float, str]:
    """Calculate composite safety risk score (0-100%) and risk tier."""
    # 1. Operator safety vulnerability (lower score = higher risk)
    op_risk = max(0.0, (100.0 - operator_safety_score) / 100.0) * 0.40

    # 2. Machine wear risk
    mach_risk = max(0.0, min(1.0, machine_wear)) * 0.20

    # 3. Task complexity
    task_risk = max(0.0, min(1.0, task_difficulty)) * 0.15

    # 4. Environmental factor
    env_risk = WEATHER_RISK_FACTORS.get(weather, 0.10)

    total_risk = (op_risk + mach_risk + task_risk + env_risk) * 100.0
    risk_score = float(max(5.0, min(95.0, round(total_risk, 1))))

    if risk_score < 35.0:
        level = "low"
    elif risk_score < 60.0:
        level = "moderate"
    else:
        level = "elevated"

    return risk_score, level


def evaluate_training_need(skill_fit: float, safety_risk: float) -> tuple[bool, str | None]:
    """Evaluate whether targeted training/coaching is recommended before assignment."""
    low_skill = skill_fit < 55.0
    high_risk = safety_risk >= 60.0

    if low_skill and high_risk:
        return (
            True,
            "Demonstrated skill deficit on this task type combined with elevated site risk; refresher training recommended prior to assignment.",
        )
    elif low_skill:
        return (
            True,
            "Operator dynamic competence rating indicates a targeted skill refresher is recommended for this task difficulty.",
        )
    elif high_risk:
        return (
            True,
            "Elevated operational safety risk in current conditions; pre-task coaching and safety briefing recommended.",
        )

    return False, None


def assess_risk_and_fit(
    operator_score: float,
    operator_safety_score: float,
    machine_wear: float,
    task_difficulty: float,
    weather: str,
) -> RiskFitResult:
    """Convenience evaluator combining skill fit, safety risk, and training trigger."""
    skill_fit, fit_label = calculate_skill_fit(operator_score, task_difficulty)
    safety_risk, risk_level = calculate_safety_risk(
        operator_safety_score, machine_wear, task_difficulty, weather
    )
    training_rec, reason = evaluate_training_need(skill_fit, safety_risk)

    return RiskFitResult(
        skill_fit_score=skill_fit,
        skill_fit_label=fit_label,
        safety_risk_score=safety_risk,
        safety_risk_level=risk_level,
        training_recommended=training_rec,
        training_reason=reason,
    )
