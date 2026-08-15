"""
simulation_engine.py — Module F1: builds the simulated world from Module A's
output and runs the social force + panic-contagion simulation end to end.

HONESTY NOTE (keep this in the pitch/docs -- see also Section 5 of the
master brief, "Known Downsides"):
This simulation is a PRE-EVENT PLANNING TOOL. It models predicted density
buildup and predicted panic propagation using an established pedestrian-
dynamics technique (the social force model), so organizers can pressure-
test a blueprint before the event. It is explicitly NOT a live detection
capability -- Module D's physically-measured push-wave signal remains the
real-time trigger during the actual event. Do not blur this distinction.
"""

import math
import cv2
import numpy as np
from scipy.ndimage import distance_transform_edt

from social_force_model import (
    SocialForceSimulation,
    CRUSH_RISK_DENSITY_PEOPLE_PER_M2,
    PANIC_THRESHOLD,
    AGENT_RADIUS_M,
    AGENT_REPULSION_RANGE_M,
)

MAX_SIM_AGENTS = 250          # hackathon-scale performance cap
DEFAULT_SIM_DURATION_S = 30.0
DT_S = 0.15
FRAME_SUBSAMPLE_EVERY_N_STEPS = 4  # keep every 4th step for the output animation


def _build_walkable_mask(zones: list[dict], width_px: int, height_px: int) -> np.ndarray:
    """Reconstruct which pixels are walkable space by filling every zone's
    polygon onto a blank canvas. This directly reuses Module A's real
    detected geometry rather than approximating with bounding boxes."""
    mask = np.zeros((height_px, width_px), dtype=np.uint8)
    for zone in zones:
        pts = np.array(zone["contour_px"], dtype=np.int32)
        if len(pts) >= 3:
            cv2.fillPoly(mask, [pts], 255)
    return mask


def _find_zone_for_point(zones: list[dict], point_px: tuple[float, float]) -> str | None:
    for zone in zones:
        pts = np.array(zone["contour_px"], dtype=np.int32)
        if len(pts) >= 3 and cv2.pointPolygonTest(pts, point_px, False) >= 0:
            return zone["zone_id"]
    return None


def _sample_points_in_polygon(contour_px: list[list[int]], n_points: int,
                               rng: np.random.Generator) -> np.ndarray:
    """Rejection-sample n_points uniformly distributed inside a polygon."""
    pts = np.array(contour_px, dtype=np.int32)
    x_min, y_min, w, h = cv2.boundingRect(pts)
    x_max, y_max = x_min + w, y_min + h

    accepted = []
    attempts = 0
    max_attempts = n_points * 50
    while len(accepted) < n_points and attempts < max_attempts:
        batch = min(n_points * 2, max_attempts - attempts)
        xs = rng.uniform(x_min, x_max, batch)
        ys = rng.uniform(y_min, y_max, batch)
        for x, y in zip(xs, ys):
            if cv2.pointPolygonTest(pts, (float(x), float(y)), False) >= 0:
                accepted.append([x, y])
                if len(accepted) >= n_points:
                    break
        attempts += batch

    if len(accepted) < n_points:
        # Fallback: fill remainder at the polygon centroid if sampling struggled
        # (can happen for very thin/degenerate polygons).
        M = cv2.moments(pts)
        cx = M["m10"] / M["m00"] if M["m00"] != 0 else (x_min + x_max) / 2
        cy = M["m01"] / M["m00"] if M["m00"] != 0 else (y_min + y_max) / 2
        while len(accepted) < n_points:
            accepted.append([cx, cy])

    return np.array(accepted[:n_points])


def run_simulation(blueprint_output: dict, expected_turnout: int | None = None,
                    trigger_event: dict | None = None,
                    duration_s: float = DEFAULT_SIM_DURATION_S,
                    random_seed: int = 42) -> dict:
    """
    Args:
        blueprint_output: the exact JSON dict returned by Module A's
            /analyze-blueprint endpoint.
        expected_turnout: overrides blueprint_output's expected_turnout if
            given (lets organizers stress-test, e.g. "what if turnout is
            2x the permit").
        trigger_event: optional dict {"zone_id": str, "at_time_s": float,
            "radius_m": float} -- injects a panic trigger at that zone's
            centroid, modeling a discrete disturbance (e.g. someone falls).
        duration_s: how many simulated seconds to run.
        random_seed: for reproducible demo runs.

    Returns: frames (downsampled animation data), per-zone peak stats,
        predicted_high_density_zones, panic_spread_summary.
    """
    zones = blueprint_output["zones"]
    width_px = blueprint_output["image_width_px"]
    height_px = blueprint_output["image_height_px"]
    scale_m_per_px = blueprint_output["scale_m_per_px"]
    turnout = expected_turnout or blueprint_output.get("expected_turnout") or 1000

    rng = np.random.default_rng(random_seed)

    # --- Build walkable-space geometry & wall-distance field ---
    walkable_mask = _build_walkable_mask(zones, width_px, height_px)
    # distance_transform_edt gives, for each pixel, distance (px) to the
    # nearest ZERO pixel -- so we run it on the walkable mask directly:
    # walkable pixels get their distance to the nearest non-walkable pixel.
    dist_px = distance_transform_edt(walkable_mask > 0)
    wall_distance_field_m = dist_px * scale_m_per_px

    # --- Identify goal zone (stage) and spawn zones (everything else,
    # excluding narrow chokepoint corridors as initial spawn locations) ---
    stage_zones = [z for z in zones if "stage" in z.get("symbols_present", [])]
    goal_zone = stage_zones[0] if stage_zones else max(zones, key=lambda z: z["area_m2"])
    goal_px = np.array(goal_zone["centroid_px"], dtype=float)

    spawn_zones = [z for z in zones if z["zone_id"] != goal_zone["zone_id"] and not z["is_chokepoint"]]
    if not spawn_zones:
        spawn_zones = [z for z in zones if z["zone_id"] != goal_zone["zone_id"]]

    total_spawn_area = sum(z["area_m2"] for z in spawn_zones) or 1.0

    # --- Determine agent count (scaled down from real turnout for
    # hackathon-scale performance -- stated explicitly, not hidden) ---
    n_agents = min(MAX_SIM_AGENTS, max(20, turnout // 20))
    people_per_agent = max(1, round(turnout / n_agents))

    # --- Spawn agents distributed proportional to zone area ---
    positions_px = []
    for zone in spawn_zones:
        share = zone["area_m2"] / total_spawn_area
        n_here = max(1, round(n_agents * share))
        pts = _sample_points_in_polygon(zone["contour_px"], n_here, rng)
        positions_px.append(pts)
    positions_px = np.vstack(positions_px)[:n_agents]
    # top up if rounding left us short
    while positions_px.shape[0] < n_agents:
        extra_zone = spawn_zones[rng.integers(0, len(spawn_zones))]
        extra = _sample_points_in_polygon(extra_zone["contour_px"], 1, rng)
        positions_px = np.vstack([positions_px, extra])

    n_agents = positions_px.shape[0]
    positions_m = positions_px * scale_m_per_px
    goals_m = np.tile(goal_px * scale_m_per_px, (n_agents, 1))

    # A super-agent represents `people_per_agent` real people. Its physical
    # footprint should scale with that (space scales with area, so radius
    # scales with sqrt) -- otherwise many real people get compressed into
    # an unrealistically small simulated area and density readings inflate.
    footprint_scale = math.sqrt(people_per_agent)
    sim = SocialForceSimulation(
        positions_m=positions_m,
        goals_m=goals_m,
        wall_distance_field_m=wall_distance_field_m,
        field_origin_m=(0.0, 0.0),
        field_resolution_m_per_cell=scale_m_per_px,
        dt_s=DT_S,
        agent_radius_m=AGENT_RADIUS_M * footprint_scale,
        agent_repulsion_range_m=AGENT_REPULSION_RANGE_M * footprint_scale,
    )

    if trigger_event:
        trigger_zone_id = trigger_event.get("zone_id")
        trigger_zone = next((z for z in zones if z["zone_id"] == trigger_zone_id), None)
        if trigger_zone:
            loc_px = np.array(trigger_zone["centroid_px"], dtype=float)
            sim.inject_trigger_event(
                location_m=tuple(loc_px * scale_m_per_px),
                radius_m=trigger_event.get("radius_m", 3.0),
                at_time_s=trigger_event.get("at_time_s", 5.0),
            )

    n_steps = int(duration_s / DT_S)

    frames = []
    zone_peak_density = {z["zone_id"]: 0.0 for z in zones}
    zone_peak_stress = {z["zone_id"]: 0.0 for z in zones}
    max_panicked_fraction_over_time = 0.0

    for step in range(n_steps):
        sim.step()

        density_per_agent = sim.current_density_per_agent() * people_per_agent
        stress = sim.state.stress
        panicked_fraction = float((stress >= PANIC_THRESHOLD).mean())
        max_panicked_fraction_over_time = max(max_panicked_fraction_over_time, panicked_fraction)

        positions_px_now = sim.state.positions_m / scale_m_per_px
        for idx in range(n_agents):
            zid = _find_zone_for_point(zones, tuple(positions_px_now[idx]))
            if zid is None:
                continue
            zone_peak_density[zid] = max(zone_peak_density[zid], float(density_per_agent[idx]))
            zone_peak_stress[zid] = max(zone_peak_stress[zid], float(stress[idx]))

        if step % FRAME_SUBSAMPLE_EVERY_N_STEPS == 0:
            frames.append({
                "t_s": round(sim.time_s, 2),
                "positions_px": positions_px_now.round(1).tolist(),
                "stress": stress.round(2).tolist(),
                "panicked_fraction": round(panicked_fraction, 3),
            })

    predicted_high_density_zones = [
        zid for zid, peak in zone_peak_density.items()
        if peak >= CRUSH_RISK_DENSITY_PEOPLE_PER_M2
    ]
    predicted_panic_zones = [
        zid for zid, peak in zone_peak_stress.items()
        if peak >= PANIC_THRESHOLD
    ]

    return {
        "n_agents_simulated": n_agents,
        "people_per_agent": people_per_agent,
        "goal_zone_id": goal_zone["zone_id"],
        "duration_s": duration_s,
        "dt_s": DT_S,
        "frames": frames,
        "zone_peak_density_people_per_m2": {k: round(v, 2) for k, v in zone_peak_density.items()},
        "zone_peak_stress": {k: round(v, 2) for k, v in zone_peak_stress.items()},
        "predicted_high_density_zones": predicted_high_density_zones,
        "predicted_panic_zones": predicted_panic_zones,
        "panic_spread_summary": {
            "max_panicked_population_fraction": round(max_panicked_fraction_over_time, 3),
            "trigger_event_applied": trigger_event is not None,
        },
    }
