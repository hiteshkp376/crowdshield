import React, { useEffect, useRef, useState } from "react";
import * as api from "../api.js";

function slope(values) {
  const n = values.length;
  if (n < 2) return 0;
  const xMean = (n - 1) / 2;
  const yMean = values.reduce((a, b) => a + b, 0) / n;
  let num = 0, den = 0;
  for (let i = 0; i < n; i++) {
    num += (i - xMean) * (values[i] - yMean);
    den += (i - xMean) ** 2;
  }
  return den === 0 ? 0 : num / den;
}

const MAX_GRAPH_POINTS = 90; // ~90 seconds of history at 1s polling

export default function PredictionPanel({ selectedZoneId, blueprintOutput }) {
  const [history, setHistory] = useState([]); // [{t, probability}]
  const [latest, setLatest] = useState(null);
  const [error, setError] = useState(null);
  const intervalRef = useRef(null);

  useEffect(() => {
    setHistory([]);
    setLatest(null);
    setError(null);
  }, [selectedZoneId]);

  useEffect(() => {
    if (!selectedZoneId || !blueprintOutput) return;

    const zone = blueprintOutput.zones.find((z) => z.zone_id === selectedZoneId);
    if (!zone) return;

    const tick = async () => {
      try {
        const raw = await api.getFusionHistoryRaw(2); // last 2 minutes
        const readings = (raw.zones[selectedZoneId] || []).filter(
          (r) => r.density_people_per_m2 !== null && r.density_people_per_m2 !== undefined
        );

        if (readings.length < 2) {
          setError("Not enough readings yet for this zone -- feed a few signals first.");
          return;
        }

        const densities = readings.map((r) => r.density_people_per_m2);
        const corroboration = readings.map((r) => (r.physical_corroboration ? 1 : 0));

        const features = {
          early_density_mean: densities.reduce((a, b) => a + b, 0) / densities.length,
          early_density_slope: slope(densities),
          early_density_max: Math.max(...densities),
          early_panic_mean: corroboration.reduce((a, b) => a + b, 0) / corroboration.length,
          early_panic_slope: slope(corroboration),
          zone_area_m2: zone.area_m2,
          is_chokepoint: zone.is_chokepoint,
          is_vip_corridor: zone.is_vip_corridor,
        };

        const prediction = await api.predictDanger(features);
        setLatest(prediction);
        setError(null);
        setHistory((prev) => {
          const next = [...prev, { t: Date.now(), probability: prediction.danger_probability_0_1 }];
          return next.slice(-MAX_GRAPH_POINTS);
        });
      } catch (e) {
        setError(e.message);
      }
    };

    tick();
    intervalRef.current = setInterval(tick, 1000);
    return () => clearInterval(intervalRef.current);
  }, [selectedZoneId, blueprintOutput]);

  if (!selectedZoneId) {
    return (
      <div className="panel">
        <div className="panel-header">
          <span className="panel-eyebrow">07</span> EARLY WARNING PREDICTION
        </div>
        <div className="panel-empty-note">Select a zone to see its live danger prediction.</div>
      </div>
    );
  }

  const riskColor =
    latest?.risk_label === "High" ? "var(--tier-red)" :
    latest?.risk_label === "Moderate" ? "var(--tier-yellow)" : "var(--tier-green)";

  // Build a simple SVG line path from the rolling probability history
  const graphW = 280, graphH = 60;
  const points = history.map((h, i) => {
    const x = (i / Math.max(1, MAX_GRAPH_POINTS - 1)) * graphW;
    const y = graphH - h.probability * graphH;
    return `${x},${y}`;
  }).join(" ");

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-eyebrow">07</span> EARLY WARNING PREDICTION — {selectedZoneId}
      </div>

      <div className="panel-empty-note" style={{ marginBottom: 10 }}>
        Trained on Module F1's own simulation data, not real historical stampede
        records — a simulation-grounded decision aid, not a certified forecast.
        Updates every second from live Module D readings.
      </div>

      {error && <div className="panel-empty-note">{error}</div>}

      {latest && (
        <>
          <div className="explain-score">
            <span style={{ color: riskColor }}>
              {(latest.danger_probability_0_1 * 100).toFixed(0)}%
            </span>
            <span className="explain-tier" style={{ color: riskColor }}>
              {latest.risk_label} risk
            </span>
          </div>

          <svg width={graphW} height={graphH} className="prediction-graph">
            <polyline points={points} fill="none" stroke={riskColor} strokeWidth="2" />
            <line x1="0" y1={graphH * 0.3} x2={graphW} y2={graphH * 0.3}
                  stroke="var(--bp-line)" strokeDasharray="3,3" />
          </svg>
          <div className="playback-meta">{history.length} readings in rolling window</div>
        </>
      )}
    </div>
  );
}
