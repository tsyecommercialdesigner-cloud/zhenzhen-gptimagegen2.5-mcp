"""Real MCP / SDK serialization of explicit groups and official Images options."""

import base64
import json
import unittest
from unittest.mock import patch

import httpx2
import test_protocol as protocol
from mcp import Client
from openai import AsyncOpenAI
from PIL import Image
from pydantic import TypeAdapter
from test_core import png

from zhenzhen_image_mcp.api import API
from zhenzhen_image_mcp.config import FLARE, SUNBURST
from zhenzhen_image_mcp.contracts import ImageResult
from zhenzhen_image_mcp.server import mcp


class GroupProtocolTests(unittest.IsolatedAsyncioTestCase):
    setUp = protocol.ProtocolRecoveryTests.setUp
    call = protocol.ProtocolRecoveryTests.call
    task = protocol.ProtocolRecoveryTests.task

    def success(self):
        return (200, {"data": [{"b64_json": base64.b64encode(png()).decode()}]})

    async def test_reverse_is_default_and_only_five_fields_reach_provider(self):
        self.sequence = [self.success()]
        result = await self.call("generate_image", {"prompt": "blue bag", "model": FLARE, "quality": "high"})
        self.assertFalse(result.is_error)
        self.assertEqual(
            json.loads(self.requests[0].content), {"prompt": "blue bag", "model": FLARE, "quality": "high"}
        )
        value = json.loads(result.content[0].text)
        self.assertEqual(value["group"], "reverse")
        TypeAdapter(ImageResult).validate_python(value)
        self.assertEqual(result.structured_content, value)

    async def test_undeclared_official_options_never_send_or_create_destination(self):
        for options in ({}, {"n": 2}, {"background": "transparent"}):
            result = await self.call(
                "generate_image", {"prompt": "cat", "model": FLARE, "official_options": options}
            )
            self.assertTrue(result.is_error)
            self.assertIn('group="official"', result.content[0].text)
        self.assertEqual(self.requests, [])
        self.assertEqual(list(self.root.iterdir()), [])

    async def test_official_json_fields_forwarded_without_local_declaration(self):
        self.sequence = [self.success()]
        options = {
            "n": 2,
            "background": "transparent",
            "output_format": "webp",
            "output_compression": 80,
            "moderation": "auto",
            "input_fidelity": "high",
            "safety_identifier": "test-user-hash",
            "response_format": "url",
        }
        result = await self.call(
            "generate_image",
            {
                "prompt": "bag",
                "model": FLARE,
                "group": "official",
                "quality": "xhigh",
                "official_options": options,
            },
        )
        self.assertFalse(result.is_error, result.content)
        body = json.loads(self.requests[0].content)
        self.assertEqual(body, {"prompt": "bag", "model": FLARE, "quality": "xhigh", **options})
        self.assertNotIn("group", body)
        self.assertNotIn("official_options", body)

    async def test_invalid_group_unknown_fields_and_ranges_are_errors_before_http(self):
        for addition in (
            {"group": "auto"},
            {"quality": "max"},
            {"group": "official", "official_options": {"n": 0}},
            {"group": "official", "official_options": {"n": True}},
            {"group": "official", "official_options": {"n": "2"}},
            {"group": "official", "official_options": {"unknown_field": 1}},
            {"group": "official", "official_options": {"output_format": "gif"}},
            {"group": "official", "official_options": {"output_format": "jpeg", "background": "transparent"}},
            {"group": "official", "official_options": {"output_compression": 50}},
            {"group": "official", "official_options": {"partial_images": 1}},
        ):
            with self.subTest(addition=addition):
                result = await self.call("generate_image", {"prompt": "bag", "model": FLARE, **addition})
                self.assertTrue(result.is_error)
        self.assertFalse(self.requests)

    async def test_unknown_top_level_and_stringified_options_are_not_silently_ignored(self):
        for addition in (
            {"n": 2},
            {"group": "official", "official_options": '{"n":2}'},
            {"images": '["C:/wrong.png"]'},
        ):
            result = await self.call("generate_image", {"prompt": "bag", "model": FLARE, **addition})
            self.assertTrue(result.is_error)
        self.assertFalse(self.requests)

    async def test_official_edit_uploads_mask_and_all_fields(self):
        ref = self.root / "ref.png"
        ref.write_bytes(png())
        mask = self.root / "mask.png"
        Image.new("RGBA", (32, 32), (0, 0, 0, 0)).save(mask)
        self.sequence = [self.success()]
        result = await self.call(
            "edit_image",
            {
                "prompt": "make red",
                "model": SUNBURST,
                "images": [str(ref)],
                "group": "official",
                "official_options": {
                    "mask": str(mask),
                    "n": 1,
                    "input_fidelity": "high",
                    "moderation": "auto",
                    "safety_identifier": "hash-only",
                    "output_format": "png",
                },
            },
        )
        self.assertFalse(result.is_error, result.content)
        request = self.requests[0]
        self.assertEqual(request.url.path, "/v1/images/edits")
        for field in (
            "image[]",
            "mask",
            "input_fidelity",
            "moderation",
            "safety_identifier",
            "n",
            "output_format",
        ):
            self.assertIn(f'name="{field}"'.encode(), request.content)
        self.assertNotIn(b'name="group"', request.content)

    async def test_bad_mask_and_generation_mask_rejected_before_post(self):
        ref = self.root / "ref.png"
        ref.write_bytes(png())
        for tool in ("edit_image", "generate_image"):
            result = await self.call(
                tool,
                {
                    "prompt": "mask",
                    "model": SUNBURST,
                    "images": [str(ref)],
                    "group": "official",
                    "official_options": {"mask": str(ref)},
                },
            )
            self.assertTrue(result.is_error)
        self.assertFalse(self.requests)

    async def test_async_top_level_id_metadata_and_restart_result(self):
        self.sequence = [(200, {"task_id": "recover_123"}), self.task()]
        submitted = await self.call(
            "submit_image_generation",
            {"prompt": "bag", "model": FLARE, "group": "official", "official_options": {"n": 1}},
        )
        self.assertFalse(submitted.is_error)
        metadata = json.loads((self.root / ".tasks/recover_123.json").read_text())
        self.assertEqual(metadata["group"], "official")
        self.assertNotIn("prompt", metadata)
        finished = await self.call("get_image_task", {"task_id": "recover_123"})
        self.assertFalse(finished.is_error)
        self.assertEqual(json.loads(finished.content[0].text)["group"], "official")
        self.assertEqual(self.requests[0].url.query, b"async=true")

    async def test_async_stream_combination_never_posts(self):
        result = await self.call(
            "submit_image_generation",
            {"prompt": "bag", "model": FLARE, "group": "official", "official_options": {"stream": True}},
        )
        self.assertTrue(result.is_error)
        self.assertFalse(self.requests)

    async def test_conflicting_submission_ids_do_not_retry(self):
        self.sequence = [(200, {"task_id": "recover_123", "data": "different_task"})]
        result = await self.call("submit_image_generation", {"prompt": "bag", "model": FLARE})
        self.assertTrue(result.is_error)
        self.assertEqual(len(self.requests), 1)
        self.assertIn("do not resubmit", result.content[0].text)

    async def test_empty_completed_result_is_an_error_without_retry(self):
        self.sequence = [(200, {"data": []})]
        result = await self.call("generate_image", {"prompt": "bag", "model": FLARE})
        self.assertTrue(result.is_error)
        self.assertEqual(len(self.requests), 1)

    async def test_official_async_edit_forwards_multipart_options(self):
        ref = self.root / "ref.png"
        ref.write_bytes(png())
        self.sequence = [(200, {"task_id": "recover_123"})]
        result = await self.call(
            "submit_image_edit",
            {
                "prompt": "make red",
                "model": SUNBURST,
                "images": [str(ref)],
                "group": "official",
                "official_options": {"n": 1, "output_format": "webp"},
            },
        )
        self.assertFalse(result.is_error)
        self.assertEqual(self.requests[0].url.query, b"async=true")
        self.assertIn(b'name="image[]"', self.requests[0].content)
        self.assertIn(b'name="output_format"', self.requests[0].content)

    async def test_completed_url_with_empty_base64_uses_url(self):
        from unittest.mock import AsyncMock

        self.sequence = [(200, {"data": [{"url": "https://cdn.example/image.png", "b64_json": ""}]})]
        with patch("zhenzhen_image_mcp.media.download", new=AsyncMock(return_value=png())) as download:
            result = await self.call("generate_image", {"prompt": "bag", "model": FLARE})
        self.assertFalse(result.is_error)
        download.assert_awaited_once_with("https://cdn.example/image.png")

    async def test_discovered_schema_declares_defaults_options_and_outputs(self):
        async with Client(mcp, mode="legacy") as client:
            tools = (await client.list_tools()).tools
        for tool in tools:
            schema = tool.model_dump(mode="json", by_alias=True)
            self.assertIsNotNone(schema["outputSchema"])
            if tool.name in {"generate_image", "edit_image", "submit_image_generation", "submit_image_edit"}:
                self.assertEqual(schema["inputSchema"]["properties"]["group"]["default"], "reverse")
                self.assertIn("OfficialOptions", schema["inputSchema"]["$defs"])
                self.assertFalse(schema["inputSchema"]["$defs"]["OfficialOptions"]["additionalProperties"])


class ImagesStreamingTests(unittest.IsolatedAsyncioTestCase):
    setUp = protocol.ProtocolRecoveryTests.setUp
    call = protocol.ProtocolRecoveryTests.call

    async def streaming_call(self, tool, events):
        wire = "".join(
            "event: image\r\ndata: " + json.dumps(event, ensure_ascii=False) + "\r\n\r\n" for event in events
        ).encode()

        class Chunks(httpx2.AsyncByteStream):
            async def __aiter__(self):
                for index in range(0, len(wire), 7):
                    yield wire[index : index + 7]

        def handler(request):
            self.requests.append(request)
            return httpx2.Response(200, headers={"content-type": "text/event-stream"}, stream=Chunks())

        def sdk(instance, key):
            return AsyncOpenAI(
                api_key=key,
                base_url="https://provider.example/v1/",
                max_retries=0,
                http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
            )

        args = {
            "prompt": "blue cup",
            "model": FLARE,
            "group": "official",
            "official_options": {"stream": True, "partial_images": 1},
        }
        if tool == "edit_image":
            ref = self.root / "ref.png"
            ref.write_bytes(png())
            args["images"] = [str(ref)]
        with patch.object(API, "sdk", sdk):
            return await self.call(tool, args)

    async def test_generation_and_edit_sse_save_only_completed_image(self):
        for tool, prefix in (("generate_image", "image_generation"), ("edit_image", "image_edit")):
            with self.subTest(tool=tool):
                self.requests.clear()
                result = await self.streaming_call(
                    tool,
                    [
                        {"type": prefix + ".partial_image", "b64_json": "invalid-preview-ignored"},
                        {
                            "type": prefix + ".completed",
                            "created_at": 123,
                            "revised_prompt": "蓝色杯子",
                            "b64_json": base64.b64encode(png()).decode(),
                            "usage": {"total_tokens": 2},
                        },
                    ],
                )
                self.assertFalse(result.is_error, result.content)
                value = json.loads(result.content[0].text)
                self.assertEqual(value["save_status"], "saved")
                self.assertEqual(len(value["files"]), 1)
                self.assertEqual(value["response"]["usage"]["total_tokens"], 2)
                self.assertEqual(len(self.requests), 1)

    async def test_partial_only_and_error_events_are_not_retried(self):
        for events in (
            [{"type": "image_generation.partial_image", "b64_json": "preview"}],
            [{"type": "error", "error": {"message": self.secret}}],
            [{"type": "image_generation.completed", "b64_json": ""}],
            [{"type": "unknown.event"}],
        ):
            with self.subTest(events=events):
                self.requests.clear()
                result = await self.streaming_call("generate_image", events)
                self.assertTrue(result.is_error)
                self.assertNotIn(self.secret, result.content[0].text)
                self.assertEqual(len(self.requests), 1)
