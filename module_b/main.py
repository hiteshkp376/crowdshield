"""
main.py — Module B FastAPI service.

Run with:
    uvicorn main:app --reload --port 8002

Endpoint:
    POST /plan-placement
        JSON body:
            blueprint_output: Module A's exact /analyze-blueprint response
            f1_result: Module F1's exact /simulate response (optional --
                omit to place sensors using only Module A's static risk)
            sensor_budget: int (optional, default 6)
            steward_budget: int (optional, default 4)
            coverage_radius_m: float (optional, default 15.0)
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from placement_engine import plan_placement, DEFAULT_COVERAGE_RADIUS_M

app = FastAPI(title="CrowdShield — Module B: Sensor & Resource Placement")


class PlanPlacementRequest(BaseModel):
    blueprint_output: dict
    f1_result: dict | None = None
    sensor_budget: int = 6
    steward_budget: int = 4
    coverage_radius_m: float = DEFAULT_COVERAGE_RADIUS_M


@app.get("/health")
def health():
    return {"status": "ok", "module": "B - Sensor & Resource Placement"}


@app.post("/plan-placement")
def plan_placement_endpoint(req: PlanPlacementRequest):
    if "zones" not in req.blueprint_output or not req.blueprint_output["zones"]:
        raise HTTPException(
            status_code=400,
            detail="blueprint_output must be Module A's full /analyze-blueprint "
                   "response, including a non-empty 'zones' list with 'contour_px'.",
        )
    if "contour_px" not in req.blueprint_output["zones"][0]:
        raise HTTPException(
            status_code=400,
            detail="blueprint_output zones are missing 'contour_px' -- "
                   "make sure Module A is running the updated pipeline version.",
        )
    if req.sensor_budget < 1:
        raise HTTPException(status_code=400, detail="sensor_budget must be >= 1")

    result = plan_placement(
        blueprint_output=req.blueprint_output,
        f1_result=req.f1_result,
        sensor_budget=req.sensor_budget,
        steward_budget=req.steward_budget,
        coverage_radius_m=req.coverage_radius_m,
    )
    return result
