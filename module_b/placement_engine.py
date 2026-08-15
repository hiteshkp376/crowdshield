"""
placement_engine.py — Module B: Optimal Sensor & Resource Placement.

Implements the Maximal Covering Location Problem (MCLP) -- an established
operations-research technique for siting emergency facilities/cameras
(same family of methods used for real-world fire station and ambulance
placement). Given a candidate set of sensor sites and a set of weighted
"demand points" (places that need coverage, weighted by risk), MCLP
selects the subset of sites -- within a device budget -- that maximizes
the total weighted demand covered.

Classic MCLP formulation (Church & ReVelle, 1974):
    maximize   sum_j w_j * y_j
    subject to y_j <= sum_{i in N_j} x_i      for every demand point j
               sum_i x_i <= p                  (device budget)
               x_i, y_j in {0, 1}
where N_j = candidate sites within coverage_radius of demand point j.

INPUTS CONSUMED:
  - Module A's blueprint output (zone geometry, LOS scores, VIP/chokepoint
    flags) -- this is the STATIC risk baseline.
  - Module F1's simulation output (predicted_high_density_zones,
    predicted_panic_zones, zone_peak_density) -- this is the SIMULATED
    risk overlay, added on top of the static baseline per the brief's
    workflow ("Module B now also ingests Module F1's simulated risk
    zones as additional weighted risk points").
"""

import cv2
import numpy as np
import pulp

LOS_BAND_RISK_WEIGHT = {"A": 1, "B": 2, "C": 4, "D": 7, "E": 12, "F": 20}
VIP_CORRIDOR_WEIGHT_BONUS = 15       # matches Module A's "highest baseline risk" rule
CHOKEPOINT_WEIGHT_BONUS = 8
F1_HIGH_DENSITY_WEIGHT_BONUS = 10
F1_PANIC_ZONE_WEIGHT_BONUS = 10

DEFAULT_COVERAGE_RADIUS_M = 15.0     # typical CCTV/thermal coverage radius
DEFAULT_CANDIDATE_SPACING_M = 5.0    # candidate sensor site grid spacing
DEFAULT_DEMAND_SPACING_M = 3.0       # demand point grid spacing (finer than candidates)


def _build_walkable_mask(zones: list[dict], width_px: int, height_px: int) -> np.ndarray:
    mask = np.zeros((height_px, width_px), dtype=np.uint8)
    for zone in zones:
        pts = np.array(zone["contour_px"], dtype=np.int32)
        if len(pts) >= 3:
            cv2.fillPoly(mask, [pts], 255)
    return mask


def _zone_for_point(zones: list[dict], point_px: tuple[float, float]) -> dict | None:
    for zone in zones:
        pts = np.array(zone["contour_px"], dtype=np.int32)
        if len(pts) >= 3 and cv2.pointPolygonTest(pts, point_px, False) >= 0:
            return zone
    return None


def _compute_zone_risk_weight(zone: dict, f1_result: dict | None) -> float:
    """Combines Module A's static risk (LOS band, VIP, chokepoint) with
    Module F1's simulated risk (predicted high-density / panic zones) into
    a single per-zone weight used to prioritize sensor coverage."""
    weight = LOS_BAND_RISK_WEIGHT.get(zone["los"]["los_band"], 1)

    if zone["is_vip_corridor"]:
        weight += VIP_CORRIDOR_WEIGHT_BONUS
    if zone["is_chokepoint"]:
        weight += CHOKEPOINT_WEIGHT_BONUS

    if f1_result:
        if zone["zone_id"] in f1_result.get("predicted_high_density_zones", []):
            weight += F1_HIGH_DENSITY_WEIGHT_BONUS
        if zone["zone_id"] in f1_result.get("predicted_panic_zones", []):
            weight += F1_PANIC_ZONE_WEIGHT_BONUS

    return weight


def _grid_points_in_mask(mask: np.ndarray, spacing_px: float) -> np.ndarray:
    h, w = mask.shape
    xs = np.arange(0, w, spacing_px)
    ys = np.arange(0, h, spacing_px)
    grid_x, grid_y = np.meshgrid(xs, ys)
    candidates = np.stack([grid_x.ravel(), grid_y.ravel()], axis=1)
    valid = []
    for x, y in candidates:
        xi, yi = int(x), int(y)
        if 0 <= yi < h and 0 <= xi < w and mask[yi, xi] > 0:
            valid.append([x, y])
    return np.array(valid) if valid else np.empty((0, 2))


def _generate_candidates_and_demand(zones: list[dict], width_px: int, height_px: int,
                                     scale_m_per_px: float, f1_result: dict | None,
                                     candidate_spacing_m: float, demand_spacing_m: float):
    mask = _build_walkable_mask(zones, width_px, height_px)

    candidate_spacing_px = candidate_spacing_m / scale_m_per_px
    demand_spacing_px = demand_spacing_m / scale_m_per_px

    candidates_px = _grid_points_in_mask(mask, candidate_spacing_px)
    demand_px = _grid_points_in_mask(mask, demand_spacing_px)

    zone_weight_cache = {z["zone_id"]: _compute_zone_risk_weight(z, f1_result) for z in zones}

    demand_weights = []
    demand_zone_ids = []
    kept_demand = []
    for pt in demand_px:
        zone = _zone_for_point(zones, tuple(pt))
        if zone is None:
            continue
        kept_demand.append(pt)
        demand_weights.append(zone_weight_cache[zone["zone_id"]])
        demand_zone_ids.append(zone["zone_id"])

    return (candidates_px, np.array(kept_demand), np.array(demand_weights),
            demand_zone_ids, zone_weight_cache)


def solve_mclp(candidates_px: np.ndarray, demand_px: np.ndarray, demand_weights: np.ndarray,
               budget: int, coverage_radius_px: float) -> dict:
    """Solves the MCLP exactly via integer programming (PuLP/CBC).
    Returns which candidate indices were selected and coverage stats."""
    n_candidates = candidates_px.shape[0]
    n_demand = demand_px.shape[0]

    if n_candidates == 0 or n_demand == 0:
        return {"selected_indices": [], "covered_weight": 0.0, "total_weight": float(demand_weights.sum())}

    # N_j: for each demand point, which candidate sites cover it
    dists = np.linalg.norm(
        demand_px[:, None, :] - candidates_px[None, :, :], axis=2
    )
    coverage = dists <= coverage_radius_px  # (n_demand, n_candidates) boolean

    prob = pulp.LpProblem("MCLP", pulp.LpMaximize)
    x = [pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(n_candidates)]
    y = [pulp.LpVariable(f"y_{j}", cat="Binary") for j in range(n_demand)]

    prob += pulp.lpSum(demand_weights[j] * y[j] for j in range(n_demand))

    for j in range(n_demand):
        covering = np.where(coverage[j])[0]
        if len(covering) == 0:
            prob += y[j] == 0
        else:
            prob += y[j] <= pulp.lpSum(x[i] for i in covering)

    prob += pulp.lpSum(x) <= budget

    solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=30)
    prob.solve(solver)

    selected = [i for i in range(n_candidates) if pulp.value(x[i]) and pulp.value(x[i]) > 0.5]
    covered_weight = sum(
        demand_weights[j] for j in range(n_demand)
        if pulp.value(y[j]) and pulp.value(y[j]) > 0.5
    )

    return {
        "selected_indices": selected,
        "covered_weight": float(covered_weight),
        "total_weight": float(demand_weights.sum()),
        "solver_status": pulp.LpStatus[prob.status],
    }


def _one_way_flow_recommendation(zones: list[dict], goal_zone_id: str | None) -> list[dict]:
    """For each chokepoint/corridor zone, recommend a flow direction:
    from the crowd's general spawn area toward the goal (stage/VIP
    destination). Direction is computed from the corridor's centroid
    toward the goal zone's centroid -- a simple, defensible heuristic
    given the geometry we have."""
    if goal_zone_id is None:
        return []
    goal_zone = next((z for z in zones if z["zone_id"] == goal_zone_id), None)
    if goal_zone is None:
        return []
    goal_pt = np.array(goal_zone["centroid_px"], dtype=float)

    recommendations = []
    for zone in zones:
        if not zone["is_chokepoint"]:
            continue
        corridor_pt = np.array(zone["centroid_px"], dtype=float)
        direction = goal_pt - corridor_pt
        norm = np.linalg.norm(direction)
        if norm < 1e-6:
            continue
        direction_unit = direction / norm
        angle_deg = float(np.degrees(np.arctan2(direction_unit[1], direction_unit[0])))
        recommendations.append({
            "zone_id": zone["zone_id"],
            "recommended_flow_direction_deg": round(angle_deg, 1),
            "note": f"One-way flow toward {goal_zone_id} recommended through this corridor "
                    f"to prevent counter-flow congestion at the chokepoint.",
        })
    return recommendations


def _barricade_recommendations(zones: list[dict]) -> list[dict]:
    """Flags chokepoint zones (especially VIP corridors) for serpentine/
    switchback barricade layout -- an established crowd-engineering
    technique to break a single mass surge into smaller queued segments."""
    recommendations = []
    for zone in zones:
        if zone["is_chokepoint"]:
            urgency = "critical" if zone["is_vip_corridor"] else "recommended"
            recommendations.append({
                "zone_id": zone["zone_id"],
                "urgency": urgency,
                "recommendation": "serpentine/switchback barricade layout",
                "note": f"Chokepoint width {zone.get('chokepoint_width_m', '?')}m. "
                        f"{'VIP corridor -- ' if zone['is_vip_corridor'] else ''}"
                        f"Serpentine barricades break a single mass surge into smaller, "
                        f"queued segments rather than one continuous crowd front.",
            })
    return recommendations


def plan_placement(blueprint_output: dict, f1_result: dict | None = None,
                    sensor_budget: int = 6, steward_budget: int = 4,
                    coverage_radius_m: float = DEFAULT_COVERAGE_RADIUS_M,
                    candidate_spacing_m: float = DEFAULT_CANDIDATE_SPACING_M,
                    demand_spacing_m: float = DEFAULT_DEMAND_SPACING_M) -> dict:
    """
    Full Module B pipeline entry point.

    Args:
        blueprint_output: Module A's exact /analyze-blueprint response.
        f1_result: Module F1's exact /simulate response (optional -- if
            omitted, placement uses only Module A's static risk).
        sensor_budget: how many cameras/thermal/pressure sensors to place.
        steward_budget: how many steward positions to place (uses the
            same MCLP mechanism against the same risk-weighted demand).
        coverage_radius_m: assumed coverage radius per device.
    """
    zones = blueprint_output["zones"]
    width_px = blueprint_output["image_width_px"]
    height_px = blueprint_output["image_height_px"]
    scale_m_per_px = blueprint_output["scale_m_per_px"]
    coverage_radius_px = coverage_radius_m / scale_m_per_px

    candidates_px, demand_px, demand_weights, demand_zone_ids, zone_weights = \
        _generate_candidates_and_demand(
            zones, width_px, height_px, scale_m_per_px, f1_result,
            candidate_spacing_m, demand_spacing_m,
        )

    sensor_result = solve_mclp(candidates_px, demand_px, demand_weights,
                                sensor_budget, coverage_radius_px)
    sensor_positions_px = [candidates_px[i].tolist() for i in sensor_result["selected_indices"]]

    steward_result = solve_mclp(candidates_px, demand_px, demand_weights,
                                 steward_budget, coverage_radius_px * 0.5)  # stewards cover a tighter radius
    steward_positions_px = [candidates_px[i].tolist() for i in steward_result["selected_indices"]]

    goal_zone_id = f1_result.get("goal_zone_id") if f1_result else None
    if goal_zone_id is None:
        stage_zones = [z for z in zones if "stage" in z.get("symbols_present", [])]
        goal_zone_id = stage_zones[0]["zone_id"] if stage_zones else None

    coverage_pct = (100.0 * sensor_result["covered_weight"] / sensor_result["total_weight"]) \
        if sensor_result["total_weight"] > 0 else 0.0

    return {
        "sensor_budget": sensor_budget,
        "sensor_positions_px": sensor_positions_px,
        "sensor_coverage_pct_of_weighted_risk": round(coverage_pct, 1),
        "steward_budget": steward_budget,
        "steward_positions_px": steward_positions_px,
        "zone_risk_weights": zone_weights,
        "barricade_recommendations": _barricade_recommendations(zones),
        "one_way_flow_recommendations": _one_way_flow_recommendation(zones, goal_zone_id),
        "n_candidate_sites_considered": int(candidates_px.shape[0]),
        "n_demand_points_considered": int(demand_px.shape[0]),
        "coverage_radius_m": coverage_radius_m,
    }
