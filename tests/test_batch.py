"""Real MCP protocol + official SDK transport, with no billable network access."""

import asyncio
import json
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx2
import test_protocol as protocol
from jsonschema import Draft202012Validator
from mcp import Client
from openai import AsyncOpenAI
from test_core import png

from zhenzhen_image_mcp.api import API
from zhenzhen_image_mcp.batch import BatchService
from zhenzhen_image_mcp.checkpoints import CheckpointStore
from zhenzhen_image_mcp.config import FLARE
from zhenzhen_image_mcp.contracts import BatchImageTask
from zhenzhen_image_mcp.server import mcp


class BatchProtocolTests(unittest.IsolatedAsyncioTestCase):
    call = protocol.ProtocolRecoveryTests.call
    task = protocol.ProtocolRecoveryTests.task

    def setUp(self):
        protocol.ProtocolRecoveryTests.setUp(self)
        mock = patch("zhenzhen_image_mcp.checkpoints.PROJECT_DIR", self.root)
        mock.start()
        self.addCleanup(mock.stop)

    def arguments(self, count=1, **kwargs):
        result = {
            "checkpointer": "detail-pages",
            "thread_id": "product-001",
            "tasks": [
                {"task_id": f"page_{i}", "model": FLARE, "prompt": f"blue garbage bag page {i}"}
                for i in range(count)
            ],
        }
        result.update(kwargs)
        return result

    async def submit(self, count=1, **kwargs):
        return await self.call("submit_image_batch", self.arguments(count, **kwargs))

    def install_handler(self, handler):
        def sdk(instance, key):
            return AsyncOpenAI(
                api_key=key,
                base_url="https://provider.example/v1/",
                max_retries=0,
                http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
            )

        mock = patch.object(API, "sdk", sdk)
        mock.start()
        self.addCleanup(mock.stop)

    async def test_twenty_tasks_one_tool_call_bounded_parallel_posts_no_generation_wait(self):
        active = peak = 0
        gate = asyncio.Event()
        reached = asyncio.Event()

        async def handler(request):
            nonlocal active, peak
            self.requests.append(request)
            active += 1
            peak = max(peak, active)
            if active == 5:
                reached.set()
            await gate.wait()
            active -= 1
            index = json.loads(request.content)["prompt"].rsplit(" ", 1)[-1]
            return httpx2.Response(200, json={"code": "success", "data": f"provider_{index}"})

        self.install_handler(handler)
        pending = asyncio.create_task(self.submit(20))
        try:
            await asyncio.wait_for(reached.wait(), 10)
            self.assertEqual(len(self.requests), 5)
            # The checkpoint read can run while the batch's POSTs are awaiting acknowledgements.
            snapshot = await self.call(
                "get_image_batch", {"checkpointer": "detail-pages", "thread_id": "product-001"}
            )
            self.assertFalse(snapshot.is_error)
            self.assertEqual(len(snapshot.structured_content["tasks"]), 20)
        finally:
            gate.set()
        result = await pending
        self.assertFalse(result.is_error)
        self.assertEqual(result.structured_content["status"], "ACCEPTED")
        self.assertEqual(
            [t["task_id"] for t in result.structured_content["tasks"]], [f"page_{i}" for i in range(20)]
        )
        self.assertEqual(peak, 5)
        self.assertEqual(len(self.requests), 20)
        self.assertTrue(all(r.method == "POST" and r.url.query == b"async=true" for r in self.requests))
        self.assertTrue(all(set(json.loads(r.content)) == {"prompt", "model"} for r in self.requests))
        self.assertFalse(list(self.root.glob("*.png")))

    async def test_simultaneous_duplicate_calls_and_restart_reuse_provider_ids(self):
        async def handler(request):
            self.requests.append(request)
            await asyncio.sleep(0.02)
            index = json.loads(request.content)["prompt"].rsplit(" ", 1)[-1]
            return httpx2.Response(200, json={"data": f"provider_{index}"})

        self.install_handler(handler)
        results = await asyncio.gather(self.submit(3), self.submit(3))
        self.assertTrue(all(not result.is_error for result in results), [r.content for r in results])
        self.assertEqual(len(self.requests), 3)
        # Every tool call constructs a new service/store, as after an MCP restart.
        replay = await self.submit(3, max_concurrency=1)
        self.assertTrue(all(t["reused"] for t in replay.structured_content["tasks"]))
        self.assertEqual(
            [t["provider_task_id"] for t in replay.structured_content["tasks"]],
            [f"provider_{i}" for i in range(3)],
        )
        self.assertEqual(len(self.requests), 3)

    async def test_conflicting_item_rolls_back_entire_new_batch_before_post(self):
        self.sequence = [(200, {"data": "provider_0"})]
        await self.submit()
        args = self.arguments(2)
        args["tasks"].reverse()  # A new task precedes the conflicting existing task.
        args["tasks"][1]["prompt"] = "different request"
        result = await self.call("submit_image_batch", args)
        self.assertTrue(result.is_error)
        self.assertIn("Idempotency conflict", result.content[0].text)
        snapshot = await BatchService().snapshot("detail-pages", "product-001")
        self.assertEqual(len(snapshot["tasks"]), 1)
        self.assertEqual(len(self.requests), 1)

    async def test_identity_is_scoped_by_checkpointer_and_thread(self):
        self.sequence = [(200, {"data": f"provider_{i}"}) for i in range(3)]
        for override in ({}, {"thread_id": "other-thread"}, {"checkpointer": "other-checkpointer"}):
            result = await self.submit(**override)
            self.assertFalse(result.is_error)
        self.assertEqual(len(self.requests), 3)

    async def test_invalid_batch_inputs_rejected_before_any_post(self):
        cases = []
        for override in (
            {"max_concurrency": 0},
            {"max_concurrency": 21},
            {"max_concurrency": "3"},
            {"checkpointer": "../escape"},
            {"thread_id": ""},
            {"unknown": True},
        ):
            cases.append(self.arguments(**override))
        cases.extend([self.arguments(0), self.arguments(21)])
        duplicate = self.arguments(2)
        duplicate["tasks"][1]["task_id"] = "page_0"
        cases.append(duplicate)
        for field, value in (
            ("task_id", "../../escape"),
            ("unknown", True),
            ("prompt", " "),
            ("operation", "edit"),
            ("size", "10x10"),
            ("official_options", {}),
        ):
            args = self.arguments(2)
            args["tasks"][1][field] = value
            cases.append(args)
        for args in cases:
            with self.subTest(args=args):
                result = await self.call("submit_image_batch", args)
                self.assertTrue(result.is_error)
        self.assertEqual(self.requests, [])

    async def test_timeout_is_durable_uncertain_and_cannot_resubmit(self):
        self.sequence = [httpx2.ReadTimeout("lost acknowledgement")]
        result = await self.submit()
        self.assertFalse(result.is_error)
        self.assertEqual(result.structured_content["status"], "ATTENTION_REQUIRED")
        self.assertEqual(result.structured_content["tasks"][0]["status"], "SUBMISSION_UNCERTAIN")
        replay = await self.submit()
        self.assertEqual(replay.structured_content["tasks"][0]["status"], "SUBMISSION_UNCERTAIN")
        query = await self.call(
            "get_batch_image_task",
            {"checkpointer": "detail-pages", "thread_id": "product-001", "task_id": "page_0"},
        )
        self.assertIsNone(query.structured_content["provider_task_id"])
        self.assertEqual(len(self.requests), 1)

    async def test_missing_acknowledgement_id_blocks_replay(self):
        self.sequence = [(200, {"code": "success", "data": {}})]
        result = await self.submit()
        self.assertEqual(result.structured_content["tasks"][0]["status"], "SUBMISSION_UNCERTAIN")
        await self.submit()
        self.assertEqual(len(self.requests), 1)

    async def test_partial_failure_keeps_other_acceptances_and_never_retries(self):
        self.sequence = [
            (200, {"data": "provider_0"}),
            (429, {"error": {"message": self.secret}}),
            (200, {"data": "provider_2"}),
        ]
        result = await self.submit(3, max_concurrency=1)
        states = [t["status"] for t in result.structured_content["tasks"]]
        self.assertEqual(states, ["SUBMITTED", "SUBMISSION_UNCERTAIN", "SUBMITTED"])
        self.assertNotIn(self.secret, json.dumps(result.structured_content))
        await self.submit(3)
        self.assertEqual(len(self.requests), 3)

    async def test_queued_then_temporary_query_failure_recovers_and_saves(self):
        self.sequence = [(200, {"data": "recover_123"})]
        args = self.arguments()
        destination = self.root / "chosen-output"
        args["tasks"][0]["output_dir"] = str(destination)
        await self.call("submit_image_batch", args)
        query_args = {"checkpointer": "detail-pages", "thread_id": "product-001", "task_id": "page_0"}
        self.sequence = [self.task("NOT_START")]
        queued = await self.call("get_batch_image_task", query_args)
        self.assertEqual(queued.structured_content["status"], "NOT_START")
        self.sequence = [(503, {}), self.task()]
        # Exercise the actual read retry without its wall-clock backoff.
        real_sleep = asyncio.sleep

        async def fast_sleep(delay):
            await real_sleep(0)

        with patch("zhenzhen_image_mcp.api.asyncio.sleep", fast_sleep):
            done = await self.call("get_batch_image_task", query_args)
        self.assertFalse(done.is_error)
        self.assertEqual(done.structured_content["status"], "SUCCESS")
        self.assertEqual(done.structured_content["task_id"], "page_0")
        self.assertEqual(done.structured_content["provider_task_id"], "recover_123")
        self.assertEqual(done.structured_content["result"]["save_status"], "saved")
        self.assertTrue(
            Path(done.structured_content["result"]["files"][0]["path"]).parent.samefile(destination)
        )
        snapshot = await BatchService().snapshot("detail-pages", "product-001")
        self.assertEqual(snapshot["tasks"][0]["status"], "SUCCESS")
        self.assertEqual([r.method for r in self.requests], ["POST", "GET", "GET", "GET"])

    async def test_upstream_failure_is_protocol_error_and_checkpoint_retains_failure(self):
        self.sequence = [(200, {"data": "recover_123"}), self.task("FAILURE")]
        await self.submit()
        result = await self.call(
            "get_batch_image_task",
            {"checkpointer": "detail-pages", "thread_id": "product-001", "task_id": "page_0"},
        )
        self.assertTrue(result.is_error)
        snapshot = await BatchService().snapshot("detail-pages", "product-001")
        self.assertEqual(snapshot["tasks"][0]["status"], "FAILURE")
        await self.submit()
        self.assertEqual(len(self.requests), 2)

    async def test_cancelled_post_is_not_repeated_but_reserved_items_can_submit(self):
        started = asyncio.Event()

        async def handler(request):
            self.requests.append(request)
            started.set()
            await asyncio.Event().wait()

        self.install_handler(handler)
        tasks = [BatchImageTask.model_validate(task) for task in self.arguments(2)["tasks"]]
        service = BatchService()
        finishing = threading.Event()
        release = threading.Event()
        original_finish = service.store.finish

        def slow_finish(*args):
            finishing.set()
            if not release.wait(10):
                raise TimeoutError("Test did not release checkpoint write")
            return original_finish(*args)

        with patch.object(service.store, "finish", slow_finish):
            pending = asyncio.create_task(service.submit("detail-pages", "product-001", tasks, 1))
            await asyncio.wait_for(started.wait(), 10)
            pending.cancel()
            try:
                self.assertTrue(await asyncio.to_thread(finishing.wait, 10))
                self.assertFalse(pending.done(), "Cancellation returned before checkpoint cleanup")
            finally:
                release.set()
            with self.assertRaises(asyncio.CancelledError):
                await pending
        snapshot = await service.snapshot("detail-pages", "product-001")
        self.assertEqual([t["status"] for t in snapshot["tasks"]], ["SUBMISSION_UNCERTAIN", "RESERVED"])

        async def accept(request):
            self.requests.append(request)
            return httpx2.Response(200, json={"data": "provider_1"})

        self.install_handler(accept)
        replay = await self.submit(2)
        self.assertEqual(
            [t["status"] for t in replay.structured_content["tasks"]], ["SUBMISSION_UNCERTAIN", "SUBMITTED"]
        )
        self.assertEqual(len(self.requests), 2)

    async def test_crash_after_claim_is_never_automatically_reclaimed(self):
        self.sequence = [(200, {"data": "provider_0"})]
        tasks = [BatchImageTask.model_validate(t) for t in self.arguments()["tasks"]]
        service = BatchService()
        with patch.object(service.store, "claim", return_value=False):
            await service.submit("detail-pages", "product-001", tasks)
        self.assertTrue(service.store.claim("detail-pages", "product-001", "page_0"))
        replay = await self.submit()
        self.assertEqual(replay.structured_content["tasks"][0]["status"], "SUBMITTING")
        self.assertEqual(self.requests, [])

    async def test_checkpoint_failure_before_post_fails_closed(self):
        store = CheckpointStore()
        store.root.mkdir()
        store.path.write_bytes(b"invalid SQLite database")
        result = await self.submit()
        self.assertTrue(result.is_error)
        self.assertEqual(self.requests, [])

    async def test_checkpoint_write_failure_after_ack_returns_provider_id(self):
        self.sequence = [(200, {"data": "provider_0"})]
        with patch.object(CheckpointStore, "finish", side_effect=OSError("disk full")):
            result = await self.submit()
        item = result.structured_content["tasks"][0]
        self.assertEqual(item["status"], "SUBMISSION_UNCERTAIN")
        self.assertEqual(item["provider_task_id"], "provider_0")
        replay = await self.submit()
        self.assertEqual(replay.structured_content["tasks"][0]["status"], "SUBMITTING")
        self.assertEqual(len(self.requests), 1)

    async def test_reference_content_change_conflicts_and_database_omits_private_inputs(self):
        self.sequence = [(200, {"data": "provider_0"})]
        image = self.root / "reference.png"
        image.write_bytes(png())
        args = self.arguments()
        args["tasks"][0].update(operation="edit", images=[str(image)])
        result = await self.call("submit_image_batch", args)
        self.assertFalse(result.is_error)
        # A different valid reference at the same path must not reuse an old payment identity.
        from PIL import Image

        Image.new("RGB", (32, 32), "blue").save(image)
        conflict = await self.call("submit_image_batch", args)
        self.assertTrue(conflict.is_error)
        self.assertEqual(len(self.requests), 1)
        raw = CheckpointStore().path.read_bytes()
        for private in (self.secret, args["tasks"][0]["prompt"], str(image)):
            self.assertNotIn(private.encode(), raw)

    async def test_two_processes_can_claim_only_once(self):
        service = BatchService()
        tasks = [BatchImageTask.model_validate(t) for t in self.arguments()["tasks"]]
        with patch.object(service.store, "claim", return_value=False):
            await service.submit("detail-pages", "product-001", tasks)
        code = (
            "import sys; from pathlib import Path; "
            "from zhenzhen_image_mcp.checkpoints import CheckpointStore; "
            "print(int(CheckpointStore(Path(sys.argv[1])).claim('detail-pages','product-001','page_0')))"
        )
        results = await asyncio.gather(
            *(
                asyncio.to_thread(
                    subprocess.run,
                    [sys.executable, "-c", code, str(service.store.root)],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                for _ in range(2)
            )
        )
        self.assertEqual(sorted(r.stdout.strip() for r in results), ["0", "1"])
        self.assertEqual(self.requests, [])

    async def test_group_validation_and_mixed_edit_generation_contract(self):
        ref = self.root / "reference.png"
        ref.write_bytes(png())
        args = self.arguments(2)
        args["tasks"][1].update(
            operation="edit",
            images=[str(ref)],
            group="official",
            official_options={"n": 1, "input_fidelity": "high"},
        )
        self.sequence = [(200, {"data": "provider_0"}), (200, {"data": "provider_1"})]
        result = await self.call("submit_image_batch", {**args, "max_concurrency": 1})
        self.assertFalse(result.is_error)
        self.assertEqual([r.url.path for r in self.requests], ["/v1/images/generations", "/v1/images/edits"])
        self.assertIn(b'name="image[]"', self.requests[1].content)
        self.assertIn(b'name="input_fidelity"', self.requests[1].content)
        self.assertNotIn(b'"checkpointer"', self.requests[0].content)

    async def test_discovery_and_structured_outputs_follow_schema(self):
        async with Client(mcp, mode="legacy") as client:
            tools = (await client.list_tools()).tools
        by_name = {t.name: t for t in tools}
        batch = by_name["submit_image_batch"]
        self.assertTrue(batch.annotations.idempotent_hint)
        self.assertEqual(batch.input_schema["properties"]["tasks"]["maxItems"], 20)
        self.sequence = [(200, {"data": "provider_0"})]
        result = await self.submit()
        Draft202012Validator(batch.output_schema).validate(result.structured_content)
        snapshot = await self.call(
            "get_image_batch", {"checkpointer": "detail-pages", "thread_id": "product-001"}
        )
        Draft202012Validator(by_name["get_image_batch"].output_schema).validate(snapshot.structured_content)

    async def test_exhausted_query_can_recover_in_a_later_tool_call(self):
        self.sequence = [(200, {"data": "recover_123"})]
        await self.submit()
        args = {
            "checkpointer": "detail-pages",
            "thread_id": "product-001",
            "task_id": "page_0",
            "save": False,
        }
        self.sequence = [(503, {})] * 3
        real_sleep = asyncio.sleep

        async def fast_sleep(delay):
            await real_sleep(0)

        with patch("zhenzhen_image_mcp.api.asyncio.sleep", fast_sleep):
            failed = await self.call("get_batch_image_task", args)
        self.assertTrue(failed.is_error)
        self.assertIn("recover_123", failed.content[0].text)
        snapshot = await BatchService().snapshot("detail-pages", "product-001")
        self.assertEqual(snapshot["tasks"][0]["provider_task_id"], "recover_123")
        self.sequence = [self.task()]
        recovered = await self.call("get_batch_image_task", args)
        self.assertFalse(recovered.is_error)
        self.assertEqual(recovered.structured_content["status"], "SUCCESS")
        self.assertEqual(sum(r.method == "POST" for r in self.requests), 1)

    async def test_empty_local_snapshot_does_not_create_a_database(self):
        result = await self.call(
            "get_image_batch", {"checkpointer": "new-planning", "thread_id": "new-thread"}
        )
        self.assertFalse(result.is_error)
        self.assertEqual(result.structured_content["tasks"], [])
        self.assertFalse(CheckpointStore().path.exists())
        self.assertEqual(self.requests, [])

    async def test_batch_memory_budget_fails_before_post(self):
        service = BatchService()
        prepare = service.api.prepare_images

        async def oversized(*args, **kwargs):
            request = await prepare(*args, **kwargs)
            request.input_bytes = 70 * 1024 * 1024
            return request

        tasks = [BatchImageTask.model_validate(t) for t in self.arguments(2)["tasks"]]
        with patch.object(service.api, "prepare_images", oversized):
            with self.assertRaisesRegex(ValueError, "128 MiB"):
                await service.submit("detail-pages", "product-001", tasks)
        self.assertFalse(CheckpointStore().path.exists())
        self.assertEqual(self.requests, [])

    async def test_provider_change_does_not_query_the_wrong_endpoint(self):
        self.sequence = [(200, {"data": "provider_0"})]
        await self.submit()
        service = BatchService()
        from zhenzhen_image_mcp.config import Settings

        service.api = API(Settings("https://different.example/v1", self.root))
        with self.assertRaisesRegex(ValueError, "base URL differs"):
            await service.query("detail-pages", "product-001", "page_0")
        self.assertEqual(len(self.requests), 1)
