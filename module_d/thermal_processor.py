"""
thermal_processor.py — Module D: thermal signal (collapse + heat-stress).

HONESTY NOTE (per brief Section 5, "Known Downsides," and Section 7's
build timeline note): real thermal hardware is unlikely to be available
for the hackathon. This module's detection ALGORITHM is genuine --
real contour/blob analysis on a thermal-style grayscale frame (brighter
= hotter) -- but the input frame itself is simulated/mocked, exactly as
the brief explicitly instructs: "build the fusion layer to accept a
mocked/simulated JSON sensor feed so the AI logic and dashboard can be
demonstrated convincingly." Swapping in a real FLIR Lepton-class feed
later requires no change to the detection logic below.

Also implements the brief's stated honest limitation: thermal contrast
weakens in high ambient heat (~40C+) -- modeled here as reduced
detection sensitivity at high baseline frame temperature, not ignored.
"""

from dataclasses import dataclass
import cv2
import numpy as np

# Ground-level collapse: a small, isolated hot blob near the bottom of
# frame (a body at ground level reads warmer than the ground itself).
COLLAPSE_BLOB_MIN_AREA_PX = 150
COLLAPSE_BLOB_MAX_AREA_PX = 2000
COLLAPSE_INTENSITY_THRESHOLD = 200      # 0-255 grayscale, brighter = hotter

# Heat-stress: a large contiguous area of elevated warmth (crowd body
# heat building up, distinct from a single collapse blob).
HEAT_STRESS_MIN_AREA_PX = 5000
HEAT_STRESS_INTENSITY_THRESHOLD = 170

HIGH_AMBIENT_TEMP_C_DEGRADATION_THRESHOLD = 40.0
HIGH_AMBIENT_SENSITIVITY_PENALTY = 25    # raises effective threshold, modeling real contrast loss


@dataclass
class ThermalSignal:
    collapse_detected: bool
    collapse_locations_px: list[tuple[int, int]]
    heat_stress_detected: bool
    heat_stress_area_px: int
    degraded_sensitivity: bool
    note: str


def detect_thermal_events(thermal_frame_gray: np.ndarray,
                           ambient_temp_c: float | None = None) -> ThermalSignal:
    """
    thermal_frame_gray: single-channel frame where pixel brightness
    represents relative temperature (standard thermal-camera convention).
    ambient_temp_c: if provided and >= 40C, detection thresholds are
    honestly degraded to reflect real thermal contrast loss in extreme
    heat (per the brief's stated limitation).
    """
    collapse_threshold = COLLAPSE_BLOB_MIN_AREA_PX
    intensity_threshold_collapse = COLLAPSE_INTENSITY_THRESHOLD
    intensity_threshold_stress = HEAT_STRESS_INTENSITY_THRESHOLD
    degraded = False

    if ambient_temp_c is not None and ambient_temp_c >= HIGH_AMBIENT_TEMP_C_DEGRADATION_THRESHOLD:
        intensity_threshold_collapse = min(255, intensity_threshold_collapse + HIGH_AMBIENT_SENSITIVITY_PENALTY)
        intensity_threshold_stress = min(255, intensity_threshold_stress + HIGH_AMBIENT_SENSITIVITY_PENALTY)
        degraded = True

    # --- Collapse detection: small isolated hot blobs ---
    _, hot_mask = cv2.threshold(thermal_frame_gray, intensity_threshold_collapse, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(hot_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    collapse_locations = []
    for c in contours:
        area = cv2.contourArea(c)
        if COLLAPSE_BLOB_MIN_AREA_PX <= area <= COLLAPSE_BLOB_MAX_AREA_PX:
            M = cv2.moments(c)
            if M["m00"] != 0:
                cx, cy = int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])
                collapse_locations.append((cx, cy))

    # --- Heat-stress detection: large contiguous warm area ---
    _, warm_mask = cv2.threshold(thermal_frame_gray, intensity_threshold_stress, 255, cv2.THRESH_BINARY)
    warm_contours, _ = cv2.findContours(warm_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    total_warm_area = sum(cv2.contourArea(c) for c in warm_contours if cv2.contourArea(c) >= HEAT_STRESS_MIN_AREA_PX)

    note = "Normal thermal readings."
    if degraded:
        note = (f"Thermal sensitivity degraded -- ambient temp {ambient_temp_c}C exceeds "
                 f"{HIGH_AMBIENT_TEMP_C_DEGRADATION_THRESHOLD}C, real contrast loss modeled "
                 f"per known hardware limitation. ")
    if collapse_locations:
        note += f" {len(collapse_locations)} potential collapse blob(s) detected."
    if total_warm_area >= HEAT_STRESS_MIN_AREA_PX:
        note += " Elevated heat-stress area detected."

    return ThermalSignal(
        collapse_detected=len(collapse_locations) > 0,
        collapse_locations_px=collapse_locations,
        heat_stress_detected=total_warm_area >= HEAT_STRESS_MIN_AREA_PX,
        heat_stress_area_px=int(total_warm_area),
        degraded_sensitivity=degraded,
        note=note.strip(),
    )


def generate_mock_thermal_frame(width: int = 400, height: int = 300,
                                 collapse_at: tuple[int, int] | None = None,
                                 heat_stress_region: tuple[int, int, int, int] | None = None) -> np.ndarray:
    """Builds a synthetic thermal-style frame for testing/demo purposes.
    heat_stress_region: (x, y, w, h) of a large warm patch."""
    frame = np.full((height, width), 90, dtype=np.uint8)  # baseline "ground/ambient" temp
    frame = cv2.GaussianBlur(frame + np.random.randint(0, 15, (height, width), dtype=np.uint8), (5, 5), 0)

    if heat_stress_region:
        x, y, w, h = heat_stress_region
        cv2.rectangle(frame, (x, y), (x + w, y + h), 190, -1)

    if collapse_at:
        cv2.circle(frame, collapse_at, 12, 230, -1)

    return frame
