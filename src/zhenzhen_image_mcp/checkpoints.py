"""SQLite checkpoint ledger: durable claims precede every billable batch POST."""

from __future__ import annotations

import re
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .config import PROJECT_DIR
from .tasks import task_id_check

UNCERTAIN = "Submission outcome is uncertain. Do not resubmit; verify with the provider."
KEY_PATTERN = r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}"


def scope_check(checkpointer: str, thread_id: str) -> None:
    for name, value in (("checkpointer", checkpointer), ("thread_id", thread_id)):
        if not re.fullmatch(KEY_PATTERN, value):
            raise ValueError(f"{name} must match {KEY_PATTERN}")


class CheckpointStore:
    """Shared across processes; no prompts, input images or credentials are stored."""

    def __init__(self, root: Path | None = None):
        self.root = root if root is not None else PROJECT_DIR / ".runtime"
        self.path = self.root / "checkpoints.sqlite3"

    @contextmanager
    def connection(self, *, read_only: bool = False):
        if self.root.is_symlink() or self.root.is_junction() or self.path.is_symlink():
            raise ValueError("Checkpoint storage must not be a link")
        if not read_only:
            self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        connection = None
        try:
            target = self.path.resolve().as_uri() + "?mode=ro" if read_only else str(self.path)
            connection = sqlite3.connect(target, timeout=5, isolation_level=None, uri=read_only)
            connection.row_factory = sqlite3.Row
            if not read_only:
                connection.execute("PRAGMA synchronous=FULL")
            connection.execute("BEGIN" if read_only else "BEGIN IMMEDIATE")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in ({1} if read_only else {0, 1}):
                raise ValueError("Unsupported checkpoint database version; preserve the file")
            if read_only:
                yield connection
                return
            connection.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    checkpointer TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    base_url TEXT NOT NULL,
                    output_dir TEXT NOT NULL,
                    group_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    provider_task_id TEXT,
                    error TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (checkpointer, thread_id, task_id)
                )
            """)
            connection.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS provider_identity
                ON tasks (base_url, provider_task_id) WHERE provider_task_id IS NOT NULL
            """)
            connection.execute("PRAGMA user_version=1")
            yield connection
            connection.commit()
        except sqlite3.Error:
            raise ValueError(
                "Checkpoint database unavailable or invalid; no automatic resubmission"
            ) from None
        finally:
            if connection is not None:
                connection.close()  # Rolls back unfinished transactions, including conflicts.

    def reserve(self, checkpointer: str, thread_id: str, tasks: list[dict[str, Any]]) -> None:
        """Reserve a whole validated batch atomically, rejecting any changed request."""
        scope_check(checkpointer, thread_id)
        with self.connection() as db:
            count = db.execute(
                "SELECT COUNT(*) FROM tasks WHERE checkpointer=? AND thread_id=?", (checkpointer, thread_id)
            ).fetchone()[0]
            for task in tasks:
                task_id_check(task["task_id"])
                key = (checkpointer, thread_id, task["task_id"])
                row = db.execute(
                    "SELECT fingerprint FROM tasks WHERE checkpointer=? AND thread_id=? AND task_id=?", key
                ).fetchone()
                if row is not None:
                    if row["fingerprint"] != task["fingerprint"]:
                        raise ValueError(
                            f"Idempotency conflict for task_id={task['task_id']}; no batch POST sent"
                        )
                    continue
                count += 1
                if count > 1000:
                    raise ValueError("Checkpoint thread has reached the 1000-task limit; use a new thread_id")
                now = time.time()
                db.execute(
                    "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,'RESERVED',NULL,NULL,?,?)",
                    (
                        *key,
                        task["fingerprint"],
                        task["base_url"],
                        task["output_dir"],
                        task["group"],
                        now,
                        now,
                    ),
                )

    def claim(self, checkpointer: str, thread_id: str, task_id: str) -> bool:
        with self.connection() as db:
            cursor = db.execute(
                "UPDATE tasks SET status='SUBMITTING', updated_at=? "
                "WHERE checkpointer=? AND thread_id=? AND task_id=? AND status='RESERVED'",
                (time.time(), checkpointer, thread_id, task_id),
            )
            return cursor.rowcount == 1

    def finish(self, checkpointer: str, thread_id: str, task_id: str, provider_task_id: str | None) -> None:
        if provider_task_id is not None:
            task_id_check(provider_task_id)
        with self.connection() as db:
            cursor = db.execute(
                "UPDATE tasks SET status=?, provider_task_id=?, error=?, updated_at=? "
                "WHERE checkpointer=? AND thread_id=? AND task_id=? AND status='SUBMITTING'",
                (
                    "SUBMITTED" if provider_task_id else "SUBMISSION_UNCERTAIN",
                    provider_task_id,
                    None if provider_task_id else UNCERTAIN,
                    time.time(),
                    checkpointer,
                    thread_id,
                    task_id,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("Checkpoint submission claim changed; preserve the provider task ID")

    def get(self, checkpointer: str, thread_id: str, task_id: str) -> dict[str, Any]:
        scope_check(checkpointer, thread_id)
        task_id_check(task_id)
        with self.connection(read_only=True) as db:
            row = db.execute(
                "SELECT * FROM tasks WHERE checkpointer=? AND thread_id=? AND task_id=?",
                (checkpointer, thread_id, task_id),
            ).fetchone()
            if row is None:
                raise ValueError("Checkpoint task not found; check checkpointer, thread_id and task_id")
            return dict(row)

    def list(self, checkpointer: str, thread_id: str) -> list[dict[str, Any]]:
        scope_check(checkpointer, thread_id)
        if not self.path.exists():
            return []
        with self.connection(read_only=True) as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM tasks WHERE checkpointer=? AND thread_id=? ORDER BY created_at, task_id",
                    (checkpointer, thread_id),
                )
            ]

    def observe(self, checkpointer: str, thread_id: str, task_id: str, status: str) -> None:
        # A slow concurrent GET must not regress a terminal state.
        with self.connection() as db:
            db.execute(
                "UPDATE tasks SET status=?, updated_at=? "
                "WHERE checkpointer=? AND thread_id=? AND task_id=? AND status NOT IN ('SUCCESS','FAILURE')",
                (status, time.time(), checkpointer, thread_id, task_id),
            )
