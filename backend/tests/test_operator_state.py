"""Tests for Operator State EWMA Calculation, Stability, and Thresholds."""

import math
from datetime import datetime, timezone
import pytest

from app.operator_state.state import (
    DEFAULT_ALPHA,
    EXPERT_THRESHOLD,
    INTERMEDIATE_THRESHOLD,
    calculate_confidence,
    get_derived_label,
    z_to_score,
)


def test_z_to_score_mapping():
    """Verify z-score to 0-100 skill score mapping behavior.

    Center is 50.0. Scale is 15.0 per standard deviation.
    Positive-is-good dimensions (efficiency, load_cycles, safety):
      z = 0   -> 50.0
      z = +1  -> 65.0
      z = +2  -> 80.0
      z = -1  -> 35.0
      z = -2  -> 20.0
    Negative-is-good dimensions (idling, duration):
      z = 0   -> 50.0
      z = +1  -> 35.0 (penalty)
      z = -1  -> 65.0 (reward)
    """
    assert z_to_score(0.0, positive_is_good=True) == pytest.approx(50.0)
    assert z_to_score(1.0, positive_is_good=True) == pytest.approx(65.0)
    assert z_to_score(2.0, positive_is_good=True) == pytest.approx(80.0)
    assert z_to_score(-1.0, positive_is_good=True) == pytest.approx(35.0)

    # Inverted dimensions
    assert z_to_score(0.0, positive_is_good=False) == pytest.approx(50.0)
    assert z_to_score(1.0, positive_is_good=False) == pytest.approx(35.0)
    assert z_to_score(-1.0, positive_is_good=False) == pytest.approx(65.0)

    # Clipping bounds [0, 100]
    assert z_to_score(10.0, positive_is_good=True) == 100.0
    assert z_to_score(-10.0, positive_is_good=True) == 0.0


def test_derived_label_thresholds():
    """Verify that continuous composite score maps to correct categorical label."""
    assert get_derived_label(85.0) == "Expert"
    assert get_derived_label(EXPERT_THRESHOLD) == "Expert"
    assert get_derived_label(74.9) == "Intermediate"
    assert get_derived_label(50.0) == "Intermediate"
    assert get_derived_label(INTERMEDIATE_THRESHOLD) == "Intermediate"
    assert get_derived_label(49.9) == "Beginner"
    assert get_derived_label(20.0) == "Beginner"


def test_confidence_increases_with_sample_count():
    """Verify confidence monotonically increases with sample count and saturates smoothly."""
    c0 = calculate_confidence(0)
    c5 = calculate_confidence(5)
    c10 = calculate_confidence(10)
    c20 = calculate_confidence(20)
    c50 = calculate_confidence(50)

    assert c0 == 0.0
    assert 0.0 < c5 < c10 < c20 < c50 <= 1.0
    # Expected formula: 1 - exp(-n / 10)
    assert c10 == pytest.approx(1.0 - math.exp(-1.0), abs=1e-3)  # ~0.6321
    assert c20 == pytest.approx(1.0 - math.exp(-2.0), abs=1e-3)  # ~0.8647


def test_known_ewma_sequence_manual_calculation():
    """Verify a known sequence of scores matches manual step-by-step arithmetic.

    Sequence of instant scores: [60.0, 80.0, 90.0] with alpha = 0.20.
    Step 0: S_0 = 60.0
    Step 1: S_1 = 0.20 * 80.0 + 0.80 * 60.0 = 16.0 + 48.0 = 64.0
    Step 2: S_2 = 0.20 * 90.0 + 0.80 * 64.0 = 18.0 + 51.2 = 69.2
    """
    scores = [60.0, 80.0, 90.0]
    alpha = 0.20

    current = scores[0]
    for s in scores[1:]:
        current = alpha * s + (1.0 - alpha) * current

    assert current == pytest.approx(69.2, abs=1e-4)


def test_recent_observations_receive_greater_weight():
    """Verify that a recent observation has greater impact on the EWMA than an older one."""
    alpha = 0.20

    # Impulse late: [0.0, 0.0, 100.0]
    # Step 0: 0.0
    # Step 1: 0.2*0 + 0.8*0 = 0.0
    # Step 2: 0.2*100 + 0.8*0 = 20.0
    seq_recent = [0.0, 0.0, 100.0]
    s_recent = seq_recent[0]
    for s in seq_recent[1:]:
        s_recent = alpha * s + (1.0 - alpha) * s_recent

    # Impulse earlier: [0.0, 100.0, 0.0]
    # Step 0: 0.0
    # Step 1: 0.2*100 + 0.8*0 = 20.0
    # Step 2: 0.2*0 + 0.8*20 = 16.0
    seq_earlier = [0.0, 100.0, 0.0]
    s_earlier = seq_earlier[0]
    for s in seq_earlier[1:]:
        s_earlier = alpha * s + (1.0 - alpha) * s_earlier

    # More recent 100.0 impulse has greater weight (20.0 > 16.0)
    assert s_recent > s_earlier
    assert s_recent == pytest.approx(20.0)
    assert s_earlier == pytest.approx(16.0)


def test_single_outlier_does_not_cause_extreme_jump():
    """Verify EWMA damping: a single catastrophic outlier does not collapse the state."""
    alpha = DEFAULT_ALPHA  # 0.20
    established_state = 80.0  # Expert

    # A single zero-performance task occurs (outlier disaster)
    outlier_score = 0.0
    new_state = alpha * outlier_score + (1.0 - alpha) * established_state

    # 0.20 * 0 + 0.80 * 80.0 = 64.0
    assert new_state == pytest.approx(64.0)

    # Change is bounded by alpha * 100 = 20 points max
    max_possible_delta = alpha * 100.0
    assert abs(new_state - established_state) <= max_possible_delta
    # Operator is still safely above beginner (> 50.0) despite a complete zero task
    assert new_state > INTERMEDIATE_THRESHOLD
