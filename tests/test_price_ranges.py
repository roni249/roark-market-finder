from __future__ import annotations

from app.scoring.price_ranges import recommend_value_range, score_affordability


def test_affordability_best_range_scores_high() -> None:
    assert score_affordability(250000, "GA") == 100
    assert score_affordability(900000, "GA") == 0


def test_recommend_value_range_is_state_aware() -> None:
    assert recommend_value_range(180000, "MI") == "$90k-$240k"
    assert recommend_value_range(420000, "FL") == "$225k-$475k"
