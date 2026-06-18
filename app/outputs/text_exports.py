from __future__ import annotations

import pandas as pd


STATE_NAMES = {"FL": "FLORIDA", "MI": "MICHIGAN", "GA": "GEORGIA", "AL": "ALABAMA"}


def cold_calling_plain_text(df: pd.DataFrame) -> str:
    if df.empty:
        return "No eligible ZIP codes assigned this month."
    sections: list[str] = []
    for state, state_group in df.groupby("state", sort=True):
        sections.append(STATE_NAMES.get(state, state))
        for county, county_group in state_group.groupby("county", sort=True):
            zips = ", ".join(county_group["zip"].astype(str).tolist())
            value_range = county_group["recommended_home_value_range"].mode()
            priority = county_group["priority"].mode()
            reason = county_group["reason"].iloc[0]
            sections.append(f"County: {county}")
            sections.append(f"ZIPs: {zips}")
            sections.append(f"Target home value range: {value_range.iloc[0] if not value_range.empty else ''}")
            sections.append(f"Priority: {priority.iloc[0] if not priority.empty else 'High'}")
            sections.append(f"Reason: {reason}")
            sections.append("")
    return "\n".join(sections).strip()

