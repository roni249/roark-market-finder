from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path

import pandas as pd

from app.config import Settings
from app.outputs.text_exports import cold_calling_plain_text


@dataclass
class PreparedEmail:
    recipient: str
    subject: str
    body: str
    attachments: list[Path]


def prepare_agency_email(
    list_name: str,
    agency_name: str,
    agency_email: str,
    assigned_df: pd.DataFrame,
    report_month: str,
    attachment_path: Path | None = None,
) -> PreparedEmail:
    body = f"""Hi {agency_name},

Here is your cold-calling market list for {report_month}.

Important:
* These ZIP codes are assigned only to your team.
* The other calling team received a separate non-overlapping list.
* Please focus on the target home value ranges listed below.
* Suggested lead criteria: absentee owners, high equity, vacant, tired landlords, out-of-state owners, pre-foreclosure if available, probate if available, ownership length 7+ years, and property value inside the recommended range.

List:
{cold_calling_plain_text(assigned_df)}

Thank you,
ROARK ACQUISITIONS LLC
"""
    attachments = [attachment_path] if attachment_path and attachment_path.exists() else []
    return PreparedEmail(
        recipient=agency_email,
        subject=f"ROARK Monthly Cold Calling Markets - {list_name} - {report_month}",
        body=body,
        attachments=attachments,
    )


def prepare_owner_email(
    owner_email: str,
    report_month: str,
    executive_summary: str,
    list_a: pd.DataFrame,
    list_b: pd.DataFrame,
    manual_review: pd.DataFrame,
    google_sheet_link: str | None = None,
    attachments: list[Path] | None = None,
) -> PreparedEmail:
    link_line = f"\nGoogle Sheet: {google_sheet_link}\n" if google_sheet_link else ""
    body = f"""ROARK Monthly Market Finder Full Report - {report_month}
{link_line}
Executive Summary:
{executive_summary or "Summary unavailable."}

Warnings / Manual Review Items:
{manual_review.to_string(index=False) if not manual_review.empty else "None."}

Cold Caller List A:
{cold_calling_plain_text(list_a)}

Cold Caller List B:
{cold_calling_plain_text(list_b)}
"""
    return PreparedEmail(
        recipient=owner_email,
        subject=f"ROARK Monthly Market Finder Full Report - {report_month}",
        body=body,
        attachments=attachments or [],
    )


def _send_email(settings: Settings, email: PreparedEmail) -> None:
    if not all([settings.smtp_host, settings.from_email, email.recipient]):
        raise RuntimeError("SMTP settings are incomplete; email was not sent.")
    message = EmailMessage()
    message["From"] = settings.from_email
    message["To"] = email.recipient
    message["Subject"] = email.subject
    message.set_content(email.body)
    for attachment in email.attachments:
        message.add_attachment(
            attachment.read_bytes(),
            maintype="text",
            subtype="csv",
            filename=attachment.name,
        )
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


def send_agency_email(settings: Settings, email: PreparedEmail) -> None:
    _send_email(settings, email)


def send_owner_report_email(settings: Settings, email: PreparedEmail) -> None:
    _send_email(settings, email)

