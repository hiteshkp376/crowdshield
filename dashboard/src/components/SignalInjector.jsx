import React, { useState, useEffect } from "react";

/**
 * Computes a real, data-derived starting density for a zone instead of
 * an arbitrary fixed default. Prefers Module F1's actual simulated peak
 * density for this zone (real agent-based simulation result); falls
 * back to Module A's proportional-area occupancy estimate if F1 hasn't
 * run. Either way, this is REAL computed data, not a guess -- and it
 * changes correctly per zone and per turnout, fixing the bug where
 * every zone showed the same score regardless of size or headcount.
 *
 * CAPPED at a physically realistic maximum: F1's super-agent simulation
 * can occasionally report instantaneous peak densities beyond any real
 * crowd crush (the deadliest documented crushes top out around 8-10
 * people/m^2 -- human bodies can't compress further). This is a known
 * approximation limit of representing thousands of people with ~250
 * simulated agents (see Module F1's README). Rather than feed an
 * unrealistic number into the live fusion engine, the suggestion is
 * capped here and the raw simulated value is shown for transparency.
 */
const REALISTIC_MAX_DENSITY_PEOPLE_PER_M2 = 10.0;

function computeSuggestedDensity(zoneId, blueprintOutput, f1Result) {
  if (f1Result?.zone_peak_density_people_per_m2?.[zoneId] !== undefined) {
    const raw = f1Result.zone_peak_density_people_per_m2[zoneId];
    if (raw > REALISTIC_MAX_DENSITY_PEOPLE_PER_M2) {
      return {
        value: REALISTIC_MAX_DENSITY_PEOPLE_PER_M2,
        source: `capped at ${REALISTIC_MAX_DENSITY_PEOPLE_PER_M2}/m² (raw F1 peak was ${raw.toFixed(1)}/m² -- beyond any real crowd crush, a known super-agent approximation limit)`,
      };
    }
    return { value: raw, source: "F1 simulated peak density" };
  }
  const zone = blueprintOutput?.zones.find((z) => z.zone_id === zoneId);
  if (zone?.expected_occupancy && zone.area_m2 > 0) {
    return {
      value: Math.min(zone.expected_occupancy / zone.area_m2, REALISTIC_MAX_DENSITY_PEOPLE_PER_M2),
      source: "Module A proportional estimate",
    };
  }
  return { value: 0, source: "no data available -- set manually" };
}

function computeSuggestedConvergence(zoneId, f1Result) {
  if (!f1Result) return { value: 0.3, source: "no F1 data -- default" };
  if (f1Result.predicted_panic_zones?.includes(zoneId)) {
    return { value: 0.8, source: "F1 flagged this as a panic zone" };
  }
  if (f1Result.predicted_high_density_zones?.includes(zoneId)) {
    return { value: 0.55, source: "F1 flagged this as high-density" };
  }
  return { value: 0.25, source: "F1 ran, zone not flagged as elevated risk" };
}

export default function SignalInjector({
  selectedZoneId,
  blueprintOutput,
  f1Result,
  recalThreshold,
  organizerScore,
  onInject,
  injecting,
}) {
  const [density, setDensity] = useState(0);
  const [densitySource, setDensitySource] = useState("");
  const [flowConvergence, setFlowConvergence] = useState(0.3);
  const [convergenceSource, setConvergenceSource] = useState("");
  const [reverseFlow, setReverseFlow] = useState(false);
  const [routeBlockage, setRouteBlockage] = useState(false);
  const [thermalCollapse, setThermalCollapse] = useState(false);
  const [heatStress, setHeatStress] = useState(false);
  const [pushWave, setPushWave] = useState(false);

  // Re-seed every field from real data whenever the selected zone changes
  // (or new pipeline data arrives) -- this is the actual fix: previously
  // these values never reset, so every zone showed identical numbers.
  useEffect(() => {
    if (!selectedZoneId) return;
    const d = computeSuggestedDensity(selectedZoneId, blueprintOutput, f1Result);
    const c = computeSuggestedConvergence(selectedZoneId, f1Result);
    setDensity(Number(d.value.toFixed(2)));
    setDensitySource(d.source);
    setFlowConvergence(Number(c.value.toFixed(2)));
    setConvergenceSource(c.source);
    setReverseFlow(false);
    setRouteBlockage(false);
    setThermalCollapse(false);
    setHeatStress(false);
    setPushWave(false);
  }, [selectedZoneId, blueprintOutput, f1Result]);

  if (!selectedZoneId) {
    return (
      <div className="panel">
        <div className="panel-header">
          <span className="panel-eyebrow">03</span> LIVE SIGNAL INJECTOR
        </div>
        <div className="panel-empty-note">Select a zone to feed a live sensor reading into Module D.</div>
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-eyebrow">03</span> LIVE SIGNAL — {selectedZoneId}
      </div>
      <div className="panel-empty-note" style={{ marginBottom: 10 }}>
        Density and convergence below are seeded from real computed data for
        this zone (see the source note under each), not arbitrary defaults —
        adjust them to test hypothetical scenarios.
      </div>

      <label className="field-label">Density (people/m²): {density.toFixed(2)}</label>
      <input type="range" min="0" max="15" step="0.1" value={density} onChange={(e) => setDensity(+e.target.value)} className="field-slider" />
      <div className="field-source-note">source: {densitySource}</div>

      <label className="field-label">Flow convergence: {flowConvergence.toFixed(2)}</label>
      <input type="range" min="0" max="1" step="0.01" value={flowConvergence} onChange={(e) => setFlowConvergence(+e.target.value)} className="field-slider" />
      <div className="field-source-note">source: {convergenceSource}</div>

      <div className="toggle-grid">
        <Toggle label="🔄 Reverse flow" checked={reverseFlow} onChange={setReverseFlow} />
        <Toggle label="🚧 Route blockage" checked={routeBlockage} onChange={setRouteBlockage} />
        <Toggle label="🚨 Thermal collapse" checked={thermalCollapse} onChange={setThermalCollapse} />
        <Toggle label="🔥 Heat stress" checked={heatStress} onChange={setHeatStress} />
        <Toggle label="⚠️ Push-wave detected" checked={pushWave} onChange={setPushWave} highlight />
      </div>

      {recalThreshold && (
        <div className="threshold-note">
          Dynamic threshold (Module C): {recalThreshold.toFixed(2)} people/m² safe limit
        </div>
      )}

      <button
        className="btn-primary"
        disabled={injecting}
        onClick={() =>
          onInject(
            selectedZoneId,
            {
              zone_id: selectedZoneId,
              density_people_per_m2: density,
              safe_density_threshold_people_per_m2: recalThreshold || 4.0,
              flow_convergence_score_0_1: flowConvergence,
              reverse_flow_detected: reverseFlow,
              route_blockage_detected: routeBlockage,
              thermal_collapse_detected: thermalCollapse,
              heat_stress_detected: heatStress,
              push_wave_detected: pushWave,
              organizer_history_baseline_0_100: organizerScore || 0,
            },
            { reverseFlow, routeBlockage, thermalCollapse, heatStress, pushWave }
          )
        }
      >
        {injecting ? "PROCESSING…" : "FEED TO FUSION ENGINE →"}
      </button>
    </div>
  );
}

function Toggle({ label, checked, onChange, highlight }) {
  return (
    <button
      className={`toggle ${checked ? "toggle-on" : ""} ${checked && highlight ? "toggle-highlight" : ""}`}
      onClick={() => onChange(!checked)}
      type="button"
    >
      <span className="toggle-box" />
      {label}
    </button>
  );
}
