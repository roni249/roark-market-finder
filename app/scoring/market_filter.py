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


def filter_dense_residential_zips(
    zips: pd.DataFrame,
    min_lead_volume: int,
    target_zips_per_state: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Keep dense ZIPs while preserving enough report volume per state.

    Realtor ZIP data does not include land area or true population density in the
    MVP. Estimated lead volume is the best available density proxy, falling back
    to active listing count when Census data is unavailable.
    """
    if zips.empty:
        empty = zips.copy()
        return empty, empty, pd.DataFrame(columns=["State", "Dense ZIPs", "Top-Up ZIPs", "Excluded Sparse ZIPs"])
    included_parts: list[pd.DataFrame] = []
    excluded_parts: list[pd.DataFrame] = []
    diagnostics: list[dict[str, int | str]] = []
    for state, group in zips.groupby("state", sort=True):
        work = group.copy()
        work["_density_proxy"] = pd.to_numeric(work["estimated_lead_volume"], errors="coerce").fillna(0)
        work["_active_proxy"] = pd.to_numeric(work.get("active_listing_count", 0), errors="coerce").fillna(0)
        work = work.sort_values(["_density_proxy", "_active_proxy", "zip_score"], ascending=[False, False, False])
        dense = work[work["_density_proxy"] >= min_lead_volume].copy()
        top_up = work[work["_density_proxy"] < min_lead_volume].head(max(target_zips_per_state - len(dense), 0)).copy()
        if not top_up.empty:
            top_up["dense_residential_top_up"] = True
            top_up["dense_residential_reason"] = (
                "Top-up from the next densest available ZIPs to preserve report lead volume."
            )
        dense["dense_residential_top_up"] = False
        dense["dense_residential_reason"] = "Meets dense residential lead-volume threshold."
        included = pd.concat([dense, top_up], ignore_index=True)
        excluded = work[~work["zip"].isin(included["zip"])].copy()
        excluded["dense_residential_reason"] = "Excluded as lower-density residential inventory."
        included_parts.append(included.drop(columns=["_density_proxy", "_active_proxy"]))
        excluded_parts.append(excluded.drop(columns=["_density_proxy", "_active_proxy"]))
        diagnostics.append(
            {
                "State": state,
                "Dense ZIPs": len(dense),
                "Top-Up ZIPs": len(top_up),
                "Excluded Sparse ZIPs": len(excluded),
            }
        )
    included_df = pd.concat(included_parts, ignore_index=True) if included_parts else zips.iloc[0:0].copy()
    excluded_df = pd.concat(excluded_parts, ignore_index=True) if excluded_parts else zips.iloc[0:0].copy()
    return included_df, excluded_df, pd.DataFrame(diagnostics)


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
