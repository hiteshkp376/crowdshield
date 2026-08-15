"""
main.py — Module E FastAPI service: Tiered Escalation & Human-Confirmed
Response.

Run with:
    uvicorn main:app --reload --port 8005

Endpoints:
    POST /process-fusion-result   -- feed Module D's per-zone fusion
                                      output in; creates escalation
                                      events on tier increases
    POST /confirm-dispatch/{event_id}  -- human confirms a pending Tier 2/3 event
    POST /reject-dispatch/{event_id}   -- human rejects a pending Tier 2/3 event
    GET  /pending-events           -- events awaiting human confirmation
    GET  /all-events               -- full event history
    GET  /alert-translations/{template_key}  -- multilingual alert text
    POST /citizen-reports          -- submit a citizen incident report
    GET  /citizen-reports          -- list citizen reports (unverified)
    GET  /incident-summary         -- GenAI/template plain-language summary
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from escalation_state_machine import EscalationStateMachine
from translation_layer import get_multilingual_alert, SUPPORTED_LANGUAGES
from incident_logger import (
    log_incident, get_incident_log, submit_citizen_report, get_citizen_reports,
)
from genai_summary import generate_incident_summary

app = FastAPI(title="CrowdShield — Module E: Tiered Escalation & Human-Confirmed Response")

_state_machine = EscalationStateMachine()

# Maps escalation tier -> which phrasebook template to attach
_TIER_TO_TEMPLATE = {
    "Tier 1 - Yellow": "tier1_reroute",
    "Tier 2 - Red": "tier2_dispersal",
    "Tier 3 - Active": "tier3_evacuate",
}


@app.get("/health")
def health():
    return {"status": "ok", "module": "E - Tiered Escalation & Human-Confirmed Response"}


class ZoneFusionResultInput(BaseModel):
    zone_id: str
    tier: str
    composite_risk_score_0_100: float
    explainability_breakdown: dict


@app.post("/process-fusion-result")
def process_fusion_result(req: ZoneFusionResultInput):
    event = _state_machine.process_fusion_result(
        req.zone_id, req.tier, req.composite_risk_score_0_100, req.explainability_breakdown
    )
    if event is None:
        return {
            "new_event_created": False,
            "current_tier": _state_machine.get_current_zone_tier(req.zone_id).value,
            "note": "No new escalation event -- zone did not cross to a higher tier.",
        }

    log_incident(
        event.event_id, event.zone_id, event.tier.value, event.composite_risk_score,
        event.explainability_breakdown, event.dispatch_status.value,
    )

    alert_translations = None
    template_key = _TIER_TO_TEMPLATE.get(event.tier.value)
    if template_key:
        alert = get_multilingual_alert(template_key)
        alert_translations = {
            "template_key": alert.template_key,
            "translations": alert.translations,
            "languages_needing_review": alert.languages_needing_review,
        }

    return {
        "new_event_created": True,
        "event_id": event.event_id,
        "zone_id": event.zone_id,
        "tier": event.tier.value,
        "dispatch_status": event.dispatch_status.value,
        "actions": [
            {"action_type": a.action_type, "description": a.description,
             "requires_human_confirmation": a.requires_human_confirmation}
            for a in event.actions
        ],
        "alert_translations": alert_translations,
        "explainability_breakdown": event.explainability_breakdown,
    }


class ConfirmRequest(BaseModel):
    confirmed_by: str


@app.post("/confirm-dispatch/{event_id}")
def confirm_dispatch(event_id: str, req: ConfirmRequest):
    try:
        event = _state_machine.confirm_dispatch(event_id, req.confirmed_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    log_incident(
        event.event_id, event.zone_id, event.tier.value, event.composite_risk_score,
        event.explainability_breakdown, event.dispatch_status.value, event.confirmed_by,
    )
    return {"event_id": event.event_id, "dispatch_status": event.dispatch_status.value,
            "confirmed_by": event.confirmed_by, "confirmed_at": event.confirmed_at.isoformat()}


@app.post("/reject-dispatch/{event_id}")
def reject_dispatch(event_id: str, req: ConfirmRequest):
    try:
        event = _state_machine.reject_dispatch(event_id, req.confirmed_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    log_incident(
        event.event_id, event.zone_id, event.tier.value, event.composite_risk_score,
        event.explainability_breakdown, event.dispatch_status.value, event.confirmed_by,
    )
    return {"event_id": event.event_id, "dispatch_status": event.dispatch_status.value}


@app.get("/pending-events")
def pending_events():
    return {
        "pending_events": [
            {"event_id": e.event_id, "zone_id": e.zone_id, "tier": e.tier.value,
             "composite_risk_score": e.composite_risk_score, "created_at": e.created_at.isoformat()}
            for e in _state_machine.get_pending_events()
        ]
    }


@app.get("/all-events")
def all_events():
    return {
        "events": [
            {"event_id": e.event_id, "zone_id": e.zone_id, "tier": e.tier.value,
             "composite_risk_score": e.composite_risk_score,
             "dispatch_status": e.dispatch_status.value, "created_at": e.created_at.isoformat()}
            for e in _state_machine.get_all_events()
        ]
    }


@app.get("/alert-translations/{template_key}")
def alert_translations(template_key: str):
    try:
        alert = get_multilingual_alert(template_key)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "template_key": alert.template_key,
        "translations": alert.translations,
        "languages_needing_review": alert.languages_needing_review,
    }


class CitizenReportInput(BaseModel):
    zone_id: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    text_report: str | None = None
    photo_path: str | None = None


@app.post("/citizen-reports")
def create_citizen_report(req: CitizenReportInput):
    report_id = submit_citizen_report(
        req.zone_id, req.latitude, req.longitude, req.text_report, req.photo_path,
    )
    return {"report_id": report_id, "verified": False}


@app.get("/citizen-reports")
def list_citizen_reports():
    return {"reports": get_citizen_reports()}


@app.get("/incident-summary")
def incident_summary():
    log = get_incident_log()
    result = generate_incident_summary(log)
    return result
