from __future__ import annotations

from datetime import date

import pandas as pd

from app.scoring.cooldown import apply_zip_cooldown_filter, is_zip_eligible


def test_zip_ineligible_inside_cooldown() -> None:
    history = pd.DataFrame([{"ZIP": "30301", "Date Sent": "2025-06-01"}])
    assert not is_zip_eligible("30301", date(2026, 6, 1), 18, history)


def test_cooldown_filter_excludes_recent_zip() -> None:
    zips = pd.DataFrame([{"zip": "30301"}, {"zip": "30302"}])
    history = pd.DataFrame([{"ZIP": "30301", "Date Sent": "2025-06-01"}])
    eligible, excluded, warnings = apply_zip_cooldown_filter(zips, history, date(2026, 6, 1), 18)
    assert eligible["zip"].tolist() == ["30302"]
    assert excluded["zip"].tolist() == ["30301"]
    assert warnings

