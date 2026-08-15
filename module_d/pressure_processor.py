"""
pressure_processor.py — Module D: physical pressure network signal
(push-wave propagation detection).

Detects the specific mechanical signature the brief calls out as the
"physical signature of crowd turbulence" -- a pressure spike traveling
directionally across sequential barricade/ground sensors (A -> B -> C
within a short time window), distinct from ordinary excited movement.

HONESTY NOTE: real barricade load-cell/pressure-mat hardware isn't
available for the hackathon (per brief Section 5). This module's
detection ALGORITHM is genuine signal-processing logic operating on a
sequence of {sensor_id, position, timestamp, reading} records -- it
doesn't care whether those readings came from real HX711/load-cell
hardware or a mocked JSON feed, which is exactly the brief's stated
design ("sensor ingestion: MQTT -> Kafka or REST endpoint"). Swapping
in real hardware later requires no change to this detection logic.
"""

from dataclasses import dataclass

PRESSURE_SPIKE_THRESHOLD_KG = 40.0     # reading above baseline considered a "spike"
PUSH_WAVE_MAX_PROPAGATION_DELAY_S = 3.0  # spike must reach the next sensor within this window
PUSH_WAVE_MIN_SENSORS_INVOLVED = 3       # need A->B->C, not just A->B, to call it a wave


@dataclass
class SensorReading:
    sensor_id: str
    position_m: tuple[float, float]   # physical location along the barricade line
    timestamp_s: float
    reading_kg: float


@dataclass
class PushWaveSignal:
    push_wave_detected: bool
    involved_sensor_ids: list[str]
    propagation_direction: str | None   # e.g. "toward stage" -- derived from sensor position order
    peak_reading_kg: float
    note: str


def detect_push_wave(readings: list[SensorReading],
                      spike_threshold_kg: float = PRESSURE_SPIKE_THRESHOLD_KG,
                      max_delay_s: float = PUSH_WAVE_MAX_PROPAGATION_DELAY_S) -> PushWaveSignal:
    """
    Algorithm:
      1. Find all readings that spike above threshold.
      2. Sort spikes by sensor's physical position along the line.
      3. Check if spikes occur in a monotonically increasing time order
         matching that spatial order, each within max_delay_s of the
         previous -- i.e. the spike genuinely TRAVELS from one sensor to
         the next, rather than several sensors spiking independently/
         simultaneously (which would just mean "everyone is pushing",
         not a coherent wave).
    """
    spikes = [r for r in readings if r.reading_kg >= spike_threshold_kg]

    if len(spikes) < PUSH_WAVE_MIN_SENSORS_INVOLVED:
        return PushWaveSignal(
            push_wave_detected=False, involved_sensor_ids=[], propagation_direction=None,
            peak_reading_kg=max((r.reading_kg for r in readings), default=0.0),
            note=f"Only {len(spikes)} sensor(s) spiked -- below the "
                 f"{PUSH_WAVE_MIN_SENSORS_INVOLVED}-sensor minimum to call this a propagating wave.",
        )

    # Sort by physical position (assume roughly linear barricade run --
    # use x-coordinate as position-along-line for simplicity).
    spikes_by_position = sorted(spikes, key=lambda r: r.position_m[0])

    propagating_chain = [spikes_by_position[0]]
    for reading in spikes_by_position[1:]:
        prev = propagating_chain[-1]
        delay = reading.timestamp_s - prev.timestamp_s
        if 0 <= delay <= max_delay_s:
            propagating_chain.append(reading)
        else:
            # Chain broken -- check if a fresh chain starting here could
            # still be long enough; for simplicity, only track the
            # longest contiguous chain found.
            if len(propagating_chain) < PUSH_WAVE_MIN_SENSORS_INVOLVED:
                propagating_chain = [reading]

    detected = len(propagating_chain) >= PUSH_WAVE_MIN_SENSORS_INVOLVED

    direction = None
    if detected:
        start_pos = propagating_chain[0].position_m[0]
        end_pos = propagating_chain[-1].position_m[0]
        direction = "increasing_position" if end_pos > start_pos else "decreasing_position"

    peak = max((r.reading_kg for r in readings), default=0.0)

    note = (
        f"Push-wave detected across {len(propagating_chain)} sensors, "
        f"propagating in {direction} direction over "
        f"{propagating_chain[-1].timestamp_s - propagating_chain[0].timestamp_s:.1f}s."
        if detected else
        f"{len(spikes)} sensor(s) spiked but did not form a coherent directional "
        f"chain within {max_delay_s}s of each other -- likely simultaneous "
        f"excitement (e.g. cheering) rather than a propagating crush wave."
    )

    return PushWaveSignal(
        push_wave_detected=detected,
        involved_sensor_ids=[r.sensor_id for r in propagating_chain] if detected else [],
        propagation_direction=direction,
        peak_reading_kg=round(peak, 1),
        note=note,
    )
