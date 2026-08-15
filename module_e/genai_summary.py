"""
genai_summary.py — Module E: GenAI plain-language incident summaries.

Takes the structured, signal-by-signal incident log and generates a
plain-language summary -- the brief's stated bonus feature, built as a
generation step on top of data Module E already logs (no new pipeline
needed).

HONESTY NOTE: uses the Anthropic API if ANTHROPIC_API_KEY is configured;
otherwise falls back to a genuinely useful TEMPLATE-BASED summary
(not a placeholder string) built directly from the structured log data,
clearly labeled as non-AI-generated. Same honest pattern as every other
external-service integration in this project.
"""

import os
from datetime import datetime

import requests

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"


def _template_summary(incident_log: list[dict]) -> str:
    """Deterministic, template-based fallback summary -- genuinely
    informative, just not LLM-generated prose."""
    if not incident_log:
        return "No incident log entries recorded for this event."

    zones_involved = sorted(set(e["zone_id"] for e in incident_log))
    max_tier_entry = max(incident_log, key=lambda e: e["composite_risk_score"])
    confirmed = [e for e in incident_log if e["dispatch_status"] == "confirmed_dispatched"]
    start_time = incident_log[0]["created_at"]
    end_time = incident_log[-1]["created_at"]

    lines = [
        f"Incident summary ({len(incident_log)} logged events, zones: {', '.join(zones_involved)}):",
        f"- Event window: {start_time} to {end_time}",
        f"- Peak severity: {max_tier_entry['tier']} in zone {max_tier_entry['zone_id']} "
        f"(risk score {max_tier_entry['composite_risk_score']})",
        f"- {len(confirmed)} of {len(incident_log)} escalation(s) were human-confirmed and dispatched.",
    ]
    for e in incident_log:
        top_factor = max(e["explainability_breakdown"].items(), key=lambda kv: kv[1], default=(None, 0))
        lines.append(
            f"  - {e['created_at']}: Zone {e['zone_id']} reached {e['tier']} "
            f"(score {e['composite_risk_score']}), primary contributing factor: {top_factor[0]}."
        )

    return "\n".join(lines)


def generate_incident_summary(incident_log: list[dict], api_key: str | None = None) -> dict:
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

    if not api_key:
        return {
            "summary": _template_summary(incident_log),
            "is_ai_generated": False,
            "note": "No ANTHROPIC_API_KEY configured -- returning a template-based "
                    "summary built directly from the structured log. Set the "
                    "environment variable to enable LLM-generated prose summaries.",
        }

    log_text = "\n".join(
        f"{e['created_at']}: Zone {e['zone_id']} reached {e['tier']} "
        f"(risk score {e['composite_risk_score']}), dispatch status: {e['dispatch_status']}, "
        f"contributing factors: {e['explainability_breakdown']}"
        for e in incident_log
    )

    try:
        resp = requests.post(
            ANTHROPIC_API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 500,
                "messages": [{
                    "role": "user",
                    "content": (
                        "Write a concise, plain-language incident summary (3-5 sentences) "
                        "for a crowd-safety control room log, based on this structured event "
                        "data. Be factual and neutral, no speculation beyond what's logged:\n\n"
                        f"{log_text}"
                    ),
                }],
            },
            timeout=15,
        )
        resp.raise_for_status()
        summary_text = resp.json()["content"][0]["text"]
        return {"summary": summary_text, "is_ai_generated": True, "note": "Live Claude-generated summary."}
    except Exception as e:
        return {
            "summary": _template_summary(incident_log),
            "is_ai_generated": False,
            "note": f"Live API call failed ({type(e).__name__}: {e}) -- "
                    f"returning template-based summary instead.",
        }
