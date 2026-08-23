"""
live_camera_worker.py — live webcam demo for CrowdShield.

Captures your webcam, runs REAL detection (HOG density + Farneback
optical flow -- the same functions already tested in Module D), and
automatically feeds the results into Module D -> Module E every few
seconds, so the dashboard's Digital Twin updates live as it sees you
move in front of the camera. Also opens a local preview window showing
what it's detecting, for the in-person demo.

HONEST LABELING (keep this framing in the pitch): this uses a NORMAL
webcam. The "thermal-style" view (press 't' to toggle) is a color-
mapped recoloring of the normal camera feed for visual demo effect --
it is NOT real thermal sensor data, and is labeled as such on-screen.
Real thermal hardware isn't available for this build (see Module D's
README) -- this demo mode exists specifically to show the detection
pipeline live using equipment you actually have on hand.

NOTE: this script's camera-capture loop could not be tested in the
environment this was built in (no camera hardware available there) --
see live_processing.py for the part that WAS rigorously tested with
synthetic frames. If the camera won't open, check --camera-index (try
0, then 1) and that no other app is currently using the webcam.

Usage:
    python live_camera_worker.py --zone-id Z1

Run this AFTER:
  1. Module A, C, D, E servers are running
  2. The dashboard's "RUN FULL ANALYSIS" has completed at least once
     (so /current-blueprint has real zone data for --zone-id to match)

Controls while running:
  q  - quit
  t  - toggle simulated-thermal-style view
"""

import argparse
import time
import sys

import cv2
import requests

from live_processing import process_frame_pair, build_fusion_payload

TIER_COLOR_BGR = {
    "Green": (100, 220, 80),
    "Tier 1 - Yellow": (30, 190, 250),
    "Tier 2 - Red": (60, 60, 240),
    "Tier 3 - Active": (30, 30, 220),
}


def fetch_zone_area_m2(module_a_url: str, zone_id: str) -> float:
    resp = requests.get(f"{module_a_url}/current-blueprint", timeout=5)
    if resp.status_code == 404:
        print("ERROR: No blueprint has been analyzed yet. Run the dashboard's "
              "'RUN FULL ANALYSIS' step first, then restart this script.")
        sys.exit(1)
    resp.raise_for_status()
    blueprint = resp.json()["blueprint"]
    for zone in blueprint["zones"]:
        if zone["zone_id"] == zone_id:
            return zone["area_m2"]
    available = [z["zone_id"] for z in blueprint["zones"]]
    print(f"ERROR: zone_id '{zone_id}' not found in the current blueprint. "
          f"Available zones: {available}")
    sys.exit(1)


def fetch_safe_threshold(module_c_url: str, fallback: float = 4.0) -> float:
    """Best-effort: use Module C's dynamically recalibrated threshold if
    reachable, otherwise fall back to a flat default -- this demo mode
    shouldn't hard-fail just because Module C isn't running."""
    try:
        resp = requests.post(
            f"{module_c_url}/recalibrate-threshold",
            json={"heat_index_c": 30.0, "avg_wait_time_min": 30, "water_coverage_score_0_1": 0.8},
            timeout=5,
        )
        resp.raise_for_status()
        adjusted_area = resp.json()["adjusted_safe_area_per_person_m2"]
        return 1.0 / adjusted_area if adjusted_area > 0 else fallback
    except Exception:
        print(f"NOTE: Module C not reachable, using flat safe threshold of {fallback} people/m^2.")
        return fallback


def main():
    parser = argparse.ArgumentParser(description="Live webcam demo feeding CrowdShield's real backend.")
    parser.add_argument("--zone-id", required=True, help="Which zone this camera represents (e.g. Z1)")
    parser.add_argument("--camera-index", type=int, default=0, help="Webcam device index (try 0, then 1)")
    parser.add_argument("--report-interval-s", type=float, default=2.0,
                         help="How often to POST results to the backend")
    parser.add_argument("--module-a-url", default="http://localhost:8001")
    parser.add_argument("--module-c-url", default="http://localhost:8003")
    parser.add_argument("--module-d-url", default="http://localhost:8004")
    parser.add_argument("--module-e-url", default="http://localhost:8005")
    parser.add_argument("--organizer-history-score", type=float, default=0.0,
                         help="Optional fixed organizer-history baseline to include")
    args = parser.parse_args()

    print(f"Fetching zone '{args.zone_id}' area from Module A...")
    zone_area_m2 = fetch_zone_area_m2(args.module_a_url, args.zone_id)
    print(f"  Zone area: {zone_area_m2} m^2")

    safe_threshold = fetch_safe_threshold(args.module_c_url)
    print(f"  Using safe density threshold: {safe_threshold:.2f} people/m^2")

    cap = cv2.VideoCapture(args.camera_index)
    if not cap.isOpened():
        print(f"ERROR: could not open camera index {args.camera_index}. "
              f"Try --camera-index 1, and make sure no other app is using the webcam.")
        sys.exit(1)

    print("\nCamera opened. Press 'q' to quit, 't' to toggle simulated-thermal view.\n")

    show_thermal_style = False
    prev_frame = None
    last_report_time = 0.0
    latest_tier = "Green"
    latest_score = 0.0
    latest_note = ""

    while True:
        ok, frame = cap.read()
        if not ok:
            print("WARNING: failed to read a frame from the camera, stopping.")
            break

        display_frame = frame.copy()

        if show_thermal_style:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            display_frame = cv2.applyColorMap(gray, cv2.COLORMAP_INFERNO)
            cv2.putText(display_frame, "SIMULATED THERMAL VIEW -- not real thermal data",
                        (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

        now = time.time()
        if prev_frame is not None and (now - last_report_time) >= args.report_interval_s:
            try:
                result = process_frame_pair(prev_frame, frame, zone_area_m2)
                payload = build_fusion_payload(
                    args.zone_id, result, safe_threshold, args.organizer_history_score,
                )

                fuse_resp = requests.post(f"{args.module_d_url}/fuse",
                                           json={"zones": [payload]}, timeout=5)
                fuse_resp.raise_for_status()
                zone_result = fuse_resp.json()["zones"][0]
                latest_tier = zone_result["tier"]
                latest_score = zone_result["composite_risk_score_0_100"]
                latest_note = zone_result["cross_validation_note"]

                requests.post(f"{args.module_e_url}/process-fusion-result", json={
                    "zone_id": args.zone_id,
                    "tier": latest_tier,
                    "composite_risk_score_0_100": latest_score,
                    "explainability_breakdown": zone_result["explainability_breakdown"],
                }, timeout=5)

                print(f"[{time.strftime('%H:%M:%S')}] people={result.people_count} "
                      f"density={result.density_people_per_m2:.2f}/m^2 "
                      f"tier={latest_tier} score={latest_score}")

            except requests.exceptions.RequestException as e:
                print(f"WARNING: backend request failed ({e}) -- continuing camera loop.")

            last_report_time = now

        prev_frame = frame.copy()

        tier_color = TIER_COLOR_BGR.get(latest_tier, (200, 200, 200))
        cv2.rectangle(display_frame, (0, display_frame.shape[0] - 60),
                      (display_frame.shape[1], display_frame.shape[0]), (20, 20, 20), -1)
        cv2.putText(display_frame, f"Zone {args.zone_id}  |  Tier: {latest_tier}  |  Score: {latest_score:.1f}",
                    (10, display_frame.shape[0] - 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, tier_color, 2, cv2.LINE_AA)
        cv2.putText(display_frame, "Normal webcam feed -- press 't' for simulated-thermal view, 'q' to quit",
                    (10, display_frame.shape[0] - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1, cv2.LINE_AA)

        cv2.imshow("CrowdShield Live Demo", display_frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('t'):
            show_thermal_style = not show_thermal_style

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
