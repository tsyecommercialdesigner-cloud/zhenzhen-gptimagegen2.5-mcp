"""Upgrade/restore and interrupted migrations use only synthetic local ledgers."""

import asyncio
import hashlib
import shutil
import sqlite3
import subprocess
import sys
import textwrap
import unittest
from contextlib import closing
from unittest.mock import patch

import test_batch as batch_tests
import test_protocol as protocol

from zhenzhen_image_mcp.api import API
from zhenzhen_image_mcp.batch import BatchService
from zhenzhen_image_mcp.checkpoints import CheckpointStore
from zhenzhen_image_mcp.monitor import TaskMonitor


class MigrationRecoveryTests(unittest.IsolatedAsyncioTestCase):
    setUp = protocol.ProtocolRecoveryTests.setUp
    call = protocol.ProtocolRecoveryTests.call
    task = protocol.ProtocolRecoveryTests.task
    arguments = batch_tests.BatchProtocolTests.arguments

    async def legacy_store(self):
        store = CheckpointStore()
        store.root.mkdir()
        rows = []
        for index, task in enumerate(self.arguments(2)["tasks"]):
            prepared = await API().prepare_images(task["prompt"], task["model"], asynchronous=True)
            rows.append(
                (
                    "detail-pages",
                    "product-001",
                    task["task_id"],
                    prepared.fingerprint,
                    "https://provider.example/v1",
                    str(prepared.directory),
                    "reverse",
                    "SUBMITTED" if index == 0 else "SUBMISSION_UNCERTAIN",
                    "recover_123" if index == 0 else None,
                    None if index == 0 else "Unknown submission outcome",
                    1,
                    1,
                )
            )
        with closing(sqlite3.connect(store.path)) as db:
            db.execute(
                "CREATE TABLE tasks (checkpointer TEXT,thread_id TEXT,task_id TEXT,fingerprint TEXT,"
                "base_url TEXT,output_dir TEXT,group_name TEXT,status TEXT,provider_task_id TEXT,"
                "error TEXT,created_at REAL,updated_at REAL,PRIMARY KEY(checkpointer,thread_id,task_id))"
            )
            db.executemany("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
            db.execute("PRAGMA user_version=1")
            db.commit()
        return store, rows

    def inspect_legacy(self, path, rows):
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 1)
            self.assertNotIn("result_json", [column[1] for column in db.execute("PRAGMA table_info(tasks)")])
            self.assertEqual(db.execute("SELECT * FROM tasks ORDER BY task_id").fetchall(), rows)
            self.assertEqual(db.execute("SELECT name FROM sqlite_master WHERE name='watches'").fetchall(), [])

    async def test_backup_upgrade_restart_query_recovery_and_no_resubmission(self):
        store, rows = await self.legacy_store()
        backup = self.root / "v1-backup.sqlite3"
        with closing(sqlite3.connect(store.path)) as source:
            with closing(sqlite3.connect(backup)) as destination:
                source.backup(destination)
        backup_hash = hashlib.sha256(backup.read_bytes()).hexdigest()
        fixture_env = self.root / ".env"
        fixture_env.write_text("SYNTHETIC_KEY=fixture-only\n", encoding="utf-8")
        env_hash = hashlib.sha256(fixture_env.read_bytes()).hexdigest()

        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=100):
            # A new process opening a v1 ledger migrates it without claiming a paid submission.
            self.assertEqual(store.claim_polls("https://provider.example/v1", 5, 300), [])
            replay = await self.call("submit_image_batch", self.arguments(2))
        self.assertFalse(replay.is_error, replay.content)
        self.assertTrue(all(task["reused"] for task in replay.structured_content["tasks"]))
        self.assertEqual(replay.structured_content["tasks"][1]["status"], "SUBMISSION_UNCERTAIN")
        self.assertEqual(self.requests, [])

        self.sequence = [(503, {})]
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=190):
            await TaskMonitor(API(), CheckpointStore()).tick()
        self.sequence = [self.task()]
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=280):
            # Recreate both services: restoration must use only the durable provider identity.
            await TaskMonitor(API(), CheckpointStore()).tick()
        snapshot = await BatchService().snapshot("detail-pages", "product-001")
        first, uncertain = snapshot["tasks"]
        self.assertEqual(first["provider_task_id"], "recover_123")
        self.assertEqual(first["result"]["save_status"], "saved")
        self.assertEqual(uncertain["status"], "SUBMISSION_UNCERTAIN")
        self.assertEqual([request.method for request in self.requests], ["GET", "GET"])
        self.assertEqual(len({str(request.url) for request in self.requests}), 1)
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=1000):
            await TaskMonitor(API(), CheckpointStore()).tick()
        self.assertEqual(len(self.requests), 2)

        self.inspect_legacy(backup, rows)
        self.assertEqual(hashlib.sha256(backup.read_bytes()).hexdigest(), backup_hash)
        self.assertEqual(hashlib.sha256(fixture_env.read_bytes()).hexdigest(), env_hash)
        restored = CheckpointStore(self.root / "restored")
        restored.root.mkdir()
        shutil.copyfile(backup, restored.path)
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=100):
            self.assertFalse(restored.claim("detail-pages", "product-001", "page_0"))
            self.assertFalse(restored.claim("detail-pages", "product-001", "page_1"))
        with restored.connection(read_only=True) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 2)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM watches").fetchone()[0], 1)
        self.assertEqual(restored.get("detail-pages", "product-001", "page_0")["fingerprint"], rows[0][3])

    async def test_interrupted_schema_migration_rolls_back_and_can_resume(self):
        store, rows = await self.legacy_store()
        real_connect = sqlite3.connect

        class InterruptedMigration(sqlite3.Connection):
            def execute(self, statement, parameters=(), /):
                if "CREATE TABLE IF NOT EXISTS watches" in statement:
                    # Real SQLite failure after ALTER TABLE but before watches/version publication.
                    return super().execute("SELECT FROM invalid")
                return super().execute(statement, parameters)

        def connect(*args, **kwargs):
            return real_connect(*args, **kwargs, factory=InterruptedMigration)

        with patch("zhenzhen_image_mcp.checkpoints.sqlite3.connect", connect):
            with self.assertRaisesRegex(ValueError, "no automatic resubmission"):
                store.claim("detail-pages", "product-001", "page_0")
        self.inspect_legacy(store.path, rows)
        # No partial column/table remains; retrying the migration must succeed exactly once.
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=100):
            for _ in range(2):
                self.assertFalse(CheckpointStore().claim("detail-pages", "product-001", "page_0"))
                self.assertFalse(CheckpointStore().claim("detail-pages", "product-001", "page_1"))
        with store.connection(read_only=True) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 2)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM watches").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0], 2)
        self.assertEqual(store.get("detail-pages", "product-001", "page_0")["fingerprint"], rows[0][3])
        self.assertEqual(self.requests, [])

    async def test_process_exit_during_migration_recovers_original_ledger(self):
        store, rows = await self.legacy_store()
        code = textwrap.dedent("""
            import os, sqlite3, sys
            from pathlib import Path
            from unittest.mock import patch
            from zhenzhen_image_mcp.checkpoints import CheckpointStore
            real_connect = sqlite3.connect
            class Interrupted(sqlite3.Connection):
                def execute(self, statement, parameters=(), /):
                    if 'CREATE TABLE IF NOT EXISTS watches' in statement:
                        os._exit(23)
                    return super().execute(statement, parameters)
            def connect(*args, **kwargs):
                return real_connect(*args, **kwargs, factory=Interrupted)
            with patch('zhenzhen_image_mcp.checkpoints.sqlite3.connect', connect):
                CheckpointStore(Path(sys.argv[1])).claim('detail-pages', 'product-001', 'page_0')
            """)
        result = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, "-c", code, str(store.root)],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        self.assertEqual(result.returncode, 23, result.stderr)
        self.inspect_legacy(store.path, rows)
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=100):
            self.assertFalse(CheckpointStore().claim("detail-pages", "product-001", "page_0"))
            self.assertFalse(CheckpointStore().claim("detail-pages", "product-001", "page_1"))
        with store.connection(read_only=True) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 2)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM watches").fetchone()[0], 1)
        self.assertEqual(self.requests, [])
