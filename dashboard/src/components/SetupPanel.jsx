import React, { useState } from "react";
import ScaleCalibrator from "./ScaleCalibrator.jsx";

const EVENT_TYPES = ["political_rally", "religious_festival", "concert", "sports_event", "other"];

export default function SetupPanel({ onRunPipeline, running, log }) {
  const [file, setFile] = useState(null);
  const [scale, setScale] = useState(0.155);
  const [scaleSource, setScaleSource] = useState("default"); // "default" | "calibrated" | "manual"
  const [turnout, setTurnout] = useState(27000);
  const [organizer, setOrganizer] = useState("Example Organizer A");
  const [eventType, setEventType] = useState("political_rally");
  const [triggerZone, setTriggerZone] = useState("");
  const [sensorBudget, setSensorBudget] = useState(6);
  const [stewardBudget, setStewardBudget] = useState(4);

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-eyebrow">01</span> PRE-EVENT SETUP
      </div>

      <label className="field-label">Venue blueprint</label>
      <input
        type="file"
        accept="image/png,image/jpeg"
        onChange={(e) => setFile(e.target.files[0])}
        className="field-file"
      />

      {file && (
        <ScaleCalibrator
          file={file}
          onCalibrated={(computedScale) => {
            setScale(computedScale);
            setScaleSource("calibrated");
          }}
        />
      )}

      <div className="field-row">
        <div>
          <label className="field-label">
            Scale (m/px) {scaleSource === "calibrated" && <span className="field-badge">CALIBRATED</span>}
          </label>
          <input
            type="number"
            step="0.001"
            value={scale}
            onChange={(e) => {
              setScale(+e.target.value);
              setScaleSource("manual");
            }}
            className="field-input"
          />
        </div>
        <div>
          <label className="field-label">Expected turnout</label>
          <input type="number" value={turnout} onChange={(e) => setTurnout(+e.target.value)} className="field-input" />
        </div>
      </div>

      <div className="field-row">
        <div>
          <label className="field-label">Organizer</label>
          <input type="text" value={organizer} onChange={(e) => setOrganizer(e.target.value)} className="field-input" />
        </div>
        <div>
          <label className="field-label">Event type</label>
          <select value={eventType} onChange={(e) => setEventType(e.target.value)} className="field-input">
            {EVENT_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="field-row">
        <div>
          <label className="field-label">Sensor budget</label>
          <input type="number" value={sensorBudget} onChange={(e) => setSensorBudget(+e.target.value)} className="field-input" />
        </div>
        <div>
          <label className="field-label">Steward budget</label>
          <input type="number" value={stewardBudget} onChange={(e) => setStewardBudget(+e.target.value)} className="field-input" />
        </div>
      </div>

      <label className="field-label">Panic trigger zone (optional — see zone IDs after analysis)</label>
      <input
        type="text"
        value={triggerZone}
        onChange={(e) => setTriggerZone(e.target.value)}
        placeholder="e.g. Z1"
        className="field-input"
      />

      <button
        className="btn-primary"
        disabled={!file || running}
        onClick={() =>
          onRunPipeline({ file, scale, turnout, organizer, eventType, triggerZone, sensorBudget, stewardBudget })
        }
      >
        {running ? "RUNNING PIPELINE…" : "RUN FULL ANALYSIS →"}
      </button>

      {file && scaleSource === "default" && (
        <div className="field-warning">
          ⚠ Using an uncalibrated default scale ({scale} m/px). Click the
          scale bar above for an accurate reading — total venue m² and
          every downstream calculation depend on this being right.
        </div>
      )}

      {log.length > 0 && (
        <div className="setup-log">
          {log.map((line, i) => (
            <div key={i} className={`setup-log-line ${line.startsWith("✓") ? "ok" : line.startsWith("✗") ? "err" : ""}`}>
              {line}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
