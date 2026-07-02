from __future__ import annotations

import pandas as pd


def validate_no_duplicate_zips(list_a: pd.DataFrame, list_b: pd.DataFrame) -> None:
    overlap = set(list_a["zip"].astype(str)) & set(list_b["zip"].astype(str))
    if overlap:
        raise ValueError(f"Cold caller lists contain overlapping ZIP codes: {', '.join(sorted(overlap))}")


def calculate_state_balance(list_a: pd.DataFrame, list_b: pd.DataFrame) -> pd.DataFrame:
    rows = []
    states = sorted(set(list_a.get("state", [])) | set(list_b.get("state", [])))
    for state in states:
        a_volume = float(list_a.loc[list_a["state"] == state, "estimated_lead_volume"].sum())
        b_volume = float(list_b.loc[list_b["state"] == state, "estimated_lead_volume"].sum())
        total = a_volume + b_volume
        variance_pct = 0.0 if total == 0 else abs(a_volume - b_volume) / total * 100
        rows.append(
            {
                "State": state,
                "List A Volume": a_volume,
                "List B Volume": b_volume,
                "Variance Percent": round(variance_pct, 2),
            }
        )
    return pd.DataFrame(rows)


def _reason(row: pd.Series) -> str:
    major_city = row.get("major_city", "")
    dense_note = "dense residential inventory"
    if row.get("dense_residential_top_up", False):
        dense_note = "one of the next densest available residential ZIPs needed to preserve report volume"
    if major_city:
        return (
            f"Within the configured 45-minute drive market for {major_city}; {dense_note}; strong pending ratio, "
            "healthy active inventory, good price range, and enough estimated lead volume."
        )
    return f"{dense_note}; strong pending ratio, healthy active inventory, good price range, and enough estimated lead volume."


def split_into_two_balanced_lists(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    work = df.copy().sort_values(["state", "zip_score"], ascending=[True, False])
    list_a_parts: list[pd.DataFrame] = []
    list_b_parts: list[pd.DataFrame] = []
    for state, group in work.groupby("state", sort=True):
        a_indices: list[int] = []
        b_indices: list[int] = []
        totals = {"A": 0.0, "B": 0.0}
        for rank, (idx, row) in enumerate(group.iterrows(), start=1):
            volume = float(row.get("estimated_lead_volume", 0) or 0)
            if rank == 1:
                target = "A"
            elif rank == 2:
                target = "B"
            else:
                target = "A" if totals["A"] <= totals["B"] else "B"
            if target == "A":
                a_indices.append(idx)
            else:
                b_indices.append(idx)
            totals[target] += volume
        list_a_parts.append(work.loc[a_indices])
        list_b_parts.append(work.loc[b_indices])
    list_a = pd.concat(list_a_parts, ignore_index=True) if list_a_parts else work.iloc[0:0].copy()
    list_b = pd.concat(list_b_parts, ignore_index=True) if list_b_parts else work.iloc[0:0].copy()
    for assigned, name in ((list_a, "List A"), (list_b, "List B")):
        assigned["assigned_list"] = name
        assigned["priority"] = assigned.groupby("state")["zip_score"].rank(ascending=False, method="first").map(
            lambda rank: "High" if rank <= 5 else "Medium"
        )
        assigned["reason"] = assigned.apply(_reason, axis=1)
        assigned["suggested_lead_pull_criteria"] = (
            "Absentee owners; high equity; vacant; tired landlords; out-of-state owners; "
            "pre-foreclosure if available; probate if available; ownership length 7+ years; "
            "property value inside recommended range."
        )
    validate_no_duplicate_zips(list_a, list_b)
    return list_a.reset_index(drop=True), list_b.reset_index(drop=True), calculate_state_balance(list_a, list_b)
