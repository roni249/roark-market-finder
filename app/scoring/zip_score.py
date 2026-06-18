from __future__ import annotations

import pandas as pd

from app.scoring.county_score import (
    inverse_percentile_score,
    normalize_county_name,
    percentile_score,
    safe_numeric_column,
)
from app.scoring.price_ranges import recommend_value_range, score_affordability


def normalize_zip(zip_code: object) -> str:
    if pd.isna(zip_code):
        return ""
    value = str(zip_code).strip().split(".")[0]
    digits = "".join(ch for ch in value if ch.isdigit())
    return digits.zfill(5)[:5] if digits else value


def score_zips(df: pd.DataFrame) -> pd.DataFrame:
    scored = df.copy()
    scored["state"] = scored["state"].astype(str).str.upper().str.strip()
    scored["county"] = scored["county"].map(normalize_county_name)
    scored["zip"] = scored["zip"].map(normalize_zip)
    active = safe_numeric_column(scored, "active_listing_count")
    pending = safe_numeric_column(scored, "pending_listing_count")
    price_decrease = safe_numeric_column(scored, "price_decrease_count")
    median_dom = safe_numeric_column(scored, "median_days_on_market")
    median_price = safe_numeric_column(scored, "median_listing_price")
    population = safe_numeric_column(scored, "population")
    households = safe_numeric_column(scored, "households")
    estimated_volume = population.where(population > 0, households)
    estimated_volume = estimated_volume.where(estimated_volume > 0, active)
    scored["estimated_population"] = population.where(population > 0, estimated_volume)
    scored["estimated_lead_volume"] = estimated_volume
    scored["pending_ratio"] = (pending / active.replace(0, pd.NA)).fillna(0)
    scored["median_price_fit_score"] = [
        score_affordability(price, state) for price, state in zip(median_price, scored["state"], strict=False)
    ]
    data_quality = pd.Series([100.0] * len(scored), index=scored.index)
    if "quality_flag" in scored.columns:
        data_quality = scored["quality_flag"].astype(str).str.lower().map(
            lambda flag: 100.0 if flag in {"", "nan", "good", "ok", "none"} else 50.0
        )
    scored["zip_score"] = (
        percentile_score(scored["pending_ratio"]) * 0.25
        + percentile_score(active) * 0.20
        + percentile_score(estimated_volume) * 0.15
        + scored["median_price_fit_score"] * 0.15
        + percentile_score(price_decrease) * 0.10
        + inverse_percentile_score(median_dom) * 0.10
        + data_quality * 0.05
    ).round(2)
    scored["recommended_home_value_range"] = [
        recommend_value_range(price, state) for price, state in zip(median_price, scored["state"], strict=False)
    ]
    return scored.sort_values(["state", "zip_score"], ascending=[True, False]).reset_index(drop=True)

