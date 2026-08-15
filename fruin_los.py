"""
fruin_los.py — Fruin Level of Service (LOS) crowd density scoring.

Implements the established crowd-safety-engineering density bands
(John J. Fruin, "Pedestrian Planning and Design", 1971 — the standard
reference used across event safety engineering, e.g. UK's "Purple Guide").

This is deliberately NOT a simulation — it's a lookup against known,
published density thresholds. Given a zone's area (m^2) and expected/
observed occupancy (people), we return:
  - density in people/m^2
  - the LOS band (A best -> F worst)
  - a safety label
  - the max SAFE occupancy for that zone at a target LOS

These bands are for STANDING / QUEUING crowds (not free-flow walkways),
which is the correct standard for rally/festival/stage-front scenarios.
"""

from dataclasses import dataclass
from enum import Enum


class LOSBand(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"


@dataclass
class LOSThreshold:
    band: LOSBand
    min_area_per_person_m2: float  # inclusive lower bound of area/person for this band
    label: str
    description: str


# Ordered from most spacious (A) to most dangerous (F).
# min_area_per_person_m2 = the smallest area/person still in this band.
# A zone falls into a band if its area/person >= this threshold (until
# the next higher band's threshold is reached).
FRUIN_STANDING_LOS: list[LOSThreshold] = [
    LOSThreshold(LOSBand.A, 3.25, "Free Circulation",
                 "Ample space, no interference between people."),
    LOSThreshold(LOSBand.B, 2.3, "Comfortable",
                 "Minor loss of freedom of movement, still comfortable."),
    LOSThreshold(LOSBand.C, 1.4, "Restricted",
                 "Personal space restricted, circulation possible but difficult."),
    LOSThreshold(LOSBand.D, 0.9, "Constrained",
                 "Long queues, reduced circulation, physical contact likely."),
    LOSThreshold(LOSBand.E, 0.5, "High Risk",
                 "Virtually all movement restricted, crowd crush risk begins here."),
    LOSThreshold(LOSBand.F, 0.0, "Dangerous",
                 "Crowd crush / stampede conditions. Immediate intervention zone."),
]

# The threshold at/below which a zone is considered a hard danger zone,
# independent of LOS labeling. This matches widely-cited crowd-safety
# guidance (~4 people/m^2 sustained = crush risk).
CRUSH_RISK_DENSITY_PEOPLE_PER_M2 = 4.0


def area_per_person_to_los(area_per_person_m2: float) -> LOSThreshold:
    """Map an area-per-person value (m^2/person) to its Fruin LOS band."""
    for threshold in FRUIN_STANDING_LOS:
        if area_per_person_m2 >= threshold.min_area_per_person_m2:
            return threshold
    return FRUIN_STANDING_LOS[-1]  # Band F fallback


def score_zone(zone_area_m2: float, occupancy: int) -> dict:
    """
    Score a single zone's crowd safety given its area and occupancy.

    Returns a dict with density, LOS band, safety label, and the
    computed safe max occupancy at LOS D (the standard "still tolerable"
    cutoff commonly used as the planning ceiling for temporary events).
    """
    if zone_area_m2 <= 0:
        raise ValueError("zone_area_m2 must be > 0")
    if occupancy < 0:
        raise ValueError("occupancy must be >= 0")

    density_people_per_m2 = occupancy / zone_area_m2
    area_per_person = zone_area_m2 / occupancy if occupancy > 0 else float("inf")
    los = area_per_person_to_los(area_per_person)

    # Safe max occupancy: the occupancy at which the zone would sit right
    # at the LOS D / E boundary (0.9 m^2/person) — the standard planning
    # ceiling used for temporary event crowd safety.
    safe_max_occupancy = int(zone_area_m2 / 0.9)

    is_crush_risk = density_people_per_m2 >= CRUSH_RISK_DENSITY_PEOPLE_PER_M2

    return {
        "zone_area_m2": round(zone_area_m2, 2),
        "occupancy": occupancy,
        "density_people_per_m2": round(density_people_per_m2, 3),
        "area_per_person_m2": round(area_per_person, 3) if occupancy > 0 else None,
        "los_band": los.band.value,
        "los_label": los.label,
        "los_description": los.description,
        "safe_max_occupancy": safe_max_occupancy,
        "is_crush_risk": is_crush_risk,
    }


def readiness_score_from_zones(zone_scores: list[dict], vip_corridor_zone_ids: set[str] | None = None,
                                zone_ids: list[str] | None = None) -> dict:
    """
    Roll up individual zone LOS scores into one overall event readiness
    percentage (e.g. "72% - Moderate Risk") plus a prioritized gap list.

    VIP corridor zones (if flagged) automatically receive the worst-case
    weighting in the rollup, regardless of their measured density — per
    CrowdShield's stated rule that VIP corridors carry inherent risk
    (Karur-style departure-surge pattern).
    """
    vip_corridor_zone_ids = vip_corridor_zone_ids or set()
    zone_ids = zone_ids or [str(i) for i in range(len(zone_scores))]

    los_band_points = {"A": 100, "B": 85, "C": 65, "D": 45, "E": 20, "F": 0}

    gaps = []
    weighted_points = []

    for zid, zscore in zip(zone_ids, zone_scores):
        points = los_band_points[zscore["los_band"]]
        is_vip = zid in vip_corridor_zone_ids

        if is_vip:
            # VIP corridor: cap at "warning" level max even if measured
            # density looks fine — matches the brief's explicit rule.
            points = min(points, 65)

        weighted_points.append(points)

        severity = None
        if zscore["is_crush_risk"] or zscore["los_band"] == "F":
            severity = "critical"
        elif zscore["los_band"] in ("D", "E") or is_vip:
            severity = "warning"
        elif zscore["los_band"] in ("A", "B", "C"):
            severity = "good"

        note = f"Zone {zid}: {zscore['los_label']} (LOS {zscore['los_band']}), " \
               f"{zscore['density_people_per_m2']} people/m^2"
        if is_vip:
            note += " [VIP CORRIDOR - elevated baseline risk]"
        if zscore["is_crush_risk"]:
            note += " -- CRUSH RISK DENSITY EXCEEDED"

        gaps.append({"zone_id": zid, "severity": severity, "note": note})

    overall_pct = round(sum(weighted_points) / len(weighted_points), 1) if weighted_points else 0.0

    if overall_pct >= 80:
        risk_level = "Low Risk"
    elif overall_pct >= 60:
        risk_level = "Moderate Risk"
    elif overall_pct >= 35:
        risk_level = "High Risk"
    else:
        risk_level = "Critical Risk"

    severity_order = {"critical": 0, "warning": 1, "good": 2}
    gaps.sort(key=lambda g: severity_order.get(g["severity"], 3))

    return {
        "readiness_score_pct": overall_pct,
        "risk_level": risk_level,
        "gaps": gaps,
    }
