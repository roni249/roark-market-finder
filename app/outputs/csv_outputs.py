from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.config import EXPORTS_DIR, PROCESSED_DIR


def save_dataframe(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path


def save_processed_outputs(
    report_month: str,
    county_rankings: pd.DataFrame,
    zip_rankings: pd.DataFrame,
    list_a: pd.DataFrame,
    list_b: pd.DataFrame,
    manual_review: pd.DataFrame,
    data_notes: pd.DataFrame,
) -> dict[str, Path]:
    suffix = report_month.replace("-", "_")
    paths = {
        "county_rankings": PROCESSED_DIR / f"county_rankings_{suffix}.csv",
        "zip_rankings": PROCESSED_DIR / f"zip_rankings_{suffix}.csv",
        "cold_caller_list_a": EXPORTS_DIR / f"cold_caller_list_a_{suffix}.csv",
        "cold_caller_list_b": EXPORTS_DIR / f"cold_caller_list_b_{suffix}.csv",
        "manual_review": PROCESSED_DIR / f"manual_review_{suffix}.csv",
        "data_notes": PROCESSED_DIR / f"data_notes_{suffix}.csv",
    }
    save_dataframe(county_rankings, paths["county_rankings"])
    save_dataframe(zip_rankings, paths["zip_rankings"])
    save_dataframe(list_a, paths["cold_caller_list_a"])
    save_dataframe(list_b, paths["cold_caller_list_b"])
    save_dataframe(manual_review, paths["manual_review"])
    save_dataframe(data_notes, paths["data_notes"])
    return paths

