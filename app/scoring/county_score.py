from __future__ import annotations

import pandas as pd

from app.scoring.price_ranges import recommend_value_range, score_affordability


def safe_numeric_column(df: pd.DataFrame, column_name: str) -> pd.Series:
    if column_name not in df.columns:
        return pd.Series([0] * len(df), index=df.index, dtype="float64")
    return pd.to_numeric(df[column_name], errors="coerce").fillna(0)


def percentile_score(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").fillna(0)
    if len(numeric) == 0:
        return numeric
    if numeric.nunique() <= 1:
        return pd.Series([50.0] * len(numeric), index=numeric.index)
    return numeric.rank(pct=True, method="average") * 100


def inverse_percentile_score(series: pd.Series) -> pd.Series:
    return 100 - percentile_score(series)


def normalize_county_name(name: object) -> str:
    value = "" if pd.isna(name) else str(name).strip()
    if "," in value:
        value = value.rsplit(",", 1)[0].strip()
    for suffix in (" County", " county", " COUNTY"):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
    return value.title()


def score_counties(df: pd.DataFrame) -> pd.DataFrame:
    scored = df.copy()
    scored["state"] = scored["state"].astype(str).str.upper().str.strip()
    scored["county"] = scored["county"].map(normalize_county_name)
    active = safe_numeric_column(scored, "active_listing_count")
    pending = safe_numeric_column(scored, "pending_listing_count")
    price_decrease = safe_numeric_column(scored, "price_decrease_count")
    median_dom = safe_numeric_column(scored, "median_days_on_market")
    median_price = safe_numeric_column(scored, "median_listing_price")
    volume = safe_numeric_column(scored, "population")
    volume = volume.where(volume > 0, active)
    scored["pending_ratio"] = pending / active.replace(0, pd.NA)
    scored["pending_ratio"] = scored["pending_ratio"].fillna(0)
    scored["affordability_score"] = [
        score_affordability(price, state) for price, state in zip(median_price, scored["state"], strict=False)
    ]
    scored["county_score"] = (
        percentile_score(scored["pending_ratio"]) * 0.30
        + percentile_score(active) * 0.20
        + percentile_score(price_decrease) * 0.15
        + inverse_percentile_score(median_dom) * 0.15
        + scored["affordability_score"] * 0.10
        + percentile_score(volume) * 0.10
    ).round(2)
    scored["recommended_home_value_range"] = [
        recommend_value_range(price, state) for price, state in zip(median_price, scored["state"], strict=False)
    ]
    scored["notes"] = scored["pending_ratio"].apply(
        lambda ratio: "Strong buyer activity" if ratio >= 0.25 else "Moderate buyer activity"
    )
    return scored.sort_values(["state", "county_score"], ascending=[True, False]).reset_index(drop=True)
