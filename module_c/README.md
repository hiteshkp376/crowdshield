# CrowdShield — Module C: Weather & Organizer History Layer

Pulls weather severity and organizer/venue incident history, computes a
Predicted Crowd Intensity Score to pre-configure event protocol, and
dynamically recalibrates the "safe density" threshold under heat/wait-
time/water-coverage stress -- the mechanism designed to catch a
Karur-style scenario before density alone looks extreme.

## Setup

```bash
pip install -r requirements.txt --break-system-packages
```

**Optional -- live weather data:** get a free API key at
[openweathermap.org/api](https://openweathermap.org/api), then either:
```bash
export OPENWEATHERMAP_API_KEY=your_key_here
```
or pass `api_key=` directly when calling `weather_client.get_weather_forecast()`.
Without a key, the service runs fully functional on clearly-labeled mock
weather data (`is_mock_data: true` in every response) -- nothing is
silently faked.

## Run

```bash
uvicorn main:app --reload --port 8003
```

Illustrative organizer/event history is seeded automatically on first
run (see `history_db.seed_illustrative_data()`).

## Test it

```bash
# Organizer risk prior (uses seeded illustrative data)
curl http://localhost:8003/organizer-risk-prior/Example%20Organizer%20A

# Full intensity score (organizer history + live/mock weather + event type)
curl -X POST http://localhost:8003/intensity-score -H "Content-Type: application/json" \
  -d '{"organizer_name": "Example Organizer A", "event_type": "political_rally", "lat": 10.96, "lon": 78.08}'

# Dynamic threshold recalibration (what Module D consumes live)
curl -X POST http://localhost:8003/recalibrate-threshold -H "Content-Type: application/json" \
  -d '{"heat_index_c": 51.6, "avg_wait_time_min": 380, "water_coverage_score_0_1": 0.2}'

# Feedback loop: record a completed event's outcome
curl -X POST http://localhost:8003/event-history/add -H "Content-Type: application/json" \
  -d '{"organizer_name": "Example Organizer A", "venue_name": "New Venue", "event_date": "2026-08-15", "event_type": "political_rally", "permitted_capacity": 12000, "actual_turnout": 13000, "had_incident": false}'
```

## What's real here

- **Heat index calculation** — real NWS Rothfusz regression, computed on
  whatever temperature/humidity is available (live or mock).
- **Organizer risk prior rollup** — real SQL aggregation over stored
  event history (turnout/permit ratio, incident rate, behavioral flags).
- **Intensity scoring** — real, explainable weighted composite (not a
  black box) with concrete recommended protocol adjustments.
- **Dynamic threshold recalibration** — real multiplicative model,
  verified to correctly tighten ~163% under Karur-like conditions
  (extreme heat + 6hr wait + poor water coverage) vs. 0% tightening
  under mild conditions.
- **Feedback loop** — `/event-history/add` genuinely persists to SQLite;
  verified via a live INSERT + returned `event_id`.

## Honest substitutions / limitations

- **Database: SQLite, not PostgreSQL.** The master brief's stack calls
  for PostgreSQL. SQLite is used here as a deliberate hackathon-scale
  substitution — identical schema/query logic, zero external server
  dependency, trivially portable later (swap the connection layer, keep
  the SQL). Stated explicitly, not hidden.
- **Weather: mock fallback without an API key.** Every response includes
  `is_mock_data` so downstream consumers (and the pitch/demo) never
  present mock numbers as live data.
- **Seeded history is illustrative**, using only the public,
  already-widely-reported facts about the Karur case study referenced
  throughout this project (permit ~10,000 vs turnout ~27,000) — labeled
  "Example Organizer A," not tied to any real named individual.

## Files

- `main.py` — FastAPI service, all endpoints
- `weather_client.py` — OpenWeatherMap integration + heat index calc
- `history_db.py` — SQLite schema, CRUD, risk-prior rollup
- `intensity_score.py` — composite scoring + dynamic threshold logic
