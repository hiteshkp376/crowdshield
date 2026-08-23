"""
main.py — Module ML Predictor FastAPI service.

Run with:
    uvicorn main:app --reload --port 8007

Endpoint:
    POST /predict-danger
        Given a zone's RECENT trend readings (same feature shape the
        model was trained on -- mean/slope/max of density and panic
        over a recent window, plus static zone properties), returns the
        model's predicted probability that this zone crosses a danger
        threshold in the upcoming prediction window.

HONESTY NOTE (state this every time this number is shown anywhere --
dashboard, pitch, docs): this model is trained ONLY on Module F1's own
social-force simulation, not real historical stampede data -- no
usable public dataset of that kind exists. It predicts patterns that
led to escalation in OUR physics simulation, not an empirically
validated real-world outcome. Treat the probability as a decision aid
grounded in simulated crowd dynamics, not a certified real-world
forecast.
"""

from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import joblib
import numpy as np

from feature_extraction import FEATURE_COLUMNS

app = FastAPI(title="CrowdShield — ML Predictor: Early Warning Model")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL_PATH = Path(__file__).parent / "model.joblib"
_model = None


@app.on_event("startup")
def load_model():
    global _model
    if not MODEL_PATH.exists():
        print(f"WARNING: {MODEL_PATH} not found. Run train_model.py first. "
              f"/predict-danger will return 503 until the model exists.")
        return
    _model = joblib.load(MODEL_PATH)
    print("Model loaded successfully.")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "module": "ML Predictor - Early Warning Model",
        "model_loaded": _model is not None,
    }


class PredictRequest(BaseModel):
    early_density_mean: float
    early_density_slope: float
    early_density_max: float
    early_panic_mean: float
    early_panic_slope: float
    zone_area_m2: float
    is_chokepoint: bool
    is_vip_corridor: bool


@app.post("/predict-danger")
def predict_danger(req: PredictRequest):
    if _model is None:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded -- run train_model.py to produce model.joblib, then restart this service.",
        )

    row = [
        req.early_density_mean, req.early_density_slope, req.early_density_max,
        req.early_panic_mean, req.early_panic_slope,
        req.zone_area_m2, int(req.is_chokepoint), int(req.is_vip_corridor),
    ]
    assert len(row) == len(FEATURE_COLUMNS)

    proba = _model.predict_proba(np.array([row]))[0]
    danger_probability = float(proba[1])

    if danger_probability >= 0.7:
        risk_label = "High"
    elif danger_probability >= 0.4:
        risk_label = "Moderate"
    else:
        risk_label = "Low"

    return {
        "danger_probability_0_1": round(danger_probability, 3),
        "risk_label": risk_label,
        "note": "Trained on Module F1's own simulation data, not real historical "
                "stampede records -- treat as a simulation-grounded decision aid, "
                "not a certified real-world forecast.",
    }
