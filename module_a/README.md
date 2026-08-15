# CrowdShield — Module A: Blueprint Intelligence

Pre-event static certification service. Upload a venue blueprint,
get back zone geometry, chokepoints, VIP corridor risk weighting,
and a Fruin LOS-based readiness score.

## Setup

```bash
# System dependency (OCR engine)
apt-get install -y tesseract-ocr libgl1

# Python dependencies
pip install -r requirements.txt --break-system-packages
```

## Run

```bash
uvicorn main:app --reload --port 8001
```

## Test it

Generate the synthetic sample blueprint (a Karur-style layout: main crowd
zone -> narrow VIP corridor -> stage, plus an exit zone):

```bash
python3 test_data/generate_sample_blueprint.py
```

Then call the endpoint:

```bash
curl -X POST http://localhost:8001/analyze-blueprint \
  -F "file=@test_data/sample_blueprint.png" \
  -F "scale_m_per_px=0.03" \
  -F "expected_turnout=3000"
```

`scale_m_per_px` = how many real-world meters one pixel represents.
The organizer/team provides this at upload time (e.g. from a known
venue dimension) — auto-detecting a scale bar is out of scope for
this build.

## What's real vs. placeholder (be upfront about this in the pitch)

| Component | Status |
|---|---|
| Zone segmentation (contour + depth-based topology) | **Real, working** |
| Fruin LOS density scoring | **Real** — implements the actual published standing-crowd LOS bands |
| Chokepoint width detection | **Real** — via minAreaRect short-side measurement |
| OCR label extraction | **Real** — Tesseract, live |
| VIP corridor risk weighting rule | **Real** — implemented exactly per the brief |
| Readiness score rollup + gap list | **Real** |
| Symbol/icon detection | **Placeholder** — color-marker detector standing in for a custom-trained YOLOv8 model (no labeled training data exists yet). Swappable via the `SymbolDetector` interface in `symbol_detector.py` with zero changes needed elsewhere. |

## Files

- `main.py` — FastAPI service, HTTP entry point
- `blueprint_pipeline.py` — core pipeline: segmentation, chokepoints, symbol/OCR attachment, scoring rollup
- `fruin_los.py` — Fruin LOS density bands and scoring logic
- `symbol_detector.py` — pluggable symbol detector (placeholder + real interface)
- `test_data/generate_sample_blueprint.py` — synthetic test blueprint generator

## Output contract (consumed downstream by Module B and Module F1)

```json
{
  "total_zones": 4,
  "total_area_m2": 339.69,
  "chokepoints_detected": 1,
  "readiness_score_pct": 0.0,
  "risk_level": "Critical Risk",
  "zones": [
    {
      "zone_id": "Z1",
      "area_m2": 7.14,
      "centroid_px": [715, 501],
      "is_chokepoint": true,
      "chokepoint_width_m": 2.22,
      "is_vip_corridor": true,
      "symbols_present": ["barricade_point", "vip_path_marker"],
      "ocr_labels": ["CORRIDOR"],
      "expected_occupancy": 63,
      "los": { "los_band": "F", "los_label": "Dangerous", "...": "..." }
    }
  ],
  "gaps": [ { "zone_id": "Z1", "severity": "critical", "note": "..." } ]
}
```
