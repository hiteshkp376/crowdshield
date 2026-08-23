"""
edge_cache.py — Module D: persistent fusion-reading history.

Serves TWO purposes with one underlying store, since both need the same
data (every fusion reading, in order, with timestamps):

1. EDGE RESILIENCE (original purpose, per brief Section 4 / workflow
   Step 7): "Edge devices run inference locally and cache the last
   several minutes of risk scores. If network connectivity drops, local
   audible/visual alerts still fire... queued data auto-syncs once
   connectivity restores."

2. MODULE F2's HISTORICAL PLAYBACK DATA SOURCE: F2 needs a genuine
   continuous time-series of every risk reading (not just the sparse
   escalation events Module E logs on tier changes) to render a
   meaningful scrubbable trend timeline. This cache -- which already
   records every /fuse call, not just escalations -- is that source.

HONEST DESIGN NOTE: earlier versions of this module used an in-memory
deque, which is fine for pure edge-resilience testing but wrong for
"historical" playback -- data vanishing on restart isn't history. This
version persists to SQLite (same honest PostgreSQL-substitution pattern
as Modules C and E), and extends default retention well beyond the
original 10-minute edge-buffer window so a full event's timeline
survives for later review.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent / "fusion_history.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS fusion_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id TEXT NOT NULL,
    tier TEXT NOT NULL,
    composite_risk_score REAL NOT NULL,
    density_people_per_m2 REAL,
    physical_corroboration INTEGER NOT NULL DEFAULT 0,
    synced INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
"""


@dataclass
class CachedRiskEvent:
    zone_id: str
    tier: str
    composite_risk_score: float
    timestamp: datetime
    synced: bool = False
    row_id: int | None = None


class EdgeCache:
    """
    Persistent (SQLite-backed) log of every fusion reading. Retention
    default is intentionally much longer than the original 10-minute
    edge-buffer figure -- long enough that a full event's history
    remains available for Module F2's playback after the event ends,
    while still supporting the original network-outage sync behavior.
    """

    def __init__(self, retention_minutes: int = 1440, db_path: Path = DEFAULT_DB_PATH):
        self.retention = timedelta(minutes=retention_minutes)
        self.db_path = db_path
        self.network_available = True
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_connection()
        conn.executescript(SCHEMA)
        conn.commit()
        conn.close()

    def set_network_status(self, available: bool):
        self.network_available = available

    def record_event(self, zone_id: str, tier: str, composite_risk_score: float,
                      density_people_per_m2: float | None = None,
                      physical_corroboration: bool = False,
                      timestamp: datetime | None = None) -> CachedRiskEvent:
        ts = timestamp or datetime.utcnow()
        conn = self._get_connection()
        cur = conn.execute(
            """INSERT INTO fusion_history
               (zone_id, tier, composite_risk_score, density_people_per_m2,
                physical_corroboration, synced, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (zone_id, tier, composite_risk_score, density_people_per_m2,
             int(physical_corroboration), int(self.network_available), ts.isoformat()),
        )
        conn.commit()
        row_id = cur.lastrowid
        conn.close()
        self._prune_expired()
        return CachedRiskEvent(
            zone_id=zone_id, tier=tier, composite_risk_score=composite_risk_score,
            timestamp=ts, synced=self.network_available, row_id=row_id,
        )

    def _prune_expired(self):
        cutoff = (datetime.utcnow() - self.retention).isoformat()
        conn = self._get_connection()
        conn.execute("DELETE FROM fusion_history WHERE created_at < ?", (cutoff,))
        conn.commit()
        conn.close()

    def _row_to_event(self, row) -> CachedRiskEvent:
        return CachedRiskEvent(
            zone_id=row["zone_id"], tier=row["tier"],
            composite_risk_score=row["composite_risk_score"],
            timestamp=datetime.fromisoformat(row["created_at"]),
            synced=bool(row["synced"]), row_id=row["id"],
        )

    def get_history_rows_by_zone(self, minutes: int | None = None) -> dict[str, list[dict]]:
        """Full row data (including density + physical_corroboration) per
        zone -- used by the ML predictor's live feature computation,
        which needs the raw inputs, not just tier/score."""
        self._prune_expired()
        conn = self._get_connection()
        if minutes is None:
            rows = conn.execute("SELECT * FROM fusion_history ORDER BY created_at ASC").fetchall()
        else:
            cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()
            rows = conn.execute(
                "SELECT * FROM fusion_history WHERE created_at >= ? ORDER BY created_at ASC", (cutoff,)
            ).fetchall()
        conn.close()

        by_zone: dict[str, list[dict]] = {}
        for r in rows:
            by_zone.setdefault(r["zone_id"], []).append({
                "tier": r["tier"],
                "composite_risk_score": r["composite_risk_score"],
                "density_people_per_m2": r["density_people_per_m2"],
                "physical_corroboration": bool(r["physical_corroboration"]),
                "timestamp": r["created_at"],
            })
        return by_zone

    def get_unsynced_events(self) -> list[CachedRiskEvent]:
        conn = self._get_connection()
        rows = conn.execute("SELECT * FROM fusion_history WHERE synced = 0 ORDER BY created_at ASC").fetchall()
        conn.close()
        return [self._row_to_event(r) for r in rows]

    def sync_queued_events(self) -> int:
        """Call once connectivity is restored. Marks all queued events as
        synced and returns how many were flushed."""
        unsynced = self.get_unsynced_events()
        if not unsynced:
            return 0
        conn = self._get_connection()
        conn.execute("UPDATE fusion_history SET synced = 1 WHERE synced = 0")
        conn.commit()
        conn.close()
        return len(unsynced)

    def get_recent_events(self, minutes: int | None = None) -> list[CachedRiskEvent]:
        self._prune_expired()
        conn = self._get_connection()
        if minutes is None:
            rows = conn.execute("SELECT * FROM fusion_history ORDER BY created_at ASC").fetchall()
        else:
            cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()
            rows = conn.execute(
                "SELECT * FROM fusion_history WHERE created_at >= ? ORDER BY created_at ASC", (cutoff,)
            ).fetchall()
        conn.close()
        return [self._row_to_event(r) for r in rows]

    def get_history_by_zone(self, minutes: int | None = None) -> dict[str, list[CachedRiskEvent]]:
        """Groups the full history by zone_id -- the exact shape Module
        F2's playback timeline needs (a per-zone time series)."""
        events = self.get_recent_events(minutes)
        by_zone: dict[str, list[CachedRiskEvent]] = {}
        for e in events:
            by_zone.setdefault(e.zone_id, []).append(e)
        return by_zone

    def clear_all(self):
        """Wipes all history -- useful for starting a fresh demo/event
        without old test data bleeding into F2's playback."""
        conn = self._get_connection()
        conn.execute("DELETE FROM fusion_history")
        conn.commit()
        conn.close()
