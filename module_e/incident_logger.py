"""
incident_logger.py — Module E: post-incident logging + citizen reports.

Two distinct record types, per the brief:
  1. Post-incident log -- structured, timestamped, signal-by-signal
     reconstruction of every escalation event. Feeds Module C's history
     database (Phase 4 feedback loop) and separately serves as
     investigation-ready documentation.
  2. Citizen incident reports -- mobile app submissions (photo/text/GPS),
     stored as UNVERIFIED, kept visually/architecturally distinct from
     sensor-confirmed escalation events (per the brief's dashboard design).

Uses SQLite for the same honest reason as Module C: hackathon-scale
substitution for PostgreSQL, identical schema/query logic, zero external
server dependency.
"""

import sqlite3
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent / "incident_log.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS incident_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    zone_id TEXT NOT NULL,
    tier TEXT NOT NULL,
    composite_risk_score REAL NOT NULL,
    explainability_breakdown TEXT NOT NULL,   -- JSON
    dispatch_status TEXT NOT NULL,
    confirmed_by TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS citizen_reports (
    report_id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id TEXT,
    latitude REAL,
    longitude REAL,
    text_report TEXT,
    photo_path TEXT,
    verified INTEGER NOT NULL DEFAULT 0,   -- always 0 (unverified) at submission
    submitted_at TEXT NOT NULL
);
"""


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)  # executescript (not execute) -- SCHEMA has multiple statements
    return conn


def log_incident(event_id: str, zone_id: str, tier: str, composite_risk_score: float,
                  explainability_breakdown: dict, dispatch_status: str,
                  confirmed_by: str | None = None, db_path: Path = DEFAULT_DB_PATH) -> int:
    conn = get_connection(db_path)
    cur = conn.execute(
        """INSERT INTO incident_log
           (event_id, zone_id, tier, composite_risk_score, explainability_breakdown,
            dispatch_status, confirmed_by, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (event_id, zone_id, tier, composite_risk_score, json.dumps(explainability_breakdown),
         dispatch_status, confirmed_by, datetime.utcnow().isoformat()),
    )
    conn.commit()
    log_id = cur.lastrowid
    conn.close()
    return log_id


def get_incident_log(db_path: Path = DEFAULT_DB_PATH) -> list[dict]:
    conn = get_connection(db_path)
    rows = conn.execute("SELECT * FROM incident_log ORDER BY created_at ASC").fetchall()
    conn.close()
    results = []
    for row in rows:
        d = dict(row)
        d["explainability_breakdown"] = json.loads(d["explainability_breakdown"])
        results.append(d)
    return results


def submit_citizen_report(zone_id: str | None, latitude: float | None, longitude: float | None,
                           text_report: str | None, photo_path: str | None,
                           db_path: Path = DEFAULT_DB_PATH) -> int:
    """Always stored as unverified (verified=0) -- verification, if it
    happens, is a separate operator action outside this module's scope."""
    conn = get_connection(db_path)
    cur = conn.execute(
        """INSERT INTO citizen_reports
           (zone_id, latitude, longitude, text_report, photo_path, verified, submitted_at)
           VALUES (?, ?, ?, ?, ?, 0, ?)""",
        (zone_id, latitude, longitude, text_report, photo_path, datetime.utcnow().isoformat()),
    )
    conn.commit()
    report_id = cur.lastrowid
    conn.close()
    return report_id


def get_citizen_reports(db_path: Path = DEFAULT_DB_PATH) -> list[dict]:
    conn = get_connection(db_path)
    rows = conn.execute("SELECT * FROM citizen_reports ORDER BY submitted_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]
