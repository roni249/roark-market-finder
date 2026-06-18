from __future__ import annotations

import pandas as pd


def generate_market_summary(
    county_rankings: pd.DataFrame,
    zip_rankings: pd.DataFrame,
    list_a: pd.DataFrame,
    list_b: pd.DataFrame,
    cooldown_summary: str,
    api_key: str | None,
) -> str:
    if not api_key:
        return ""
    try:
        from openai import OpenAI
    except ImportError:
        return ""
    prompt = f"""
You are a real estate wholesaling market analyst for ROARK ACQUISITIONS LLC.
The company wholesales residential investment properties through cold calling, SMS, and direct seller outreach.
Analyze the supplied county and ZIP rankings.
Write a practical monthly market report for the owner.
Rules: Do not make up data. Use only the supplied rankings. Be direct and investor-focused.

Top counties:
{county_rankings.head(20).to_csv(index=False)}

Top ZIPs:
{zip_rankings.head(40).to_csv(index=False)}

List A balance:
{list_a.groupby('state')['estimated_lead_volume'].sum().to_string() if not list_a.empty else 'None'}

List B balance:
{list_b.groupby('state')['estimated_lead_volume'].sum().to_string() if not list_b.empty else 'None'}

Cooldown summary:
{cooldown_summary}
"""
    try:
        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
            max_output_tokens=1200,
        )
        return response.output_text
    except Exception:
        return ""

