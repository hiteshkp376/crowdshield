"""
escalation_state_machine.py — Module E: Tiered Escalation & Human-Confirmed
Response.

Implements the three-tier escalation logic from the master brief:

  Tier 1 (Green->Yellow): auto-fires immediately, no human confirmation
    needed -- steward alert, mobile app reroute push, suggested PA
    announcement. Low-stakes, reversible, time-sensitive.

  Tier 2 (Yellow->Red): simultaneous police + command center escalation,
    ambulance pre-dispatch trigger, PA override, live feed + risk metrics
    attached. REQUIRES human confirmation before real-world dispatch.

  Tier 3 (Active incident): emergency services API trigger (India's 112)
    with GPS, auto-lockdown signal to nearby gates, real-time headcount-
    in-danger-zone estimate to responders, continuous logging begins.
    REQUIRES human confirmation before real-world dispatch.

HUMAN-CONFIRMATION GATE (brief's explicit safeguard): Tier 2/3 alerts are
created in a PENDING state -- nothing is actually "dispatched" (in this
software's terms: nothing is marked as sent to police/ambulance/112)
until a human operator calls confirm_dispatch(). This is both a technical
safeguard against false-positive auto-triggering and a stated ethical/
liability position, per the brief.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Tier(str, Enum):
    GREEN = "Green"
    TIER_1 = "Tier 1 - Yellow"
    TIER_2 = "Tier 2 - Red"
    TIER_3 = "Tier 3 - Active"


class DispatchStatus(str, Enum):
    NOT_APPLICABLE = "not_applicable"   # Tier 1 / Green -- no dispatch gate needed
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED_DISPATCHED = "confirmed_dispatched"
    REJECTED = "rejected"


@dataclass
class AlertAction:
    action_type: str
    description: str
    requires_human_confirmation: bool


@dataclass
class EscalationEvent:
    event_id: str
    zone_id: str
    tier: Tier
    composite_risk_score: float
    explainability_breakdown: dict
    actions: list[AlertAction]
    dispatch_status: DispatchStatus
    created_at: datetime
    confirmed_at: datetime | None = None
    confirmed_by: str | None = None


TIER_1_ACTIONS = [
    AlertAction("steward_alert", "Alert nearby stewards to monitor and prepare to assist.", False),
    AlertAction("mobile_reroute_push", "Push a reroute suggestion to attendees' mobile app.", False),
    AlertAction("pa_suggestion", "Suggest a calm, non-alarming PA announcement to the operator.", False),
]

TIER_2_ACTIONS = [
    AlertAction("police_escalation", "Escalate simultaneously to police control room.", True),
    AlertAction("command_center_escalation", "Escalate simultaneously to event command center.", True),
    AlertAction("ambulance_predispatch", "Pre-dispatch trigger to nearest positioned ambulance unit.", True),
    AlertAction("pa_override", "Override PA with dispersal instruction.", True),
    AlertAction("attach_live_feed", "Attach live feed + risk metrics to the alert.", False),
]

TIER_3_ACTIONS = [
    AlertAction("emergency_api_trigger", "Trigger emergency services API (India's 112) with GPS-tagged location.", True),
    AlertAction("auto_lockdown_signal", "Send auto-lockdown signal to nearby gates to halt further inflow.", True),
    AlertAction("headcount_estimate", "Send real-time headcount-in-danger-zone estimate to responders.", False),
    AlertAction("continuous_logging_start", "Begin continuous signal-by-signal incident logging.", False),
]


def _actions_for_tier(tier: Tier) -> list[AlertAction]:
    if tier == Tier.TIER_1:
        return TIER_1_ACTIONS
    if tier == Tier.TIER_2:
        return TIER_2_ACTIONS
    if tier == Tier.TIER_3:
        return TIER_3_ACTIONS
    return []


def _tier_from_string(tier_str: str) -> Tier:
    """Module D returns tier strings like 'Tier 2 - Red' -- map directly."""
    for t in Tier:
        if t.value == tier_str:
            return t
    return Tier.GREEN


class EscalationStateMachine:
    """
    Tracks per-zone escalation state over time. Each call to
    process_fusion_result() with Module D's output for a zone determines
    whether a new escalation event should be created (e.g. a zone newly
    crossing into Tier 2 generates a NEW pending-confirmation event; a
    zone remaining at the same tier does not spam duplicate events).
    """

    def __init__(self):
        self._zone_current_tier: dict[str, Tier] = {}
        self._events: list[EscalationEvent] = []
        self._event_counter = 0

    def process_fusion_result(self, zone_id: str, tier_str: str, composite_risk_score: float,
                               explainability_breakdown: dict) -> EscalationEvent | None:
        new_tier = _tier_from_string(tier_str)
        previous_tier = self._zone_current_tier.get(zone_id, Tier.GREEN)
        self._zone_current_tier[zone_id] = new_tier

        # Only generate a new escalation event on tier ESCALATION (not on
        # staying flat or de-escalating) -- avoids alert spam, matches
        # real operational practice.
        tier_order = [Tier.GREEN, Tier.TIER_1, Tier.TIER_2, Tier.TIER_3]
        if tier_order.index(new_tier) <= tier_order.index(previous_tier):
            return None

        self._event_counter += 1
        actions = _actions_for_tier(new_tier)
        needs_confirmation = any(a.requires_human_confirmation for a in actions)

        event = EscalationEvent(
            event_id=f"EVT-{self._event_counter:05d}",
            zone_id=zone_id,
            tier=new_tier,
            composite_risk_score=composite_risk_score,
            explainability_breakdown=explainability_breakdown,
            actions=actions,
            dispatch_status=(
                DispatchStatus.PENDING_CONFIRMATION if needs_confirmation
                else DispatchStatus.NOT_APPLICABLE
            ),
            created_at=datetime.utcnow(),
        )
        self._events.append(event)
        return event

    def confirm_dispatch(self, event_id: str, confirmed_by: str) -> EscalationEvent:
        event = self._find_event(event_id)
        if event.dispatch_status != DispatchStatus.PENDING_CONFIRMATION:
            raise ValueError(
                f"Event {event_id} is not pending confirmation "
                f"(current status: {event.dispatch_status.value})."
            )
        event.dispatch_status = DispatchStatus.CONFIRMED_DISPATCHED
        event.confirmed_at = datetime.utcnow()
        event.confirmed_by = confirmed_by
        return event

    def reject_dispatch(self, event_id: str, rejected_by: str) -> EscalationEvent:
        event = self._find_event(event_id)
        if event.dispatch_status != DispatchStatus.PENDING_CONFIRMATION:
            raise ValueError(
                f"Event {event_id} is not pending confirmation "
                f"(current status: {event.dispatch_status.value})."
            )
        event.dispatch_status = DispatchStatus.REJECTED
        event.confirmed_at = datetime.utcnow()
        event.confirmed_by = rejected_by
        return event

    def _find_event(self, event_id: str) -> EscalationEvent:
        for e in self._events:
            if e.event_id == event_id:
                return e
        raise ValueError(f"No escalation event found with id {event_id}")

    def get_pending_events(self) -> list[EscalationEvent]:
        return [e for e in self._events if e.dispatch_status == DispatchStatus.PENDING_CONFIRMATION]

    def get_all_events(self) -> list[EscalationEvent]:
        return list(self._events)

    def get_current_zone_tier(self, zone_id: str) -> Tier:
        return self._zone_current_tier.get(zone_id, Tier.GREEN)
