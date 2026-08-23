"""
main.py — Module F1 FastAPI service.

Run with:
    uvicorn main:app --reload --port 8006

Endpoint:
    POST /simulate
        JSON body:
            blueprint_output: Module A's exact /analyze-blueprint response
            expected_turnout: int (optional) -- overrides the blueprint's
                own turnout figure, for stress-testing (e.g. "2x permit")
            trigger_event: dict (optional) -- {"zone_id": str,
                "at_time_s": float, "radius_m": float}
            duration_s: float (optional, default 30.0)

Returns the simulation output described in simulation_engine.py, which
feeds back into Module A's readiness score and Module B's sensor
placement per the workflow.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from simulation_engine import run_simulation

app = FastAPI(title="CrowdShield — Module F1: 2D Predictive Crowd Simulation")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TriggerEvent(BaseModel):
    zone_id: str
    at_time_s: float = 5.0
    radius_m: float = 3.0


class SimulateRequest(BaseModel):
    blueprint_output: dict
    expected_turnout: int | None = None
    trigger_event: TriggerEvent | None = None
    duration_s: float = 30.0


@app.get("/health")
def health():
    return {"status": "ok", "module": "F1 - 2D Predictive Crowd Simulation"}


@app.post("/simulate")
def simulate(req: SimulateRequest):
    if "zones" not in req.blueprint_output or not req.blueprint_output["zones"]:
        raise HTTPException(
            status_code=400,
            detail="blueprint_output must be Module A's full /analyze-blueprint "
                   "response, including a non-empty 'zones' list with 'contour_px'.",
        )
    if "contour_px" not in req.blueprint_output["zones"][0]:
        raise HTTPException(
            status_code=400,
            detail="blueprint_output zones are missing 'contour_px'. "
                   "This field requires the updated Module A pipeline -- "
                   "make sure Module A is running the latest version.",
        )

    result = run_simulation(
        blueprint_output=req.blueprint_output,
        expected_turnout=req.expected_turnout,
        trigger_event=req.trigger_event.dict() if req.trigger_event else None,
        duration_s=req.duration_s,
    )
    return result
