from __future__ import annotations

from datetime import date
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlretrieve

import pandas as pd

from app.config import RAW_DIR


COUNTY_COLUMN_ALIASES = {
    "period": ["period", "month", "month_date_yyyymm", "month_date", "report_month"],
    "state": ["state", "state_id", "state_code"],
    "county": ["county", "county_name"],
    "active_listing_count": ["active_listing_count", "active_listing_count_yy", "total_listing_count"],
    "pending_listing_count": ["pending_listing_count", "pending_ratio_count"],
    "median_listing_price": ["median_listing_price", "median_listing_price_yy"],
    "median_days_on_market": ["median_days_on_market", "median_days_on_market_yy"],
    "price_decrease_count": ["price_decrease_count", "price_reduced_count", "price_reduced_count_yy"],
    "new_listing_count": ["new_listing_count", "new_listing_count_yy"],
    "quality_flag": ["quality_flag", "data_quality_flag"],
}

ZIP_COLUMN_ALIASES = {
    **COUNTY_COLUMN_ALIASES,
    "zip": ["zip", "postal_code", "zip_code", "postal_code_name"],
    "population": ["population", "estimated_population"],
    "households": ["households", "household_count"],
}


def download_csv(url: str, prefix: str, report_date: date) -> Path:
    if not url:
        raise ValueError(f"Missing configured URL for {prefix} Realtor.com CSV")
    destination = RAW_DIR / f"{prefix}_{report_date:%Y_%m}.csv"
    if destination.exists() and destination.stat().st_size > 0:
        return destination
    try:
        urlretrieve(url, destination)
    except (OSError, URLError) as exc:
        raise RuntimeError(f"Failed to download {prefix} CSV from {url}: {exc}") from exc
    return destination


def read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except Exception as exc:
        raise RuntimeError(f"Failed to read CSV file {path}: {exc}") from exc


def normalize_realtor_columns(df: pd.DataFrame, zip_level: bool = False) -> pd.DataFrame:
    aliases = ZIP_COLUMN_ALIASES if zip_level else COUNTY_COLUMN_ALIASES
    lower_to_original = {column.lower().strip(): column for column in df.columns}
    renamed: dict[str, str] = {}
    for canonical, options in aliases.items():
        for option in options:
            if option in lower_to_original:
                renamed[lower_to_original[option]] = canonical
                break
    normalized = df.rename(columns=renamed).copy()
    if "state" not in normalized.columns:
        source_column = "zip_name" if zip_level and "zip_name" in normalized.columns else "county"
        if source_column in normalized.columns:
            normalized["state"] = normalized[source_column].map(_state_from_market_name)
    if "county" not in normalized.columns and zip_level and "zip_name" in normalized.columns:
        normalized["county"] = normalized["zip_name"].map(_zip_market_label)
    required = ["state", "county", "active_listing_count", "pending_listing_count", "median_listing_price"]
    if zip_level:
        required.append("zip")
    missing = [column for column in required if column not in normalized.columns]
    if missing:
        raise ValueError(f"Realtor.com CSV is missing required columns: {', '.join(missing)}")
    return normalized


def _state_from_market_name(value: object) -> str:
    text = "" if pd.isna(value) else str(value).strip()
    if "," not in text:
        return ""
    return text.rsplit(",", 1)[1].strip().upper()


def _zip_market_label(value: object) -> str:
    text = "" if pd.isna(value) else str(value).strip()
    if "," in text:
        text = text.rsplit(",", 1)[0]
    return f"{text.title()} ZIP Market" if text else "Unknown ZIP Market"


def remove_bad_quality_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if "quality_flag" not in df.columns:
        return df.copy(), 0
    bad_values = {"bad", "poor", "low", "suppressed", "invalid"}
    mask = df["quality_flag"].astype(str).str.lower().isin(bad_values)
    return df.loc[~mask].copy(), int(mask.sum())


def filter_latest_period(df: pd.DataFrame) -> pd.DataFrame:
    if "period" not in df.columns:
        return df.copy()
    period = df["period"].astype(str).str.strip()
    latest = period.max()
    return df.loc[period == latest].copy()
