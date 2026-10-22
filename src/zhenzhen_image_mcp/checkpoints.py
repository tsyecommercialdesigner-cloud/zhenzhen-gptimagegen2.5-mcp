"""SQLite checkpoint ledger: durable claims precede every billable batch POST."""

from __future__ import annotations

import builtins
import json
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .config import PROJECT_DIR
from .tasks import task_id_check

UNCERTAIN = "Submission outcome is uncertain. Do not resubmit; verify with the provider."
KEY_PATTERN = r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}"
POLL_INTERVAL = 90


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
                # Switching a newly created DB to WAL can return BUSY immediately even
                # with a busy timeout. Retry only this pre-transaction initialization.
                for attempt in range(10):
                    try:
                        connection.execute("PRAGMA journal_mode=WAL")
                        break
                    except sqlite3.OperationalError as exc:
                        if exc.sqlite_errorcode != sqlite3.SQLITE_BUSY or attempt == 9:
                            raise
                        time.sleep(min(0.01 * 2**attempt, 0.25))
                connection.execute("PRAGMA synchronous=FULL")
            connection.execute("BEGIN" if read_only else "BEGIN IMMEDIATE")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in ({1, 2} if read_only else {0, 1, 2}):
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
            if version < 2:
                connection.execute("ALTER TABLE tasks ADD COLUMN result_json TEXT")
            connection.execute("""
                CREATE TABLE IF NOT EXISTS watches (
                    base_url TEXT NOT NULL,
                    provider_task_id TEXT NOT NULL,
                    output_dir TEXT NOT NULL,
                    group_name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'SUBMITTED',
                    save_status TEXT,
                    result_json TEXT,
                    next_poll_at REAL NOT NULL,
                    lease_token TEXT,
                    lease_until REAL NOT NULL DEFAULT 0,
                    poll_attempts INTEGER NOT NULL DEFAULT 0,
                    error TEXT,
                    PRIMARY KEY (base_url, provider_task_id)
                )
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS pending_polls ON watches (base_url, next_poll_at)
                WHERE status != 'FAILURE' AND (save_status IS NULL OR save_status != 'saved')
            """)
            # Old acknowledged batches are recoverable without storing or replaying their inputs.
            if version < 2:
                connection.execute(
                    """
                INSERT OR IGNORE INTO watches
                    (base_url, provider_task_id, output_dir, group_name, status, next_poll_at)
                SELECT base_url, provider_task_id, output_dir, group_name, status, ? FROM tasks
                WHERE provider_task_id IS NOT NULL AND status != 'FAILURE'
                    """,
                    (time.time() + POLL_INTERVAL,),
                )
            connection.execute("PRAGMA user_version=2")
            yield connection
            connection.commit()
        except sqlite3.Error as exc:
            raise ValueError(
                f"Checkpoint database unavailable or invalid ({exc.sqlite_errorname}); no automatic resubmission"
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
                    "INSERT INTO tasks (checkpointer,thread_id,task_id,fingerprint,base_url,output_dir,"
                    "group_name,status,provider_task_id,error,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,?,?,'RESERVED',NULL,NULL,?,?)",
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

    def complete_sync(self, checkpointer: str, thread_id: str, task_id: str, result: dict) -> None:
        with self.connection() as db:
            cursor = db.execute(
                "UPDATE tasks SET status='SUCCESS', result_json=?, updated_at=? "
                "WHERE checkpointer=? AND thread_id=? AND task_id=? AND status='SUBMITTING'",
                (json.dumps(result), time.time(), checkpointer, thread_id, task_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("Checkpoint submission claim changed; do not resubmit")

    def watch(self, base_url: str, task_id: str, output_dir: str, group: str) -> None:
        task_id_check(task_id)
        with self.connection() as db:
            db.execute(
                "INSERT OR IGNORE INTO watches "
                "(base_url,provider_task_id,output_dir,group_name,next_poll_at) VALUES (?,?,?,?,?)",
                (base_url, task_id, output_dir, group, time.time() + POLL_INTERVAL),
            )

    def observe_provider(self, base_url: str, task_id: str, status: str, result: dict | None) -> None:
        """Manual queries can finish a watch; stale background leases cannot undo that result."""
        if not self.path.exists():
            return
        saved = result.get("save_status") if result else None
        terminal = status == "FAILURE" or saved == "saved"
        encoded = json.dumps(result) if result else None
        with self.connection() as db:
            cursor = db.execute(
                "UPDATE watches SET status=?, save_status=COALESCE(?,save_status), "
                "result_json=CASE WHEN ?='FAILURE' THEN NULL ELSE COALESCE(?,result_json) END, "
                "next_poll_at=MAX(next_poll_at,?), error=NULL, "
                "lease_token=CASE WHEN ? THEN NULL ELSE lease_token END, "
                "lease_until=CASE WHEN ? THEN 0 ELSE lease_until END "
                "WHERE base_url=? AND provider_task_id=? AND (status NOT IN ('SUCCESS','FAILURE') "
                "OR (status=? AND (save_status IS NULL OR save_status!='saved' OR ?='saved')))",
                (
                    status,
                    saved,
                    status,
                    encoded,
                    time.time() + POLL_INTERVAL,
                    terminal,
                    terminal,
                    base_url,
                    task_id,
                    status,
                    saved,
                ),
            )
            if cursor.rowcount:
                db.execute(
                    "UPDATE tasks SET status=?, result_json=CASE WHEN ?='FAILURE' THEN NULL "
                    "ELSE COALESCE(?,result_json) END, updated_at=? WHERE base_url=? AND provider_task_id=?",
                    (status, status, encoded, time.time(), base_url, task_id),
                )

    def claim_polls(self, base_url: str, limit: int, lease_seconds: float) -> builtins.list[dict[str, Any]]:
        if not self.path.exists():
            return []
        now = time.time()
        with self.connection() as db:
            rows = db.execute(
                "SELECT * FROM watches WHERE base_url=? AND status != 'FAILURE' "
                "AND (save_status IS NULL OR save_status != 'saved') "
                "AND next_poll_at<=? AND lease_until<=? ORDER BY next_poll_at LIMIT ?",
                (base_url, now, now, limit),
            ).fetchall()
            claimed = []
            for row in rows:
                token = uuid.uuid4().hex
                db.execute(
                    "UPDATE watches SET lease_token=?, lease_until=?, next_poll_at=?, "
                    "poll_attempts=poll_attempts+1 WHERE base_url=? AND provider_task_id=?",
                    (token, now + lease_seconds, now + POLL_INTERVAL, base_url, row["provider_task_id"]),
                )
                claimed.append({**dict(row), "lease_token": token})
            return claimed

    def finish_poll(self, row: dict, status: str | None, result: dict | None) -> None:
        """Only the current lease holder can publish; terminal state never regresses."""
        with self.connection() as db:
            cursor = db.execute(
                "UPDATE watches SET status=CASE WHEN status IN ('SUCCESS','FAILURE') THEN status "
                "ELSE COALESCE(?,status) END, save_status=COALESCE(?,save_status), "
                "result_json=COALESCE(?,result_json), next_poll_at=?, lease_token=NULL, lease_until=0, "
                "error=? WHERE base_url=? AND provider_task_id=? AND lease_token=?",
                (
                    status,
                    result.get("save_status") if result else None,
                    json.dumps(result) if result else None,
                    time.time() + POLL_INTERVAL,
                    "Result retrieval failed; will retry without resubmission"
                    if status != "FAILURE" and result is None
                    else None,
                    row["base_url"],
                    row["provider_task_id"],
                    row["lease_token"],
                ),
            )
            if cursor.rowcount:
                db.execute(
                    "UPDATE tasks SET status=CASE WHEN status IN ('SUCCESS','FAILURE') THEN status "
                    "ELSE COALESCE(?,status) END, result_json=COALESCE(?,result_json), updated_at=? "
                    "WHERE base_url=? AND provider_task_id=?",
                    (
                        status,
                        json.dumps(result) if result else None,
                        time.time(),
                        row["base_url"],
                        row["provider_task_id"],
                    ),
                )
