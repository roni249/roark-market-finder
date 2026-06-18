from __future__ import annotations

import pandas as pd

from app.scoring.split_lists import split_into_two_balanced_lists, validate_no_duplicate_zips


def test_split_lists_has_no_duplicate_zips_and_balances_states() -> None:
    df = pd.DataFrame(
        [
            {"state": "FL", "county": "A", "zip": "33001", "zip_score": 99, "estimated_lead_volume": 100, "estimated_population": 100, "recommended_home_value_range": "$180k-$450k"},
            {"state": "FL", "county": "A", "zip": "33002", "zip_score": 98, "estimated_lead_volume": 90, "estimated_population": 90, "recommended_home_value_range": "$180k-$450k"},
            {"state": "GA", "county": "B", "zip": "30301", "zip_score": 97, "estimated_lead_volume": 80, "estimated_population": 80, "recommended_home_value_range": "$140k-$350k"},
            {"state": "GA", "county": "B", "zip": "30302", "zip_score": 96, "estimated_lead_volume": 70, "estimated_population": 70, "recommended_home_value_range": "$140k-$350k"},
        ]
    )
    list_a, list_b, balance = split_into_two_balanced_lists(df)
    validate_no_duplicate_zips(list_a, list_b)
    assert set(balance["State"]) == {"FL", "GA"}
    assert len(list_a) == 2
    assert len(list_b) == 2

