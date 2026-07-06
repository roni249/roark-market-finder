from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.config import Settings, validate_for_live_run


def main() -> int:
    settings = Settings.from_env()
    missing = validate_for_live_run(settings)
    print("ROARK Market Finder preflight")
    print(f"Target states: {', '.join(settings.target_states)}")
    print(f"Cooldown months: {settings.zip_cooldown_months}")
    print(f"Cooldown override: {settings.allow_cooldown_override}")
    print(f"Owner email: {'set' if settings.owner_email else 'missing'}")
    print(f"Cold Caller A: {'set' if settings.cold_caller_a_email else 'missing'}")
    print(f"Cold Caller B: {'set' if settings.cold_caller_b_email else 'missing'}")
    print(f"County CSV URL: {'set' if settings.realtor_county_csv_url else 'missing'}")
    print(f"ZIP CSV URL: {'set' if settings.realtor_zip_csv_url else 'missing'}")
    print(f"Google Sheets: {'set' if settings.google_sheet_id and settings.google_service_account_json else 'not configured'}")
    print(f"OpenAI summary: {'set' if settings.openai_api_key else 'not configured'}")
    if missing:
        print("Missing required live-run settings:")
        for name in missing:
            print(f"- {name}")
            print(f"::error title=Missing GitHub Action secret::{name} is required for the monthly market finder.")
        return 1
    print("Preflight passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
