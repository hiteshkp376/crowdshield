"""
blueprint_pipeline.py — Module A: Blueprint Intelligence.

Pipeline: image ingestion -> symbol detection -> OCR label extraction ->
zone segmentation & area calc -> chokepoint detection -> Fruin LOS scoring
-> readiness score + prioritized gap list.

INPUT ASSUMPTION (stated for the demo / documentation):
Zones are drawn on the blueprint as closed regions bounded by dark
outlines on a light background (standard convention for site-plan
diagrams). Symbols are colored circular markers per the standardized
legend in symbol_detector.py. A scale (meters-per-pixel) is provided
by the organizer at upload time, since auto-detecting a scale bar
reliably is out of scope for the hackathon build.
"""

from dataclasses import dataclass, field
import cv2
import numpy as np
import pytesseract

from symbol_detector import get_default_detector, DetectedSymbol
from fruin_los import score_zone, readiness_score_from_zones

CHOKEPOINT_WIDTH_THRESHOLD_M = 3.0   # narrower than this = flagged chokepoint
MIN_ZONE_AREA_PX = 1500              # filters out noise contours
VIP_MARKER_PROXIMITY_PX = 80         # how close a vip_path_marker must be to tag a zone as VIP


@dataclass
class Zone:
    zone_id: str
    contour: np.ndarray
    area_px: float
    area_m2: float
    is_chokepoint: bool
    chokepoint_width_m: float | None
    is_vip_corridor: bool
    symbols_present: list[str] = field(default_factory=list)
    ocr_labels: list[str] = field(default_factory=list)
    centroid: tuple[int, int] = (0, 0)


def _contour_depth(hierarchy: np.ndarray, index: int) -> int:
    """Walk the parent chain to compute nesting depth (0 = top-level)."""
    depth = 0
    parent = hierarchy[0][index][3]
    while parent != -1:
        depth += 1
        parent = hierarchy[0][parent][3]
    return depth


def _segment_zones(gray: np.ndarray, scale_m_per_px: float) -> list[Zone]:
    """
    Find enclosed zone regions bounded by dark outline strokes.

    Topology of a blueprint like this, from outermost to innermost:
      depth 0: page background (one contour, the whole canvas)
      depth 1: the wall/outline stroke shapes themselves (holes in the
               background -- e.g. the union of a zone's rectangle outline,
               possibly merged with adjacent zones that share a border)
      depth 2: the actual enclosed zone interiors (holes within the wall
               shape) -- THIS is what we want to keep as "zones"
      depth 3+: things drawn inside a zone that are dark enough to register
               as foreground (e.g. symbol markers) -- not zones, excluded

    We use RETR_TREE (not RETR_CCOMP) specifically because CCOMP only
    tracks outer-vs-hole and collapses everything beyond 2 levels back to
    parent=-1, which would incorrectly conflate zone interiors with the
    wall-stroke shapes. RETR_TREE preserves the full chain so we can
    filter by exact depth.
    """
    # Dark lines -> white in the binary mask; enclosed regions stay black
    # after threshold, so we invert to get zones as foreground blobs.
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    # Close small gaps in outline strokes so zones are fully enclosed.
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=2)
    inverted = cv2.bitwise_not(binary)

    contours, hierarchy = cv2.findContours(inverted, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    zones: list[Zone] = []
    zone_counter = 0
    if hierarchy is None:
        return zones

    for i, contour in enumerate(contours):
        area_px = cv2.contourArea(contour)
        if area_px < MIN_ZONE_AREA_PX:
            continue
        if _contour_depth(hierarchy, i) != 2:
            continue  # not a true zone interior -- skip background/wall/marker contours

        area_m2 = area_px * (scale_m_per_px ** 2)

        rect = cv2.minAreaRect(contour)
        (_, _), (rw, rh), _ = rect
        short_side_px = min(rw, rh)
        short_side_m = short_side_px * scale_m_per_px

        is_chokepoint = short_side_m < CHOKEPOINT_WIDTH_THRESHOLD_M

        M = cv2.moments(contour)
        cx = int(M["m10"] / M["m00"]) if M["m00"] != 0 else 0
        cy = int(M["m01"] / M["m00"]) if M["m00"] != 0 else 0

        zone_counter += 1
        zones.append(Zone(
            zone_id=f"Z{zone_counter}",
            contour=contour,
            area_px=area_px,
            area_m2=round(area_m2, 2),
            is_chokepoint=is_chokepoint,
            chokepoint_width_m=round(short_side_m, 2) if is_chokepoint else None,
            is_vip_corridor=False,
            centroid=(cx, cy),
        ))

    return zones


def _attach_symbols(zones: list[Zone], symbols: list[DetectedSymbol]) -> None:
    """Assign each detected symbol to the zone whose contour contains it
    (or the nearest zone centroid if it falls just outside a boundary)."""
    for sym in symbols:
        point = (float(sym.x), float(sym.y))
        assigned = False
        for zone in zones:
            if cv2.pointPolygonTest(zone.contour, point, False) >= 0:
                zone.symbols_present.append(sym.symbol_type)
                assigned = True
                break
        if not assigned and zones:
            nearest = min(zones, key=lambda z: (z.centroid[0] - sym.x) ** 2 + (z.centroid[1] - sym.y) ** 2)
            nearest.symbols_present.append(sym.symbol_type)

        if sym.symbol_type == "vip_path_marker":
            for zone in zones:
                dist = ((zone.centroid[0] - sym.x) ** 2 + (zone.centroid[1] - sym.y) ** 2) ** 0.5
                if dist <= VIP_MARKER_PROXIMITY_PX or cv2.pointPolygonTest(zone.contour, point, False) >= 0:
                    zone.is_vip_corridor = True


def _attach_ocr_labels(zones: list[Zone], image_bgr: np.ndarray) -> None:
    """Run OCR on the whole image, then assign each recognized text
    block to the nearest zone centroid as a human-readable label."""
    try:
        ocr_data = pytesseract.image_to_data(image_bgr, output_type=pytesseract.Output.DICT)
    except pytesseract.TesseractNotFoundError:
        return  # OCR unavailable in this environment; pipeline still runs without labels

    n = len(ocr_data.get("text", []))
    for i in range(n):
        text = ocr_data["text"][i].strip()
        conf = float(ocr_data["conf"][i]) if ocr_data["conf"][i] not in ("-1", "") else -1
        if not text or conf < 40:
            continue
        x, y, w, h = (ocr_data["left"][i], ocr_data["top"][i],
                      ocr_data["width"][i], ocr_data["height"][i])
        tx, ty = x + w / 2, y + h / 2

        if not zones:
            continue
        nearest = min(zones, key=lambda z: (z.centroid[0] - tx) ** 2 + (z.centroid[1] - ty) ** 2)
        nearest.ocr_labels.append(text)


def analyze_blueprint(image_bgr: np.ndarray, scale_m_per_px: float,
                       expected_turnout: int | None = None) -> dict:
    """
    Full Module A pipeline entry point.

    Args:
        image_bgr: the loaded blueprint image (OpenCV BGR array)
        scale_m_per_px: real-world meters represented by one pixel
        expected_turnout: total expected attendees, distributed across
            zones proportional to area, to check against each zone's
            safe max occupancy. If omitted, only safe-max-occupancy
            ceilings are reported (no over-capacity check).

    Returns a JSON-serializable dict: zones, readiness score, gaps.
    """
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

    zones = _segment_zones(gray, scale_m_per_px)
    if not zones:
        return {
            "error": "No enclosed zones detected. Ensure the blueprint has "
                     "closed dark outlines around each zone.",
            "zones": [],
        }

    detector = get_default_detector()
    symbols = detector.detect(image_bgr)
    _attach_symbols(zones, symbols)
    _attach_ocr_labels(zones, image_bgr)

    total_area_m2 = sum(z.area_m2 for z in zones)

    zone_results = []
    zone_scores_for_rollup = []
    vip_ids = set()

    for zone in zones:
        if expected_turnout and total_area_m2 > 0:
            proportional_occupancy = round(expected_turnout * (zone.area_m2 / total_area_m2))
        else:
            proportional_occupancy = 0

        los_score = score_zone(zone.area_m2, proportional_occupancy) if proportional_occupancy > 0 \
            else score_zone(zone.area_m2, max(1, int(zone.area_m2 / 0.9)))  # score at capacity if no turnout given

        zone_scores_for_rollup.append(los_score)
        if zone.is_vip_corridor:
            vip_ids.add(zone.zone_id)

        zone_results.append({
            "zone_id": zone.zone_id,
            "area_m2": zone.area_m2,
            "centroid_px": zone.centroid,
            "is_chokepoint": zone.is_chokepoint,
            "chokepoint_width_m": zone.chokepoint_width_m,
            "is_vip_corridor": zone.is_vip_corridor,
            "symbols_present": zone.symbols_present,
            "ocr_labels": zone.ocr_labels,
            "expected_occupancy": proportional_occupancy if expected_turnout else None,
            "los": los_score,
        })

    rollup = readiness_score_from_zones(
        zone_scores_for_rollup,
        vip_corridor_zone_ids=vip_ids,
        zone_ids=[z["zone_id"] for z in zone_results],
    )

    chokepoints = [z for z in zone_results if z["is_chokepoint"]]

    return {
        "total_zones": len(zone_results),
        "total_area_m2": round(total_area_m2, 2),
        "chokepoints_detected": len(chokepoints),
        "expected_turnout": expected_turnout,
        "zones": zone_results,
        "readiness_score_pct": rollup["readiness_score_pct"],
        "risk_level": rollup["risk_level"],
        "gaps": rollup["gaps"],
    }
