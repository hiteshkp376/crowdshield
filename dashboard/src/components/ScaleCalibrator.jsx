import React, { useRef, useState, useEffect } from "react";

/**
 * ScaleCalibrator — replaces blind entry of scale_m_per_px with a real
 * measurement: the user clicks the two ends of the blueprint's own scale
 * bar (a standard element every real venue floor plan includes) and
 * enters what real-world distance it represents. scale_m_per_px is then
 * computed, not guessed.
 */
export default function ScaleCalibrator({ file, onCalibrated }) {
  const imgRef = useRef(null);
  const [imgUrl, setImgUrl] = useState(null);
  const [naturalSize, setNaturalSize] = useState({ w: 0, h: 0 });
  const [points, setPoints] = useState([]);
  const [realDistance, setRealDistance] = useState(30);
  const [calibrated, setCalibrated] = useState(null);

  useEffect(() => {
    if (!file) {
      setImgUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setImgUrl(url);
    setPoints([]);
    setCalibrated(null);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  function handleImgLoad() {
    setNaturalSize({ w: imgRef.current.naturalWidth, h: imgRef.current.naturalHeight });
  }

  function handleClick(e) {
    if (points.length >= 2) {
      setPoints([]);
      setCalibrated(null);
      return;
    }
    const rect = imgRef.current.getBoundingClientRect();
    const scaleX = naturalSize.w / rect.width;
    const scaleY = naturalSize.h / rect.height;
    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;

    if (points.length === 1) {
      const dx = x - points[0].x;
      const dy = y - points[0].y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < 5) {
        alert("That second click landed on almost the same spot as the first. " +
              "Click the OTHER end of the scale bar, further away, not the same point twice.");
        return;
      }
    }
    setPoints((prev) => [...prev, { x, y }]);
  }

  const MIN_REASONABLE_SCALE = 0.005; // 0.5cm/px -- tighter than any realistic venue photo
  const MAX_REASONABLE_SCALE = 2.0;   // 2m/px -- looser than any realistic venue photo

  function computeScale() {
    if (points.length !== 2 || !realDistance) return;
    const dx = points[1].x - points[0].x;
    const dy = points[1].y - points[0].y;
    const pixelDist = Math.sqrt(dx * dx + dy * dy);

    if (pixelDist < 5) {
      alert("Your two calibration points are almost identical -- can't compute a scale from zero pixel distance. Click two clearly separate points on the scale bar.");
      return;
    }

    const scaleMPerPx = realDistance / pixelDist;

    if (scaleMPerPx < MIN_REASONABLE_SCALE || scaleMPerPx > MAX_REASONABLE_SCALE) {
      const proceed = window.confirm(
        `This computes to ${scaleMPerPx.toFixed(4)} m/px, which is outside a realistic range ` +
        `(${MIN_REASONABLE_SCALE}-${MAX_REASONABLE_SCALE} m/px for a normal venue photo). ` +
        `This usually means the two points you clicked aren't actually the two ends of the scale ` +
        `bar, or the real-world distance you entered doesn't match. Use this value anyway?`
      );
      if (!proceed) return;
    }

    setCalibrated(scaleMPerPx);
    onCalibrated(scaleMPerPx);
  }

  if (!imgUrl) return null;

  return (
    <div className="calibrator">
      <label className="field-label">
        Scale calibration — click the two ends of the blueprint's own scale
        bar (every real venue floor plan has one)
      </label>

      <div className="calibrator-img-wrap" onClick={handleClick}>
        <img ref={imgRef} src={imgUrl} onLoad={handleImgLoad} className="calibrator-img" alt="blueprint" />
        {points.length > 0 && naturalSize.w > 0 && (
          <svg className="calibrator-overlay" viewBox={`0 0 ${naturalSize.w} ${naturalSize.h}`}>
            {points.map((p, i) => (
              <circle key={i} cx={p.x} cy={p.y} r="8" fill="var(--signal)" />
            ))}
            {points.length === 2 && (
              <line
                x1={points[0].x}
                y1={points[0].y}
                x2={points[1].x}
                y2={points[1].y}
                stroke="var(--signal)"
                strokeWidth="3"
                strokeDasharray="6,4"
              />
            )}
          </svg>
        )}
      </div>

      <div className="calibrator-status">
        {points.length === 0 && "Click one end of the scale bar."}
        {points.length === 1 && "Click the other end of the scale bar."}
        {points.length === 2 && "Both points set. Click the image again to redo."}
      </div>

      <div className="field-row">
        <div>
          <label className="field-label">Real-world distance (meters)</label>
          <input
            type="number"
            value={realDistance}
            onChange={(e) => setRealDistance(+e.target.value)}
            className="field-input"
          />
        </div>
        <div style={{ display: "flex", alignItems: "flex-end" }}>
          <button
            className="btn-primary"
            style={{ marginTop: 0 }}
            disabled={points.length !== 2}
            onClick={computeScale}
          >
            COMPUTE SCALE →
          </button>
        </div>
      </div>

      {calibrated && (
        <div className="calibrator-result">
          Computed scale: <strong>{calibrated.toFixed(4)} m/px</strong> — applied below.
        </div>
      )}
    </div>
  );
}
