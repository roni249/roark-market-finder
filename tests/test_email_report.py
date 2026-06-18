from __future__ import annotations

import pandas as pd

from app.outputs.email_report import prepare_agency_email


def test_prepare_agency_email_contains_only_assigned_list() -> None:
    assigned = pd.DataFrame(
        [
            {
                "state": "FL",
                "county": "Orange",
                "zip": "32801",
                "recommended_home_value_range": "$180k-$450k",
                "priority": "High",
                "reason": "Strong pending ratio.",
            }
        ]
    )
    email = prepare_agency_email("List A", "Agency A", "a@example.com", assigned, "2026-06")
    assert "32801" in email.body
    assert "List B" not in email.body
    assert email.recipient == "a@example.com"

