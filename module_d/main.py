"""
main.py — Module D FastAPI service: Live Multi-Sensor Fusion Detection.

Run with:
    uvicorn main:app --reload --port 8004

Endpoints:
    POST /fuse                  -- main endpoint: takes per-zone signal
                                    inputs (already computed by edge
                                    devices, per the ethics commitment
                                    that only aggregated metrics leave
                                    the edge) and returns composite risk
                                    scores + tiers + explainability.
    POST /detect-pushwave        -- pressure sensor sequence -> push-wave signal
    GET  /edge-cache/status      -- current cache state (demo/testing)
    POST /edge-cache/set-network -- simulate network up/down (demo/testing)
    POST /edge-cache/sync        -- simulate reconnect + flush

Vision (detect_density / analyze_flow) and thermal
(detect_thermal_events) operate on image frames, which aren't practical
to pass through this HTTP JSON API for a hackathon demo -- their
algorithms are directly tested in the module's own test suite (see
README) and consumed programmatically. /fuse is the endpoint Module E
actually calls in the live pipeline.
"""

from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from fusion_engine import fuse_zone_signals, ZoneFusionInput, fuse_all_zones
from pressure_processor import detect_push_wave, SensorReading
from edge_cache import EdgeCache

app = FastAPI(title="CrowdShield — Module D: Live Multi-Sensor Fusion Detection")

_edge_cache = EdgeCache(retention_minutes=10)


@app.get("/health")
def health():
    return {"status": "ok", "module": "D - Live Multi-Sensor Fusion Detection"}


class ZoneSignalInput(BaseModel):
    zone_id: str
    density_people_per_m2: float
    safe_density_threshold_people_per_m2: float
    flow_convergence_score_0_1: float = 0.0
    reverse_flow_detected: bool = False
    route_blockage_detected: bool = False
    thermal_collapse_detected: bool = False
    heat_stress_detected: bool = False
    push_wave_detected: bool = False
    organizer_history_baseline_0_100: float = 0.0


class FuseRequest(BaseModel):
    zones: list[ZoneSignalInput]


@app.post("/fuse")
def fuse(req: FuseRequest):
    if not req.zones:
        raise HTTPException(status_code=400, detail="zones list cannot be empty")

    inputs = [ZoneFusionInput(**z.dict()) for z in req.zones]
    results = fuse_all_zones(inputs)

    for r in results:
        _edge_cache.record_event(r.zone_id, r.tier, r.composite_risk_score_0_100)

    return {
        "zones": [
            {
                "zone_id": r.zone_id,
                "composite_risk_score_0_100": r.composite_risk_score_0_100,
                "tier": r.tier,
                "explainability_breakdown": r.explainability_breakdown,
                "cross_validation_note": r.cross_validation_note,
            }
            for r in results
        ]
    }


class PressureReadingInput(BaseModel):
    sensor_id: str
    position_m: tuple[float, float]
    timestamp_s: float
    reading_kg: float


class PushWaveRequest(BaseModel):
    readings: list[PressureReadingInput]


@app.post("/detect-pushwave")
def detect_pushwave(req: PushWaveRequest):
    readings = [SensorReading(**r.dict()) for r in req.readings]
    result = detect_push_wave(readings)
    return {
        "push_wave_detected": result.push_wave_detected,
        "involved_sensor_ids": result.involved_sensor_ids,
        "propagation_direction": result.propagation_direction,
        "peak_reading_kg": result.peak_reading_kg,
        "note": result.note,
    }


@app.get("/edge-cache/status")
def edge_cache_status():
    return {
        "network_available": _edge_cache.network_available,
        "recent_events_count": len(_edge_cache.get_recent_events()),
        "unsynced_events_count": len(_edge_cache.get_unsynced_events()),
    }


class SetNetworkRequest(BaseModel):
    available: bool


@app.post("/edge-cache/set-network")
def set_network(req: SetNetworkRequest):
    _edge_cache.set_network_status(req.available)
    return {"network_available": _edge_cache.network_available}


@app.post("/edge-cache/sync")
def sync_edge_cache():
    flushed = _edge_cache.sync_queued_events()
    return {"flushed_event_count": flushed}
