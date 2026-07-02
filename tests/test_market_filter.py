from __future__ import annotations

import pandas as pd

from app.scoring.market_filter import filter_dense_residential_zips, filter_zips_near_major_cities


def test_zip_filter_keeps_configured_major_city_prefixes() -> None:
    zips = pd.DataFrame(
        [
            {"state": "GA", "zip": "30301", "county": "Atlanta ZIP Market"},
            {"state": "GA", "zip": "39813", "county": "Arlington ZIP Market"},
        ]
    )
    filters = pd.DataFrame(
        [
            {
                "state": "GA",
                "major_city": "Atlanta",
                "county": "Fulton",
                "zip_prefix": "303",
                "approx_drive_minutes": 45,
            }
        ]
    )
    filters["county_key"] = filters["county"].str.lower()
    kept, excluded = filter_zips_near_major_cities(zips, filters, 45)
    assert kept["zip"].tolist() == ["30301"]
    assert excluded["zip"].tolist() == ["39813"]
    assert kept.loc[0, "major_city"] == "Atlanta"


def test_dense_residential_filter_tops_up_to_preserve_state_volume() -> None:
    zips = pd.DataFrame(
        [
            {"state": "AL", "zip": "35201", "estimated_lead_volume": 40, "active_listing_count": 40, "zip_score": 80},
            {"state": "AL", "zip": "35202", "estimated_lead_volume": 20, "active_listing_count": 20, "zip_score": 90},
            {"state": "AL", "zip": "35203", "estimated_lead_volume": 5, "active_listing_count": 5, "zip_score": 95},
        ]
    )
    kept, excluded, diagnostics = filter_dense_residential_zips(zips, min_lead_volume=25, target_zips_per_state=2)
    assert kept["zip"].tolist() == ["35201", "35202"]
    assert excluded["zip"].tolist() == ["35203"]
    assert diagnostics.loc[0, "Dense ZIPs"] == 1
    assert diagnostics.loc[0, "Top-Up ZIPs"] == 1
