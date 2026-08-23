"""
fusion_engine.py — Module D: AI Fusion Layer.

Combines vision, thermal, pressure, and organizer-history signals into
one composite risk score per zone, using the exact weighted formula from
the master brief:

    Risk Score = w1(density) + w2(flow_convergence) + w3(thermal_collapse)
               + w4(heat_stress) + w5(push_wave_signal) + w6(organizer_history_baseline)
               + w7(reverse_flow_signal) + w8(route_blockage_signal)

CROSS-VALIDATION (the brief's key false-positive filter): vision showing
rising density ALONE does not escalate to a high tier -- it needs
corroboration from a physical signal (push-wave or thermal collapse) to
reach Tier 2/3. This is what filters "fans cheering/excited" false
positives, since normal excitement doesn't produce a directional
pressure shockwave. Implemented explicitly below, not just described.

Consumes Module C's dynamically recalibrated threshold (heat/wait-time/
water-adjusted safe density) instead of a fixed baseline, per the
workflow: "Module C continuously recalibrates the safe-density threshold
based on live heat index and wait times."
"""

from dataclasses import dataclass, field

# Base weights from the brief's formula (relative importance, 0-100 scale
# contribution per fully-triggered signal)
WEIGHTS = {
    "density": 20,
    "flow_convergence": 12,
    "thermal_collapse": 20,
    "heat_stress": 10,
    "push_wave": 25,
    "organizer_history_baseline": 8,
    "reverse_flow": 8,
    "route_blockage": 12,
}

TIER_1_THRESHOLD = 30   # Green -> Yellow
TIER_2_THRESHOLD = 55   # Yellow -> Red
TIER_3_THRESHOLD = 75   # Red -> Active

# Real-world crowd density literature (see Module A's Fruin LOS bands,
# and documented crowd-crush incidents) puts even the deadliest recorded
# crushes around 8-10 people/m^2 -- density doesn't meaningfully increase
# beyond that because human bodies physically can't compress further.
# So density readings far beyond the safe threshold aren't just "risky,"
# they're direct physical evidence of an active or imminent crush --
# unlike moderate density (which genuinely can be innocent, e.g. excited
# fans), extreme density doesn't need a corroborating signal to be
# believed. This mirrors the project's core principle: false negatives
# in a safety system are worse than false positives.
DENSITY_SEVERE_OVERRIDE_RATIO = 4.0   # 4x the dynamic safe threshold
SEVERE_DENSITY_SCORE_FLOOR = 95.0     # forces Tier 3 regardless of other corroboration


@dataclass
class ZoneFusionInput:
    zone_id: str
    density_people_per_m2: float
    safe_density_threshold_people_per_m2: float  # from Module C's dynamic recalibration
    flow_convergence_score_0_1: float
    reverse_flow_detected: bool
    route_blockage_detected: bool
    thermal_collapse_detected: bool
    heat_stress_detected: bool
    push_wave_detected: bool
    organizer_history_baseline_0_100: float = 0.0  # from Module C's intensity score


@dataclass
class ZoneRiskResult:
    zone_id: str
    composite_risk_score_0_100: float
    tier: str
    explainability_breakdown: dict
    cross_validation_note: str


def _density_component(density: float, safe_threshold: float) -> float:
    """Scales density contribution relative to the DYNAMIC safe threshold
    (not a fixed number) -- density at or below threshold contributes ~0;
    density well above it saturates the weight."""
    if safe_threshold <= 0:
        return 0.0
    ratio = density / safe_threshold
    if ratio <= 1.0:
        return 0.0
    # Saturates at 2x the safe threshold
    scaled = min(1.0, (ratio - 1.0))
    return scaled * WEIGHTS["density"]


def fuse_zone_signals(zone_input: ZoneFusionInput) -> ZoneRiskResult:
    breakdown = {}

    density_pts = _density_component(
        zone_input.density_people_per_m2, zone_input.safe_density_threshold_people_per_m2
    )
    breakdown["density"] = round(density_pts, 1)

    flow_pts = zone_input.flow_convergence_score_0_1 * WEIGHTS["flow_convergence"]
    breakdown["flow_convergence"] = round(flow_pts, 1)

    reverse_flow_pts = WEIGHTS["reverse_flow"] if zone_input.reverse_flow_detected else 0.0
    breakdown["reverse_flow"] = reverse_flow_pts

    route_blockage_pts = WEIGHTS["route_blockage"] if zone_input.route_blockage_detected else 0.0
    breakdown["route_blockage"] = route_blockage_pts

    thermal_collapse_pts = WEIGHTS["thermal_collapse"] if zone_input.thermal_collapse_detected else 0.0
    breakdown["thermal_collapse"] = thermal_collapse_pts

    heat_stress_pts = WEIGHTS["heat_stress"] if zone_input.heat_stress_detected else 0.0
    breakdown["heat_stress"] = heat_stress_pts

    push_wave_pts = WEIGHTS["push_wave"] if zone_input.push_wave_detected else 0.0
    breakdown["push_wave"] = push_wave_pts

    history_pts = (zone_input.organizer_history_baseline_0_100 / 100.0) * WEIGHTS["organizer_history_baseline"]
    breakdown["organizer_history_baseline"] = round(history_pts, 1)

    raw_total = sum(breakdown.values())

    # --- SEVERE DENSITY OVERRIDE: extreme density is unambiguous evidence
    # on its own, unlike moderate density which needs corroboration ---
    density_ratio = (
        zone_input.density_people_per_m2 / zone_input.safe_density_threshold_people_per_m2
        if zone_input.safe_density_threshold_people_per_m2 > 0 else 0
    )
    is_severe_density = density_ratio >= DENSITY_SEVERE_OVERRIDE_RATIO

    # --- CROSS-VALIDATION: the brief's key false-positive filter ---
    # Density/flow risk alone (no physical corroboration) is HELD DOWN,
    # even if the raw weighted sum would otherwise cross a tier boundary.
    # Severe density (see override above) counts AS corroboration on its
    # own -- it doesn't need a push-wave to be believed.
    has_physical_corroboration = (
        zone_input.thermal_collapse_detected or zone_input.push_wave_detected or is_severe_density
    )
    cross_validation_note = "Physical signal corroboration present (thermal collapse and/or push-wave)."

    capped_total = raw_total
    if not has_physical_corroboration:
        # Cap at just below Tier 2 -- vision/flow signals alone can raise
        # concern (Tier 1) but cannot, by themselves, trigger a Red/Active
        # escalation. This is the literal implementation of: "Vision alone
        # flags risk with no physical push-wave -> held at lower tier."
        capped_total = min(raw_total, TIER_2_THRESHOLD - 0.1)
        if raw_total > capped_total:
            cross_validation_note = (
                f"No physical signal (thermal/push-wave) corroborates the vision-only "
                f"risk reading -- capped at Tier 1 ceiling ({TIER_2_THRESHOLD - 0.1:.1f}) "
                f"to filter likely false positive (e.g. excited/cheering crowd) rather than "
                f"escalating on density/flow alone."
            )
        else:
            cross_validation_note = "No physical corroboration present, but raw score was already below the Tier 1 ceiling."

    final_score = round(min(100.0, capped_total), 1)

    if is_severe_density:
        final_score = max(final_score, SEVERE_DENSITY_SCORE_FLOOR)
        cross_validation_note = (
            f"Density ({zone_input.density_people_per_m2:.1f} people/m^2) is "
            f"{density_ratio:.1f}x the dynamic safe threshold -- beyond the "
            f"{DENSITY_SEVERE_OVERRIDE_RATIO}x severe-override point. This exceeds even the "
            f"densest crowd crushes on record; treated as unambiguous evidence on its own, "
            f"overriding the cross-validation cap and forcing Tier 3 regardless of other signals "
            f"(false negatives are worse than false positives in a safety system)."
        )

    if final_score >= TIER_3_THRESHOLD:
        tier = "Tier 3 - Active"
    elif final_score >= TIER_2_THRESHOLD:
        tier = "Tier 2 - Red"
    elif final_score >= TIER_1_THRESHOLD:
        tier = "Tier 1 - Yellow"
    else:
        tier = "Green"

    return ZoneRiskResult(
        zone_id=zone_input.zone_id,
        composite_risk_score_0_100=final_score,
        tier=tier,
        explainability_breakdown=breakdown,
        cross_validation_note=cross_validation_note,
    )


def fuse_all_zones(zone_inputs: list[ZoneFusionInput]) -> list[ZoneRiskResult]:
    return [fuse_zone_signals(z) for z in zone_inputs]
