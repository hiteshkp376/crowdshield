import React from "react";

const TIER_COLOR = {
  Green: "var(--tier-green)",
  "Tier 1 - Yellow": "var(--tier-yellow)",
  "Tier 2 - Red": "var(--tier-red)",
  "Tier 3 - Active": "var(--tier-active)",
};

const TIER_GLOW = {
  Green: "var(--tier-green-glow)",
  "Tier 1 - Yellow": "var(--tier-yellow-glow)",
  "Tier 2 - Red": "var(--tier-red-glow)",
  "Tier 3 - Active": "var(--tier-active-glow)",
};

const SIGNAL_ICONS = [
  { key: "pushWave", icon: "⚠️" },
  { key: "thermalCollapse", icon: "🚨" },
  { key: "heatStress", icon: "🔥" },
  { key: "reverseFlow", icon: "🔄" },
  { key: "routeBlockage", icon: "🚧" },
];

function polygonPoints(contourPx) {
  return contourPx.map(([x, y]) => `${x},${y}`).join(" ");
}

function centroidOf(contourPx) {
  const n = contourPx.length;
  const sx = contourPx.reduce((s, p) => s + p[0], 0) / n;
  const sy = contourPx.reduce((s, p) => s + p[1], 0) / n;
  return [sx, sy];
}

export default function DigitalTwinMap({
  blueprintOutput,
  zoneTiers,
  f1Result,
  sensorPositions = [],
  stewardPositions = [],
  selectedZoneId,
  onSelectZone,
}) {
  if (!blueprintOutput) {
    return (
      <div className="map-empty">
        <div className="map-empty-inner">
          <div className="map-empty-icon">▦</div>
          <div>No venue loaded</div>
          <div className="map-empty-sub">Run blueprint analysis to render the Digital Twin</div>
        </div>
      </div>
    );
  }

  const w = blueprintOutput.image_width_px;
  const h = blueprintOutput.image_height_px;

  // Goal zone centroid (from F1's simulation) -- used to compute the
  // "normal flow direction" arrow per zone, which flips 180deg when
  // reverse_flow is the active injected signal for that zone. This is
  // real geometry (same goal used by the actual simulation), not a
  // decorative arrow.
  const goalZone = f1Result?.goal_zone_id
    ? blueprintOutput.zones.find((z) => z.zone_id === f1Result.goal_zone_id)
    : null;
  const goalCentroid = goalZone ? centroidOf(goalZone.contour_px) : null;

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="digital-twin-svg" preserveAspectRatio="xMidYMid meet">
      <defs>
        <pattern id="hazard" patternUnits="userSpaceOnUse" width="10" height="10" patternTransform="rotate(45)">
          <rect width="10" height="10" fill="transparent" />
          <line x1="0" y1="0" x2="0" y2="10" stroke="var(--tier-yellow)" strokeWidth="4" opacity="0.5" />
        </pattern>
      </defs>

      {blueprintOutput.zones.map((zone) => {
        const tierInfo = zoneTiers[zone.zone_id];
        const tier = tierInfo?.tier || "Green";
        const isSelected = selectedZoneId === zone.zone_id;
        const [cx, cy] = centroidOf(zone.contour_px);

        return (
          <g key={zone.zone_id} onClick={() => onSelectZone(zone.zone_id)} style={{ cursor: "pointer" }}>
            <polygon
              points={polygonPoints(zone.contour_px)}
              fill={TIER_GLOW[tier]}
              stroke={isSelected ? "var(--signal)" : TIER_COLOR[tier]}
              strokeWidth={isSelected ? 4 : 2}
              style={tier !== "Green" ? { animation: "pulse-glow 2s ease-in-out infinite" } : {}}
            />
            {zone.is_chokepoint && (
              <polygon points={polygonPoints(zone.contour_px)} fill="url(#hazard)" opacity="0.4" />
            )}
            <text
              x={cx}
              y={cy - 6}
              textAnchor="middle"
              className="zone-label"
              fill="var(--text-primary)"
            >
              {zone.zone_id}
            </text>
            <text x={cx} y={cy + 12} textAnchor="middle" className="zone-sublabel" fill="var(--text-secondary)">
              {tierInfo ? `${tierInfo.score.toFixed(0)}` : zone.los.los_band}
            </text>
            {zone.is_vip_corridor && (
              <text x={cx} y={cy + 28} textAnchor="middle" className="zone-tag" fill="var(--tier-yellow)">
                VIP CORRIDOR
              </text>
            )}
            {tierInfo?.signalFlags && (
              <text x={cx} y={cy - 24} textAnchor="middle" fontSize="18">
                {SIGNAL_ICONS.filter((s) => tierInfo.signalFlags[s.key]).map((s) => s.icon).join(" ")}
              </text>
            )}
            {tierInfo?.signalFlags?.reverseFlow && goalCentroid && (
              <FlowArrow from={[cx, cy]} to={goalCentroid} reversed />
            )}
            {tierInfo?.signalFlags?.routeBlockage && (
              <BlockageBar contourPx={zone.contour_px} />
            )}
          </g>
        );
      })}

      {stewardPositions.map(([x, y], i) => (
        <g key={`stw-${i}`}>
          <circle cx={x} cy={y} r="9" fill="none" stroke="var(--signal)" strokeWidth="1.5" opacity="0.6" />
          <circle cx={x} cy={y} r="4" fill="var(--signal)" />
        </g>
      ))}

      {sensorPositions.map(([x, y], i) => (
        <g key={`sen-${i}`}>
          <rect x={x - 6} y={y - 6} width="12" height="12" fill="none" stroke="var(--text-secondary)" strokeWidth="1.5" transform={`rotate(45 ${x} ${y})`} />
          <circle cx={x} cy={y} r="2.5" fill="var(--text-secondary)" />
        </g>
      ))}
    </svg>
  );
}

function FlowArrow({ from, to, reversed }) {
  const dx = to[0] - from[0];
  const dy = to[1] - from[1];
  const len = Math.sqrt(dx * dx + dy * dy) || 1;
  let ux = dx / len, uy = dy / len;
  if (reversed) { ux = -ux; uy = -uy; }

  const arrowLen = 45;
  const tailX = from[0] - ux * (arrowLen / 2);
  const tailY = from[1] - uy * (arrowLen / 2);
  const headX = from[0] + ux * (arrowLen / 2);
  const headY = from[1] + uy * (arrowLen / 2);
  const angle = Math.atan2(uy, ux) * (180 / Math.PI);

  return (
    <g>
      <line x1={tailX} y1={tailY} x2={headX} y2={headY} stroke="var(--tier-red)" strokeWidth="3" />
      <polygon
        points="0,-6 14,0 0,6"
        fill="var(--tier-red)"
        transform={`translate(${headX},${headY}) rotate(${angle})`}
      />
    </g>
  );
}

function BlockageBar({ contourPx }) {
  const xs = contourPx.map((p) => p[0]);
  const ys = contourPx.map((p) => p[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const width = maxX - minX, height = maxY - minY;
  const vertical = height > width;

  const midX = (minX + maxX) / 2;
  const midY = (minY + maxY) / 2;

  const x1 = vertical ? minX + width * 0.15 : midX;
  const x2 = vertical ? maxX - width * 0.15 : midX;
  const y1 = vertical ? midY : minY + height * 0.15;
  const y2 = vertical ? midY : maxY - height * 0.15;

  return (
    <line
      x1={x1} y1={y1} x2={x2} y2={y2}
      stroke="var(--tier-red)"
      strokeWidth="6"
      strokeDasharray="10,6"
      strokeLinecap="round"
    />
  );
}
