import React from "react";

const TIER_COLOR = {
  Green: "var(--tier-green)",
  "Tier 1 - Yellow": "var(--tier-yellow)",
  "Tier 2 - Red": "var(--tier-red)",
  "Tier 3 - Active": "var(--tier-active)",
};

export default function ExplainabilityPanel({ selectedZoneId, tierInfo }) {
  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-eyebrow">04</span> EXPLAINABILITY
      </div>

      {!tierInfo ? (
        <div className="panel-empty-note">
          No fusion result yet for {selectedZoneId || "the selected zone"}. Feed a signal above.
        </div>
      ) : (
        <>
          <div className="explain-score">
            <span style={{ color: TIER_COLOR[tierInfo.tier] }}>{tierInfo.score.toFixed(1)}</span>
            <span className="explain-tier" style={{ color: TIER_COLOR[tierInfo.tier] }}>
              {tierInfo.tier}
            </span>
          </div>

          <div className="explain-bars">
            {Object.entries(tierInfo.breakdown).map(([factor, value]) => (
              <div key={factor} className="explain-bar-row">
                <span className="explain-bar-label">{factor.replace(/_/g, " ")}</span>
                <div className="explain-bar-track">
                  <div
                    className="explain-bar-fill"
                    style={{ width: `${Math.min(100, (value / 25) * 100)}%` }}
                  />
                </div>
                <span className="explain-bar-value">{value}</span>
              </div>
            ))}
          </div>

          <div className="cross-validation-note">{tierInfo.crossValidationNote}</div>
        </>
      )}
    </div>
  );
}
