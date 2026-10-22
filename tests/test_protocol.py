"""MCP JSON-RPC tests with the real SDK client/server and mocked upstream HTTP."""

import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx2
from mcp import Client
from openai import AsyncOpenAI
from test_core import png

from zhenzhen_image_mcp.api import API
from zhenzhen_image_mcp.config import FLARE, SUNBURST, Settings
from zhenzhen_image_mcp.server import mcp


class ProtocolRecoveryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.requests = []
        self.sequence = []
        self.secret = "private-test-credential"
        ledger = patch("zhenzhen_image_mcp.checkpoints.PROJECT_DIR", self.root)
        ledger.start()
        self.addCleanup(ledger.stop)

        def handler(request):
            self.requests.append(request)
            item = self.sequence.pop(0)
            if isinstance(item, Exception):
                raise item
            status, body = item
            return httpx2.Response(status, json=body)

        def sdk(instance, key):
            return AsyncOpenAI(
                api_key=key,
                base_url="https://provider.example/v1/",
                max_retries=0,
                http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
            )

        for target, kwargs in (
            ("zhenzhen_image_mcp.api.api_key", {"return_value": self.secret}),
            ("zhenzhen_image_mcp.server.api_key", {"return_value": self.secret}),
            (
                "zhenzhen_image_mcp.server.Settings.load",
                {"return_value": Settings("https://provider.example/v1", self.root)},
            ),
        ):
            mock = patch(target, **kwargs)
            mock.start()
            self.addCleanup(mock.stop)
        mock = patch.object(API, "sdk", sdk)
        mock.start()
        self.addCleanup(mock.stop)

    def task(self, status="SUCCESS"):
        return (
            200,
            {
                "code": "success",
                "data": {
                    "task_id": "recover_123",
                    "status": status,
                    "data": {"data": [{"b64_json": base64.b64encode(png()).decode()}]},
                },
            },
        )

    async def call(self, tool, args):
        # legacy mode exercises serialized JSON-RPC tools/call, as stdio Hosts do.
        async with Client(mcp, mode="legacy") as client:
            return await client.call_tool(tool, args)

    async def test_wait_recovers_after_503_and_saves_without_extra_get(self):
        self.sequence = [(503, {"error": "temporary"}), self.task("IN_PROGRESS"), self.task()]
        result = await self.call(
            "wait_image_task", {"task_id": "recover_123", "timeout_seconds": 10, "poll_interval": 1}
        )
        self.assertFalse(result.is_error)
        value = json.loads(result.content[0].text)
        self.assertEqual(value["task_id"], "recover_123")
        self.assertEqual(value["status"], "SUCCESS")
        self.assertEqual(value["save_status"], "saved")
        self.assertEqual(Path(value["files"][0]["path"]).read_bytes(), png())
        self.assertEqual(len(self.requests), 3)
        self.assertTrue(
            all(r.method == "GET" and r.url.path == "/v1/images/tasks/recover_123" for r in self.requests)
        )

    async def test_get_recovers_from_connection_failure_and_429(self):
        self.sequence = [httpx2.ConnectError("temporary"), (429, {"error": "rate limit"}), self.task()]
        result = await self.call("get_image_task", {"task_id": "recover_123", "save": False})
        self.assertFalse(result.is_error)
        self.assertEqual(json.loads(result.content[0].text)["status"], "SUCCESS")
        self.assertEqual(len(self.requests), 3)
        self.assertFalse(list(self.root.glob("*.png")))

    async def test_exhausted_query_reports_task_and_status_without_secret(self):
        self.sequence = [(503, {"error": self.secret})] * 3
        result = await self.call("get_image_task", {"task_id": "recover_123", "save": False})
        self.assertTrue(result.is_error)
        message = result.content[0].text
        for part in ("recover_123", "503", "3 attempt", "do not resubmit"):
            self.assertIn(part, message)
        self.assertNotIn(self.secret, message)
        self.assertEqual(len(self.requests), 3)

    async def test_nontransient_query_not_retried(self):
        self.sequence = [(401, {"error": self.secret})]
        result = await self.call("get_image_task", {"task_id": "recover_123"})
        self.assertTrue(result.is_error)
        self.assertIn("401", result.content[0].text)
        self.assertEqual(len(self.requests), 1)

    async def test_wait_timeout_during_retry_retains_id(self):
        self.sequence = [(503, {"error": "temporary"})] * 3
        result = await self.call("wait_image_task", {"task_id": "recover_123", "timeout_seconds": 1})
        self.assertFalse(result.is_error)
        self.assertEqual(json.loads(result.content[0].text)["task_id"], "recover_123")
        self.assertTrue(json.loads(result.content[0].text)["wait_timed_out"])
        self.assertEqual(len(self.requests), 1)

    async def test_billable_posts_never_retried(self):
        ref = self.root / "input.png"
        ref.write_bytes(png())
        for tool, args in (
            ("submit_image_generation", {"prompt": "cat", "model": FLARE}),
            ("generate_image", {"prompt": "cat", "model": FLARE}),
            ("edit_image", {"prompt": "glasses", "model": SUNBURST, "images": [str(ref)]}),
            ("submit_image_edit", {"prompt": "glasses", "model": SUNBURST, "images": [str(ref)]}),
        ):
            with self.subTest(tool=tool, args=args):
                self.requests.clear()
                self.sequence = [(503, {"error": self.secret})]
                result = await self.call(tool, args)
                self.assertTrue(result.is_error)
                self.assertIn("503", result.content[0].text)
                self.assertNotIn(self.secret, result.content[0].text)
                self.assertEqual(len(self.requests), 1)
                self.assertEqual(self.requests[0].method, "POST")

    async def test_expected_error_is_visible_and_redacted(self):
        with patch.object(
            API,
            "query",
            side_effect=ValueError(
                f"Invalid input {self.secret} Bearer token-value https://example.com/secret?q=credential"
            ),
        ):
            result = await self.call("get_image_task", {"task_id": "recover_123"})
        self.assertTrue(result.is_error)
        message = result.content[0].text
        self.assertIn("Invalid input", message)
        for secret in (self.secret, "token-value", "https://example.com", "q=credential"):
            self.assertNotIn(secret, message)

    async def test_responses_not_advertised(self):
        async with Client(mcp, mode="legacy") as client:
            inventory = await client.list_tools()
        names = {tool.name for tool in inventory.tools}
        self.assertEqual(len(names), 12)
        self.assertNotIn("create_response", names)
        self.assertTrue({"edit_image", "submit_image_edit"} <= names)

    async def test_precise_edit_sync_and_async_use_images_endpoint(self):
        refs = [self.root / "person.png", self.root / "style.png"]
        for ref in refs:
            ref.write_bytes(png())
        args = {
            "prompt": "只添加眼镜，保持五官和背景不变",
            "model": SUNBURST,
            "images": [str(ref) for ref in refs],
            "size": "2048x1152",
        }
        self.sequence = [(200, {"data": [{"b64_json": base64.b64encode(png()).decode()}]})]
        result = await self.call("edit_image", args)
        self.assertFalse(result.is_error)
        value = json.loads(result.content[0].text)
        self.assertEqual(value["save_status"], "saved")
        self.assertEqual(Path(value["files"][0]["path"]).read_bytes(), png())
        self.sequence = [(200, {"code": "success", "data": "recover_123"}), self.task()]
        submitted = await self.call("submit_image_edit", args)
        self.assertFalse(submitted.is_error)
        self.assertEqual(json.loads(submitted.content[0].text)["task_id"], "recover_123")
        finished = await self.call("wait_image_task", {"task_id": "recover_123"})
        self.assertFalse(finished.is_error)
        self.assertEqual(json.loads(finished.content[0].text)["save_status"], "saved")
        self.assertEqual(
            [r.url.path for r in self.requests],
            ["/v1/images/edits", "/v1/images/edits", "/v1/images/tasks/recover_123"],
        )
        self.assertEqual(self.requests[0].url.query, b"")
        self.assertEqual(self.requests[1].url.query, b"async=true")
        for request in self.requests[:2]:
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.content.count(b'name="image[]"'), 2)
            self.assertIn(SUNBURST.encode(), request.content)
            self.assertIn(args["prompt"].encode(), request.content)
            self.assertIn(b"2048x1152", request.content)

    def queued_task(self):
        return (
            200,
            {
                "code": "success",
                "data": {"task_id": "recover_123", "status": "NOT_START", "progress": "0%", "data": None},
            },
        )

    async def test_get_queued_task_preserves_status_without_saving(self):
        self.sequence = [self.queued_task()]
        result = await self.call("get_image_task", {"task_id": "recover_123", "save": True})
        self.assertFalse(result.is_error)
        value = json.loads(result.content[0].text)
        self.assertEqual(value["status"], "NOT_START")
        self.assertEqual(value["progress"], "0%")
        self.assertIsNone(value["response"])
        self.assertNotIn("files", value)
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertEqual(len(self.requests), 1)

    async def test_wait_queue_to_processing_to_success(self):
        self.sequence = [self.queued_task(), self.task("IN_PROGRESS"), self.task()]
        result = await self.call(
            "wait_image_task", {"task_id": "recover_123", "timeout_seconds": 10, "poll_interval": 1}
        )
        self.assertFalse(result.is_error)
        value = json.loads(result.content[0].text)
        self.assertEqual(value["status"], "SUCCESS")
        self.assertEqual(value["save_status"], "saved")
        self.assertEqual(Path(value["files"][0]["path"]).read_bytes(), png())
        self.assertEqual(len(self.requests), 3)
        self.assertTrue(all(r.method == "GET" for r in self.requests))

    async def test_queued_timeout_retains_task_and_can_resume(self):
        self.sequence = [self.queued_task()]
        result = await self.call(
            "wait_image_task", {"task_id": "recover_123", "timeout_seconds": 1, "poll_interval": 5}
        )
        self.assertFalse(result.is_error)
        value = json.loads(result.content[0].text)
        self.assertEqual(value["status"], "NOT_START")
        self.assertEqual(value["task_id"], "recover_123")
        self.assertTrue(value["wait_timed_out"])
        self.assertEqual(list(self.root.iterdir()), [])
        self.sequence = [self.task()]
        resumed = await self.call("wait_image_task", {"task_id": value["task_id"]})
        self.assertFalse(resumed.is_error)
        self.assertEqual(json.loads(resumed.content[0].text)["save_status"], "saved")
        self.assertEqual(len(self.requests), 2)
        self.assertTrue(all(r.method == "GET" for r in self.requests))

    async def test_queue_to_failure_returns_failure_without_saving(self):
        self.sequence = [
            self.queued_task(),
            (
                200,
                {
                    "data": {
                        "task_id": "recover_123",
                        "status": "FAILURE",
                        "fail_reason": "Provider rejected task",
                        "data": None,
                    }
                },
            ),
        ]
        result = await self.call("wait_image_task", {"task_id": "recover_123", "poll_interval": 1})
        self.assertTrue(result.is_error)
        self.assertIn("recover_123: FAILURE: Provider rejected task", result.content[0].text)
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertEqual(len(self.requests), 2)
