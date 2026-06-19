# ROARK Market Finder

Internal monthly automation for ROARK ACQUISITIONS LLC. The app downloads Realtor.com county and ZIP inventory CSVs, ranks wholesaling markets in Florida, Michigan, Georgia, and Alabama, creates two non-overlapping cold-calling lists, updates Google Sheets, emails each agency only its assigned ZIPs, and maintains ZIP usage history for the 18-month cooldown.

## What It Does

- Downloads configured Realtor.com county and ZIP CSV files.
- Saves raw files in `data/raw/`.
- Scores counties and ZIP codes with deterministic pandas logic.
- Excludes ZIPs used in the last `ZIP_COOLDOWN_MONTHS` months unless override is explicitly enabled.
- Filters counties and ZIPs to configured markets approximately 45 minutes from major cities.
- Splits eligible ZIPs into List A and List B with no overlap and approximate state-level lead-volume balance.
- Uses active listing count as lead-volume proxy when population or household data is unavailable.
- Saves processed rankings and agency exports under `data/processed/`.
- Updates Google Sheet tabs when credentials are configured.
- Sends each cold-calling company only its own list.
- Sends the owner the full report with both lists and warnings.
- Updates `data/history/zip_usage_history.csv` after a successful report run.

## Local Setup

```bash
cd roark-market-finder
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env` with the Realtor.com CSV URLs, Google Sheet settings, SMTP settings, and recipient emails. Do not commit `.env`.

## Environment Variables

Required for a real monthly run:

- `REALTOR_COUNTY_CSV_URL`
- `REALTOR_ZIP_CSV_URL`
- `OWNER_EMAIL`
- `COLD_CALLER_A_EMAIL`
- `COLD_CALLER_B_EMAIL`
- SMTP settings if emails should send
- Google settings if Sheets should update

Optional:

- `OPENAI_API_KEY` for the written executive summary
- `CENSUS_API_KEY` and `FRED_API_KEY` for future enrichment
- `ALLOW_COOLDOWN_OVERRIDE=true` only when ROARK explicitly approves reusing cooldown ZIPs

## Run Manually

```bash
python app/jobs/monthly_run.py
```

The app saves local CSVs even if Google Sheets, OpenAI, or email sending fails.

## Google Sheets

Create a Google Cloud service account with Sheets API access. Share the target Google Sheet with the service account email, then set:

- `GOOGLE_SERVICE_ACCOUNT_JSON` to the full JSON service account object as one environment variable
- `GOOGLE_SHEET_ID` to the Sheet ID from the URL

Tabs created or updated:

- Executive Summary
- County Rankings
- ZIP Rankings
- Cold Caller List A
- Cold Caller List B
- ZIP Usage History
- Manual Review
- Data Notes

## Email Setup

Set:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `FROM_EMAIL`
- `OWNER_EMAIL`
- `COLD_CALLER_A_EMAIL`
- `COLD_CALLER_B_EMAIL`
- `COLD_CALLER_A_NAME`
- `COLD_CALLER_B_NAME`

The app validates that List A and List B do not share ZIP codes before agency emails are sent.

## ZIP Cooldown

The history file lives at:

```text
data/history/zip_usage_history.csv
```

A ZIP is eligible only if it has never been used or its most recent `Date Sent` is at least `ZIP_COOLDOWN_MONTHS` months before the report date. The default is 18 months.

If the eligible ZIP pool is short, the app:

- uses the best eligible ZIPs first
- flags the shortage in Executive Summary and Manual Review
- does not silently reuse old ZIPs

To reset or edit history, update `data/history/zip_usage_history.csv` carefully. Keep ZIP codes, sent dates, assigned lists, agencies, and report months intact.

## Major-City Market Filter

The file `data/config/major_city_market_filter.csv` controls which counties and ZIP prefixes are treated as being approximately 45 minutes from a major city. The monthly report filters to this list before cooldown and splitting.

Defaults:

- `MAJOR_CITY_FILTER_ENABLED=true`
- `MAJOR_CITY_DRIVE_MINUTES=45`
- `TARGET_ZIPS_PER_STATE=200`

`TARGET_ZIPS_PER_STATE` keeps the report volume steady after the filter is applied. If the filtered/cooldown-safe pool is short, the report completes and flags the shortage in Manual Review.

## GitHub Actions

The workflow at `.github/workflows/monthly_market_finder.yml` runs at 10:00 UTC on the 5th of every month and can also be started manually with `workflow_dispatch`.

After each successful run, the workflow commits `data/history/zip_usage_history.csv` and `data/processed/` back to the repository. This is what makes the 18-month ZIP cooldown work automatically across future monthly runs.

Add these GitHub secrets before enabling the workflow:

- `OPENAI_API_KEY`
- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `GOOGLE_SHEET_ID`
- `REALTOR_COUNTY_CSV_URL`
- `REALTOR_ZIP_CSV_URL`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `FROM_EMAIL`
- `OWNER_EMAIL`
- `COLD_CALLER_A_EMAIL`
- `COLD_CALLER_B_EMAIL`
- `COLD_CALLER_A_NAME`
- `COLD_CALLER_B_NAME`
- `TARGET_STATES`
- `ZIP_COOLDOWN_MONTHS`
- `ALLOW_COOLDOWN_OVERRIDE`
- `TOP_COUNTIES_PER_STATE`
- `TOP_ZIPS_PER_COUNTY`
- `MIN_ACTIVE_LISTING_COUNT`
- `MIN_PENDING_LISTING_COUNT`

## Tests

```bash
pytest
```

Current tests cover:

- county scoring
- ZIP scoring
- target value ranges
- cooldown eligibility
- non-overlapping balanced list splitting
- agency email preparation

## Extension Points

The MVP includes stubs for Census and FRED. Future versions can add population/household enrichment, FRED economic scoring, lead-provider exports, month-over-month trend comparison, and buyer/dispo feedback.
