import React, { useEffect, useState, useCallback } from "react";
import SystemStatusBar from "./components/SystemStatusBar.jsx";
import SetupPanel from "./components/SetupPanel.jsx";
import DigitalTwinMap from "./components/DigitalTwinMap.jsx";
import ZoneRiskPanel from "./components/ZoneRiskPanel.jsx";
import SignalInjector from "./components/SignalInjector.jsx";
import ExplainabilityPanel from "./components/ExplainabilityPanel.jsx";
import PendingEscalations from "./components/PendingEscalations.jsx";
import IncidentLog from "./components/IncidentLog.jsx";
import SimulationPlayback from "./components/SimulationPlayback.jsx";
import HistoricalPlayback from "./components/HistoricalPlayback.jsx";
import PredictionPanel from "./components/PredictionPanel.jsx";
import * as api from "./api.js";

export default function App() {
  const [health, setHealth] = useState({ A: false, F1: false, B: false, C: false, D: false, E: false });
  const [blueprintOutput, setBlueprintOutput] = useState(null);
  const [f1Result, setF1Result] = useState(null);
  const [bResult, setBResult] = useState(null);
  const [organizerScore, setOrganizerScore] = useState(null);
  const [recalThreshold, setRecalThreshold] = useState(null);
  const [zoneTiers, setZoneTiers] = useState({});
  const [selectedZoneId, setSelectedZoneId] = useState(null);
  const [mapView, setMapView] = useState("live"); // "live" | "playback"
  const [pendingEvents, setPendingEvents] = useState([]);
  const [allEvents, setAllEvents] = useState([]);
  const [summary, setSummary] = useState(null);

  const [running, setRunning] = useState(false);
  const [injecting, setInjecting] = useState(false);
  const [processingEvent, setProcessingEvent] = useState(false);
  const [generatingSummary, setGeneratingSummary] = useState(false);
  const [setupLog, setSetupLog] = useState([]);

  useEffect(() => {
    const poll = async () => setHealth(await api.checkAllHealth());
    poll();
    const interval = setInterval(poll, 8000);
    return () => clearInterval(interval);
  }, []);

  const refreshEvents = useCallback(async () => {
    try {
      const pending = await api.getPendingEvents();
      const all = await api.getAllEvents();
      setPendingEvents(pending.pending_events);
      setAllEvents(all.events);
    } catch (e) {
      console.error("Failed to refresh events:", e);
    }
  }, []);

  // Auto-poll Module D's history for the latest reading per zone -- this
  // makes the Digital Twin update live from ANY source pushing to Module
  // D (e.g. live_camera_worker.py), not just this dashboard's own manual
  // Signal Injector. Merges into zoneTiers without clobbering signalFlags
  // set by the injector, since externally-driven updates (camera feed)
  // don't carry those toggle-derived flags.
  useEffect(() => {
    const pollHistory = async () => {
      try {
        const history = await api.getFusionHistory(5); // last 5 minutes
        setZoneTiers((prev) => {
          const next = { ...prev };
          Object.entries(history.zones).forEach(([zoneId, readings]) => {
            if (readings.length === 0) return;
            const latest = readings[readings.length - 1];
            const existing = next[zoneId];
            // Only overwrite if this reading is newer than what we have,
            // so a slow external poll doesn't stomp a just-injected signal.
            const existingIsNewer =
              existing?._lastTimestamp && existing._lastTimestamp >= latest.timestamp;
            if (!existingIsNewer) {
              next[zoneId] = {
                tier: latest.tier,
                score: latest.composite_risk_score,
                breakdown: existing?.breakdown || {},
                crossValidationNote: existing?.crossValidationNote || "",
                signalFlags: existing?.signalFlags,
                _lastTimestamp: latest.timestamp,
              };
            }
          });
          return next;
        });
      } catch (e) {
        // Silent -- this is a background convenience poll, not a
        // user-initiated action; don't spam errors for a transient
        // network hiccup.
      }
    };
    const interval = setInterval(pollHistory, 5000);
    return () => clearInterval(interval);
  }, []);

  async function runPipeline({ file, scale, turnout, organizer, eventType, triggerZone, sensorBudget, stewardBudget }) {
    setRunning(true);
    setSetupLog([]);
    const log = (line) => setSetupLog((prev) => [...prev, line]);

    try {
      log("→ Module A: analyzing blueprint…");
      const a = await api.analyzeBlueprint(file, scale, turnout);
      setBlueprintOutput(a);
      log(`✓ Module A: ${a.total_zones} zones, ${a.total_area_m2}m² total, ${a.readiness_score_pct}% readiness (${a.risk_level})`);

      const areaPerPerson = a.total_area_m2 / turnout;
      const REALISTIC_MIN_AREA_PER_PERSON = 0.15; // denser than worst recorded real crowd crushes
      if (areaPerPerson < REALISTIC_MIN_AREA_PER_PERSON) {
        const proceed = window.confirm(
          `This turnout (${turnout.toLocaleString()}) implies ${areaPerPerson.toFixed(4)} m² per person ` +
          `across the venue's ${a.total_area_m2}m² total area — denser than the worst recorded real crowd ` +
          `crushes (~0.2 m²/person minimum). This is very likely an unrealistic input.\n\n` +
          `Continue anyway, or Cancel to stop and re-check your turnout number?`
        );
        if (!proceed) {
          log(`✗ Stopped — turnout ${turnout.toLocaleString()} is physically implausible for a ` +
              `${a.total_area_m2}m² venue (${areaPerPerson.toFixed(4)} m²/person). Adjust turnout or ` +
              `re-check scale calibration, then re-run.`);
          setRunning(false);
          return;
        }
        log(`⚠ Proceeding despite implausible density (${areaPerPerson.toFixed(4)} m²/person) — user confirmed.`);
      }

      log("→ Module F1: running crowd simulation…");
      const trigger = triggerZone ? { zone_id: triggerZone, at_time_s: 6.0, radius_m: 20.0 } : null;
      const f1 = await api.runSimulation(a, turnout, trigger, 20.0);
      setF1Result(f1);
      log(`✓ Module F1: ${f1.n_agents_simulated} agents, panic zones: ${f1.predicted_panic_zones.join(", ") || "none"}`);

      log("→ Module B: planning sensor & steward placement…");
      const b = await api.planPlacement(a, f1, sensorBudget, stewardBudget);
      setBResult(b);
      log(`✓ Module B: ${b.sensor_positions_px.length} sensors, ${b.sensor_coverage_pct_of_weighted_risk}% coverage`);

      log("→ Module C: computing organizer intensity score…");
      const intensity = await api.getIntensityScore(organizer, eventType, 10.96, 78.08);
      setOrganizerScore(intensity.intensity_score_0_100);
      log(`✓ Module C: intensity score ${intensity.intensity_score_0_100}/100 (${intensity.risk_tier})`);

      const recal = await api.recalibrateThreshold(intensity.weather.heat_index_c, 300, 0.3);
      setRecalThreshold(1.0 / recal.adjusted_safe_area_per_person_m2);
      log(`✓ Module C: threshold tightened ${Math.round((recal.combined_tightening_multiplier - 1) * 100)}%`);

      setSelectedZoneId(a.zones[0]?.zone_id || null);
      log("✓ Pipeline complete — select a zone and feed a live signal below.");
    } catch (e) {
      log(`✗ ${e.message}`);
    } finally {
      setRunning(false);
    }
  }

  async function injectSignal(zoneId, signalInput, signalFlags) {
    setInjecting(true);
    try {
      const fuseResp = await api.fuseSignals([signalInput]);
      const zoneResult = fuseResp.zones[0];

      setZoneTiers((prev) => ({
        ...prev,
        [zoneId]: {
          tier: zoneResult.tier,
          score: zoneResult.composite_risk_score_0_100,
          breakdown: zoneResult.explainability_breakdown,
          crossValidationNote: zoneResult.cross_validation_note,
          signalFlags,
        },
      }));

      await api.processFusionResult(
        zoneId,
        zoneResult.tier,
        zoneResult.composite_risk_score_0_100,
        zoneResult.explainability_breakdown
      );
      await refreshEvents();
    } catch (e) {
      console.error("Signal injection failed:", e);
      alert(`Signal injection failed: ${e.message}`);
    } finally {
      setInjecting(false);
    }
  }

  async function handleConfirm(eventId) {
    setProcessingEvent(true);
    try {
      await api.confirmDispatch(eventId, "dashboard_operator");
      await refreshEvents();
    } finally {
      setProcessingEvent(false);
    }
  }

  async function handleReject(eventId) {
    setProcessingEvent(true);
    try {
      await api.rejectDispatch(eventId, "dashboard_operator");
      await refreshEvents();
    } finally {
      setProcessingEvent(false);
    }
  }

  async function handleGenerateSummary() {
    setGeneratingSummary(true);
    try {
      setSummary(await api.getIncidentSummary());
    } finally {
      setGeneratingSummary(false);
    }
  }

  const selectedTierInfo = selectedZoneId ? zoneTiers[selectedZoneId] : null;

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-title">
          <span className="app-title-mark">◆</span> CROWDSHIELD
          <span className="app-title-sub">COMMAND DASHBOARD</span>
        </div>
        <SystemStatusBar health={health} />
      </header>

      <div className="app-grid">
        <div className="col-left">
          <SetupPanel onRunPipeline={runPipeline} running={running} log={setupLog} />
          <ZoneRiskPanel
            blueprintOutput={blueprintOutput}
            zoneTiers={zoneTiers}
            selectedZoneId={selectedZoneId}
            onSelectZone={setSelectedZoneId}
          />
        </div>

        <div className="col-center">
          <div className="map-panel">
            <div className="panel-header">
              <div className="map-view-toggle">
                <button
                  className={`view-toggle-btn ${mapView === "live" ? "view-toggle-active" : ""}`}
                  onClick={() => setMapView("live")}
                >
                  DIGITAL TWIN
                </button>
                <button
                  className={`view-toggle-btn ${mapView === "playback" ? "view-toggle-active" : ""}`}
                  onClick={() => setMapView("playback")}
                >
                  F1 PLAYBACK
                </button>
                <button
                  className={`view-toggle-btn ${mapView === "history" ? "view-toggle-active" : ""}`}
                  onClick={() => setMapView("history")}
                >
                  F2 HISTORY
                </button>
              </div>
              {blueprintOutput && mapView === "live" && (
                <span className="map-readiness">
                  {blueprintOutput.total_area_m2.toLocaleString()} m² TOTAL · READINESS {blueprintOutput.readiness_score_pct}%
                </span>
              )}
            </div>
            {mapView === "live" ? (
              <DigitalTwinMap
                blueprintOutput={blueprintOutput}
                zoneTiers={zoneTiers}
                f1Result={f1Result}
                sensorPositions={bResult?.sensor_positions_px || []}
                stewardPositions={bResult?.steward_positions_px || []}
                selectedZoneId={selectedZoneId}
                onSelectZone={setSelectedZoneId}
              />
            ) : mapView === "playback" ? (
              <SimulationPlayback blueprintOutput={blueprintOutput} f1Result={f1Result} />
            ) : (
              <HistoricalPlayback blueprintOutput={blueprintOutput} />
            )}
          </div>
          <PendingEscalations
            pendingEvents={pendingEvents}
            onConfirm={handleConfirm}
            onReject={handleReject}
            processing={processingEvent}
          />
        </div>

        <div className="col-right">
          <SignalInjector
            selectedZoneId={selectedZoneId}
            blueprintOutput={blueprintOutput}
            f1Result={f1Result}
            recalThreshold={recalThreshold}
            organizerScore={organizerScore}
            onInject={injectSignal}
            injecting={injecting}
          />
          <PredictionPanel selectedZoneId={selectedZoneId} blueprintOutput={blueprintOutput} />
          <ExplainabilityPanel selectedZoneId={selectedZoneId} tierInfo={selectedTierInfo} />
          <IncidentLog
            allEvents={allEvents}
            summary={summary}
            onGenerateSummary={handleGenerateSummary}
            generatingSummary={generatingSummary}
          />
        </div>
      </div>
    </div>
  );
}
