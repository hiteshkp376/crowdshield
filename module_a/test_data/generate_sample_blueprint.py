"""
generate_sample_blueprint.py — creates a synthetic venue blueprint image
so Module A can be tested end-to-end without a real organizer upload.

Draws a simple rally-style layout: a large main crowd zone, a narrower
VIP corridor connecting to a stage zone (chokepoint by design), an exit
zone, and colored circular markers per the standardized legend in
symbol_detector.py.
"""

import cv2
import numpy as np

CANVAS_W, CANVAS_H = 1000, 800


def generate() -> np.ndarray:
    img = np.full((CANVAS_H, CANVAS_W, 3), 255, dtype=np.uint8)
    line_color = (0, 0, 0)
    thickness = 3

    # Main crowd zone (large rectangle)
    cv2.rectangle(img, (50, 250), (650, 750), line_color, thickness)

    # Narrow VIP corridor (deliberately narrow -> should trigger chokepoint)
    cv2.rectangle(img, (650, 460), (780, 540), line_color, thickness)

    # Stage zone (VIP destination)
    cv2.rectangle(img, (780, 350), (950, 650), line_color, thickness)

    # Exit zone (small, separate, bottom left)
    cv2.rectangle(img, (50, 50), (250, 200), line_color, thickness)

    # --- Symbol markers (standardized legend colors, BGR format) ---
    def marker(center, color_bgr, radius=14):
        cv2.circle(img, center, radius, color_bgr, -1)

    marker((150, 125), (0, 0, 255))     # exit zone -> red = exit
    marker((100, 700), (255, 150, 0))   # main zone -> blue = water_point
    marker((550, 700), (0, 180, 0))     # main zone -> green = medical
    marker((865, 500), (180, 0, 180))   # stage zone -> purple = stage
    marker((715, 500), (0, 165, 255))   # corridor -> orange = barricade_point
    marker((715, 470), (0, 220, 220))   # corridor -> yellow = vip_path_marker

    # --- Text labels (for OCR extraction) ---
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(img, "MAIN CROWD ZONE", (150, 240), font, 0.6, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.putText(img, "VIP CORRIDOR", (640, 450), font, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.putText(img, "STAGE", (830, 340), font, 0.6, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.putText(img, "EXIT", (110, 40), font, 0.6, (0, 0, 0), 1, cv2.LINE_AA)

    return img


if __name__ == "__main__":
    image = generate()
    out_path = "/home/claude/crowdshield/module_a/test_data/sample_blueprint.png"
    cv2.imwrite(out_path, image)
    print(f"Sample blueprint written to {out_path}")
