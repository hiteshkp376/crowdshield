"""
live_processing.py — testable core logic for the live camera demo.

Deliberately separated from the camera-capture loop (live_camera_worker.py)
so this part can be tested with synthetic frames even without camera
hardware -- this file has zero dependency on cv2.VideoCapture.

Reuses Module D's ALREADY-TESTED detection functions directly
(vision_processor.py) rather than reimplementing detection logic --
same HOG density detector and Farneback optical flow proven earlier in
this project, just wired to a live frame source instead of a synthetic
test frame.

HONESTY NOTE (carry this into the demo/pitch): this uses a NORMAL
webcam, not real thermal hardware -- consistent with the project's
stated hackathon-scale constraint (see Module D's README). Any
"thermal-style" visualization this script shows is a color-mapped
recoloring of the normal camera feed for visual demo effect, NOT real
thermal data, and is clearly labeled as such on-screen and in code.
"""

import sys
from pathlib import Path
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent / "module_d"))
from vision_processor import detect_density, compute_optical_flow, analyze_flow  # noqa: E402


@dataclass
class LiveFrameResult:
    people_count: int
    density_people_per_m2: float
    flow_magnitude: float
    flow_convergence: float
    reverse_flow_detected: bool
    route_blockage_detected: bool


def process_frame_pair(prev_frame_bgr, curr_frame_bgr, zone_area_m2: float,
                        expected_direction_deg: float | None = None,
                        route_blockage_density_threshold: float = 3.0) -> LiveFrameResult:
    """
    Given two consecutive camera frames and the real zone area (fetched
    from Module A), computes the same signal set Module D's /fuse
    endpoint expects -- genuine HOG detection + optical flow, not a
    placeholder.
    """
    import cv2

    density_signal = detect_density(curr_frame_bgr, zone_area_m2)

    prev_gray = cv2.cvtColor(prev_frame_bgr, cv2.COLOR_BGR2GRAY)
    curr_gray = cv2.cvtColor(curr_frame_bgr, cv2.COLOR_BGR2GRAY)
    flow = compute_optical_flow(prev_gray, curr_gray)
    flow_signal = analyze_flow(
        flow,
        expected_direction_deg=expected_direction_deg,
        density_people_per_m2=density_signal.density_people_per_m2,
        route_blockage_density_threshold=route_blockage_density_threshold,
    )

    return LiveFrameResult(
        people_count=density_signal.people_count,
        density_people_per_m2=density_signal.density_people_per_m2,
        flow_magnitude=flow_signal.avg_flow_magnitude_px_per_frame,
        flow_convergence=flow_signal.convergence_score_0_1,
        reverse_flow_detected=flow_signal.reverse_flow_detected,
        route_blockage_detected=flow_signal.route_blockage_detected,
    )


def build_fusion_payload(zone_id: str, result: LiveFrameResult,
                          safe_density_threshold: float,
                          organizer_history_baseline: float = 0.0) -> dict:
    """Formats a LiveFrameResult into exactly the JSON shape Module D's
    POST /fuse endpoint expects (see module_d/main.py's ZoneSignalInput)."""
    return {
        "zone_id": zone_id,
        "density_people_per_m2": round(result.density_people_per_m2, 3),
        "safe_density_threshold_people_per_m2": safe_density_threshold,
        "flow_convergence_score_0_1": round(result.flow_convergence, 3),
        "reverse_flow_detected": result.reverse_flow_detected,
        "route_blockage_detected": result.route_blockage_detected,
        "thermal_collapse_detected": False,  # honest: no real thermal sensor
        "heat_stress_detected": False,       # honest: no real thermal sensor
        "push_wave_detected": False,         # honest: no pressure sensor
        "organizer_history_baseline_0_100": organizer_history_baseline,
    }
