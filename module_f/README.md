# CrowdShield — Module F1: 2D Predictive Crowd Simulation

Pre-event planning tool. Takes Module A's blueprint analysis as input,
simulates how a crowd would move and build density using an established
pedestrian-dynamics technique (the social force model), and models
predicted panic propagation from an injectable trigger event.

## IMPORTANT — what this is and isn't (read before demoing/pitching)

This is a **pre-event planning simulation**, not a live detection
capability. It helps organizers pressure-test a blueprint before the
event (e.g. "what happens if turnout is 2x the permit and someone falls
near the VIP corridor?"). It is explicitly **not** claiming to detect
real panic in real time — during the actual live event, Module D's
physically-measured push-wave signal remains the real-time trigger.
Keep this distinction clear in the pitch; blurring it is the kind of
overclaim that doesn't survive judge questioning.

## Setup

```bash
pip install -r requirements.txt --break-system-packages
```

## Run

```bash
uvicorn main:app --reload --port 8006
```

## Test it (full pipeline: Module A -> Module F1)

```bash
# 1. Make sure Module A is running (port 8001) and has generated its
#    sample blueprint (see module_a/README.md)

# 2. Get Module A's output, feed it into F1
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
print(json.dumps(resp_f1.json(), indent=2))
"
```

`zone_id` in `trigger_event` should match one of Module A's `zone_id`
values from its own output (e.g. the VIP corridor zone) — this models
"someone falls/a disturbance occurs at this specific location."

## What's real here

Everything in this module is a genuine working implementation, not a
placeholder:
- **Social force model** — real vectorized implementation (Helbing &
  Molnár, 1995 lineage): drive force toward goal, agent-agent repulsion,
  wall repulsion computed via a real distance-transform field built from
  Module A's actual detected zone geometry (not approximated shapes).
- **Panic contagion layer** — stress rises with local crush-risk density
  (same 4 people/m² threshold `fruin_los.py` uses), spreads to nearby
  agents, decays over time, and can be triggered by an injectable
  disturbance event at a specific place/time.
- **Super-agent scaling** — since simulating one agent per real attendee
  doesn't scale for a hackathon build, each simulated agent represents
  multiple real people (`people_per_agent`, computed automatically,
  capped at 250 simulated agents). Agent personal-space footprint is
  scaled by `sqrt(people_per_agent)` to keep density readings physically
  sensible — this was a real bug found and fixed during development
  (see git history / dev notes): without the scaling, local density
  readings came out 5-10x too high because super-agents were clustering
  as if they had a single person's footprint.

## Known limitations (state honestly)

- Agent count is capped at 250 for performance — large events use a
  coarser approximation, not a 1:1 simulation of every attendee.
- The wall/obstacle model uses Module A's 2D zone polygons directly;
  it doesn't model 3D obstacles (stages, barriers with gaps, etc.)
  beyond what's drawn on the blueprint.
- Panic contagion parameters (rise rate, contagion rate, decay rate)
  are reasonable literature-informed defaults, not calibrated against
  real incident data — a genuine next step once real event data exists
  (this ties into the Module C feedback loop in the master brief).

## Files

- `main.py` — FastAPI service, `/simulate` endpoint
- `simulation_engine.py` — builds the simulated world from Module A's
  output (walkable-space mask, wall-distance field, agent spawning,
  goal assignment) and orchestrates the run
- `social_force_model.py` — the core vectorized physics + panic layer
- `test_data/simulation_frames_preview.png` — a rendered preview showing
  agents converging toward the stage and panic propagating after a
  trigger event

## Output contract (consumed downstream by Module A's readiness score
## and Module B's sensor placement)

```json
{
  "n_agents_simulated": 40,
  "people_per_agent": 20,
  "goal_zone_id": "Z2",
  "frames": [ { "t_s": 0.15, "positions_px": [[x,y], ...], "stress": [0.0, ...], "panicked_fraction": 0.0 } ],
  "zone_peak_density_people_per_m2": { "Z1": 5.66, "Z2": 5.66, "Z3": 8.49, "Z4": 2.83 },
  "predicted_high_density_zones": ["Z1", "Z2", "Z3"],
  "predicted_panic_zones": ["Z1", "Z2"],
  "panic_spread_summary": { "max_panicked_population_fraction": 0.075, "trigger_event_applied": true }
}
```
