import React from "react";

export default function PendingEscalations({ pendingEvents, onConfirm, onReject, processing }) {
  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-eyebrow">05</span> PENDING ESCALATIONS — HUMAN CONFIRMATION REQUIRED
      </div>

      {pendingEvents.length === 0 ? (
        <div className="panel-empty-note">No escalations awaiting confirmation.</div>
      ) : (
        <div className="pending-list">
          {pendingEvents.map((ev) => (
            <div key={ev.event_id} className="pending-card">
              <div className="pending-card-top">
                <span className="pending-event-id">{ev.event_id}</span>
                <span className="pending-tier">{ev.tier}</span>
              </div>
              <div className="pending-zone">
                Zone {ev.zone_id} · score {ev.composite_risk_score.toFixed(1)}
              </div>
              <div className="pending-actions">
                <button
                  className="btn-confirm"
                  disabled={processing}
                  onClick={() => onConfirm(ev.event_id)}
                >
                  CONFIRM DISPATCH
                </button>
                <button
                  className="btn-reject"
                  disabled={processing}
                  onClick={() => onReject(ev.event_id)}
                >
                  REJECT
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
