"""
symbol_detector.py — Blueprint symbol/icon detection.

HONESTY NOTE (keep this in the pitch/docs, don't hide it):
The production design calls for a custom-trained YOLOv8 model trained on
CrowdShield's standardized symbol legend (exit, water point, medical tent,
stage, barricade, VIP path). We do not have labeled training data yet for
that model in this hackathon window.

This module instead implements a WORKING color/shape-based detector as a
placeholder against a standardized legend of colored markers, so the full
pipeline (detection -> OCR -> zone scoring) is genuinely runnable end to
end for the demo. The interface (`SymbolDetector.detect`) is what a real
trained YOLOv8 model would plug into later -- swapping the placeholder for
a real model requires no changes anywhere else in the pipeline.

Standardized legend used by the placeholder detector (colored circle
markers on the blueprint, matching CrowdShield's symbol standardization
requirement):
    RED     circle -> exit
    BLUE    circle -> water_point
    GREEN   circle -> medical
    PURPLE  circle -> stage
    ORANGE  circle -> barricade_point
    YELLOW  circle -> vip_path_marker
"""

from dataclasses import dataclass, asdict
from typing import Protocol
import cv2
import numpy as np


@dataclass
class DetectedSymbol:
    symbol_type: str
    confidence: float
    x: int          # pixel center x
    y: int          # pixel center y
    radius: int      # pixel radius (bounding size)

    def to_dict(self):
        return asdict(self)


class SymbolDetector(Protocol):
    def detect(self, image_bgr: np.ndarray) -> list[DetectedSymbol]:
        ...


# HSV color ranges for the standardized placeholder legend.
# (hue, sat, val) ranges tuned for pure/near-pure marker colors.
_LEGEND_HSV_RANGES: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    "exit":             ((0, 150, 100), (8, 255, 255)),       # red
    "water_point":       ((100, 150, 100), (130, 255, 255)),   # blue
    "medical":          ((45, 150, 100), (75, 255, 255)),     # green
    "stage":            ((130, 100, 100), (155, 255, 255)),   # purple
    "barricade_point":   ((10, 150, 100), (22, 255, 255)),     # orange
    "vip_path_marker":   ((26, 150, 100), (34, 255, 255)),     # yellow
}


class ColorMarkerSymbolDetector:
    """
    Placeholder implementation of SymbolDetector. Detects colored circular
    markers per the standardized legend above via HSV thresholding +
    contour blob detection. This is intentionally simple and fast --
    it exists to make the rest of the pipeline demonstrable, not to be
    the final production detector.
    """

    def __init__(self, min_blob_radius_px: int = 6, max_blob_radius_px: int = 60):
        self.min_blob_radius_px = min_blob_radius_px
        self.max_blob_radius_px = max_blob_radius_px

    def detect(self, image_bgr: np.ndarray) -> list[DetectedSymbol]:
        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
        detections: list[DetectedSymbol] = []

        for symbol_type, (lo, hi) in _LEGEND_HSV_RANGES.items():
            mask = cv2.inRange(hsv, np.array(lo), np.array(hi))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for c in contours:
                (x, y), radius = cv2.minEnclosingCircle(c)
                if self.min_blob_radius_px <= radius <= self.max_blob_radius_px:
                    area = cv2.contourArea(c)
                    circle_area = np.pi * radius * radius
                    # circularity check filters out non-marker blobs (e.g. text)
                    circularity = area / circle_area if circle_area > 0 else 0
                    if circularity > 0.6:
                        detections.append(DetectedSymbol(
                            symbol_type=symbol_type,
                            confidence=round(min(circularity, 0.99), 2),
                            x=int(x),
                            y=int(y),
                            radius=int(radius),
                        ))

        return detections


def get_default_detector() -> SymbolDetector:
    """
    Factory so the pipeline code doesn't need to know which detector
    implementation it's using. Swap this out for a real YOLOv8-backed
    detector once training data exists -- nothing else in the pipeline
    needs to change.
    """
    return ColorMarkerSymbolDetector()
