# CrowdShield

AI-powered early warning system for preventing crowd stampedes.
TechNova Season 3, Round 2 (Grand Master) — Problem Statement 01.

## Repo structure

module_a/ — Blueprint Intelligence (built, working)
module_b/ — Sensor & Resource Placement Engine (not yet built)
module_c/ — Weather & Organizer History Layer (not yet built)
module_d/ — Live Multi-Sensor Fusion Detection (not yet built)
module_e/ — Tiered Escalation & Response (not yet built)
module_f/ — 2D Crowd Simulation (F1, built) & Historical Playback (F2, not yet built)
dashboard/ — React command dashboard (not yet built)
mobile_app/ — Flutter mobile app (not yet built)

## Running Module A

cd module_a
pip install -r requirements.txt --break-system-packages
uvicorn main:app --reload --port 8001

## Running Module F1

cd module_f
pip install -r requirements.txt --break-system-packages
uvicorn main:app --reload --port 8006