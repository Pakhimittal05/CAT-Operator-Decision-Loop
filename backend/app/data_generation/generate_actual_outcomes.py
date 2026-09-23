"""Process B — Independent Stochastic Actual Outcome Generator (§5, §15).

Generates real-world actual operational telemetry for tasks executed after What-If
simulation or in field operations.

CRITICAL INDEPENDENCE RULES:
  1. ZERO imports from historical generation code (Process A).
  2. Distinct mathematical formulation:
     - Multiplicative Log-Normal duration noise (representing real-world site delays and skew)
       rather than Process A's additive Gaussian noise.
     - Unmodeled dynamic variation factor: hidden daily operator fatigue / site mood multiplier
       (unobserved by ML models).
     - Distinct piecewise idling behavior incorporating site delays.
     - Threshold-based safety event triggers rather than independent Bernoulli flips.
  3. Independent RNG stream with optional demo seed for reproducible demonstrations.
  4. Tagged ``source_process='B'``, ``is_synthetic=True``.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Weather multipliers unique to Process B (independent parameterization)
PROCESS_B_WEATHER_FACTORS: dict[str, dict[str, float]] = {
    "Clear": {"duration_mult": 1.00, "idle_mult": 1.00, "hazard_factor": 1.00},
    "Rain": {"duration_mult": 1.18, "idle_mult": 1.25, "hazard_factor": 1.45},
    "Mud": {"duration_mult": 1.28, "idle_mult": 1.40, "hazard_factor": 1.70},
    "Snow/Ice": {"duration_mult": 1.35, "idle_mult": 1.50, "hazard_factor": 2.10},
    # Synonyms / fallbacks
    "sunny": {"duration_mult": 1.00, "idle_mult": 1.00, "hazard_factor": 1.00},
    "cloudy": {"duration_mult": 1.03, "idle_mult": 1.05, "hazard_factor": 1.05},
    "rainy": {"duration_mult": 1.18, "idle_mult": 1.25, "hazard_factor": 1.45},
    "windy": {"duration_mult": 1.08, "idle_mult": 1.12, "hazard_factor": 1.25},
    "hot": {"duration_mult": 1.12, "idle_mult": 1.18, "hazard_factor": 1.20},
    "cold": {"duration_mult": 1.10, "idle_mult": 1.20, "hazard_factor": 1.30},
}


def generate_process_b_telemetry(
    *,
    baseline_duration: float,
    baseline_load_cycles: int,
    task_difficulty: float,
    machine_age_years: float,
    machine_wear_factor: float,
    operator_skill_tier: str,
    operator_latent_efficiency: float | None = None,
    operator_latent_idle: float | None = None,
    operator_latent_safety: float | None = None,
    weather: str = "Clear",
    seed: int | None = None,
) -> dict[str, Any]:
    """Generate realistic actual task telemetry using Stochastic Process B.

    Args:
        baseline_duration: Standard task duration in minutes.
        baseline_load_cycles: Standard cycle count.
        task_difficulty: 0–1 task complexity scale.
        machine_age_years: Machine age.
        machine_wear_factor: Machine wear factor.
        operator_skill_tier: 'Expert', 'Intermediate', or 'Beginner'.
        operator_latent_efficiency: Optional latent efficiency score (0–1).
        operator_latent_idle: Optional latent idle tendency.
        operator_latent_safety: Optional latent safety risk tendency.
        weather: Weather condition string.
        seed: Optional RNG seed. If provided, ensures reproducible outcome.
              If None, uses system entropy for stochastic live runs.

    Returns:
        Dictionary of actual observed telemetry fields.
    """
    rng = np.random.default_rng(seed)

    w_info = PROCESS_B_WEATHER_FACTORS.get(
        weather, {"duration_mult": 1.05, "idle_mult": 1.10, "hazard_factor": 1.15}
    )

    # ── 1. Hidden Daily Dynamic Factor (Unobserved by ML models) ───────────
    # Simulates circadian fatigue, weather perception, or daily crew pacing.
    # Process A does NOT have this hidden daily multiplier.
    daily_fatigue_mood = float(rng.uniform(0.92, 1.12))

    # Base operator capability approximation
    if operator_latent_efficiency is not None:
        eff_base = operator_latent_efficiency
    else:
        tier_eff = {"Expert": 0.84, "Intermediate": 0.67, "Beginner": 0.50}
        eff_base = tier_eff.get(operator_skill_tier, 0.65)

    if operator_latent_idle is not None:
        idle_base = operator_latent_idle
    else:
        tier_idle = {"Expert": 0.08, "Intermediate": 0.22, "Beginner": 0.38}
        idle_base = tier_idle.get(operator_skill_tier, 0.20)

    if operator_latent_safety is not None:
        safety_tendency = operator_latent_safety
    else:
        tier_safety = {"Expert": 0.03, "Intermediate": 0.10, "Beginner": 0.18}
        safety_tendency = tier_safety.get(operator_skill_tier, 0.10)

    # ── 2. Duration Generation with Log-Normal Multiplicative Noise ────────
    # Construction field tasks experience positive skew (delays > accelerations)
    operator_duration_factor = 1.35 - 0.45 * eff_base
    machine_delay_factor = 1.0 + 0.02 * machine_age_years + 0.05 * (machine_wear_factor - 1.0)
    weather_dur_factor = w_info["duration_mult"]
    difficulty_factor = 1.0 + 0.25 * (task_difficulty - 0.5)

    median_duration = (
        baseline_duration
        * operator_duration_factor
        * machine_delay_factor
        * weather_dur_factor
        * difficulty_factor
        * daily_fatigue_mood
    )

    # Log-normal multiplicative noise: exp(N(0, sigma^2))
    # sigma=0.09 yields realistic site variance with positive delay tail
    lognorm_noise = float(rng.lognormal(mean=0.0, sigma=0.09))
    actual_duration = max(round(median_duration * lognorm_noise, 2), round(baseline_duration * 0.35, 2))

    # ── 3. Idling Generation (Piecewise Site Delay Model) ───────────────────
    # Process B models idling as: Warm-up + Queue Wait Delays + In-task pauses
    warmup_idle = float(rng.uniform(30.0, 90.0))
    queue_delays = float(rng.exponential(scale=60.0 * idle_base * w_info["idle_mult"]))
    pacing_idle = actual_duration * 60.0 * (0.04 + 0.12 * idle_base)
    actual_idle_seconds = max(round(warmup_idle + queue_delays + pacing_idle, 1), 0.0)

    # ── 4. Load Cycles ─────────────────────────────────────────────────────
    # Expected cycles influenced by efficiency and machine response
    expected_cycles = baseline_load_cycles * (1.08 - 0.12 * eff_base)
    cycle_noise = int(rng.integers(-2, 3))
    actual_load_cycles = max(int(round(expected_cycles)) + cycle_noise, 1)

    # ── 5. Cycle Efficiency Score ──────────────────────────────────────────
    # Dynamic efficiency reflecting fatigue, terrain, and duration excursion
    eff_shift = (
        (eff_base * 1.02)
        - (0.015 * machine_age_years)
        - ((w_info["duration_mult"] - 1.0) * 0.35)
        - (0.08 * (daily_fatigue_mood - 1.0))
    )
    # Add slight random perturbation
    eff_noise = float(rng.normal(0.0, 0.035))
    actual_efficiency = float(np.clip(round(eff_shift + eff_noise, 4), 0.10, 0.99))

    # ── 6. Safety Outcomes (Threshold & Hazard-Burst Logic) ─────────────────
    # Rather than independent Bernoulli coin flips, Process B models proximity
    # as spatial clearance influenced by hazard bursts and fatigue.
    hazard_multiplier = w_info["hazard_factor"] * (1.0 + 0.8 * (daily_fatigue_mood - 1.0))

    # Safe baseline clearance: 10.0m - 15.0m
    clearance_base = float(rng.uniform(9.0, 14.0))
    proximity_reduction = safety_tendency * 12.0 * hazard_multiplier

    # Occasional near-miss hazard event if fatigue/hazard factor is very high
    hazard_burst = 0.0
    if rng.random() < (0.08 * safety_tendency * hazard_multiplier):
        hazard_burst = float(rng.uniform(3.0, 6.0))

    actual_proximity = max(round(clearance_base - proximity_reduction - hazard_burst, 2), 0.60)

    # Seatbelt compliance: threshold-based on safety tendency and high fatigue
    # Highly compliant operators almost always wear seatbelts; risk increases under high fatigue
    seatbelt_disengage_risk = (safety_tendency * 0.10) * (daily_fatigue_mood**2)
    seatbelt_engaged = bool(rng.random() >= seatbelt_disengage_risk)

    return {
        "duration_minutes": actual_duration,
        "idle_seconds": actual_idle_seconds,
        "load_cycles": actual_load_cycles,
        "efficiency_score": actual_efficiency,
        "seatbelt_engaged": seatbelt_engaged,
        "min_proximity_distance": actual_proximity,
    }
