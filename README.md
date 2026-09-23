[README (2).md](https://github.com/user-attachments/files/32548446/README.2.md)
# CrowdShield

**An AI-powered early warning system for preventing crowd stampedes.**

Built for TechNova Season 3, Round 2 (Grand Master) — Problem Statement 01.

Grounded in the September 27, 2025 stampede at a political rally in Karur, Tamil Nadu, where 39–41 people died in a crowd of nearly 27,000 — permitted for 10,000.

---

## What it does

CrowdShield closes the loop on crowd safety, end to end:

1. **Certifies venue blueprints** before a single person arrives — detects zones, chokepoints, and the VIP corridor, and scores readiness using the Fruin Level-of-Service standard
2. **Simulates the crowd** with a real social-force physics model, including panic propagation, to stress-test a venue on paper first
3. **Optimally places sensors** using the same class of integer programming used to site ambulances and fire stations
4. **Fuses live vision and pressure signals**, cross-validated so an excited crowd of fans never triggers a false alarm — only real physical corroboration (a directional pressure wave, a thermal collapse signature) escalates a genuine emergency
5. **Predicts danger minutes before it's visible**, using a trained ML model reading early density and stress trends
6. **Escalates through human-confirmed tiers** — steward, then police/medical, then emergency services — with multilingual alerts, because no automated system dispatches real-world help without a person approving it

---

## What's actually built (not mockups)

| Component | What it does | Status |
|---|---|---|
| **Module A** — Blueprint Intelligence | Zone/chokepoint detection, Fruin LOS scoring | ✅ Built & tested |
| **Module F1** — Crowd Simulation | Social-force model with panic propagation | ✅ Built & tested |
| **Module F2** — Historical Playback | Scrubbable timeline of real logged event data | ✅ Built & tested |
| **Module B** — Sensor Placement | MCLP-based optimal camera/steward placement | ✅ Built & tested |
| **Module C** — Weather & History | Dynamic risk threshold recalibration | ✅ Built & tested |
| **Module D** — Live Fusion Detection | HOG detection, optical flow, push-wave cross-validation | ✅ Built & tested |
| **Module E** — Escalation & Response | Tiered alerts, human confirmation, GenAI summaries | ✅ Built & tested |
| **ML Early-Warning Predictor** | Gradient-boosted classifier, trained on 861 real examples | ✅ Built & tested — **93.1% accuracy, 96.5% precision, 91.0% recall** on held-out test data |
| **Command Dashboard** (React) | Live Digital Twin, playback, signal injection, live prediction graph | ✅ Built & tested |
| **Mobile App** (Flutter) | Attendee heatmap, SOS, incident reporting with photo + GPS | ✅ Built |
| **Live Camera Demo** | Real webcam feed driving live detection into the dashboard | ✅ Built |

---

## Repo structure

```
crowdshield/
├── module_a/              Blueprint Intelligence
├── module_b/              Sensor & Resource Placement
├── module_c/              Weather & Organizer History
├── module_d/              Live Multi-Sensor Fusion Detection
├── module_e/              Tiered Escalation & Response
├── module_f/              Crowd Simulation (F1) & Historical Playback (F2)
├── module_ml_predictor/   Early-warning ML model — training data, trained model, live service
├── dashboard/             React command dashboard
├── mobile_app/            Flutter attendee app
├── live_demo/             Live webcam demo script
├── e2e_test/              End-to-end test scripts
└── docker-compose.yml
```

Every module has its own `README.md` with exact setup steps and an honest breakdown of what's real vs. placeholder.

---

## Quick start

Each backend module runs as its own FastAPI service:

```bash
cd module_a   # repeat for module_b, module_c, module_d, module_e, module_f, module_ml_predictor
pip install -r requirements.txt
uvicorn main:app --reload --port <see module's own README for its port>
```

Then the dashboard:

```bash
cd dashboard
npm install
npm run dev
```

Upload one of the 5 sample venue blueprints in `module_a/test_data/maps/`, and run the full pipeline from the dashboard.

---

## What we're honest about

We'd rather state a limitation plainly than have it discovered later:

- **Blueprint symbol detection** uses a color-marker placeholder, not a trained YOLOv8 model — no labeled training data exists yet for the real legend
- **Thermal and pressure sensor data is simulated.** Real hardware wasn't available for this build — a stated constraint, not a hidden one
- **The ML predictor is trained on our own physics simulation**, not real historical stampede data, because no usable public dataset of that kind exists anywhere
- **Hindi and Tamil alert translations are a first pass**, not yet verified by a native speaker

Every module's own README repeats its specific real-vs-placeholder breakdown in detail.

---

## Tech stack

**Backend:** Python, FastAPI, OpenCV, Tesseract OCR, OR-Tools/PuLP (MCLP solver), SQLite, scikit-learn
**Frontend:** React + Vite (dashboard), Flutter (mobile app)
**Infra:** Docker, GitHub

Nothing exotic — the goal was something that genuinely works on a low budget for temporary events, not a research prototype that needs a data center.
