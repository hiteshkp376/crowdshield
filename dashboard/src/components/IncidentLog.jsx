import React from "react";

export default function IncidentLog({ allEvents, summary, onGenerateSummary, generatingSummary }) {
  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-eyebrow">06</span> INCIDENT LOG
      </div>

      <div className="incident-log-list">
        {allEvents.length === 0 ? (
          <div className="panel-empty-note">No events logged yet.</div>
        ) : (
          allEvents
            .slice()
            .reverse()
            .map((ev) => (
              <div key={ev.event_id} className="log-row">
                <span className="log-time">{new Date(ev.created_at).toLocaleTimeString()}</span>
                <span className="log-zone">{ev.zone_id}</span>
                <span className="log-tier">{ev.tier}</span>
                <span className={`log-status log-status-${ev.dispatch_status}`}>{ev.dispatch_status}</span>
              </div>
            ))
        )}
      </div>

      <button className="btn-secondary" onClick={onGenerateSummary} disabled={generatingSummary}>
        {generatingSummary ? "GENERATING…" : "GENERATE INCIDENT SUMMARY"}
      </button>

      {summary && (
        <div className="summary-box">
          <div className="summary-label">
            {summary.is_ai_generated ? "AI-GENERATED SUMMARY" : "TEMPLATE SUMMARY (no ANTHROPIC_API_KEY configured)"}
          </div>
          <pre className="summary-text">{summary.summary}</pre>
        </div>
      )}
    </div>
  );
}
