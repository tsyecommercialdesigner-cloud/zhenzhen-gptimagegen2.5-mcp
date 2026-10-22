"""Concurrent protocol calls and durable scheduling, without paid provider traffic."""

import asyncio
import base64
import hashlib
import json
import sqlite3
import subprocess
import sys
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import httpx2
import test_batch as batch_tests
import test_protocol as protocol
from jsonschema import Draft202012Validator
from mcp import Client
from test_core import png

from zhenzhen_image_mcp import media
from zhenzhen_image_mcp.api import API
from zhenzhen_image_mcp.batch import BatchService
from zhenzhen_image_mcp.checkpoints import CheckpointStore
from zhenzhen_image_mcp.config import FLARE
from zhenzhen_image_mcp.monitor import TaskMonitor
from zhenzhen_image_mcp.server import mcp


class ConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    setUp = protocol.ProtocolRecoveryTests.setUp
    call = protocol.ProtocolRecoveryTests.call
    task = protocol.ProtocolRecoveryTests.task
    arguments = batch_tests.BatchProtocolTests.arguments
    install_handler = batch_tests.BatchProtocolTests.install_handler

    def success(self):
        return {"data": [{"b64_json": base64.b64encode(png()).decode()}]}

    async def test_sync_twenty_tasks_five_in_flight_and_hash_verified_replay(self):
        active = peak = 0
        gate, reached = asyncio.Event(), asyncio.Event()

        async def handler(request):
            nonlocal active, peak
            self.requests.append(request)
            active += 1
            peak = max(active, peak)
            if active == 5:
                reached.set()
            await gate.wait()
            active -= 1
            return httpx2.Response(200, json=self.success())

        self.install_handler(handler)
        args = self.arguments(20)
        job = asyncio.create_task(self.call("run_image_batch", args))
        try:
            await asyncio.wait_for(reached.wait(), 10)
            self.assertEqual(len(self.requests), 5)
        finally:
            gate.set()
        result = await job
        self.assertFalse(result.is_error, result.content)
        self.assertEqual(result.structured_content["status"], "COMPLETED")
        self.assertEqual(peak, 5)
        self.assertEqual(len(self.requests), 20)
        self.assertTrue(all(not r.url.query for r in self.requests))
        for item in result.structured_content["tasks"]:
            file = item["result"]["files"][0]
            self.assertEqual(hashlib.sha256(Path(file["path"]).read_bytes()).hexdigest(), file["sha256"])
        replay = await self.call("run_image_batch", args)
        self.assertFalse(replay.is_error, replay.content)
        self.assertTrue(all(t["reused"] for t in replay.structured_content["tasks"]))
        self.assertEqual(len(self.requests), 20)
        async with Client(mcp, mode="legacy") as client:
            tool = next(t for t in (await client.list_tools()).tools if t.name == "run_image_batch")
        Draft202012Validator(tool.output_schema).validate(result.structured_content)

    async def test_parallel_sync_batches_share_process_limit(self):
        active = peak = 0
        gate, reached = asyncio.Event(), asyncio.Event()

        async def handler(request):
            nonlocal active, peak
            self.requests.append(request)
            active += 1
            peak = max(peak, active)
            if active == 5:
                reached.set()
            await gate.wait()
            active -= 1
            return httpx2.Response(200, json=self.success())

        self.install_handler(handler)
        jobs = asyncio.gather(
            *[self.call("run_image_batch", self.arguments(8, thread_id=f"thread-{i}")) for i in range(3)]
        )
        try:
            await asyncio.wait_for(reached.wait(), 10)
            self.assertEqual(len(self.requests), 5)
        finally:
            gate.set()
        values = await jobs
        self.assertTrue(all(not v.is_error for v in values))
        self.assertEqual(len(self.requests), 24)
        self.assertEqual(peak, 5)

    async def test_twenty_async_submissions_can_all_be_in_flight(self):
        gate, reached = asyncio.Event(), asyncio.Event()

        async def handler(request):
            self.requests.append(request)
            if len(self.requests) == 20:
                reached.set()
            await gate.wait()
            index = json.loads(request.content)["prompt"].split()[-1]
            return httpx2.Response(200, json={"data": f"task_{index}"})

        self.install_handler(handler)
        job = asyncio.create_task(self.call("submit_image_batch", self.arguments(20, max_concurrency=20)))
        try:
            await asyncio.wait_for(reached.wait(), 10)
            self.assertEqual(len(self.requests), 20)
        finally:
            gate.set()
        result = await job
        self.assertFalse(result.is_error, result.content)
        self.assertEqual(result.structured_content["status"], "ACCEPTED")
        with CheckpointStore().connection(read_only=True) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM watches").fetchone()[0], 20)

    async def test_single_sync_key_reuses_result_and_rejects_changed_request(self):
        self.sequence = [(200, self.success())]
        args = {"prompt": "test", "model": FLARE, "idempotency_key": "same-key"}
        values = await asyncio.gather(self.call("generate_image", args), self.call("generate_image", args))
        self.assertTrue(any(not v.is_error for v in values))
        replay = await self.call("generate_image", args)
        self.assertFalse(replay.is_error, replay.content)
        self.assertTrue(replay.structured_content["reused"])
        conflict = await self.call("generate_image", {**args, "prompt": "changed"})
        self.assertTrue(conflict.is_error)
        self.assertEqual(len(self.requests), 1)

    async def test_single_async_key_reuses_provider_id_and_sync_mode_conflicts(self):
        self.sequence = [(200, {"data": "provider_same"})]
        args = {"prompt": "test", "model": FLARE, "idempotency_key": "async-key"}
        for _ in range(2):
            result = await self.call("submit_image_generation", args)
            self.assertFalse(result.is_error, result.content)
            self.assertEqual(result.structured_content["task_id"], "provider_same")
        conflict = await self.call("generate_image", args)
        self.assertTrue(conflict.is_error)
        self.assertEqual(len(self.requests), 1)

    async def test_sync_file_tampering_fails_without_new_paid_request(self):
        self.sequence = [(200, self.success())]
        args = self.arguments()
        result = await self.call("run_image_batch", args)
        file = Path(result.structured_content["tasks"][0]["result"]["files"][0]["path"])
        original = file.read_bytes()
        file.write_bytes(bytes([original[0] ^ 1]) + original[1:])
        replay = await self.call("run_image_batch", args)
        self.assertTrue(replay.is_error)
        self.assertIn("hash mismatch", replay.content[0].text)
        self.assertEqual(len(self.requests), 1)

    async def test_sync_unknown_response_is_frozen_and_never_retried(self):
        self.sequence = [httpx2.ReadTimeout("lost response")]
        args = self.arguments()
        for _ in range(2):
            result = await self.call("run_image_batch", args)
            self.assertEqual(result.structured_content["tasks"][0]["status"], "SUBMISSION_UNCERTAIN")
        self.assertEqual(len(self.requests), 1)

    async def test_sync_checkpoint_failure_retains_files_and_blocks_replay(self):
        self.sequence = [(200, self.success())]
        args = self.arguments()
        with patch.object(CheckpointStore, "complete_sync", side_effect=OSError("disk full")):
            result = await self.call("run_image_batch", args)
        item = result.structured_content["tasks"][0]
        self.assertEqual(item["status"], "SUBMISSION_UNCERTAIN")
        self.assertTrue(Path(item["result"]["files"][0]["path"]).is_file())
        replay = await self.call("run_image_batch", args)
        self.assertEqual(replay.structured_content["tasks"][0]["status"], "SUBMITTING")
        self.assertEqual(len(self.requests), 1)

    async def test_sync_partial_download_is_reported_without_regeneration(self):
        self.sequence = [(200, {"data": [{"url": "https://public.example/image.png"}]})]
        args = self.arguments()
        with patch(
            "zhenzhen_image_mcp.media.download",
            side_effect=ValueError("bad image https://public.example/private?token=hidden Bearer hidden"),
        ):
            result = await self.call("run_image_batch", args)
        self.assertEqual(result.structured_content["status"], "ATTENTION_REQUIRED")
        replay = await self.call("run_image_batch", args)
        for response in (result, replay):
            saved = response.structured_content["tasks"][0]["result"]
            self.assertEqual(saved["save_status"], "failed")
            self.assertEqual(saved["download_errors"][0]["index"], 0)
            self.assertIsNone(saved["download_errors"][0]["url"])
            self.assertIn("bad image", saved["download_errors"][0]["error"])
            self.assertNotIn("hidden", json.dumps(saved))
            self.assertNotIn("public.example", json.dumps(saved))
        with CheckpointStore().connection(read_only=True) as db:
            stored = db.execute("SELECT result_json FROM tasks").fetchone()[0]
        self.assertNotIn("hidden", stored)
        self.assertNotIn("public.example", stored)
        self.assertEqual(len(self.requests), 1)

    async def test_invalid_sync_limits_fail_before_payment(self):
        for args in (
            self.arguments(21),
            self.arguments(max_concurrency=6),
            self.arguments(max_concurrency=0),
        ):
            self.assertTrue((await self.call("run_image_batch", args)).is_error)
        self.assertEqual(self.requests, [])


class AutomaticPollingTests(unittest.IsolatedAsyncioTestCase):
    setUp = protocol.ProtocolRecoveryTests.setUp
    call = protocol.ProtocolRecoveryTests.call
    task = protocol.ProtocolRecoveryTests.task
    arguments = batch_tests.BatchProtocolTests.arguments

    def monitor(self):
        from zhenzhen_image_mcp.config import Settings

        return TaskMonitor(API(Settings("https://provider.example/v1", self.root)))

    async def submit(self):
        self.sequence = [(200, {"data": "recover_123"})]
        result = await self.call("submit_image_batch", self.arguments())
        self.assertFalse(result.is_error, result.content)

    async def test_ninety_second_schedule_restart_saved_manifest_and_stop(self):
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=100):
            await self.submit()
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=189):
            await self.monitor().tick()
        self.assertEqual(len(self.requests), 1)
        self.sequence = [self.task("NOT_START")]
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=190):
            await self.monitor().tick()
        self.assertEqual(len(self.requests), 2)
        self.sequence = [self.task()]
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=279):
            await self.monitor().tick()
        self.assertEqual(len(self.requests), 2)
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=280):
            await self.monitor().tick()
        snapshot = await BatchService().snapshot("detail-pages", "product-001")
        item = snapshot["tasks"][0]
        self.assertEqual(item["status"], "SUCCESS")
        self.assertEqual(item["result"]["save_status"], "saved")
        self.assertTrue(Path(item["result"]["files"][0]["path"]).is_file())
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=10000):
            await self.monitor().tick()
        self.assertEqual([r.method for r in self.requests], ["POST", "GET", "GET"])

    async def test_transient_query_retries_only_after_ninety_seconds(self):
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=100):
            await self.submit()
        self.sequence = [(503, {})]
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=190):
            await self.monitor().tick()
            await self.monitor().tick()
        self.assertEqual(len(self.requests), 2)
        self.sequence = [self.task()]
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=280):
            await self.monitor().tick()
        self.assertEqual(len(self.requests), 3)
        self.assertEqual(sum(r.method == "POST" for r in self.requests), 1)

    async def test_successful_provider_task_retries_failed_download_without_resubmission(self):
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=100):
            await self.submit()
        self.sequence = [self.task()]
        with patch("zhenzhen_image_mcp.api.API.store_images", side_effect=ValueError("save failed")):
            with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=190):
                await self.monitor().tick()
        self.sequence = [self.task()]
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=280):
            await self.monitor().tick()
        snapshot = await BatchService().snapshot("detail-pages", "product-001")
        self.assertEqual(snapshot["tasks"][0]["result"]["save_status"], "saved")
        self.assertEqual(sum(r.method == "POST" for r in self.requests), 1)

    async def test_download_diagnostics_survive_polling_and_clear_after_recovery(self):
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=100):
            await self.submit()
        response = self.task()
        response[1]["data"]["data"] = {"data": [{"url": "https://public.example/private?token=hidden"}]}
        self.sequence = [response]
        with patch("zhenzhen_image_mcp.media.download", side_effect=ValueError("Image download HTTP 403")):
            with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=190):
                await self.monitor().tick()
        snapshot = await BatchService().snapshot("detail-pages", "product-001")
        failed = snapshot["tasks"][0]["result"]
        self.assertEqual(failed["save_status"], "failed")
        self.assertIn("403", failed["download_errors"][0]["error"])
        self.assertNotIn("hidden", json.dumps(failed))
        self.assertIsNone(failed["download_errors"][0]["url"])
        self.sequence = [self.task()]
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=280):
            await self.monitor().tick()
        saved = (await BatchService().snapshot("detail-pages", "product-001"))["tasks"][0]["result"]
        self.assertEqual(saved["save_status"], "saved")
        self.assertEqual(saved["download_errors"], [])
        self.assertTrue(Path(saved["files"][0]["path"]).is_file())
        self.assertEqual([r.method for r in self.requests], ["POST", "GET", "GET"])

    async def test_provider_failure_is_terminal_and_never_resubmitted(self):
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=100):
            await self.submit()
        self.sequence = [self.task("FAILURE")]
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=190):
            await self.monitor().tick()
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=1000):
            await self.monitor().tick()
        self.assertEqual(len(self.requests), 2)
        snapshot = await BatchService().snapshot("detail-pages", "product-001")
        self.assertEqual(snapshot["tasks"][0]["status"], "FAILURE")

    async def test_single_async_without_key_is_registered_for_automatic_polling(self):
        self.sequence = [(200, {"data": "recover_123"})]
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=100):
            result = await self.call("submit_image_generation", {"prompt": "test", "model": FLARE})
        self.assertFalse(result.is_error, result.content)
        self.sequence = [self.task()]
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=190):
            await self.monitor().tick()
        self.assertEqual(len(self.requests), 2)
        self.assertTrue(list(self.root.glob("image-*.png")))

    async def test_poll_leases_exclude_other_workers_and_expire_after_crash(self):
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=100):
            await self.submit()
        store = CheckpointStore()
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=190):
            rows = await asyncio.gather(
                *[
                    asyncio.to_thread(store.claim_polls, "https://provider.example/v1", 20, 300)
                    for _ in range(5)
                ]
            )
        claimed = [row for batch in rows for row in batch]
        self.assertEqual(len(claimed), 1)
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=489):
            self.assertEqual(store.claim_polls("https://provider.example/v1", 20, 300), [])
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=490):
            recovered = store.claim_polls("https://provider.example/v1", 20, 300)
        self.assertEqual(len(recovered), 1)
        store.finish_poll(claimed[0], "FAILURE", None)  # Stale worker cannot overwrite new lease.
        with store.connection(read_only=True) as db:
            self.assertEqual(db.execute("SELECT status FROM watches").fetchone()[0], "SUBMITTED")

    async def test_twenty_watches_across_processes_have_one_owner_each(self):
        store = CheckpointStore()
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=1):
            for index in range(20):
                store.watch("https://provider.example/v1", f"task_{index}", str(self.root), "reverse")
        code = (
            "import json,sys; from pathlib import Path; "
            "from zhenzhen_image_mcp.checkpoints import CheckpointStore; "
            "rows=CheckpointStore(Path(sys.argv[1])).claim_polls('https://provider.example/v1',20,300); "
            "print(json.dumps([r['provider_task_id'] for r in rows]))"
        )
        results = await asyncio.gather(
            *[
                asyncio.to_thread(
                    subprocess.run,
                    [sys.executable, "-c", code, str(store.root)],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                for _ in range(4)
            ]
        )
        ids = [value for result in results for value in json.loads(result.stdout)]
        self.assertEqual(len(ids), 20)
        self.assertEqual(len(set(ids)), 20)

    async def test_manual_completion_stops_polling_and_stale_worker_cannot_regress(self):
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=100):
            await self.submit()
        store = CheckpointStore()
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=190):
            row = store.claim_polls("https://provider.example/v1", 5, 300)[0]
            self.sequence = [self.task()]
            result = await self.call("get_image_task", {"task_id": "recover_123"})
            self.assertFalse(result.is_error, result.content)
            store.finish_poll(row, "IN_PROGRESS", {"status": "IN_PROGRESS", "task_id": "recover_123"})
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=1000):
            await self.monitor().tick()
        snapshot = await BatchService().snapshot("detail-pages", "product-001")
        self.assertEqual(snapshot["tasks"][0]["result"]["save_status"], "saved")
        self.assertEqual(snapshot["tasks"][0]["status"], "SUCCESS")
        self.assertEqual(len(self.requests), 2)

    async def test_unknown_submission_and_wrong_provider_are_never_polled(self):
        self.sequence = [httpx2.ReadTimeout("lost submission")]
        await self.call("submit_image_batch", self.arguments())
        store = CheckpointStore()
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=1):
            store.watch("https://other.example/v1", "foreign_task", str(self.root), "reverse")
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=10000):
            await self.monitor().tick()
        self.assertEqual(len(self.requests), 1)

    async def test_legacy_v1_database_migrates_without_losing_idempotency(self):
        store = CheckpointStore()
        store.root.mkdir()
        with closing(sqlite3.connect(store.path)) as db:
            db.execute(
                "CREATE TABLE tasks (checkpointer TEXT,thread_id TEXT,task_id TEXT,fingerprint TEXT,"
                "base_url TEXT,output_dir TEXT,group_name TEXT,status TEXT,provider_task_id TEXT,"
                "error TEXT,created_at REAL,updated_at REAL,PRIMARY KEY(checkpointer,thread_id,task_id))"
            )
            db.execute(
                "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "old",
                    "thread",
                    "item",
                    "fingerprint",
                    "https://provider.example/v1",
                    str(self.root),
                    "reverse",
                    "SUBMITTED",
                    "old_provider",
                    None,
                    1,
                    1,
                ),
            )
            db.execute("PRAGMA user_version=1")
            db.commit()
        with patch("zhenzhen_image_mcp.checkpoints.time.time", return_value=100):
            self.assertFalse(store.claim("old", "thread", "item"))
        self.assertEqual(store.get("old", "thread", "item")["provider_task_id"], "old_provider")
        with store.connection(read_only=True) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 2)
            self.assertEqual(db.execute("PRAGMA journal_mode").fetchone()[0], "wal")
            self.assertEqual(db.execute("SELECT provider_task_id FROM watches").fetchone()[0], "old_provider")

    async def test_server_lifespan_starts_and_stops_monitor(self):
        started, stopped = asyncio.Event(), asyncio.Event()

        async def run(_self):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()

        with patch.object(TaskMonitor, "run", run):
            async with Client(mcp, mode="legacy") as client:
                await client.list_tools()
                await asyncio.wait_for(started.wait(), 5)
            self.assertTrue(stopped.is_set())


class DownloadRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_transient_downloads_retry_without_disabling_validation(self):
        once = AsyncMock(
            side_effect=[httpx.ReadTimeout("timeout"), media.TransientDownloadError("503"), png()]
        )
        with patch("zhenzhen_image_mcp.media._download_once", once):
            with patch("zhenzhen_image_mcp.media.asyncio.sleep", new_callable=AsyncMock):
                self.assertEqual(await media.download("https://public.example/image.png"), png())
        self.assertEqual(once.await_count, 3)

    async def test_bad_image_or_hash_is_not_retried_as_a_transient_error(self):
        once = AsyncMock(side_effect=ValueError("invalid image"))
        with patch("zhenzhen_image_mcp.media._download_once", once):
            with self.assertRaisesRegex(ValueError, "invalid image"):
                await media.download("https://public.example/image.png")
        self.assertEqual(once.await_count, 1)
