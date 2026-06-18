from __future__ import annotations

import pandas as pd


def enrich_with_census(df: pd.DataFrame, api_key: str | None = None) -> pd.DataFrame:
    """Placeholder for future Census enrichment.

    The MVP intentionally works without Census credentials. When unavailable, active
    listings remain the lead-volume proxy.
    """
    return df.copy()

