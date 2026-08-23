// api.js — thin fetch wrappers for all 6 CrowdShield backend services.
// Each module runs on its own port, exactly as documented in every
// module's own README. If a port is unreachable, the calling component
// is responsible for surfacing that clearly rather than failing silently.

const PORTS = {
  A: 8001,
  F1: 8006,
  B: 8002,
  C: 8003,
  D: 8004,
  E: 8005,
};

function base(mod) {
  return `http://localhost:${PORTS[mod]}`;
}

async function asJson(resp) {
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore parse failure, use statusText */
    }
    throw new Error(`${resp.status}: ${detail}`);
  }
  return resp.json();
}

export async function checkHealth(mod) {
  try {
    const resp = await fetch(`${base(mod)}/health`, { signal: AbortSignal.timeout(3000) });
    return resp.ok;
  } catch {
    return false;
  }
}

export async function checkAllHealth() {
  const results = {};
  await Promise.all(
    Object.keys(PORTS).map(async (mod) => {
      results[mod] = await checkHealth(mod);
    })
  );
  return results;
}

// ---- Module A ----
export async function analyzeBlueprint(file, scaleMPerPx, expectedTurnout) {
  const form = new FormData();
  form.append("file", file);
  form.append("scale_m_per_px", scaleMPerPx);
  if (expectedTurnout) form.append("expected_turnout", expectedTurnout);
  const resp = await fetch(`${base("A")}/analyze-blueprint`, { method: "POST", body: form });
  return asJson(resp);
}

// ---- Module F1 ----
export async function runSimulation(blueprintOutput, expectedTurnout, triggerEvent, durationS) {
  const resp = await fetch(`${base("F1")}/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      blueprint_output: blueprintOutput,
      expected_turnout: expectedTurnout,
      trigger_event: triggerEvent,
      duration_s: durationS,
    }),
  });
  return asJson(resp);
}

// ---- Module B ----
export async function planPlacement(blueprintOutput, f1Result, sensorBudget, stewardBudget) {
  const resp = await fetch(`${base("B")}/plan-placement`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      blueprint_output: blueprintOutput,
      f1_result: f1Result,
      sensor_budget: sensorBudget,
      steward_budget: stewardBudget,
    }),
  });
  return asJson(resp);
}

// ---- Module C ----
export async function getIntensityScore(organizerName, eventType, lat, lon) {
  const resp = await fetch(`${base("C")}/intensity-score`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ organizer_name: organizerName, event_type: eventType, lat, lon }),
  });
  return asJson(resp);
}

export async function recalibrateThreshold(heatIndexC, avgWaitTimeMin, waterCoverageScore) {
  const resp = await fetch(`${base("C")}/recalibrate-threshold`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      heat_index_c: heatIndexC,
      avg_wait_time_min: avgWaitTimeMin,
      water_coverage_score_0_1: waterCoverageScore,
    }),
  });
  return asJson(resp);
}

// ---- Module D ----
export async function fuseSignals(zoneInputs) {
  const resp = await fetch(`${base("D")}/fuse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ zones: zoneInputs }),
  });
  return asJson(resp);
}

// ---- Module E ----
export async function processFusionResult(zoneId, tier, score, breakdown) {
  const resp = await fetch(`${base("E")}/process-fusion-result`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      zone_id: zoneId,
      tier,
      composite_risk_score_0_100: score,
      explainability_breakdown: breakdown,
    }),
  });
  return asJson(resp);
}

export async function confirmDispatch(eventId, confirmedBy) {
  const resp = await fetch(`${base("E")}/confirm-dispatch/${eventId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirmed_by: confirmedBy }),
  });
  return asJson(resp);
}

export async function rejectDispatch(eventId, confirmedBy) {
  const resp = await fetch(`${base("E")}/reject-dispatch/${eventId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirmed_by: confirmedBy }),
  });
  return asJson(resp);
}

export async function getPendingEvents() {
  const resp = await fetch(`${base("E")}/pending-events`);
  return asJson(resp);
}

export async function getFusionHistory(minutes) {
  const url = minutes ? `${base("D")}/history?minutes=${minutes}` : `${base("D")}/history`;
  const resp = await fetch(url);
  return asJson(resp);
}

export async function getFusionHistoryRaw(minutes) {
  const url = minutes ? `${base("D")}/history-raw?minutes=${minutes}` : `${base("D")}/history-raw`;
  const resp = await fetch(url);
  return asJson(resp);
}

export async function predictDanger(features) {
  const resp = await fetch("http://localhost:8007/predict-danger", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(features),
  });
  return asJson(resp);
}

export async function clearFusionHistory() {
  const resp = await fetch(`${base("D")}/history/clear`, { method: "POST" });
  return asJson(resp);
}

export async function getAllEvents() {
  const resp = await fetch(`${base("E")}/all-events`);
  return asJson(resp);
}

export async function getCitizenReports() {
  const resp = await fetch(`${base("E")}/citizen-reports`);
  return asJson(resp);
}

export async function getIncidentSummary() {
  const resp = await fetch(`${base("E")}/incident-summary`);
  return asJson(resp);
}

export { PORTS };
