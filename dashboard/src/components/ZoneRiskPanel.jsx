import React from "react";

const TIER_COLOR = {
  Green: "var(--tier-green)",
  "Tier 1 - Yellow": "var(--tier-yellow)",
  "Tier 2 - Red": "var(--tier-red)",
  "Tier 3 - Active": "var(--tier-active)",
};

export default function ZoneRiskPanel({ blueprintOutput, zoneTiers, selectedZoneId, onSelectZone }) {
  if (!blueprintOutput) return null;

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-eyebrow">02</span> ZONE RISK
      </div>
      <div className="zone-list">
        {blueprintOutput.zones.map((zone) => {
          const tierInfo = zoneTiers[zone.zone_id];
          const tier = tierInfo?.tier || "Green";
          return (
            <button
              key={zone.zone_id}
              className={`zone-row ${selectedZoneId === zone.zone_id ? "zone-row-selected" : ""}`}
              onClick={() => onSelectZone(zone.zone_id)}
            >
              <span className="zone-row-dot" style={{ background: TIER_COLOR[tier] }} />
              <span className="zone-row-id">{zone.zone_id}</span>
              <span className="zone-row-symbols">{zone.symbols_present.join(", ") || "—"}</span>
              <span className="zone-row-tier">{tierInfo ? tierInfo.score.toFixed(0) : zone.los.los_band}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
