"""SQLite persistence for GroupAnalysis records across pipeline runs.

Two tables:
  runs      — one row per pipeline execution (daily or backfill)
  analyses  — one row per topic group per run

Timeline queries use period_start/period_end (article publication dates),
not run_date, so backfill records are stamped with when the content was
written rather than when the pipeline ran.

Idempotency: (topic, period_start, period_end) is unique — re-running a
backfill over the same date range produces no duplicates.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Generator

from sources.base import Item

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "output" / "analyses.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date    TEXT    NOT NULL,
    is_backfill INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS analyses (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              INTEGER NOT NULL REFERENCES runs(id),
    topic               TEXT    NOT NULL,
    period_start        TEXT    NOT NULL,
    period_end          TEXT    NOT NULL,
    agreements_json     TEXT    NOT NULL,
    contradictions_json TEXT    NOT NULL,
    debunks_json        TEXT    NOT NULL,
    unresolved_json     TEXT    NOT NULL,
    sources_json        TEXT    NOT NULL,
    UNIQUE (topic, period_start, period_end)
);

CREATE INDEX IF NOT EXISTS idx_analyses_topic  ON analyses(topic);
CREATE INDEX IF NOT EXISTS idx_analyses_period ON analyses(period_start);
"""


@dataclass
class GroupAnalysis:
    """Structured compare-and-contrast result for one topic group.

    Produced by analyst.py; persisted and retrieved by store.py.
    period_start/period_end reflect the publication dates of the source
    articles, not the date the pipeline ran.
    """

    topic: str
    run_date: date
    period_start: datetime
    period_end: datetime
    agreements: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    debunks: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    sources: list[Item] = field(default_factory=list)


# ---------- serialization helpers ----------

def _item_to_dict(item: Item) -> dict[str, Any]:
    return {
        "source": item.source,
        "title": item.title,
        "url": item.url,
        "score": item.score,
        "published_at": item.published_at.isoformat(),
        "summary_raw": item.summary_raw,
        "extra": item.extra,
    }


def _dict_to_item(d: dict[str, Any]) -> Item:
    return Item(
        source=d["source"],
        title=d["title"],
        url=d["url"],
        score=d["score"],
        published_at=datetime.fromisoformat(d["published_at"]).replace(tzinfo=timezone.utc),
        summary_raw=d.get("summary_raw", ""),
        extra=d.get("extra", {}),
    )


def _row_to_analysis(row: sqlite3.Row, run_date: date) -> GroupAnalysis:
    return GroupAnalysis(
        topic=row["topic"],
        run_date=run_date,
        period_start=datetime.fromisoformat(row["period_start"]).replace(tzinfo=timezone.utc),
        period_end=datetime.fromisoformat(row["period_end"]).replace(tzinfo=timezone.utc),
        agreements=json.loads(row["agreements_json"]),
        contradictions=json.loads(row["contradictions_json"]),
        debunks=json.loads(row["debunks_json"]),
        unresolved=json.loads(row["unresolved_json"]),
        sources=[_dict_to_item(d) for d in json.loads(row["sources_json"])],
    )


# ---------- store ----------

class Store:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._init()

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init(self) -> None:
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    def save_run(
        self,
        analyses: list[GroupAnalysis],
        run_date: date,
        is_backfill: bool = False,
    ) -> int:
        """Persist a set of analyses for one pipeline run.

        Returns the run_id. On (topic, period_start, period_end) conflict
        the duplicate analysis row is silently skipped (INSERT OR IGNORE),
        but the run row is still created.
        """
        with self._conn() as conn:
            cursor = conn.execute(
                "INSERT INTO runs (run_date, is_backfill) VALUES (?, ?)",
                (run_date.isoformat(), int(is_backfill)),
            )
            run_id = cursor.lastrowid

            skipped = 0
            for analysis in analyses:
                result = conn.execute(
                    """
                    INSERT OR IGNORE INTO analyses
                        (run_id, topic, period_start, period_end,
                         agreements_json, contradictions_json, debunks_json,
                         unresolved_json, sources_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        analysis.topic,
                        analysis.period_start.isoformat(),
                        analysis.period_end.isoformat(),
                        json.dumps(analysis.agreements),
                        json.dumps(analysis.contradictions),
                        json.dumps(analysis.debunks),
                        json.dumps(analysis.unresolved),
                        json.dumps([_item_to_dict(i) for i in analysis.sources]),
                    ),
                )
                if result.rowcount == 0:
                    skipped += 1

        if skipped:
            logger.info("Store: skipped %d duplicate analysis row(s) for run %d", skipped, run_id)
        logger.info("Store: saved run %d (%d analyses, backfill=%s)", run_id, len(analyses) - skipped, is_backfill)
        return run_id

    def get_timeline(self, topic: str) -> list[GroupAnalysis]:
        """All analyses for a topic, ordered chronologically by period_start."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT a.*, r.run_date
                FROM analyses a
                JOIN runs r ON r.id = a.run_id
                WHERE a.topic = ?
                ORDER BY a.period_start ASC
                """,
                (topic,),
            ).fetchall()

        return [_row_to_analysis(row, date.fromisoformat(row["run_date"])) for row in rows]

    def get_run(self, run_id: int) -> list[GroupAnalysis]:
        """All analyses for a specific run, ordered by topic."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT a.*, r.run_date
                FROM analyses a
                JOIN runs r ON r.id = a.run_id
                WHERE a.run_id = ?
                ORDER BY a.topic ASC
                """,
                (run_id,),
            ).fetchall()

        return [_row_to_analysis(row, date.fromisoformat(row["run_date"])) for row in rows]

    def topics(self) -> list[str]:
        """All distinct topic labels in the store, alphabetically."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT topic FROM analyses ORDER BY topic ASC"
            ).fetchall()
        return [row["topic"] for row in rows]

    def latest_run_id(self) -> int | None:
        """The most recently created run ID, or None if the store is empty."""
        with self._conn() as conn:
            row = conn.execute("SELECT MAX(id) as id FROM runs").fetchone()
        return row["id"] if row and row["id"] is not None else None
