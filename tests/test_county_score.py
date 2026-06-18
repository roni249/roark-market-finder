from __future__ import annotations

import pandas as pd

from app.scoring.county_score import score_counties


def test_score_counties_adds_scores_and_ranges() -> None:
    df = pd.DataFrame(
        [
            {"state": "GA", "county": "Fulton County", "active_listing_count": 100, "pending_listing_count": 30, "median_listing_price": 250000, "median_days_on_market": 30, "price_decrease_count": 12},
            {"state": "GA", "county": "Cobb", "active_listing_count": 50, "pending_listing_count": 5, "median_listing_price": 600000, "median_days_on_market": 90, "price_decrease_count": 2},
        ]
    )
    scored = score_counties(df)
    assert "county_score" in scored.columns
    assert scored.loc[0, "county"] == "Fulton"
    assert scored["county_score"].between(0, 100).all()
    assert scored.loc[0, "recommended_home_value_range"].startswith("$")

