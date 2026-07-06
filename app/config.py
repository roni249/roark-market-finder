from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
EXPORTS_DIR = PROCESSED_DIR / "exports"
HISTORY_DIR = DATA_DIR / "history"
ZIP_HISTORY_PATH = HISTORY_DIR / "zip_usage_history.csv"
MAJOR_CITY_FILTER_PATH = DATA_DIR / "config" / "major_city_market_filter.csv"
DEFAULT_REALTOR_COUNTY_CSV_URL = (
    "https://econdata.s3-us-west-2.amazonaws.com/Reports/Core/RDC_Inventory_Core_Metrics_County_History.csv"
)
DEFAULT_REALTOR_ZIP_CSV_URL = (
    "https://econdata.s3-us-west-2.amazonaws.com/Reports/Core/RDC_Inventory_Core_Metrics_Zip_History.csv"
)


def load_local_env() -> None:
    """Load local .env values without overriding the process environment."""
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def _str(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _states() -> list[str]:
    raw = _str("TARGET_STATES", "FL,MI,GA,AL") or "FL,MI,GA,AL"
    return [state.strip().upper() for state in raw.split(",") if state.strip()]


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    google_service_account_json: str | None
    google_sheet_id: str | None
    realtor_county_csv_url: str | None
    realtor_zip_csv_url: str | None
    census_api_key: str | None
    fred_api_key: str | None
    target_states: list[str]
    run_day: int
    email_provider: str
    smtp_host: str | None
    smtp_port: int
    smtp_username: str | None
    smtp_password: str | None
    from_email: str | None
    owner_email: str | None
    cold_caller_a_email: str | None
    cold_caller_b_email: str | None
    cold_caller_a_name: str
    cold_caller_b_name: str
    zip_cooldown_months: int
    allow_cooldown_override: bool
    top_counties_per_state: int
    top_zips_per_county: int
    min_active_listing_count: int
    min_pending_listing_count: int
    major_city_filter_enabled: bool
    major_city_filter_path: Path
    major_city_drive_minutes: int
    target_zips_per_state: int
    dense_residential_filter_enabled: bool
    dense_residential_min_lead_volume: int

    @classmethod
    def from_env(cls) -> "Settings":
        load_local_env()
        return cls(
            openai_api_key=_str("OPENAI_API_KEY"),
            google_service_account_json=_str("GOOGLE_SERVICE_ACCOUNT_JSON"),
            google_sheet_id=_str("GOOGLE_SHEET_ID"),
            realtor_county_csv_url=_str("REALTOR_COUNTY_CSV_URL", DEFAULT_REALTOR_COUNTY_CSV_URL),
            realtor_zip_csv_url=_str("REALTOR_ZIP_CSV_URL", DEFAULT_REALTOR_ZIP_CSV_URL),
            census_api_key=_str("CENSUS_API_KEY"),
            fred_api_key=_str("FRED_API_KEY"),
            target_states=_states(),
            run_day=_int("RUN_DAY", 5),
            email_provider=_str("EMAIL_PROVIDER", "smtp") or "smtp",
            smtp_host=_str("SMTP_HOST"),
            smtp_port=_int("SMTP_PORT", 587),
            smtp_username=_str("SMTP_USERNAME"),
            smtp_password=_str("SMTP_PASSWORD"),
            from_email=_str("FROM_EMAIL"),
            owner_email=_str("OWNER_EMAIL"),
            cold_caller_a_email=_str("COLD_CALLER_A_EMAIL"),
            cold_caller_b_email=_str("COLD_CALLER_B_EMAIL"),
            cold_caller_a_name=_str("COLD_CALLER_A_NAME", "Cold Caller A") or "Cold Caller A",
            cold_caller_b_name=_str("COLD_CALLER_B_NAME", "Cold Caller B") or "Cold Caller B",
            zip_cooldown_months=_int("ZIP_COOLDOWN_MONTHS", 18),
            allow_cooldown_override=_bool(os.getenv("ALLOW_COOLDOWN_OVERRIDE"), False),
            top_counties_per_state=_int("TOP_COUNTIES_PER_STATE", 5),
            top_zips_per_county=_int("TOP_ZIPS_PER_COUNTY", 10),
            min_active_listing_count=_int("MIN_ACTIVE_LISTING_COUNT", 10),
            min_pending_listing_count=_int("MIN_PENDING_LISTING_COUNT", 3),
            major_city_filter_enabled=_bool(os.getenv("MAJOR_CITY_FILTER_ENABLED"), True),
            major_city_filter_path=Path(_str("MAJOR_CITY_FILTER_PATH", str(MAJOR_CITY_FILTER_PATH)) or MAJOR_CITY_FILTER_PATH),
            major_city_drive_minutes=_int("MAJOR_CITY_DRIVE_MINUTES", 45),
            target_zips_per_state=_int("TARGET_ZIPS_PER_STATE", 200),
            dense_residential_filter_enabled=_bool(os.getenv("DENSE_RESIDENTIAL_FILTER_ENABLED"), True),
            dense_residential_min_lead_volume=_int("DENSE_RESIDENTIAL_MIN_LEAD_VOLUME", 25),
        )


def ensure_directories() -> None:
    for path in (RAW_DIR, PROCESSED_DIR, EXPORTS_DIR, HISTORY_DIR, MAJOR_CITY_FILTER_PATH.parent):
        path.mkdir(parents=True, exist_ok=True)


def validate_for_live_run(settings: Settings) -> list[str]:
    required = {
        "REALTOR_COUNTY_CSV_URL": settings.realtor_county_csv_url,
        "REALTOR_ZIP_CSV_URL": settings.realtor_zip_csv_url,
        "OWNER_EMAIL": settings.owner_email,
        "COLD_CALLER_A_EMAIL": settings.cold_caller_a_email,
        "COLD_CALLER_B_EMAIL": settings.cold_caller_b_email,
        "SMTP_HOST": settings.smtp_host,
        "SMTP_USERNAME": settings.smtp_username,
        "SMTP_PASSWORD": settings.smtp_password,
        "FROM_EMAIL": settings.from_email,
    }
    return [name for name, value in required.items() if not value]
