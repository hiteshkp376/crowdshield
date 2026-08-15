"""
intensity_score.py — Module C: Predicted Crowd Intensity Score and
dynamic risk threshold recalibration.

Two distinct outputs, both described in the master brief:

1. PREDICTED CROWD INTENSITY SCORE -- a pre-event composite of organizer
   history + weather severity + event type, used to pre-configure the
   event's safety protocol (tighter density red-lines, more medical
   stations, etc.) before a single camera goes live.

2. DYNAMIC THRESHOLD RECALIBRATION -- the "safe density" red-line is not
   fixed; it tightens under heat stress, long wait times, and low
   water-point coverage. This directly feeds Module D's live fusion
   scoring and is what would have caught Karur: 6+ hour wait + extreme
   heat + fainting, before density even looked visually extreme.

ETHICAL FRAMING (state explicitly, per brief Section 3): this predicts
PROTOCOL STRINGENCY based on event-type/organizer-level public history.
It does not predict or profile individual attendee behavior. Treat all
outputs here as probabilistic guidance, not deterministic prediction.
"""

from dataclasses import dataclass

EVENT_TYPE_BASE_RISK = {
    # Relative baseline risk multipliers by event type -- political rallies
    # and religious festivals have documented higher crowd-dynamics risk
    # than e.g. ticketed seated concerts (per brief Section 3's stated
    # event-type differentiation).
    "political_rally": 1.3,
    "religious_festival": 1.25,
    "concert": 1.0,
    "sports_event": 1.05,
    "other": 1.1,
}

# Fruin's LOS "planning ceiling" density Module A uses at baseline (area/person)
BASE_SAFE_AREA_PER_PERSON_M2 = 0.9


@dataclass
class IntensityScoreResult:
    score_0_100: float
    risk_tier: str
    contributing_factors: dict
    recommended_protocol_adjustments: list[str]


def compute_predicted_intensity_score(
    organizer_risk_prior: dict,
    heat_index_c: float,
    event_type: str,
) -> IntensityScoreResult:
    """
    Composite score combining:
      (a) organizer/venue turnout-vs-permit and incident history
      (b) forecast weather severity (heat index)
      (c) event type baseline risk

    Returns a 0-100 score (higher = more stringent protocol needed) plus
    concrete recommended adjustments -- this is what "pre-configures the
    event's safety protocol before any camera goes live" per the brief.
    """
    # --- (a) Organizer history component (0-40 points) ---
    history_score = 0.0
    if organizer_risk_prior.get("events_on_record", 0) == 0:
        history_score = 20.0  # unknown risk -- treated as moderate, NOT low
    else:
        ratio = organizer_risk_prior.get("avg_turnout_permit_ratio") or 1.0
        incident_rate = organizer_risk_prior.get("incident_rate") or 0.0
        # ratio of 1.0 (turnout matches permit) -> 0 points; ratio of 2.7
        # (Karur-scale mismatch) -> near max points
        ratio_score = min(25.0, max(0.0, (ratio - 1.0) * 15))
        incident_score = incident_rate * 15.0
        history_score = ratio_score + incident_score

    # --- (b) Weather severity component (0-35 points) ---
    if heat_index_c < 27:
        weather_score = 0.0
    elif heat_index_c < 32:
        weather_score = 8.0
    elif heat_index_c < 41:
        weather_score = 18.0
    elif heat_index_c < 54:
        weather_score = 28.0
    else:
        weather_score = 35.0

    # --- (c) Event type component (0-25 points, scaled from multiplier) ---
    multiplier = EVENT_TYPE_BASE_RISK.get(event_type, EVENT_TYPE_BASE_RISK["other"])
    event_type_score = (multiplier - 1.0) / 0.3 * 25.0
    event_type_score = max(0.0, min(25.0, event_type_score))

    total = round(min(100.0, history_score + weather_score + event_type_score), 1)

    if total >= 70:
        risk_tier = "Critical"
    elif total >= 45:
        risk_tier = "High"
    elif total >= 20:
        risk_tier = "Moderate"
    else:
        risk_tier = "Low"

    adjustments = []
    if history_score >= 20:
        adjustments.append("Organizer history shows significant turnout-vs-permit "
                            "mismatch and/or incident history -- apply stricter "
                            "density thresholds from event start, do not wait for "
                            "live signals to escalate.")
    if weather_score >= 18:
        adjustments.append("High forecast heat index -- add mandatory water "
                            "spacing along VIP approach, earlier steward call "
                            "time, additional medical stations.")
    if "rush_to_vehicle" in organizer_risk_prior.get("common_behavioral_flags", []):
        adjustments.append("Organizer history includes rush-to-vehicle pattern -- "
                            "apply maximum VIP corridor baseline risk weighting "
                            "and serpentine barricading regardless of measured density.")
    if not adjustments:
        adjustments.append("No elevated risk factors identified -- standard "
                            "protocol thresholds apply.")

    return IntensityScoreResult(
        score_0_100=total,
        risk_tier=risk_tier,
        contributing_factors={
            "organizer_history_points": round(history_score, 1),
            "weather_severity_points": round(weather_score, 1),
            "event_type_points": round(event_type_score, 1),
        },
        recommended_protocol_adjustments=adjustments,
    )


def dynamic_threshold_recalibration(
    heat_index_c: float,
    avg_wait_time_min: float,
    water_coverage_score_0_1: float,
    base_safe_area_per_person_m2: float = BASE_SAFE_AREA_PER_PERSON_M2,
) -> dict:
    """
    Tightens the "safe density" red-line under heat stress, long wait
    times, and low water-point coverage -- this is the specific mechanism
    the brief says "would have caught Karur: 6+ hour wait + extreme heat
    + fainting, before density even looked visually extreme."

    Returns an ADJUSTED safe-area-per-person figure (larger = more
    conservative/safer threshold) for Module A/D to apply instead of the
    flat baseline.

    All three inputs push the threshold the same direction (tighter under
    stress) using simple, explainable multipliers -- not a black box.
    """
    heat_multiplier = 1.0
    if heat_index_c >= 54:
        heat_multiplier = 1.6
    elif heat_index_c >= 41:
        heat_multiplier = 1.35
    elif heat_index_c >= 32:
        heat_multiplier = 1.15

    wait_multiplier = 1.0
    if avg_wait_time_min >= 360:      # 6+ hours, matches Karur
        wait_multiplier = 1.5
    elif avg_wait_time_min >= 120:
        wait_multiplier = 1.25
    elif avg_wait_time_min >= 60:
        wait_multiplier = 1.1

    water_multiplier = 1.0
    if water_coverage_score_0_1 < 0.3:
        water_multiplier = 1.3
    elif water_coverage_score_0_1 < 0.6:
        water_multiplier = 1.15

    combined_multiplier = heat_multiplier * wait_multiplier * water_multiplier
    adjusted_area_per_person = round(base_safe_area_per_person_m2 * combined_multiplier, 3)

    return {
        "base_safe_area_per_person_m2": base_safe_area_per_person_m2,
        "adjusted_safe_area_per_person_m2": adjusted_area_per_person,
        "combined_tightening_multiplier": round(combined_multiplier, 3),
        "factors": {
            "heat_multiplier": heat_multiplier,
            "wait_time_multiplier": wait_multiplier,
            "water_coverage_multiplier": water_multiplier,
        },
        "explanation": (
            f"Baseline safe density ({base_safe_area_per_person_m2} m^2/person) "
            f"tightened by {round((combined_multiplier - 1) * 100)}% due to "
            f"heat index {heat_index_c}C, {avg_wait_time_min}min average wait, "
            f"and water coverage score {water_coverage_score_0_1}."
        ),
    }
