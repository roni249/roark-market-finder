from __future__ import annotations

from pathlib import Path

import pandas as pd


def _norm(value: object) -> str:
    return "" if pd.isna(value) else str(value).strip().lower()


def load_major_city_market_filter(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["state", "major_city", "county", "zip_prefix", "approx_drive_minutes"])
    filters = pd.read_csv(path, dtype=str).fillna("")
    for column in ["state", "major_city", "county", "zip_prefix", "approx_drive_minutes"]:
        if column not in filters.columns:
            filters[column] = ""
    filters["state"] = filters["state"].str.upper().str.strip()
    filters["county_key"] = filters["county"].map(_norm)
    filters["zip_prefix"] = filters["zip_prefix"].str.strip()
    filters["approx_drive_minutes"] = pd.to_numeric(filters["approx_drive_minutes"], errors="coerce").fillna(45)
    return filters


def filter_counties_near_major_cities(
    counties: pd.DataFrame,
    filters: pd.DataFrame,
    max_drive_minutes: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if filters.empty:
        return counties.copy(), counties.iloc[0:0].copy()
    county_filters = filters[(filters["county_key"] != "") & (filters["approx_drive_minutes"] <= max_drive_minutes)]
    allowed = set(zip(county_filters["state"], county_filters["county_key"], strict=False))
    work = counties.copy()
    work["_county_key"] = work["county"].map(_norm)
    work["_filter_key"] = list(zip(work["state"], work["_county_key"], strict=False))
    work["major_city"] = work["_filter_key"].map(
        lambda key: _major_city_for_county(key, county_filters)
    )
    included = work[work["_filter_key"].isin(allowed)].copy()
    excluded = work[~work["_filter_key"].isin(allowed)].copy()
    return included.drop(columns=["_county_key", "_filter_key"]), excluded.drop(columns=["_county_key", "_filter_key"])


def filter_zips_near_major_cities(
    zips: pd.DataFrame,
    filters: pd.DataFrame,
    max_drive_minutes: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if filters.empty:
        return zips.copy(), zips.iloc[0:0].copy()
    prefix_filters = filters[(filters["zip_prefix"] != "") & (filters["approx_drive_minutes"] <= max_drive_minutes)]
    prefixes_by_state = {
        state: group[["zip_prefix", "major_city"]].to_dict("records")
        for state, group in prefix_filters.groupby("state")
    }
    work = zips.copy()
    matches = work.apply(lambda row: _zip_prefix_match(row, prefixes_by_state), axis=1)
    work["major_city"] = matches.map(lambda match: match[0])
    work["major_city_filter_reason"] = matches.map(lambda match: match[1])
    included = work[work["major_city"] != ""].copy()
    excluded = work[work["major_city"] == ""].copy()
    return included, excluded


def _major_city_for_county(key: tuple[str, str], county_filters: pd.DataFrame) -> str:
    state, county = key
    match = county_filters[(county_filters["state"] == state) & (county_filters["county_key"] == county)]
    if match.empty:
        return ""
    return str(match.iloc[0]["major_city"])


def _zip_prefix_match(row: pd.Series, prefixes_by_state: dict[str, list[dict[str, str]]]) -> tuple[str, str]:
    state = str(row.get("state", "")).upper()
    zip_code = str(row.get("zip", ""))
    for item in prefixes_by_state.get(state, []):
        prefix = item["zip_prefix"]
        if zip_code.startswith(prefix):
            return str(item["major_city"]), f"ZIP prefix {prefix} is within the configured major-city drive market."
    return "", "Excluded because ZIP prefix is outside the configured major-city drive market."

