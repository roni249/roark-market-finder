from __future__ import annotations

import math


STATE_PRICE_RANGES = {
    "FL": {"best": (180_000, 450_000), "good": (130_000, 550_000), "poor": (80_000, 700_000)},
    "MI": {"best": (90_000, 275_000), "good": (70_000, 350_000), "poor": (50_000, 450_000)},
    "GA": {"best": (140_000, 350_000), "good": (100_000, 450_000), "poor": (70_000, 575_000)},
    "AL": {"best": (100_000, 275_000), "good": (75_000, 350_000), "poor": (50_000, 450_000)},
}

STATE_INVESTOR_RANGE_MULTIPLIERS = {
    "FL": (0.535, 1.13),
    "MI": (0.50, 1.3334),
    "GA": (0.60, 1.30),
    "AL": (0.525, 1.37),
}


def _range_for_state(state: str) -> dict[str, tuple[int, int]]:
    return STATE_PRICE_RANGES.get(state.upper(), STATE_PRICE_RANGES["GA"])


def score_affordability(price: float | int | None, state: str) -> float:
    if price is None or not math.isfinite(float(price)) or float(price) <= 0:
        return 0.0
    price = float(price)
    ranges = _range_for_state(state)
    best_low, best_high = ranges["best"]
    good_low, good_high = ranges["good"]
    poor_low, poor_high = ranges["poor"]
    if best_low <= price <= best_high:
        return 100.0
    if good_low <= price <= good_high:
        if price < best_low:
            return 70.0 + 30.0 * ((price - good_low) / max(best_low - good_low, 1))
        return 100.0 - 30.0 * ((price - best_high) / max(good_high - best_high, 1))
    if poor_low <= price <= poor_high:
        if price < good_low:
            return 25.0 + 45.0 * ((price - poor_low) / max(good_low - poor_low, 1))
        return 70.0 - 45.0 * ((price - good_high) / max(poor_high - good_high, 1))
    return 0.0


def recommend_value_range(median_price: float | int | None, state: str) -> str:
    ranges = _range_for_state(state)
    best_low, best_high = ranges["best"]
    good_low, good_high = ranges["good"]
    if median_price is None or not math.isfinite(float(median_price)) or float(median_price) <= 0:
        low, high = best_low, best_high
    else:
        median = float(median_price)
        low_multiplier, high_multiplier = STATE_INVESTOR_RANGE_MULTIPLIERS.get(
            state.upper(), STATE_INVESTOR_RANGE_MULTIPLIERS["GA"]
        )
        low = max(good_low, median * low_multiplier)
        high = min(good_high, median * high_multiplier)
        if high <= low:
            high = min(good_high, low + 100_000)
    return f"${round(low / 1000):,.0f}k-${round(high / 1000):,.0f}k"
