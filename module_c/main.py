"""
main.py — Module C FastAPI service.

Run with:
    uvicorn main:app --reload --port 8003

Endpoints:
    POST /event-history/add        -- record a completed event's outcome
                                       (Phase 4 feedback loop)
    GET  /event-history/{organizer_name}  -- raw history for an organizer
    GET  /organizer-risk-prior/{organizer_name}  -- rolled-up risk prior
    POST /intensity-score          -- Predicted Crowd Intensity Score
    POST /recalibrate-threshold    -- dynamic safe-density threshold
                                       (consumed live by Module D)
    GET  /weather                  -- live/mock weather forecast lookup
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from history_db import (
    EventRecord, add_event_record, get_organizer_history,
    compute_organizer_risk_prior, seed_illustrative_data,
)
from weather_client import get_weather_forecast
from intensity_score import compute_predicted_intensity_score, dynamic_threshold_recalibration

app = FastAPI(title="CrowdShield — Module C: Weather & Organizer History")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Seed illustrative data on startup so the service is demo-ready immediately.
seed_illustrative_data()


@app.get("/health")
def health():
    return {"status": "ok", "module": "C - Weather & Organizer History"}


class AddEventRequest(BaseModel):
    organizer_name: str
    venue_name: str
    event_date: str
    event_type: str
    permitted_capacity: int | None = None
    actual_turnout: int | None = None
    had_incident: bool = False
    incident_notes: str | None = None
    behavioral_flags: list[str] | None = None


@app.post("/event-history/add")
def add_event(req: AddEventRequest):
    record = EventRecord(**req.dict())
    event_id = add_event_record(record)
    return {"event_id": event_id, "status": "recorded"}


@app.get("/event-history/{organizer_name}")
def get_history(organizer_name: str):
    return {"organizer_name": organizer_name, "events": get_organizer_history(organizer_name)}


@app.get("/organizer-risk-prior/{organizer_name}")
def get_risk_prior(organizer_name: str):
    return compute_organizer_risk_prior(organizer_name)


@app.get("/weather")
def weather(lat: float, lon: float):
    forecast = get_weather_forecast(lat, lon)
    return {
        "temperature_c": forecast.temperature_c,
        "humidity_pct": forecast.humidity_pct,
        "heat_index_c": forecast.heat_index_c,
        "heat_index_category": forecast.heat_index_category,
        "is_mock_data": forecast.is_mock_data,
        "source_note": forecast.source_note,
    }


class IntensityScoreRequest(BaseModel):
    organizer_name: str
    event_type: str
    lat: float
    lon: float


@app.post("/intensity-score")
def intensity_score(req: IntensityScoreRequest):
    valid_types = {"political_rally", "religious_festival", "concert", "sports_event", "other"}
    if req.event_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"event_type must be one of {valid_types}")

    prior = compute_organizer_risk_prior(req.organizer_name)
    forecast = get_weather_forecast(req.lat, req.lon)
    result = compute_predicted_intensity_score(prior, forecast.heat_index_c, req.event_type)

    return {
        "organizer_risk_prior": prior,
        "weather": {
            "heat_index_c": forecast.heat_index_c,
            "heat_index_category": forecast.heat_index_category,
            "is_mock_data": forecast.is_mock_data,
        },
        "intensity_score_0_100": result.score_0_100,
        "risk_tier": result.risk_tier,
        "contributing_factors": result.contributing_factors,
        "recommended_protocol_adjustments": result.recommended_protocol_adjustments,
    }


class RecalibrateThresholdRequest(BaseModel):
    heat_index_c: float
    avg_wait_time_min: float
    water_coverage_score_0_1: float
    base_safe_area_per_person_m2: float = 0.9


@app.post("/recalibrate-threshold")
def recalibrate_threshold(req: RecalibrateThresholdRequest):
    if not (0.0 <= req.water_coverage_score_0_1 <= 1.0):
        raise HTTPException(status_code=400, detail="water_coverage_score_0_1 must be between 0 and 1")

    return dynamic_threshold_recalibration(
        heat_index_c=req.heat_index_c,
        avg_wait_time_min=req.avg_wait_time_min,
        water_coverage_score_0_1=req.water_coverage_score_0_1,
        base_safe_area_per_person_m2=req.base_safe_area_per_person_m2,
    )
