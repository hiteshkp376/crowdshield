import React, { useEffect, useRef, useState } from "react";

function polygonPoints(contourPx) {
  return contourPx.map(([x, y]) => `${x},${y}`).join(" ");
}

export default function SimulationPlayback({ blueprintOutput, f1Result }) {
  const [frameIdx, setFrameIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const intervalRef = useRef(null);

  const frames = f1Result?.frames || [];
  const frame = frames[frameIdx];

  useEffect(() => {
    if (playing && frames.length > 0) {
      intervalRef.current = setInterval(() => {
        setFrameIdx((i) => (i + 1 >= frames.length ? 0 : i + 1));
      }, 150);
    }
    return () => clearInterval(intervalRef.current);
  }, [playing, frames.length]);

  useEffect(() => {
    // Reset playback whenever a new simulation result arrives
    setFrameIdx(0);
    setPlaying(false);
  }, [f1Result]);

  if (!blueprintOutput || !f1Result) {
    return (
      <div className="map-empty">
        <div className="map-empty-inner">
          <div className="map-empty-icon">▶</div>
          <div>No simulation loaded</div>
          <div className="map-empty-sub">Run "RUN FULL ANALYSIS" to generate playback frames</div>
        </div>
      </div>
    );
  }

  const w = blueprintOutput.image_width_px;
  const h = blueprintOutput.image_height_px;

  return (
    <div className="playback-wrap">
      <svg viewBox={`0 0 ${w} ${h}`} className="digital-twin-svg" preserveAspectRatio="xMidYMid meet">
        {blueprintOutput.zones.map((zone) => (
          <polygon
            key={zone.zone_id}
            points={polygonPoints(zone.contour_px)}
            fill="none"
            stroke="var(--bp-line-bright)"
            strokeWidth="2"
          />
        ))}

        {frame?.positions_px.map(([x, y], i) => {
          const stress = frame.stress[i];
          const r = Math.round(255 * stress);
          const g = Math.round(220 * (1 - stress));
          return <circle key={i} cx={x} cy={y} r={stress > 0.6 ? 6 : 4.5} fill={`rgb(${r},${g},40)`} />;
        })}
      </svg>

      <div className="playback-controls">
        <button className="btn-secondary playback-btn" onClick={() => setPlaying((p) => !p)}>
          {playing ? "⏸ PAUSE" : "▶ PLAY"}
        </button>
        <input
          type="range"
          min="0"
          max={frames.length - 1}
          value={frameIdx}
          onChange={(e) => {
            setPlaying(false);
            setFrameIdx(+e.target.value);
          }}
          className="field-slider playback-scrub"
        />
        <span className="playback-readout">
          t={frame?.t_s ?? 0}s · panicked {((frame?.panicked_fraction ?? 0) * 100).toFixed(1)}%
        </span>
      </div>

      <div className="playback-meta">
        {f1Result.n_agents_simulated} agents (×{f1Result.people_per_agent} people each) ·{" "}
        panic zones: {f1Result.predicted_panic_zones.join(", ") || "none"}
      </div>
    </div>
  );
}
