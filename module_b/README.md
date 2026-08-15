# CrowdShield — Module B: Sensor & Resource Placement Engine

Given a device budget, recommends where to place cameras/thermal/pressure
sensors and stewards to maximize coverage of the venue's highest-risk
areas, using the Maximal Covering Location Problem (MCLP) -- the same
operations-research technique used for real-world emergency-facility
siting.

## Setup

```bash
pip install -r requirements.txt --break-system-packages
```

## Run

```bash
uvicorn main:app --reload --port 8002
```

## Test it (full pipeline: Module A -> Module F1 -> Module B)

```bash
python3 -c "
import requests, json

with open('../module_a/test_data/sample_blueprint.png', 'rb') as f:
    resp_a = requests.post('http://localhost:8001/analyze-blueprint',
        files={'file': f},
        data={'scale_m_per_px': 0.03, 'expected_turnout': 800})
blueprint_output = resp_a.json()

resp_f1 = requests.post('http://localhost:8006/simulate', json={
    'blueprint_output': blueprint_output,
    'trigger_event': {'zone_id': 'Z1', 'at_time_s': 5.0, 'radius_m': 3.0},
    'duration_s': 15.0,
})
f1_result = resp_f1.json()

resp_b = requests.post('http://localhost:8002/plan-placement', json={
    'blueprint_output': blueprint_output,
    'f1_result': f1_result,
    'sensor_budget': 6,
    'steward_budget': 4,
})
print(json.dumps(resp_b.json(), indent=2))
"
```

Module F1's `f1_result` is optional -- Module B works standalone off
Module A's static risk alone if F1 hasn't been run.

## What's real here

- **MCLP solved exactly** via integer programming (PuLP + CBC solver),
  not approximated or greedily estimated.
- **Combined risk weighting** -- genuinely merges Module A's static risk
  (LOS band, VIP corridor flag, chokepoint flag) with Module F1's
  simulated risk (predicted high-density zones, predicted panic zones)
  into one weight per demand point, per the brief's stated workflow.
- **Candidate and demand grids** are built from Module A's actual
  detected walkable-space geometry (same technique as Module F1's world
  model) -- not approximated bounding boxes.
- **Barricade and one-way-flow recommendations** are derived directly
  from Module A's chokepoint/VIP flags and geometry, not hardcoded.

## Known limitations (state honestly)

- Coverage radius is a single flat value (`coverage_radius_m`) for all
  device types; real deployments would want per-device-type radii
  (thermal cameras typically see less far than RGB, for instance).
- One-way flow direction is a straight-line heuristic (corridor
  centroid -> goal centroid) -- doesn't account for curved corridors.
- Solver has a 30-second time limit per MCLP solve; very large venues
  with fine-grained grids may hit this and return a near-optimal
  (not guaranteed-optimal) solution -- PuLP/CBC will still return the
  best found within the time limit.

## Files

- `main.py` — FastAPI service, `/plan-placement` endpoint
- `placement_engine.py` — MCLP formulation, risk weighting, barricade
  and flow-direction recommendations
- `test_data/placement_preview.png` — rendered preview showing sensor
  (blue triangle) and steward (orange star) placement, with the VIP
  corridor flagged for barricade treatment

## Output contract

```json
{
  "sensor_budget": 6,
  "sensor_positions_px": [[500.0, 333.3], [333.3, 500.0], [500.0, 666.7]],
  "sensor_coverage_pct_of_weighted_risk": 100.0,
  "steward_positions_px": [...],
  "zone_risk_weights": {"Z1": 63, "Z2": 40, "Z3": 30, "Z4": 20},
  "barricade_recommendations": [
    {"zone_id": "Z1", "urgency": "critical", "recommendation": "serpentine/switchback barricade layout", "note": "..."}
  ],
  "one_way_flow_recommendations": [
    {"zone_id": "Z1", "recommended_flow_direction_deg": -0.4, "note": "..."}
  ]
}
```
