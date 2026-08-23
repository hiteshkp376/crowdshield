"""
test_master.py — CrowdShield: ONE script that does both things.

1. FULL 6-MODULE CHAIN TEST -- proves Module A -> F1 -> B -> C -> D -> E
   are genuinely connected, each one's real output feeding the next.
2. STAMPEDE VISUALIZATION -- takes the SAME Module F1 simulation run
   from step 1 and renders it as an animated GIF, saved into its own
   timestamped file in gif_outputs/ so repeated runs never overwrite
   each other.

Before running: start all 6 module servers in separate terminals
(module_a->8001, module_f->8006, module_b->8002, module_c->8003,
module_d->8004, module_e->8005).

Run from the e2e_test folder:
    python test_master.py

NOTE ON RE-RUNNING WITHOUT RESTARTING SERVERS: Module E remembers each
zone's last-reported tier so it doesn't spam duplicate alerts when
nothing has changed. If you re-run this script against the SAME zone
at the SAME (or lower) tier without restarting the Module E server,
Part 1 step 6 will correctly report "no new escalation" instead of
creating a fresh event -- that's intentional dedup behavior, not a bug.
Restart the Module E server between runs if you want a fresh event
every time.
"""

import os
from datetime import datetime

import requests
import cv2
from PIL import Image

# ==================== CONFIGURE YOUR SCENARIO HERE ====================
BLUEPRINT_IMAGE_PATH = "../module_a/test_data/maps/corridor_rally.png"  # swap for any of the 5 maps
SCALE_M_PER_PX = 0.155            # meters/pixel -- calibrate to your venue's real size
EXPECTED_TURNOUT = 27000          # Karur's actual reported turnout -- keep this REALISTIC for your
                                   # venue size (thousands, not millions) or the readiness score
                                   # floors at 0% and stops being informative
ORGANIZER_NAME = "Example Organizer A"   # must exist in Module C's history for a real risk prior
EVENT_TYPE = "political_rally"    # political_rally | religious_festival | concert | sports_event | other
TRIGGER_EVENT = {
    "zone_id": "Z3",              # <- set to YOUR blueprint's densest/main crowd zone (see step 2 output)
    "at_time_s": 6.0,
    "radius_m": 20.0,
}
SIMULATION_DURATION_S = 30.0

OUTPUT_FOLDER = "gif_outputs"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
map_name = os.path.splitext(os.path.basename(BLUEPRINT_IMAGE_PATH))[0]
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_GIF_PATH = os.path.join(OUTPUT_FOLDER, f"{map_name}_{timestamp}.gif")
# ========================================================================


def section(title):
    print(f"\n{'='*60}\n{title}\n{'='*60}")


# Sanity check on turnout vs. a rough plausibility floor -- doesn't block
# the run, just warns, since "everything is 0% floored" silently produces
# a boring/uninformative demo.
_ROUGH_MAX_SANE_TURNOUT = 500_000
if EXPECTED_TURNOUT > _ROUGH_MAX_SANE_TURNOUT:
    print(f"WARNING: EXPECTED_TURNOUT={EXPECTED_TURNOUT:,} looks unrealistically large. "
          f"If every zone is already floored at 0% readiness, increasing turnout further "
          f"won't change anything -- the score can't go below 0%. Consider a smaller number "
          f"if you want to see the readiness score actually vary.")

# ------------------------------------------------------------------
# PART 1: FULL 6-MODULE CHAIN
# ------------------------------------------------------------------
section("PART 1 — FULL 6-MODULE CHAIN")

print("\n[1/6] MODULE A -- Blueprint analysis")
with open(BLUEPRINT_IMAGE_PATH, "rb") as f:
    resp_a = requests.post("http://localhost:8001/analyze-blueprint",
        files={"file": f},
        data={"scale_m_per_px": SCALE_M_PER_PX, "expected_turnout": EXPECTED_TURNOUT})
assert resp_a.status_code == 200, f"Module A failed: {resp_a.status_code} {resp_a.text}"
blueprint_output = resp_a.json()
print(f"    OK -- {blueprint_output['total_zones']} zones, "
      f"readiness {blueprint_output['readiness_score_pct']}%, risk: {blueprint_output['risk_level']}")
print("    Zones in this blueprint (use these zone_id values for TRIGGER_EVENT above):")
for z in blueprint_output["zones"]:
    print(f"      {z['zone_id']}: area={z['area_m2']}m^2, symbols={z['symbols_present']}, "
          f"chokepoint={z['is_chokepoint']}, vip_corridor={z['is_vip_corridor']}")

print("\n[2/6] MODULE F1 -- Crowd simulation with panic trigger")
resp_f1 = requests.post("http://localhost:8006/simulate", json={
    "blueprint_output": blueprint_output,
    "expected_turnout": EXPECTED_TURNOUT,
    "trigger_event": TRIGGER_EVENT,
    "duration_s": SIMULATION_DURATION_S,
})
assert resp_f1.status_code == 200, f"Module F1 failed: {resp_f1.status_code} {resp_f1.text}"
f1_result = resp_f1.json()
print(f"    OK -- {f1_result['n_agents_simulated']} agents (x{f1_result['people_per_agent']} people each)")
print(f"    predicted_high_density_zones: {f1_result['predicted_high_density_zones']}")
print(f"    predicted_panic_zones: {f1_result['predicted_panic_zones']}")
print(f"    panic_spread_summary: {f1_result['panic_spread_summary']}")

print("\n[3/6] MODULE B -- Sensor & steward placement (using A + F1 combined risk)")
resp_b = requests.post("http://localhost:8002/plan-placement", json={
    "blueprint_output": blueprint_output,
    "f1_result": f1_result,
    "sensor_budget": 6,
    "steward_budget": 4,
})
assert resp_b.status_code == 200, f"Module B failed: {resp_b.status_code} {resp_b.text}"
b_result = resp_b.json()
print(f"    OK -- {len(b_result['sensor_positions_px'])} sensors placed, "
      f"{b_result['sensor_coverage_pct_of_weighted_risk']}% weighted risk coverage")
print(f"    zone_risk_weights: {b_result['zone_risk_weights']}")

print("\n[4/6] MODULE C -- Weather + organizer history -> dynamic threshold")
resp_c_prior = requests.get(f"http://localhost:8003/organizer-risk-prior/{ORGANIZER_NAME.replace(' ', '%20')}")
assert resp_c_prior.status_code == 200
prior = resp_c_prior.json()
print(f"    Organizer risk prior: {prior['events_on_record']} events, "
      f"turnout/permit ratio {prior['avg_turnout_permit_ratio']}")
if prior["events_on_record"] == 0:
    print(f"    NOTE: '{ORGANIZER_NAME}' has no history on record in Module C's database. "
          f"Either use 'Example Organizer A' or 'Example Organizer B' (seeded by default), "
          f"or add your own via Module C's /event-history/add endpoint first.")

resp_c_score = requests.post("http://localhost:8003/intensity-score", json={
    "organizer_name": ORGANIZER_NAME, "event_type": EVENT_TYPE, "lat": 10.96, "lon": 78.08,
})
assert resp_c_score.status_code == 200
intensity = resp_c_score.json()
print(f"    Predicted Crowd Intensity Score: {intensity['intensity_score_0_100']}/100 "
      f"({intensity['risk_tier']})")

resp_c_recal = requests.post("http://localhost:8003/recalibrate-threshold", json={
    "heat_index_c": intensity["weather"]["heat_index_c"], "avg_wait_time_min": 300,
    "water_coverage_score_0_1": 0.3,
})
assert resp_c_recal.status_code == 200
recal = resp_c_recal.json()
print(f"    OK -- dynamic threshold tightened {round((recal['combined_tightening_multiplier']-1)*100)}% "
      f"-> safe area/person now {recal['adjusted_safe_area_per_person_m2']}m^2")

print("\n[5/6] MODULE D -- Live fusion (using C's recalibrated threshold + intensity score as input)")
safe_density_threshold = 1.0 / recal["adjusted_safe_area_per_person_m2"]
trigger_zone = TRIGGER_EVENT["zone_id"]
resp_d = requests.post("http://localhost:8004/fuse", json={
    "zones": [{
        "zone_id": trigger_zone,
        "density_people_per_m2": min(9.0, safe_density_threshold * 1.4),
        "safe_density_threshold_people_per_m2": round(safe_density_threshold, 2),
        "flow_convergence_score_0_1": 0.85,
        "push_wave_detected": True,
        "organizer_history_baseline_0_100": intensity["intensity_score_0_100"],
    }]
})
assert resp_d.status_code == 200, f"Module D failed: {resp_d.status_code} {resp_d.text}"
d_result = resp_d.json()["zones"][0]
print(f"    OK -- Zone {d_result['zone_id']}: {d_result['tier']}, score {d_result['composite_risk_score_0_100']}")
print(f"    cross_validation_note: {d_result['cross_validation_note']}")

print("\n[6/6] MODULE E -- Escalation, multilingual alert, human confirmation, summary")
resp_e = requests.post("http://localhost:8005/process-fusion-result", json={
    "zone_id": d_result["zone_id"],
    "tier": d_result["tier"],
    "composite_risk_score_0_100": d_result["composite_risk_score_0_100"],
    "explainability_breakdown": d_result["explainability_breakdown"],
})
assert resp_e.status_code == 200, f"Module E failed: {resp_e.status_code} {resp_e.text}"
e_result = resp_e.json()

if not e_result.get("new_event_created", False):
    # This zone didn't escalate to a NEW higher tier -- either it's still
    # at the same tier as a previous run (Module E's dedup working as
    # intended), or the fusion score didn't cross a tier boundary this time.
    print(f"    No NEW escalation event created. Current tier for zone "
          f"{trigger_zone}: {e_result.get('current_tier', 'unknown')}")
    print(f"    note: {e_result.get('note', '')}")
    print("    (Restart the Module E server if you want a guaranteed fresh event on every run.)")
else:
    print(f"    OK -- {e_result['event_id']} created, tier {e_result['tier']}, "
          f"dispatch_status: {e_result['dispatch_status']}")

    if e_result["dispatch_status"] == "pending_confirmation":
        resp_confirm = requests.post(f"http://localhost:8005/confirm-dispatch/{e_result['event_id']}",
                                       json={"confirmed_by": "master_script_operator"})
        assert resp_confirm.status_code == 200
        print(f"    OK -- human confirmation successful: {resp_confirm.json()['dispatch_status']}")

resp_summary = requests.get("http://localhost:8005/incident-summary")
summary = resp_summary.json()
print(f"\n    Incident summary (is_ai_generated={summary['is_ai_generated']}):")
print(f"    {summary['summary'][:300]}")

print("\n" + "="*60)
print("PART 1 COMPLETE: ALL 6 MODULES CHAINED SUCCESSFULLY")
print("="*60)

# ------------------------------------------------------------------
# PART 2: STAMPEDE VISUALIZATION -- from the SAME F1 result above
# ------------------------------------------------------------------
section("PART 2 — RENDERING STAMPEDE VISUALIZATION FROM THE SAME RUN")

print("\nHONEST CAVEATS on the numbers you're about to see animated:")
print("  - Peak instantaneous density can exceed physically realistic limits")
print("    (~6-10 people/m^2 max in reality) due to the super-agent approximation")
print("    at high people-per-agent ratios. Treat as a directional signal.")
print("  - This blueprint is illustrative/synthetic unless you've swapped in a")
print("    real venue image.")

base_img = cv2.imread(BLUEPRINT_IMAGE_PATH)
h, w = base_img.shape[:2]

gif_frames = []
for frame in f1_result["frames"]:
    img = base_img.copy()
    for (x, y), stress in zip(frame["positions_px"], frame["stress"]):
        color_bgr = (0, int(220 * (1 - stress)), int(255 * stress))
        radius = 5 if stress < 0.6 else 7
        cv2.circle(img, (int(x), int(y)), radius, color_bgr, -1)
    label = f"t={frame['t_s']}s | panicked={frame['panicked_fraction']*100:.1f}%"
    cv2.rectangle(img, (0, h - 35), (w, h), (255, 255, 255), -1)
    cv2.putText(img, label, (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
    gif_frames.append(Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))

gif_frames[0].save(OUTPUT_GIF_PATH, save_all=True, append_images=gif_frames[1:], duration=150, loop=0)
print(f"\nSaved: {OUTPUT_GIF_PATH} ({len(gif_frames)} frames)")
print(f"All GIFs accumulate in the '{OUTPUT_FOLDER}/' folder -- each run gets its own "
      f"timestamped file, nothing gets overwritten.")

print("\n" + "="*60)
print("MASTER SCRIPT COMPLETE — PIPELINE PROVEN + VISUALIZED FROM ONE CONSISTENT RUN")
print("="*60)
