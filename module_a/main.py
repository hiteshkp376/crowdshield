"""
main.py — Module A FastAPI service.

Run with:
    uvicorn main:app --reload --port 8001

Endpoint:
    POST /analyze-blueprint
        form fields:
            file: the blueprint image (png/jpg)
            scale_m_per_px: float, meters represented by one pixel
            expected_turnout: int (optional), total expected attendees

Returns the full JSON output described in blueprint_pipeline.py,
which is the exact contract Module B (sensor placement) and Module F1
(crowd simulation) consume downstream.
"""

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import numpy as np
import cv2

from blueprint_pipeline import analyze_blueprint

app = FastAPI(title="CrowdShield — Module A: Blueprint Intelligence")


@app.get("/health")
def health():
    return {"status": "ok", "module": "A - Blueprint Intelligence"}


@app.post("/analyze-blueprint")
async def analyze_blueprint_endpoint(
    file: UploadFile = File(...),
    scale_m_per_px: float = Form(...),
    expected_turnout: int | None = Form(None),
):
    if scale_m_per_px <= 0:
        raise HTTPException(status_code=400, detail="scale_m_per_px must be > 0")

    contents = await file.read()
    np_arr = np.frombuffer(contents, np.uint8)
    image_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if image_bgr is None:
        raise HTTPException(status_code=400, detail="Could not decode image file")

    result = analyze_blueprint(
        image_bgr=image_bgr,
        scale_m_per_px=scale_m_per_px,
        expected_turnout=expected_turnout,
    )

    if "error" in result:
        return JSONResponse(status_code=422, content=result)

    return result
