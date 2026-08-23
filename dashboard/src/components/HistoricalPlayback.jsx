import React, { useEffect, useMemo, useRef, useState } from "react";
import * as api from "../api.js";

const TIER_COLOR = {
  Green: "var(--tier-green)",
  "Tier 1 - Yellow": "var(--tier-yellow)",
  "Tier 2 - Red": "var(--tier-red)",
  "Tier 3 - Active": "var(--tier-active)",
};

function polygonPoints(contourPx) {
  return contourPx.map(([x, y]) => `${x},${y}`).join(" ");
}

function centroidOf(contourPx) {
  const n = contourPx.length;
  const sx = contourPx.reduce((s, p) => s + p[0], 0) / n;
  const sy = contourPx.reduce((s, p) => s + p[1], 0) / n;
  return [sx, sy];
}

/**
 * For a given zone's ordered history and a target time, finds the most
 * recent reading AT OR BEFORE that time -- this is the correct way to
 * reconstruct "what was this zone's tier at time T": state holds
 * constant from one reading until the next, it doesn't interpolate
 * between scores (a risk tier is a step function over time, not a
 * continuous curve).
 */
function stateAtTime(zoneHistory, targetTimeMs) {
  let result = null;
  for (const entry of zoneHistory) {
    if (new Date(entry.timestamp).getTime() <= targetTimeMs) {
      result = entry;
    } else {
      break;
    }
  }
  return result;
}

export default function HistoricalPlayback({ blueprintOutput }) {
  const [history, setHistory] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [scrubMs, setScrubMs] = useState(0);
  const [playing, setPlaying] = useState(false);
  const intervalRef = useRef(null);

  async function loadHistory() {
    setLoading(true);
    try {
      const [h, e] = await Promise.all([api.getFusionHistory(), api.getAllEvents()]);
      setHistory(h.zones);
      setEvents(e.events);
    } catch (err) {
      console.error("Failed to load history:", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadHistory();
  }, []);

  const { minTime, maxTime, hasData } = useMemo(() => {
    if (!history) return { minTime: 0, maxTime: 0, hasData: false };
    let min = Infinity, max = -Infinity;
    Object.values(history).forEach((entries) => {
      entries.forEach((e) => {
        const t = new Date(e.timestamp).getTime();
        min = Math.min(min, t);
        max = Math.max(max, t);
      });
    });
    if (!isFinite(min)) return { minTime: 0, maxTime: 0, hasData: false };
    return { minTime: min, maxTime: max, hasData: true };
  }, [history]);

  useEffect(() => {
    if (hasData) setScrubMs(minTime);
  }, [hasData, minTime]);

  useEffect(() => {
    if (playing && hasData) {
      const totalRange = maxTime - minTime || 1;
      const stepMs = Math.max(totalRange / 200, 50); // ~200 steps across the full range
      intervalRef.current = setInterval(() => {
        setScrubMs((t) => {
          const next = t + stepMs;
          return next > maxTime ? minTime : next;
        });
      }, 80);
    }
    return () => clearInterval(intervalRef.current);
  }, [playing, hasData, minTime, maxTime]);

  if (loading) {
    return (
      <div className="map-empty">
        <div className="map-empty-inner">Loading history…</div>
      </div>
    );
  }

  if (!blueprintOutput) {
    return (
      <div className="map-empty">
        <div className="map-empty-inner">
          <div className="map-empty-icon">▤</div>
          <div>No venue loaded</div>
          <div className="map-empty-sub">Run "RUN FULL ANALYSIS" first, then feed some live signals to build history</div>
        </div>
      </div>
    );
  }

  if (!hasData) {
    return (
      <div className="map-empty">
        <div className="map-empty-inner">
          <div className="map-empty-icon">▤</div>
          <div>No history recorded yet</div>
          <div className="map-empty-sub">Feed live signals via the Signal Injector to build a timeline, then come back here</div>
          <button className="btn-secondary" style={{ marginTop: 10, width: "auto", padding: "6px 14px" }} onClick={loadHistory}>
            REFRESH
          </button>
        </div>
      </div>
    );
  }

  const w = blueprintOutput.image_width_px;
  const h = blueprintOutput.image_height_px;
  const totalRange = maxTime - minTime || 1;

  return (
    <div className="playback-wrap">
      <svg viewBox={`0 0 ${w} ${h}`} className="digital-twin-svg" preserveAspectRatio="xMidYMid meet">
        {blueprintOutput.zones.map((zone) => {
          const zoneHistory = history[zone.zone_id] || [];
          const state = stateAtTime(zoneHistory, scrubMs);
          const tier = state?.tier || "Green";
          const [cx, cy] = centroidOf(zone.contour_px);
          return (
            <g key={zone.zone_id}>
              <polygon
                points={polygonPoints(zone.contour_px)}
                fill={TIER_COLOR[tier]}
                fillOpacity="0.25"
                stroke={TIER_COLOR[tier]}
                strokeWidth="2"
              />
              <text x={cx} y={cy - 6} textAnchor="middle" className="zone-label" fill="var(--text-primary)">
                {zone.zone_id}
              </text>
              <text x={cx} y={cy + 12} textAnchor="middle" className="zone-sublabel" fill="var(--text-secondary)">
                {state ? state.composite_risk_score.toFixed(0) : "no data yet"}
              </text>
            </g>
          );
        })}
      </svg>

      <div className="playback-controls">
        <button className="btn-secondary playback-btn" onClick={() => setPlaying((p) => !p)}>
          {playing ? "⏸ PAUSE" : "▶ PLAY"}
        </button>
        <div className="timeline-track">
          <input
            type="range"
            min={minTime}
            max={maxTime}
            value={scrubMs}
            onChange={(e) => {
              setPlaying(false);
              setScrubMs(+e.target.value);
            }}
            className="field-slider playback-scrub"
          />
          {events.map((ev) => {
            const t = new Date(ev.created_at).getTime();
            const pct = ((t - minTime) / totalRange) * 100;
            if (pct < 0 || pct > 100) return null;
            return (
              <div
                key={ev.event_id}
                className="timeline-marker"
                style={{ left: `${pct}%` }}
                title={`${ev.event_id}: ${ev.zone_id} → ${ev.tier}`}
              />
            );
          })}
        </div>
        <span className="playback-readout">
          {new Date(scrubMs).toLocaleTimeString()}
        </span>
      </div>

      <div className="playback-meta">
        {Object.keys(history).length} zones with recorded history · {events.length} escalation events (tick marks on timeline) ·{" "}
        <button className="link-btn" onClick={loadHistory}>refresh</button>
      </div>
    </div>
  );
}
