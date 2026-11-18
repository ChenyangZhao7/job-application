from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from job_agent.models import ApplicationRecord


class Tracker:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS applications (
                    platform TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    company TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    score INTEGER DEFAULT 0,
                    message TEXT DEFAULT '',
                    status TEXT DEFAULT 'submitted',
                    submitted_at TEXT DEFAULT '',
                    last_checked_at TEXT DEFAULT '',
                    writer_backend TEXT DEFAULT '',
                    provider TEXT DEFAULT '',
                    memory_version TEXT DEFAULT '',
                    PRIMARY KEY (platform, job_id)
                )
                """
            )

    def record(self, record: ApplicationRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO applications
                (platform, job_id, company, title, url, score, message, status,
                 submitted_at, last_checked_at, writer_backend, provider, memory_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.platform,
                    record.job_id,
                    record.company,
                    record.title,
                    record.url,
                    record.score,
                    record.message,
                    record.status,
                    record.submitted_at,
                    record.last_checked_at,
                    record.writer_backend,
                    record.provider,
                    record.memory_version,
                ),
            )

    def exists(self, platform: str, job_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM applications WHERE platform = ? AND job_id = ? LIMIT 1",
                (platform, job_id),
            ).fetchone()
            return row is not None

    def mark(self, platform: str, job_id: str, status: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE applications SET status = ?, last_checked_at = ? "
                "WHERE platform = ? AND job_id = ?",
                (status, datetime.now(timezone.utc).isoformat(), platform, job_id),
            )

    def list(self, status: str | None = None) -> list[ApplicationRecord]:
        query = "SELECT * FROM applications"
        params: tuple[str, ...] = ()
        if status is not None:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY submitted_at DESC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [ApplicationRecord(**dict(row)) for row in rows]

    def follow_ups(self, days: int) -> list[ApplicationRecord]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM applications WHERE status = 'submitted' "
                "AND submitted_at < ? ORDER BY submitted_at ASC",
                (cutoff,),
            ).fetchall()
        return [ApplicationRecord(**dict(row)) for row in rows]
