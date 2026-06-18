from __future__ import annotations

import json

import pandas as pd

from app.config import Settings


TAB_ORDER = [
    "Executive Summary",
    "County Rankings",
    "ZIP Rankings",
    "Cold Caller List A",
    "Cold Caller List B",
    "ZIP Usage History",
    "Manual Review",
    "Data Notes",
]


def _values(df: pd.DataFrame) -> list[list[str]]:
    frame = df.fillna("").astype(str)
    return [frame.columns.tolist()] + frame.values.tolist()


def update_google_sheet(settings: Settings, tabs: dict[str, pd.DataFrame]) -> str | None:
    if not settings.google_sheet_id or not settings.google_service_account_json:
        return None
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError("Google Sheets dependencies are not installed.") from exc
    try:
        service_info = json.loads(settings.google_service_account_json)
        credentials = Credentials.from_service_account_info(
            service_info, scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        service = build("sheets", "v4", credentials=credentials)
        spreadsheet = service.spreadsheets().get(spreadsheetId=settings.google_sheet_id).execute()
        existing = {sheet["properties"]["title"] for sheet in spreadsheet.get("sheets", [])}
        requests = []
        for title in TAB_ORDER:
            if title not in existing:
                requests.append({"addSheet": {"properties": {"title": title}}})
        if requests:
            service.spreadsheets().batchUpdate(
                spreadsheetId=settings.google_sheet_id, body={"requests": requests}
            ).execute()
        for title, df in tabs.items():
            service.spreadsheets().values().clear(
                spreadsheetId=settings.google_sheet_id, range=f"'{title}'"
            ).execute()
            service.spreadsheets().values().update(
                spreadsheetId=settings.google_sheet_id,
                range=f"'{title}'!A1",
                valueInputOption="RAW",
                body={"values": _values(df)},
            ).execute()
    except Exception as exc:
        raise RuntimeError(f"Google Sheets update failed: {exc}") from exc
    return f"https://docs.google.com/spreadsheets/d/{settings.google_sheet_id}"

