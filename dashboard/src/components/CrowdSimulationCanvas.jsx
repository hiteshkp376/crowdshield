import { useEffect, useRef, useState } from "react";

/**
 * CrowdSimulationCanvas
 * ----------------------
 * Live-rendered crowd of `dotCount` people as a single <canvas> draw loop
 * (NOT individual DOM/SVG nodes — that's what makes 20,000 dots possible
 * without crashing the tab).
 *
 * Each dot drifts toward a "goal" point (e.g. an exit) with a light
 * social-force-style nudge away from locally crowded neighbors, using a
 * coarse spatial grid so neighbor lookups stay cheap at 20k dots.
 *
 * Risk zones (rectangles in the same coordinate space as the venue) are
 * passed in as props — typically wired to your Module A zone boundaries
 * + Module D/E tier output. Any dot currently inside a zone marked
 * "at risk" renders red; everyone else renders the default color.
 *
 * Props:
 *   dotCount        number of simulated people (default 20000)
 *   width, height   canvas size in px
 *   riskZones       [{ id, x, y, w, h, atRisk: bool }]  — rectangles in
 *                   canvas coordinate space
 *   goals           [{ x, y }]  — points dots drift toward (e.g. exits).
 *                   Dots pick a goal on spawn and head toward it.
 *   dotColor        default (safe) dot color
 *   riskColor       color for dots inside an atRisk zone
 *   backgroundColor canvas background
 */
export default function CrowdSimulationCanvas({
  dotCount = 20000,
  width = 900,
  height = 600,
  riskZones = [],
  goals = null,
  dotColor = "#5eead4",
  riskColor = "#ef4444",
  backgroundColor = "#0a1420",
  dotSize = 1.6,
  speed = 0.6,
}) {
  const canvasRef = useRef(null);
  const stateRef = useRef(null); // typed arrays live here, not in React state
  const rafRef = useRef(null);
  const riskZonesRef = useRef(riskZones);
  const [liveCount, setLiveCount] = useState({ total: 0, atRisk: 0 });

  // keep latest risk zones available inside the animation loop without
  // restarting the whole simulation
  useEffect(() => {
    riskZonesRef.current = riskZones;
  }, [riskZones]);

  // (re)build the simulation whenever size/count changes
  useEffect(() => {
    const goalPoints =
      goals && goals.length > 0
        ? goals
        : [
            { x: width * 0.02, y: height * 0.5 }, // default: exit on left edge
            { x: width * 0.98, y: height * 0.5 }, // and right edge
          ];

    const x = new Float32Array(dotCount);
    const y = new Float32Array(dotCount);
    const vx = new Float32Array(dotCount);
    const vy = new Float32Array(dotCount);
    const goalIdx = new Uint8Array(dotCount);

    for (let i = 0; i < dotCount; i++) {
      x[i] = Math.random() * width;
      y[i] = Math.random() * height;
      vx[i] = 0;
      vy[i] = 0;
      goalIdx[i] = Math.floor(Math.random() * goalPoints.length);
    }

    stateRef.current = { x, y, vx, vy, goalIdx, goalPoints };
  }, [dotCount, width, height, goals]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    // coarse grid for cheap neighbor-density lookups
    const cellSize = 18;
    const cols = Math.ceil(width / cellSize);
    const rows = Math.ceil(height / cellSize);

    function isInZone(px, py, z) {
      return px >= z.x && px <= z.x + z.w && py >= z.y && py <= z.y + z.h;
    }

    function step() {
      const st = stateRef.current;
      if (!st) {
        rafRef.current = requestAnimationFrame(step);
        return;
      }
      const { x, y, vx, vy, goalIdx, goalPoints } = st;
      const n = x.length;

      // --- build a coarse occupancy grid (density proxy) ---
      const grid = new Uint16Array(cols * rows);
      for (let i = 0; i < n; i++) {
        const cx = Math.min(cols - 1, Math.max(0, (x[i] / width) * cols | 0));
        const cy = Math.min(rows - 1, Math.max(0, (y[i] / height) * rows | 0));
        grid[cy * cols + cx]++;
      }

      const zones = riskZonesRef.current;
      let atRiskCount = 0;

      ctx.fillStyle = backgroundColor;
      ctx.fillRect(0, 0, width, height);

      // draw risk zone outlines (cheap, drawn once per frame)
      for (const z of zones) {
        ctx.strokeStyle = z.atRisk ? "rgba(239,68,68,0.55)" : "rgba(94,234,212,0.18)";
        ctx.lineWidth = 1.5;
        ctx.strokeRect(z.x, z.y, z.w, z.h);
      }

      ctx.beginPath();
      for (let i = 0; i < n; i++) {
        const gx = goalPoints[goalIdx[i]].x;
        const gy = goalPoints[goalIdx[i]].y;

        // steer gently toward goal
        const dx = gx - x[i];
        const dy = gy - y[i];
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        vx[i] += (dx / dist) * 0.02;
        vy[i] += (dy / dist) * 0.02;

        // local-density repulsion (very light "social force" nudge):
        // push away from the crowded cell's center if this cell is dense
        const cx = Math.min(cols - 1, Math.max(0, (x[i] / width) * cols | 0));
        const cy = Math.min(rows - 1, Math.max(0, (y[i] / height) * rows | 0));
        const density = grid[cy * cols + cx];
        if (density > 6) {
          vx[i] += (Math.random() - 0.5) * 0.15;
          vy[i] += (Math.random() - 0.5) * 0.15;
        }

        // damping so motion stays calm, not jittery
        vx[i] *= 0.92;
        vy[i] *= 0.92;

        x[i] += vx[i] * speed;
        y[i] += vy[i] * speed;

        // wrap/bounce softly at edges
        if (x[i] < 0) { x[i] = 0; vx[i] *= -1; }
        if (x[i] > width) { x[i] = width; vx[i] *= -1; }
        if (y[i] < 0) { y[i] = 0; vy[i] *= -1; }
        if (y[i] > height) { y[i] = height; vy[i] *= -1; }

        // reached goal? pick a new random goal so the sim keeps flowing
        if (dist < 6) {
          goalIdx[i] = Math.floor(Math.random() * goalPoints.length);
        }

        // is this dot inside an at-risk zone?
        let inRisk = false;
        for (const z of zones) {
          if (z.atRisk && isInZone(x[i], y[i], z)) {
            inRisk = true;
            break;
          }
        }
        if (inRisk) atRiskCount++;

        // batch-draw: same color dots share one fill pass for speed
        ctx.fillStyle = inRisk ? riskColor : dotColor;
        ctx.fillRect(x[i] - dotSize / 2, y[i] - dotSize / 2, dotSize, dotSize);
      }

      setLiveCount((prev) =>
        prev.atRisk === atRiskCount && prev.total === n
          ? prev
          : { total: n, atRisk: atRiskCount }
      );

      rafRef.current = requestAnimationFrame(step);
    }

    rafRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(rafRef.current);
  }, [width, height, backgroundColor, dotColor, riskColor, dotSize, speed]);

  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        style={{ display: "block", borderRadius: 4, background: backgroundColor }}
      />
      <div
        style={{
          position: "absolute",
          top: 8,
          left: 10,
          fontFamily: "monospace",
          fontSize: 11,
          color: "#5eead4",
          letterSpacing: 0.5,
          textShadow: "0 0 4px rgba(0,0,0,0.8)",
        }}
      >
        {liveCount.total.toLocaleString()} simulated ·{" "}
        <span style={{ color: liveCount.atRisk > 0 ? "#ef4444" : "#5eead4" }}>
          {liveCount.atRisk.toLocaleString()} in risk zone
        </span>
      </div>
    </div>
  );
}
