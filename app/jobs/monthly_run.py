from __future__ import annotations

import logging
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.ai.market_summary import generate_market_summary
from app.config import Settings, ensure_directories, validate_for_live_run
from app.data_sources.realtor import (
    download_csv,
    normalize_realtor_columns,
    read_csv,
    remove_bad_quality_rows,
    filter_latest_period,
)
from app.outputs.csv_outputs import save_processed_outputs
from app.outputs.email_report import (
    prepare_agency_email,
    prepare_owner_email,
    send_agency_email,
    send_owner_report_email,
)
from app.outputs.google_sheets import update_google_sheet
from app.scoring.cooldown import (
    HISTORY_COLUMNS,
    apply_zip_cooldown_filter,
    load_zip_usage_history,
    save_zip_usage_history,
)
from app.scoring.county_score import score_counties
from app.scoring.market_filter import (
    filter_counties_near_major_cities,
    filter_zips_near_major_cities,
    load_major_city_market_filter,
)
from app.scoring.split_lists import split_into_two_balanced_lists, validate_no_duplicate_zips
from app.scoring.zip_score import score_zips


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger(__name__)


COUNTY_COLUMNS = [
    "Rank",
    "State",
    "County",
    "County Score",
    "Pending Ratio",
    "Active Listing Count",
    "Pending Listing Count",
    "Median Listing Price",
    "Median Days on Market",
    "Price Decrease Count",
    "New Listing Count",
    "Recommended Home Value Range",
    "Notes",
]

ZIP_COLUMNS = [
    "State",
    "County",
    "ZIP",
    "ZIP Score",
    "Pending Ratio",
    "Active Listing Count",
    "Pending Listing Count",
    "Estimated Population",
    "Estimated Lead Volume",
    "Median Listing Price",
    "Median Days on Market",
    "Price Decrease Count",
    "Recommended Home Value Range",
    "Last Used Date",
    "Eligible Based on Cooldown",
    "Manual Review Flag",
]

CALLER_COLUMNS = [
    "State",
    "County",
    "ZIP",
    "Target Home Value Range",
    "Estimated Population",
    "Estimated Lead Volume",
    "Priority",
    "Reason",
    "Suggested Lead Pull Criteria",
]


def _select_top_counties(scored_counties: pd.DataFrame, per_state: int) -> pd.DataFrame:
    return scored_counties.groupby("state", group_keys=False).head(per_state).copy()


def _select_top_zips(
    scored_zips: pd.DataFrame,
    top_counties: pd.DataFrame,
    per_county: int,
    target_zips_per_state: int,
) -> pd.DataFrame:
    county_keys = set(zip(top_counties["state"], top_counties["county"], strict=False))
    selected = scored_zips[
        scored_zips.apply(lambda row: (row["state"], row["county"]) in county_keys, axis=1)
    ].copy()
    if selected.empty:
        return scored_zips.groupby("state", group_keys=False).head(target_zips_per_state).copy()
    return selected.groupby(["state", "county"], group_keys=False).head(per_county).copy()


def _format_county_rankings(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(
        {
            "State": df["state"],
            "County": df["county"],
            "County Score": df["county_score"],
            "Pending Ratio": df["pending_ratio"],
            "Active Listing Count": df.get("active_listing_count", 0),
            "Pending Listing Count": df.get("pending_listing_count", 0),
            "Median Listing Price": df.get("median_listing_price", 0),
            "Median Days on Market": df.get("median_days_on_market", 0),
            "Price Decrease Count": df.get("price_decrease_count", 0),
            "New Listing Count": df.get("new_listing_count", 0),
            "Recommended Home Value Range": df["recommended_home_value_range"],
            "Notes": df["notes"],
        }
    )
    out.insert(0, "Rank", out["County Score"].rank(ascending=False, method="first").astype(int))
    return out.sort_values("Rank")[COUNTY_COLUMNS]


def _format_zip_rankings(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "State": df["state"],
            "County": df["county"],
            "ZIP": df["zip"],
            "ZIP Score": df["zip_score"],
            "Pending Ratio": df["pending_ratio"],
            "Active Listing Count": df.get("active_listing_count", 0),
            "Pending Listing Count": df.get("pending_listing_count", 0),
            "Estimated Population": df["estimated_population"],
            "Estimated Lead Volume": df["estimated_lead_volume"],
            "Median Listing Price": df.get("median_listing_price", 0),
            "Median Days on Market": df.get("median_days_on_market", 0),
            "Price Decrease Count": df.get("price_decrease_count", 0),
            "Recommended Home Value Range": df["recommended_home_value_range"],
            "Last Used Date": df.get("last_used_date", ""),
            "Eligible Based on Cooldown": df.get("eligible_based_on_cooldown", True),
            "Manual Review Flag": df.get("manual_review_flag", ""),
        }
    )[ZIP_COLUMNS]


def _format_caller_list(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "State": df["state"],
            "County": df["county"],
            "ZIP": df["zip"],
            "Target Home Value Range": df["recommended_home_value_range"],
            "Estimated Population": df["estimated_population"],
            "Estimated Lead Volume": df["estimated_lead_volume"],
            "Priority": df["priority"],
            "Reason": df["reason"],
            "Suggested Lead Pull Criteria": df["suggested_lead_pull_criteria"],
        }
    )[CALLER_COLUMNS]


def _manual_review_rows(
    cooldown_excluded: pd.DataFrame,
    warnings: list[str],
    selected_counties: pd.DataFrame,
    eligible_zips: pd.DataFrame,
    settings: Settings,
) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for warning in warnings:
        rows.append({"State": "", "County": "", "ZIP": "", "Reason": warning, "Suggested Action": "Review before outreach."})
    for _, row in cooldown_excluded.iterrows():
        rows.append(
            {
                "State": row.get("state", ""),
                "County": row.get("county", ""),
                "ZIP": row.get("zip", ""),
                "Reason": "ZIP used within cooldown window.",
                "Suggested Action": "Do not reuse unless cooldown override is explicitly approved.",
            }
        )
    expected = len(settings.target_states) * settings.target_zips_per_state
    if len(eligible_zips) < expected:
        rows.append(
            {
                "State": "",
                "County": "",
                "ZIP": "",
                "Reason": f"Shortage: expected up to {expected} eligible ZIPs, found {len(eligible_zips)}.",
                "Suggested Action": "Use eligible ZIPs first; review cooldown override only if outreach volume is insufficient.",
            }
        )
    return pd.DataFrame(rows, columns=["State", "County", "ZIP", "Reason", "Suggested Action"])


def _data_notes(
    settings: Settings,
    report_date: date,
    county_rows: int,
    zip_rows: int,
    county_quality_removed: int,
    zip_quality_removed: int,
    cooldown_excluded_count: int,
    county_major_city_excluded_count: int,
    zip_major_city_excluded_count: int,
    list_a: pd.DataFrame,
    list_b: pd.DataFrame,
    balance: pd.DataFrame,
) -> pd.DataFrame:
    notes = [
        ("Date generated", datetime.utcnow().isoformat(timespec="seconds") + "Z"),
        ("Report month", report_date.strftime("%Y-%m")),
        ("County CSV URL", settings.realtor_county_csv_url or ""),
        ("ZIP CSV URL", settings.realtor_zip_csv_url or ""),
        ("Target states used", ",".join(settings.target_states)),
        ("County rows removed by quality flag", county_quality_removed),
        ("ZIP rows removed by quality flag", zip_quality_removed),
        ("Number of counties analyzed", county_rows),
        ("Number of ZIPs analyzed", zip_rows),
        ("Major-city drive market filter enabled", settings.major_city_filter_enabled),
        ("Configured major-city drive minutes", settings.major_city_drive_minutes),
        ("Counties excluded outside major-city drive markets", county_major_city_excluded_count),
        ("ZIPs excluded outside major-city drive markets", zip_major_city_excluded_count),
        ("Target ZIPs per state after major-city filter", settings.target_zips_per_state),
        ("Number of ZIPs excluded due to cooldown", cooldown_excluded_count),
        ("Number of ZIPs assigned to List A", len(list_a)),
        ("Number of ZIPs assigned to List B", len(list_b)),
        (
            "Scoring formula explanation",
            "County: pending ratio 30%, active inventory 20%, price decrease 15%, DOM 15%, affordability 10%, volume 10%. ZIP: pending ratio 25%, active inventory 20%, volume 15%, price fit 15%, price decrease 10%, DOM 10%, data quality 5%.",
        ),
    ]
    for _, row in balance.iterrows():
        notes.append((f"List A estimated lead volume - {row['State']}", row["List A Volume"]))
        notes.append((f"List B estimated lead volume - {row['State']}", row["List B Volume"]))
    return pd.DataFrame(notes, columns=["Item", "Value"])


def _executive_summary_tab(
    report_date: date,
    county_rankings: pd.DataFrame,
    zip_rankings: pd.DataFrame,
    balance: pd.DataFrame,
    manual_review: pd.DataFrame,
    ai_summary: str,
) -> pd.DataFrame:
    rows = [
        ("Report month", report_date.strftime("%Y-%m")),
        ("Date generated", datetime.utcnow().isoformat(timespec="seconds") + "Z"),
        ("Top 10 counties overall", "; ".join((county_rankings["State"] + " - " + county_rankings["County"]).head(10))),
        ("Top counties by state", "; ".join(county_rankings.groupby("State").head(3).apply(lambda r: f"{r['State']}: {r['County']}", axis=1))),
        ("Top ZIPs by state", "; ".join(zip_rankings.groupby("State").head(5).apply(lambda r: f"{r['State']}: {r['ZIP']}", axis=1))),
        ("Main recommendations", "Prioritize high-score ZIPs in selected counties and pull leads inside the recommended value ranges."),
        ("List A/List B balance summary", balance.to_string(index=False) if not balance.empty else "No assigned ZIPs."),
        ("ZIP cooldown summary", "See Data Notes and Manual Review for excluded ZIPs."),
        ("Markets to avoid or review manually", manual_review.to_string(index=False) if not manual_review.empty else "None."),
        ("AI-written summary", ai_summary),
    ]
    return pd.DataFrame(rows, columns=["Section", "Details"])


def _append_usage_history(
    history: pd.DataFrame,
    assigned: pd.DataFrame,
    report_date: date,
    list_name: str,
    agency_name: str,
) -> pd.DataFrame:
    rows = []
    for _, row in assigned.iterrows():
        rows.append(
            {
                "ZIP": row["zip"],
                "State": row["state"],
                "County": row["county"],
                "Date Sent": report_date.isoformat(),
                "Assigned List": list_name,
                "Assigned Agency": agency_name,
                "Report Month": report_date.strftime("%Y-%m"),
                "Estimated Population": row["estimated_population"],
                "Estimated Lead Volume": row["estimated_lead_volume"],
            }
        )
    return pd.concat([history, pd.DataFrame(rows, columns=HISTORY_COLUMNS)], ignore_index=True)


def run(report_date: date | None = None) -> dict[str, object]:
    settings = Settings.from_env()
    ensure_directories()
    missing = validate_for_live_run(settings)
    if missing:
        raise RuntimeError(f"Missing required live-run settings: {', '.join(missing)}")
    report_date = report_date or date.today()
    report_month = report_date.strftime("%Y-%m")
    county_raw = download_csv(settings.realtor_county_csv_url or "", "realtor_county", report_date)
    zip_raw = download_csv(settings.realtor_zip_csv_url or "", "realtor_zip", report_date)
    county_df = normalize_realtor_columns(read_csv(county_raw), zip_level=False)
    zip_df = normalize_realtor_columns(read_csv(zip_raw), zip_level=True)
    county_df = filter_latest_period(county_df)
    zip_df = filter_latest_period(zip_df)
    county_df, county_quality_removed = remove_bad_quality_rows(county_df)
    zip_df, zip_quality_removed = remove_bad_quality_rows(zip_df)
    county_df = county_df[county_df["state"].astype(str).str.upper().isin(settings.target_states)].copy()
    zip_df = zip_df[zip_df["state"].astype(str).str.upper().isin(settings.target_states)].copy()
    county_df = county_df[pd.to_numeric(county_df["active_listing_count"], errors="coerce").fillna(0) >= settings.min_active_listing_count]
    zip_df = zip_df[
        (pd.to_numeric(zip_df["active_listing_count"], errors="coerce").fillna(0) >= settings.min_active_listing_count)
        & (pd.to_numeric(zip_df["pending_listing_count"], errors="coerce").fillna(0) >= settings.min_pending_listing_count)
    ].copy()
    history = load_zip_usage_history()
    scored_counties = score_counties(county_df)
    county_major_city_excluded = scored_counties.iloc[0:0].copy()
    top_counties = _select_top_counties(scored_counties, settings.top_counties_per_state)
    scored_zips = score_zips(zip_df)
    zip_major_city_excluded = scored_zips.iloc[0:0].copy()
    if settings.major_city_filter_enabled:
        filters = load_major_city_market_filter(settings.major_city_filter_path)
        scored_counties, county_major_city_excluded = filter_counties_near_major_cities(
            scored_counties, filters, settings.major_city_drive_minutes
        )
        scored_zips, zip_major_city_excluded = filter_zips_near_major_cities(
            scored_zips, filters, settings.major_city_drive_minutes
        )
        top_counties = _select_top_counties(scored_counties, settings.top_counties_per_state)
    eligible_zips, cooldown_excluded, cooldown_warnings = apply_zip_cooldown_filter(
        scored_zips,
        history,
        report_date,
        settings.zip_cooldown_months,
        settings.allow_cooldown_override,
    )
    selected_zips = _select_top_zips(
        eligible_zips, top_counties, settings.top_zips_per_county, settings.target_zips_per_state
    )
    list_a, list_b, balance = split_into_two_balanced_lists(selected_zips)
    validate_no_duplicate_zips(list_a, list_b)
    manual_review = _manual_review_rows(cooldown_excluded, cooldown_warnings, top_counties, selected_zips, settings)
    county_rankings = _format_county_rankings(scored_counties)
    zip_rankings = _format_zip_rankings(scored_zips)
    caller_a = _format_caller_list(list_a)
    caller_b = _format_caller_list(list_b)
    data_notes = _data_notes(
        settings,
        report_date,
        len(county_df),
        len(zip_df),
        county_quality_removed,
        zip_quality_removed,
        len(cooldown_excluded),
        len(county_major_city_excluded),
        len(zip_major_city_excluded),
        list_a,
        list_b,
        balance,
    )
    ai_summary = generate_market_summary(
        county_rankings, zip_rankings, list_a, list_b, "; ".join(cooldown_warnings), settings.openai_api_key
    )
    executive_summary = _executive_summary_tab(report_date, county_rankings, zip_rankings, balance, manual_review, ai_summary)
    output_paths = save_processed_outputs(
        report_month, county_rankings, zip_rankings, caller_a, caller_b, manual_review, data_notes
    )
    tabs = {
        "Executive Summary": executive_summary,
        "County Rankings": county_rankings,
        "ZIP Rankings": zip_rankings,
        "Cold Caller List A": caller_a,
        "Cold Caller List B": caller_b,
        "ZIP Usage History": history,
        "Manual Review": manual_review,
        "Data Notes": data_notes,
    }
    google_sheet_link = None
    try:
        google_sheet_link = update_google_sheet(settings, tabs)
    except Exception as exc:
        LOGGER.error("%s", exc)
    agency_email_errors: list[str] = []
    owner_email_errors: list[str] = []
    if settings.cold_caller_a_email and settings.cold_caller_b_email:
        try:
            send_agency_email(
                settings,
                prepare_agency_email(
                    "List A",
                    settings.cold_caller_a_name,
                    settings.cold_caller_a_email,
                    list_a,
                    report_month,
                    output_paths["cold_caller_list_a"],
                ),
            )
        except Exception as exc:
            agency_email_errors.append(f"List A email failed: {exc}")
        try:
            send_agency_email(
                settings,
                prepare_agency_email(
                    "List B",
                    settings.cold_caller_b_name,
                    settings.cold_caller_b_email,
                    list_b,
                    report_month,
                    output_paths["cold_caller_list_b"],
                ),
            )
        except Exception as exc:
            agency_email_errors.append(f"List B email failed: {exc}")
    if settings.owner_email:
        try:
            send_owner_report_email(
                settings,
                prepare_owner_email(
                    settings.owner_email,
                    report_month,
                    ai_summary,
                    list_a,
                    list_b,
                    manual_review,
                    google_sheet_link,
                    [output_paths["cold_caller_list_a"], output_paths["cold_caller_list_b"]],
                ),
            )
        except Exception as exc:
            owner_email_errors.append(f"Owner email failed: {exc}")
    email_errors = agency_email_errors + owner_email_errors
    for error in email_errors:
        LOGGER.error("%s", error)
    if agency_email_errors:
        LOGGER.error("ZIP usage history was not updated because one or more agency emails failed.")
    else:
        updated_history = _append_usage_history(history, list_a, report_date, "List A", settings.cold_caller_a_name)
        updated_history = _append_usage_history(updated_history, list_b, report_date, "List B", settings.cold_caller_b_name)
        save_zip_usage_history(updated_history)
    LOGGER.info("Report complete for %s. Outputs saved under %s", report_month, output_paths)
    return {
        "report_month": report_month,
        "output_paths": output_paths,
        "google_sheet_link": google_sheet_link,
        "email_errors": email_errors,
    }


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        LOGGER.exception("Monthly market finder failed: %s", exc)
        sys.exit(1)
