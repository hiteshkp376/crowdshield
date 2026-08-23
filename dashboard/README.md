# CrowdShield — Command Dashboard

React + Vite control-room dashboard: live Digital Twin map, zone risk
panel, live signal injection into Module D, human-confirmation gate for
Module E escalations, and incident log with GenAI summary.

## IMPORTANT — what's verified and what isn't

- **The production build compiles cleanly** (`npm run build` succeeds,
  zero errors) — this catches broken JSX, missing imports, and syntax
  errors.
- **I could NOT get a real screenshot of this running** — the sandbox
  environment this was built in has network restrictions that blocked
  downloading a headless browser. So the visual layout, spacing, and
  color choices have NOT been visually verified by me — only reasoned
  through carefully. **The first real visual check happens when you run
  `npm run dev` and open it yourself.** If something looks off, that's
  useful information — tell me what you see and we'll fix it.

## Setup

```bash
cd dashboard
npm install
```

## Run

**You need all 6 backend servers running first** (ports 8001-8006, see
each module's own README), because this dashboard makes real requests
to your local Python services — it does not work standalone.

```bash
npm run dev
```

Open the URL it prints (usually `http://localhost:5173`).

## IMPORTANT — CORS

Every module's `main.py` was updated to allow requests from
`http://localhost:5173` (added `CORSMiddleware`). If you're running the
backend modules from BEFORE this dashboard was added, **you need to
re-download and replace each module's `main.py`** with the updated
version, or the dashboard's requests will be silently blocked by your
browser with a CORS error (visible in the browser's dev console, F12).

## How to use it

1. **Setup panel (top-left):** upload a blueprint image (use any of the
   5 test maps or your own), set scale/turnout/organizer/event type,
   optionally set a panic trigger zone, click "Run Full Analysis." This
   runs Modules A → F1 → B → C in sequence, same as `test_master.py`.
2. **Digital Twin map (center):** renders your venue's real zone
   geometry. Click a zone to select it (or use the Zone Risk list on
   the left). Hazard-stripe overlay = chokepoint. Sensor/steward
   markers appear once Module B has run.
3. **Live Signal Injector (top-right):** simulates what an edge device
   would send Module D — set density, flow convergence, and toggle
   thermal/push-wave/reverse-flow signals for the selected zone, then
   "Feed to Fusion Engine." This is a genuine call to Module D, then
   Module E.
4. **Explainability panel:** shows the real per-factor breakdown and
   cross-validation note from Module D's response.
5. **Pending Escalations:** any Tier 2/3 event appears here awaiting
   human confirmation — Confirm/Reject buttons call Module E for real.
6. **Incident Log:** every event, plus a button to generate the GenAI
   (or template-fallback) incident summary from Module E.

## Design notes

Dark blueprint/control-room aesthetic — deep navy background with thin
cyan linework (echoing architectural blueprint drafting, since Module
A's blueprint geometry is the literal subject). The only saturated
colors are the four escalation tiers (Green/Yellow/Red/Active) because
that mapping is the project's actual safety semantics, not decoration —
everything else stays deliberately quiet so tier colors read instantly,
the way they need to in a real control room.

## Known limitations

- No F2 historical playback view yet (Module F2 itself isn't built).
- The Signal Injector requires manually setting values — there's no
  live camera/sensor feed wired in (matches Module D's own documented
  scope: it consumes already-computed signals, not raw video).
- Single-organizer intensity score per pipeline run; doesn't yet let
  you compare multiple organizers side by side.

## Files

- `src/App.jsx` — orchestrates all 6 modules, top-level state
- `src/api.js` — fetch wrappers for every backend endpoint used
- `src/components/DigitalTwinMap.jsx` — SVG venue rendering
- `src/components/SetupPanel.jsx` — blueprint upload + pipeline trigger
- `src/components/SignalInjector.jsx` — Module D signal simulation
- `src/components/ExplainabilityPanel.jsx` — Module D breakdown display
- `src/components/PendingEscalations.jsx` — Module E confirmation gate
- `src/components/IncidentLog.jsx` — Module E event log + summary
- `src/index.css` — design tokens + all component styling
