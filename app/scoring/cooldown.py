from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
from dateutil.relativedelta import relativedelta

from app.config import ZIP_HISTORY_PATH
from app.scoring.zip_score import normalize_zip


HISTORY_COLUMNS = [
    "ZIP",
    "State",
    "County",
    "Date Sent",
    "Assigned List",
    "Assigned Agency",
    "Report Month",
    "Estimated Population",
    "Estimated Lead Volume",
]


def load_zip_usage_history(path: Path = ZIP_HISTORY_PATH) -> pd.DataFrame:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        history = pd.DataFrame(columns=HISTORY_COLUMNS)
        history.to_csv(path, index=False)
        return history
    history = pd.read_csv(path, dtype={"ZIP": str})
    for column in HISTORY_COLUMNS:
        if column not in history.columns:
            history[column] = ""
    history["ZIP"] = history["ZIP"].map(normalize_zip)
    return history[HISTORY_COLUMNS]


def save_zip_usage_history(history_df: pd.DataFrame, path: Path = ZIP_HISTORY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    history_df.to_csv(path, index=False)


def is_zip_eligible(
    zip_code: str,
    report_date: date,
    cooldown_months: int,
    history_df: pd.DataFrame | None = None,
) -> bool:
    if history_df is None or history_df.empty:
        return True
    normalized = normalize_zip(zip_code)
    matches = history_df.loc[history_df["ZIP"].map(normalize_zip) == normalized].copy()
    if matches.empty:
        return True
    dates = pd.to_datetime(matches["Date Sent"], errors="coerce").dropna()
    if dates.empty:
        return True
    latest = dates.max().date()
    return latest <= report_date - relativedelta(months=cooldown_months)


def apply_zip_cooldown_filter(
    df: pd.DataFrame,
    history_df: pd.DataFrame,
    report_date: date,
    cooldown_months: int,
    allow_override: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    filtered = df.copy()
    filtered["zip"] = filtered["zip"].map(normalize_zip)
    latest_dates = {}
    if not history_df.empty:
        history = history_df.copy()
        history["ZIP"] = history["ZIP"].map(normalize_zip)
        history["_date"] = pd.to_datetime(history["Date Sent"], errors="coerce")
        latest_dates = history.groupby("ZIP")["_date"].max().to_dict()
    cutoff = report_date - relativedelta(months=cooldown_months)
    filtered["last_used_date"] = filtered["zip"].map(lambda z: latest_dates.get(z, pd.NaT))
    filtered["eligible_based_on_cooldown"] = filtered["last_used_date"].map(
        lambda d: True if pd.isna(d) else d.date() <= cutoff
    )
    filtered["manual_review_flag"] = filtered["eligible_based_on_cooldown"].map(
        lambda eligible: "" if eligible else "Excluded by cooldown"
    )
    excluded = filtered.loc[~filtered["eligible_based_on_cooldown"]].copy()
    if allow_override:
        warnings = [
            "Cooldown override is enabled. Reused ZIPs must be reviewed before outreach if eligible volume is exhausted."
        ]
        return filtered, excluded, warnings
    warnings = []
    if not excluded.empty:
        warnings.append(f"{len(excluded)} ZIP codes excluded because they were used within the cooldown window.")
    return filtered.loc[filtered["eligible_based_on_cooldown"]].copy(), excluded, warnings

