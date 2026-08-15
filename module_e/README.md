# CrowdShield — Module E: Tiered Escalation & Human-Confirmed Response

Consumes Module D's fusion output, manages Tier 1/2/3 escalation with a
human-confirmation gate before real-world dispatch, dispatches
multilingual alerts, logs everything, and generates plain-language
incident summaries.

## Setup

```bash
pip install -r requirements.txt --break-system-packages
```

**Optional -- live GenAI summaries:** set `ANTHROPIC_API_KEY` to enable
LLM-generated prose summaries. Without it, summaries are built from a
genuinely informative template using the structured log directly
(`is_ai_generated: false` in the response, never silently faked).

## Run

```bash
uvicorn main:app --reload --port 8005
```

## Test it (full pipeline: Module D -> Module E)

```bash
python3 -c "
import requests, json

resp_d = requests.post('http://localhost:8004/fuse', json={
    'zones': [{
        'zone_id': 'Z1', 'density_people_per_m2': 6.0, 'safe_density_threshold_people_per_m2': 4.0,
        'flow_convergence_score_0_1': 0.9, 'push_wave_detected': True, 'organizer_history_baseline_0_100': 80
    }]
})
fusion_result = resp_d.json()['zones'][0]

resp_e = requests.post('http://localhost:8005/process-fusion-result', json={
    'zone_id': fusion_result['zone_id'],
    'tier': fusion_result['tier'],
    'composite_risk_score_0_100': fusion_result['composite_risk_score_0_100'],
    'explainability_breakdown': fusion_result['explainability_breakdown'],
})
print(json.dumps(resp_e.json(), ensure_ascii=False, indent=2))
"

# If it returns a pending Tier 2/3 event, confirm it:
curl -X POST http://localhost:8005/confirm-dispatch/EVT-00001 -H "Content-Type: application/json" -d '{"confirmed_by": "your_name"}'

# Generate the incident summary once you have some logged events:
curl http://localhost:8005/incident-summary
```

## What's real here

- **State machine** — verified: Tier 1 auto-fires with no confirmation
  needed; repeated same-tier readings don't spam duplicate events; a
  zone escalating to Tier 2/3 correctly creates a `pending_confirmation`
  event; attempting to confirm an already-confirmed event is correctly
  rejected (`400`) — the human-confirmation gate is a real state
  constraint, not just a label.
- **Multilingual layer** — a deliberate design choice explained in
  `translation_layer.py`: fixed safety templates use a curated
  phrasebook (safer for life-critical instructions than generic MT),
  not a generic translation API.
- **Structured logging** — genuinely persists to SQLite; verified via
  live INSERT + readback through `/incident-summary`.
- **Citizen reports** — stored separately from sensor-confirmed events,
  always `verified: false` at submission, matching the brief's dashboard
  design (distinct marker types).
- **GenAI summary** — real Anthropic API integration when a key is
  configured; otherwise a genuinely informative template-based summary
  built from the structured log (not a placeholder string).

## Honest limitations (state these explicitly, especially in Q&A)

- **Translation accuracy**: the Hindi and Tamil phrasebook entries are a
  first-pass implementation, **not verified by a native speaker or
  professional translator**. Every non-English entry is flagged
  `needs_native_review: true` in the API response itself — this must be
  resolved before any real deployment. Do not present these translations
  as production-ready in the pitch.
- **Database**: SQLite substitution for PostgreSQL, same honest
  trade-off as Module C.
- **"Dispatch" is simulated**: confirming an event marks it
  `confirmed_dispatched` in this software's state — it does not
  actually call a real police/ambulance/112 API (no such sandbox
  integration exists). The state-machine logic and confirmation gate
  are real; the actual downstream emergency-service integration is a
  stated Phase 3/4 roadmap item per the master brief.

## Files

- `main.py` — FastAPI service, all endpoints
- `escalation_state_machine.py` — Tier 1/2/3 logic + confirmation gate
- `translation_layer.py` — curated safety phrasebook + freeform fallback
- `incident_logger.py` — structured logging + citizen reports (SQLite)
- `genai_summary.py` — LLM summary generation with template fallback
