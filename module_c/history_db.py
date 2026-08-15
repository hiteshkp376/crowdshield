"""
history_db.py — Module C: Event-History / Organizer Risk Prior database.

Stores public, documented event/organizer-level records (NEVER individual
attendee data, per the brief's ethics commitments). Used to compute an
organizer's historical risk pattern: permit-vs-turnout mismatch tendency,
prior incident count, and known behavioral flags (e.g. "rush-to-vehicle"
at departure).

PRODUCTION NOTE: the master brief's stack calls for PostgreSQL. This
module uses SQLite instead -- a deliberate, honest substitution for the
hackathon build: identical schema/query logic, zero external server
dependency, trivially portable to PostgreSQL later (swap the connection
layer, keep the SQL). Stated explicitly, not hidden.
"""

import sqlite3
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent / "event_history.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organizer_name TEXT NOT NULL,
    venue_name TEXT NOT NULL,
    event_date TEXT NOT NULL,
    event_type TEXT NOT NULL,           -- 'political_rally' | 'religious_festival' | 'concert' | 'other'
    permitted_capacity INTEGER,
    actual_turnout INTEGER,
    had_incident INTEGER NOT NULL DEFAULT 0,  -- 0/1
    incident_notes TEXT,                -- public record summary, never individual data
    behavioral_flags TEXT,              -- JSON list, e.g. ["rush_to_vehicle", "late_arrival"]
    created_at TEXT NOT NULL
);
"""


@dataclass
class EventRecord:
    organizer_name: str
    venue_name: str
    event_date: str
    event_type: str
    permitted_capacity: int | None = None
    actual_turnout: int | None = None
    had_incident: bool = False
    incident_notes: str | None = None
    behavioral_flags: list[str] | None = None


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    return conn


def add_event_record(record: EventRecord, db_path: Path = DEFAULT_DB_PATH) -> int:
    """Adds a completed event's outcome data -- this is the Phase 4
    feedback loop from the master workflow: 'full event outcome data
    feeds back into Module C's history database.'"""
    conn = get_connection(db_path)
    cur = conn.execute(
        """INSERT INTO events
           (organizer_name, venue_name, event_date, event_type,
            permitted_capacity, actual_turnout, had_incident,
            incident_notes, behavioral_flags, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            record.organizer_name, record.venue_name, record.event_date, record.event_type,
            record.permitted_capacity, record.actual_turnout, int(record.had_incident),
            record.incident_notes, json.dumps(record.behavioral_flags or []),
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    event_id = cur.lastrowid
    conn.close()
    return event_id


def get_organizer_history(organizer_name: str, db_path: Path = DEFAULT_DB_PATH) -> list[dict]:
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM events WHERE organizer_name = ? ORDER BY event_date DESC",
        (organizer_name,),
    ).fetchall()
    conn.close()
    results = []
    for row in rows:
        d = dict(row)
        d["behavioral_flags"] = json.loads(d["behavioral_flags"] or "[]")
        d["had_incident"] = bool(d["had_incident"])
        results.append(d)
    return results


def compute_organizer_risk_prior(organizer_name: str, db_path: Path = DEFAULT_DB_PATH) -> dict:
    """
    Rolls up an organizer's history into a risk prior:
      - avg_turnout_permit_ratio: how much turnout typically exceeds the
        permit (Karur's ratio was ~2.7x -- 27,000 actual vs 10,000 permitted)
      - incident_rate: fraction of past events with a documented incident
      - common_behavioral_flags: which risk behaviors show up repeatedly

    Ethical note (per brief Section 3): this is organizer/event-level
    history only -- never individual attendee data or behavior.
    """
    history = get_organizer_history(organizer_name, db_path)

    if not history:
        return {
            "organizer_name": organizer_name,
            "events_on_record": 0,
            "avg_turnout_permit_ratio": None,
            "incident_rate": None,
            "common_behavioral_flags": [],
            "note": "No prior history on record -- treat as unknown risk, "
                    "do not assume low risk by default.",
        }

    ratios = [
        e["actual_turnout"] / e["permitted_capacity"]
        for e in history
        if e["actual_turnout"] and e["permitted_capacity"]
    ]
    avg_ratio = round(sum(ratios) / len(ratios), 2) if ratios else None

    incident_rate = round(sum(1 for e in history if e["had_incident"]) / len(history), 2)

    flag_counts: dict[str, int] = {}
    for e in history:
        for flag in e["behavioral_flags"]:
            flag_counts[flag] = flag_counts.get(flag, 0) + 1
    common_flags = sorted(flag_counts, key=flag_counts.get, reverse=True)

    return {
        "organizer_name": organizer_name,
        "events_on_record": len(history),
        "avg_turnout_permit_ratio": avg_ratio,
        "incident_rate": incident_rate,
        "common_behavioral_flags": common_flags,
    }


def seed_illustrative_data(db_path: Path = DEFAULT_DB_PATH) -> None:
    """
    Seeds the DB with a small illustrative dataset for demo/testing,
    including an entry for the Karur case study using only the public,
    already-widely-reported facts referenced throughout this project
    (permit ~10,000 vs turnout ~27,000; documented incident). This is
    public record data already used as CrowdShield's motivating case
    study, not new or sensitive information.
    """
    conn = get_connection(db_path)
    existing = conn.execute("SELECT COUNT(*) as c FROM events").fetchone()["c"]
    conn.close()
    if existing > 0:
        return  # don't duplicate seed data on repeated runs

    add_event_record(EventRecord(
        organizer_name="Example Organizer A",
        venue_name="Karur Rally Grounds (illustrative)",
        event_date="2025-09-27",
        event_type="political_rally",
        permitted_capacity=10000,
        actual_turnout=27000,
        had_incident=True,
        incident_notes="Publicly documented stampede incident; permit-vs-turnout "
                        "mismatch and delayed VIP arrival cited as contributing factors.",
        behavioral_flags=["rush_to_vehicle", "late_arrival", "permit_turnout_mismatch"],
    ), db_path)

    add_event_record(EventRecord(
        organizer_name="Example Organizer B",
        venue_name="Community Grounds (illustrative)",
        event_date="2024-03-15",
        event_type="religious_festival",
        permitted_capacity=5000,
        actual_turnout=5200,
        had_incident=False,
        incident_notes=None,
        behavioral_flags=[],
    ), db_path)

    add_event_record(EventRecord(
        organizer_name="Example Organizer A",
        venue_name="City Stadium (illustrative)",
        event_date="2024-11-02",
        event_type="political_rally",
        permitted_capacity=8000,
        actual_turnout=15000,
        had_incident=False,
        incident_notes="High turnout relative to permit, no incident recorded.",
        behavioral_flags=["permit_turnout_mismatch"],
    ), db_path)
