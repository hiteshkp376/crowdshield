import React from "react";

const MODULE_LABELS = {
  A: "A · BLUEPRINT",
  F1: "F1 · SIMULATION",
  B: "B · PLACEMENT",
  C: "C · WEATHER/HISTORY",
  D: "D · FUSION",
  E: "E · ESCALATION",
};

export default function SystemStatusBar({ health }) {
  return (
    <div className="status-bar">
      {Object.entries(MODULE_LABELS).map(([key, label]) => (
        <div key={key} className="status-chip">
          <span
            className="status-dot"
            style={{ background: health[key] ? "var(--tier-green)" : "var(--tier-red)" }}
          />
          {label}
        </div>
      ))}
    </div>
  );
}
