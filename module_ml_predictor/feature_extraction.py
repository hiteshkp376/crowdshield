"""
feature_extraction.py — ML Predictor: turns F1 simulation frames into
early-window trend features + a late-window danger label.

THE CORE IDEA (this is what makes "predict 10 minutes before" real,
not a buzzword): a simulation's timeline is split into an EARLY window
(the first ~30% of frames) and a LATE window (the rest). Features are
computed ONLY from the early window -- mean density, how fast density
is rising (slope), mean panic stress, how fast stress is rising. The
label is whether the LATE window ever crossed a danger threshold. The
model then learns: "given only what an operator could see in the first
few minutes, does this pattern tend to lead to danger later?" That's
a genuine early-warning prediction task, not just a snapshot classifier.

HONESTY NOTE (repeat this in the pitch): this is trained on Module F1's
OWN social-force simulation, not real historical stampede data -- no
labeled real-world dataset of this kind exists publicly (genuine
stampedes are rare and nobody was logging density/flow sensors during
them). The model learns patterns from our physics simulation, which is
itself only an approximation of real crowd dynamics. State this
plainly; it is the same honest limitation every system in this space
has, not something unique to CrowdShield.
"""

import cv2
import numpy as np
from dataclasses import dataclass

# A zone is "dangerous" in a window if either of these is true at any
# frame within that window -- reuses the exact thresholds already
# established elsewhere in this project (fusion_engine.py's crush
# density literature, social_force_model.py's panic threshold).
DANGER_DENSITY_PEOPLE_PER_M2 = 4.0
DANGER_PANIC_FRACTION = 0.15  # fraction of agents in that zone panicked

EARLY_WINDOW_FRACTION = 0.3  # first 30% of the simulation = "early"


@dataclass
class ZoneWindowFeatures:
    zone_id: str
    early_density_mean: float
    early_density_slope: float   # people/m^2 per frame -- how fast it's rising
    early_density_max: float
    early_panic_mean: float
    early_panic_slope: float
    zone_area_m2: float
    is_chokepoint: int
    is_vip_corridor: int
    label_danger_later: int      # 1 if the LATE window crossed a danger threshold


def _zone_membership_per_frame(zones: list[dict], positions_px: list[list[float]]) -> list[str | None]:
    """For each agent position in a frame, which zone (if any) it's in."""
    contours = [(z["zone_id"], np.array(z["contour_px"], dtype=np.int32)) for z in zones]
    membership = []
    for x, y in positions_px:
        found = None
        for zid, contour in contours:
            if cv2.pointPolygonTest(contour, (float(x), float(y)), False) >= 0:
                found = zid
                break
        membership.append(found)
    return membership


def extract_zone_window_features(blueprint_output: dict, f1_result: dict) -> list[ZoneWindowFeatures]:
    """
    Given one completed F1 simulation run, computes per-zone early-window
    features and the late-window danger label. Returns one
    ZoneWindowFeatures record per zone that had at least one agent
    present during the run.
    """
    zones = blueprint_output["zones"]
    zone_lookup = {z["zone_id"]: z for z in zones}
    frames = f1_result["frames"]
    n_frames = len(frames)
    if n_frames < 4:
        return []  # too short a run to split into meaningful windows

    early_cutoff = max(1, int(n_frames * EARLY_WINDOW_FRACTION))
    people_per_agent = f1_result["people_per_agent"]

    # per-zone, per-frame: density (people/m^2) and mean panic stress
    zone_density_series: dict[str, list[float]] = {z["zone_id"]: [] for z in zones}
    zone_panic_series: dict[str, list[float]] = {z["zone_id"]: [] for z in zones}

    for frame in frames:
        membership = _zone_membership_per_frame(zones, frame["positions_px"])
        stresses = frame["stress"]

        # group agent indices by zone for this frame
        by_zone: dict[str, list[int]] = {}
        for idx, zid in enumerate(membership):
            if zid is not None:
                by_zone.setdefault(zid, []).append(idx)

        for zid in zone_lookup:
            indices = by_zone.get(zid, [])
            area = zone_lookup[zid]["area_m2"]
            density = (len(indices) * people_per_agent / area) if area > 0 else 0.0
            panic_fraction = (
                sum(1 for i in indices if stresses[i] >= 0.6) / len(indices)
                if indices else 0.0
            )
            zone_density_series[zid].append(density)
            zone_panic_series[zid].append(panic_fraction)

    results = []
    for zid, zone in zone_lookup.items():
        density_series = zone_density_series[zid]
        panic_series = zone_panic_series[zid]

        early_density = density_series[:early_cutoff]
        early_panic = panic_series[:early_cutoff]
        late_density = density_series[early_cutoff:]
        late_panic = panic_series[early_cutoff:]

        if not any(d > 0 for d in density_series):
            continue  # this zone never had anyone in it during the run -- skip

        early_density_mean = float(np.mean(early_density))
        early_density_slope = float(np.polyfit(range(len(early_density)), early_density, 1)[0]) \
            if len(early_density) >= 2 else 0.0
        early_density_max = float(np.max(early_density))
        early_panic_mean = float(np.mean(early_panic))
        early_panic_slope = float(np.polyfit(range(len(early_panic)), early_panic, 1)[0]) \
            if len(early_panic) >= 2 else 0.0

        label = int(
            (len(late_density) > 0 and max(late_density) >= DANGER_DENSITY_PEOPLE_PER_M2)
            or (len(late_panic) > 0 and max(late_panic) >= DANGER_PANIC_FRACTION)
        )

        results.append(ZoneWindowFeatures(
            zone_id=zid,
            early_density_mean=early_density_mean,
            early_density_slope=early_density_slope,
            early_density_max=early_density_max,
            early_panic_mean=early_panic_mean,
            early_panic_slope=early_panic_slope,
            zone_area_m2=zone["area_m2"],
            is_chokepoint=int(zone["is_chokepoint"]),
            is_vip_corridor=int(zone["is_vip_corridor"]),
            label_danger_later=label,
        ))

    return results


FEATURE_COLUMNS = [
    "early_density_mean", "early_density_slope", "early_density_max",
    "early_panic_mean", "early_panic_slope",
    "zone_area_m2", "is_chokepoint", "is_vip_corridor",
]


def features_to_row(f: ZoneWindowFeatures) -> list[float]:
    return [getattr(f, col) for col in FEATURE_COLUMNS]
