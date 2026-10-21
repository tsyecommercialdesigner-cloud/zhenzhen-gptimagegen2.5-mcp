import base64
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import httpx2
from openai import AsyncOpenAI
from PIL import Image

from zhenzhen_image_mcp import media
from zhenzhen_image_mcp.api import API, size_check
from zhenzhen_image_mcp.config import FLARE, SUNBURST, Settings, api_key


def png():
    out = io.BytesIO()
    Image.new("RGB", (32, 32), "red").save(out, format="PNG")
    return out.getvalue()


class APIContractTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.api = API(Settings("https://ai.t8star.org/v1", self.root))
        self.requests = []
        self.response = {"data": [{"b64_json": base64.b64encode(png()).decode()}]}
        self.status = 200
        self.headers = {"content-type": "application/json"}

        def handler(request):
            self.requests.append(request)
            content = json.dumps(self.response).encode() if isinstance(self.response, dict) else self.response
            return httpx2.Response(self.status, content=content, headers=self.headers)

        def sdk(key):
            return AsyncOpenAI(
                api_key=key,
                base_url="https://ai.t8star.org/v1/",
                max_retries=0,
                http_client=httpx2.AsyncClient(
                    transport=httpx2.MockTransport(handler), follow_redirects=False
                ),
            )

        self.api.sdk = sdk
        self.key_patch = patch("zhenzhen_image_mcp.api.api_key", return_value="fake-test-key")
        self.key_patch.start()
        self.ledger_patch = patch("zhenzhen_image_mcp.checkpoints.PROJECT_DIR", self.root)
        self.ledger_patch.start()

    def tearDown(self):
        self.ledger_patch.stop()
        self.key_patch.stop()
        self.temp.cleanup()

    async def test_sync_generation_custom_size_and_saved_bytes(self):
        r = await self.api.images("a cat", FLARE, size="2048x1152", quality="high")
        request = self.requests[0]
        self.assertEqual(request.url.path, "/v1/images/generations")
        self.assertEqual(
            json.loads(request.content),
            {"model": FLARE, "prompt": "a cat", "size": "2048x1152", "quality": "high"},
        )
        self.assertEqual(Path(r["files"][0]["path"]).read_bytes(), png())
        self.assertNotIn(base64.b64encode(png()).decode(), json.dumps(r))

    async def test_generation_reference_serialized_as_image_array(self):
        ref = self.root / "input.png"
        ref.write_bytes(png())
        await self.api.images("reference", FLARE, images=[str(ref)])
        body = json.loads(self.requests[0].content)
        self.assertEqual(set(body), {"model", "prompt", "image"})
        self.assertTrue(body["image"][0].startswith("data:image/png;base64,"))

    async def test_async_edit_multipart_and_destination_survives_restart(self):
        ref = self.root / "input.png"
        ref.write_bytes(png())
        self.response = {"code": "success", "message": "", "data": "task_123"}
        dest = self.root / "custom"
        r = await self.api.images(
            "glasses", SUNBURST, [str(ref), str(ref)], edit=True, asynchronous=True, output_dir=str(dest)
        )
        request = self.requests[0]
        self.assertEqual(str(request.url), "https://ai.t8star.org/v1/images/edits?async=true")
        self.assertEqual(request.content.count(b'name="image[]"'), 2)
        self.assertEqual(r["task_id"], "task_123")
        self.response = {
            "code": "success",
            "data": {
                "task_id": "task_123",
                "status": "SUCCESS",
                "data": {"data": [{"b64_json": base64.b64encode(png()).decode()}]},
            },
        }
        restarted = API(self.api.settings)
        restarted.sdk = self.api.sdk
        result = await restarted.query("task_123")
        self.assertTrue(Path(result["files"][0]["path"]).parent.samefile(dest))
        again = await restarted.query("task_123")
        self.assertTrue(again["files"][0]["reused"])

    async def test_async_generation_query_contract(self):
        self.response = {"code": "success", "data": "abc", "message": ""}
        await self.api.images("cat", FLARE, asynchronous=True)
        self.assertEqual(str(self.requests[0].url), "https://ai.t8star.org/v1/images/generations?async=true")
        self.response = {"code": "success", "data": {"status": "IN_PROGRESS", "progress": "20%"}}
        r = await self.api.query("abc")
        self.assertEqual(r["status"], "IN_PROGRESS")
        self.assertEqual(self.requests[-1].url.path, "/v1/images/tasks/abc")

    async def test_failures_and_unknown_status(self):
        self.response = {"data": {"status": "FAILURE", "fail_reason": "provider rejected request"}}
        with self.assertRaisesRegex(ValueError, "abc: FAILURE: provider rejected request"):
            await self.api.query("abc")
        self.response = {"data": {"status": "DONE"}}
        with self.assertRaisesRegex(ValueError, "Unknown"):
            await self.api.query("abc")
        with self.assertRaises(ValueError):
            await self.api.query("../secret")

    async def test_validation_prevents_charges(self):
        with self.assertRaises(ValueError):
            await self.api.images("cat", FLARE, size="512x512")
        with self.assertRaises(ValueError):
            await self.api.images("cat", SUNBURST, edit=True)
        self.assertEqual(len(self.requests), 0)

    async def test_no_retries_or_secret_error_body(self):
        self.status = 429
        self.response = {"error": {"message": "Bearer fake-test-key"}}
        with self.assertRaisesRegex(ValueError, "429") as cm:
            await self.api.images("cat", FLARE)
        self.assertNotIn("fake-test-key", str(cm.exception))
        self.assertEqual(len(self.requests), 1)

    async def test_provider_redirect_is_not_followed(self):
        self.status = 307
        self.headers = {"location": "https://different.example/collect"}
        with self.assertRaises(ValueError):
            await self.api.images("cat", FLARE)
        self.assertEqual(len(self.requests), 1)

    async def test_wait_timeout_keeps_task_id(self):
        self.api.fetch_task = AsyncMock(return_value={"task_id": "abc", "status": "IN_PROGRESS"})
        r = await self.api.wait("abc", 1, 1, None)
        self.assertTrue(r["wait_timed_out"])
        self.assertEqual(r["task_id"], "abc")

    async def test_partial_download_failure_preserves_other_image(self):
        payload = {
            "data": [{"b64_json": base64.b64encode(png()).decode()}, {"url": "https://example.com/image.png"}]
        }
        with patch.object(media, "download", side_effect=ValueError("Image download HTTP 404")):
            r = await self.api.store_images(payload, self.root)
        self.assertEqual(r["save_status"], "partial")
        self.assertEqual(len(r["files"]), 1)
        self.assertEqual(r["download_errors"][0]["index"], 1)


class MediaTests(unittest.IsolatedAsyncioTestCase):
    async def test_reject_loopback_and_file_scheme(self):
        with self.assertRaises(ValueError):
            await media.public_url("http://127.0.0.1/secret")
        with self.assertRaises(ValueError):
            await media.public_url("file:///C:/secret")

    async def test_download_redirect_and_no_auth(self):
        requests = []

        def handler(request):
            requests.append(request)
            if request.url.path == "/redirect":
                return httpx.Response(302, headers={"location": "https://cdn.example.com/image"})
            return httpx.Response(200, content=png())

        original = httpx.AsyncClient
        with (
            patch.object(media, "public_url", new=AsyncMock()) as public,
            patch.object(
                media.httpx,
                "AsyncClient",
                side_effect=lambda **kw: original(transport=httpx.MockTransport(handler), **kw),
            ),
        ):
            blob = await media.download("https://example.com/redirect")
        self.assertEqual(blob, png())
        self.assertEqual(public.await_count, 2)
        self.assertTrue(all("authorization" not in r.headers for r in requests))

    def test_corrupt_file_refused_and_deduplicated(self):
        with tempfile.TemporaryDirectory() as root:
            first = media.save_image(png(), root)
            self.assertTrue(media.save_image(png(), root)["reused"])
            Path(first["path"]).write_bytes(b"damaged")
            with self.assertRaises(ValueError):
                media.save_image(png(), root)
        with self.assertRaises(ValueError):
            media.decode_image("not-base64!")
        with self.assertRaises(ValueError):
            media.image_info(b"<html>error</html>")

    def test_size_boundary(self):
        for value in (None, "auto", "3840x2160", "2160x3840", "1024x1024"):
            size_check(value)
        for value in ("3840x3840", "1025x1024", "4096x1024", "2048x512"):
            with self.assertRaises(ValueError):
                size_check(value)

    def test_process_key_wins_over_user_key(self):
        with (
            patch("zhenzhen_image_mcp.config.user_variable", return_value="user-value"),
            patch.dict("os.environ", {"ZHENZHEN_GPTIMAGEGEN_API_KEY": "stale"}),
        ):
            self.assertEqual(api_key(), "stale")


if __name__ == "__main__":
    unittest.main()
