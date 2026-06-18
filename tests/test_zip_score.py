from __future__ import annotations

import pandas as pd

from app.scoring.zip_score import normalize_zip, score_zips


def test_normalize_zip_preserves_leading_zeroes() -> None:
    assert normalize_zip("123") == "00123"


def test_score_zips_uses_active_listings_as_volume_proxy() -> None:
    df = pd.DataFrame(
        [
            {"state": "MI", "county": "Wayne", "zip": "48101", "active_listing_count": 100, "pending_listing_count": 20, "median_listing_price": 180000, "median_days_on_market": 35, "price_decrease_count": 10},
            {"state": "MI", "county": "Wayne", "zip": "48102", "active_listing_count": 25, "pending_listing_count": 4, "median_listing_price": 500000, "median_days_on_market": 100, "price_decrease_count": 1},
        ]
    )
    scored = score_zips(df)
    assert scored["estimated_lead_volume"].tolist() == [100, 25]
    assert scored["zip_score"].between(0, 100).all()

