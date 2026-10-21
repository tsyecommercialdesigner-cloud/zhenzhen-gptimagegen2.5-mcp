"""Exercise the pinned SDK constructor under a DSH-style proxy environment."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
import httpx2
from mcp import Client
from openai import DefaultAsyncHttpxClient

from zhenzhen_image_mcp.api import API, normalize_no_proxy, sanitize_proxy_env
from zhenzhen_image_mcp.config import FLARE, Settings
from zhenzhen_image_mcp.server import mcp

PROXY_ENV = {
    "HTTP_PROXY": "http://127.0.0.1:9",
    "HTTPS_PROXY": "http://127.0.0.1:9",
    "ALL_PROXY": "",
    "NO_PROXY": "localhost,127.0.0.1,::1,[::1]",
}


class ProxyNormalizationTests(unittest.TestCase):
    def test_entries_preserve_bypass_including_ports(self):
        cases = {
            "[::1]": "::1",
            "[::1]:8080": "all://[::1]:8080",
            "[2001:db8::1]": "2001:db8::1",
            "localhost,127.0.0.1,::1,[::1]": "localhost,127.0.0.1,::1,::1",
            " .example.com , *, [::1] ": ".example.com,*,::1",
            "::1": "::1",
            "": "",
            "http://[::1]:8080": "http://[::1]:8080",
            "[not-an-ip]": "[not-an-ip]",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_no_proxy(raw), expected)
                self.assertEqual(normalize_no_proxy(expected), expected)

    def test_environment_names_proxy_and_tls_settings_preserved(self):
        # Plain mapping tests both cases independently even on case-insensitive Windows.
        env = {
            "no_proxy": "[::1]",
            "NO_PROXY": "[::1]:8080",
            "HTTPS_PROXY": "http://proxy.example:8080",
            "HTTP_PROXY": "http://proxy.example:8081",
            "ALL_PROXY": "http://proxy.example:8082",
            "SSL_CERT_FILE": "certificate.pem",
        }
        with patch("zhenzhen_image_mcp.api.os.environ", env):
            sanitize_proxy_env()
            self.assertEqual(env["no_proxy"], "::1")
            self.assertEqual(env["NO_PROXY"], "all://[::1]:8080")
            for name, value in [
                ("HTTPS_PROXY", "http://proxy.example:8080"),
                ("HTTP_PROXY", "http://proxy.example:8081"),
                ("ALL_PROXY", "http://proxy.example:8082"),
                ("SSL_CERT_FILE", "certificate.pem"),
            ]:
                self.assertEqual(env[name], value)
        with patch("zhenzhen_image_mcp.api.os.environ", {}):
            sanitize_proxy_env()


class RealSDKProxyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        mock = patch("zhenzhen_image_mcp.checkpoints.PROJECT_DIR", Path(temporary.name))
        mock.start()
        self.addCleanup(mock.stop)

    async def test_original_failure_reproduced_then_client_routes_preserved(self):
        with patch.dict(os.environ, PROXY_ENV):
            with self.assertRaises(httpx2.InvalidURL):
                DefaultAsyncHttpxClient(follow_redirects=False)
            async with API().sdk("test-credential") as sdk:
                client = sdk._client
                self.assertEqual(sdk.max_retries, 0)
                self.assertIs(client._transport_for_url(httpx2.URL("http://[::1]/")), client._transport)
                self.assertIs(client._transport_for_url(httpx2.URL("http://127.0.0.1/")), client._transport)
                self.assertIsNot(
                    client._transport_for_url(httpx2.URL("https://provider.example/")), client._transport
                )
                self.assertEqual(os.environ["HTTPS_PROXY"], PROXY_ENV["HTTPS_PROXY"])

    async def test_only_bracketed_entry_and_explicit_port(self):
        for raw in ("[::1]", "[::1]:8080"):
            with self.subTest(raw=raw), patch.dict(os.environ, {**PROXY_ENV, "NO_PROXY": raw}):
                async with API().sdk("test-credential") as sdk:
                    client = sdk._client
                    self.assertIs(
                        client._transport_for_url(httpx2.URL("http://[::1]:8080/")), client._transport
                    )
                    other = client._transport_for_url(httpx2.URL("http://[::1]:8081/"))
                    if raw.endswith(":8080"):
                        self.assertIsNot(other, client._transport)
                    else:
                        self.assertIs(other, client._transport)

    async def test_protocol_calls_construct_real_sdk_with_host_env(self):
        with tempfile.TemporaryDirectory() as temporary:
            settings = Settings("https://provider.example/v1", Path(temporary))
            requests = []

            async def send(client, request, **kwargs):
                requests.append(request)
                if request.method == "POST":
                    body = {"code": "success", "data": "proxy_task"}
                else:
                    body = {
                        "code": "success",
                        "data": {"task_id": "proxy_task", "status": "IN_PROGRESS", "data": None},
                    }
                return httpx2.Response(200, json=body, request=request)

            with (
                patch.dict(os.environ, PROXY_ENV),
                patch("zhenzhen_image_mcp.api.api_key", return_value="test-credential"),
                patch("zhenzhen_image_mcp.server.api_key", return_value="test-credential"),
                patch("zhenzhen_image_mcp.server.Settings.load", return_value=settings),
                patch.object(DefaultAsyncHttpxClient, "send", send),
            ):
                async with Client(mcp, mode="legacy") as client:
                    submitted = await client.call_tool(
                        "submit_image_generation", {"model": FLARE, "prompt": "blue bag"}
                    )
                    self.assertFalse(submitted.is_error)
                    task = json.loads(submitted.content[0].text)
                    self.assertEqual(task["task_id"], "proxy_task")
                    queried = await client.call_tool(
                        "get_image_task", {"task_id": task["task_id"], "save": False}
                    )
                    self.assertFalse(queried.is_error)
                    self.assertEqual(json.loads(queried.content[0].text)["status"], "IN_PROGRESS")
            self.assertEqual([r.method for r in requests], ["POST", "GET"])

    async def test_invalid_proxy_reports_redacted_error_without_send_or_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            for exc_type in (httpx.InvalidURL, httpx2.InvalidURL):
                with (
                    self.subTest(exc_type=exc_type),
                    patch(
                        "zhenzhen_image_mcp.server.Settings.load",
                        return_value=Settings("https://provider.example/v1", Path(temporary)),
                    ),
                    patch("zhenzhen_image_mcp.api.api_key", return_value="private-test-credential"),
                    patch("zhenzhen_image_mcp.server.api_key", return_value="private-test-credential"),
                    patch.object(
                        API,
                        "sdk",
                        side_effect=exc_type(
                            "Invalid port: private-test-credential Bearer token https://proxy.example/private"
                        ),
                    ) as sdk,
                ):
                    async with Client(mcp, mode="legacy") as client:
                        result = await client.call_tool(
                            "submit_image_generation", {"model": FLARE, "prompt": "blue bag"}
                        )
                    self.assertTrue(result.is_error)
                    text = result.content[0].text
                    self.assertIn("Invalid port", text)
                    for sensitive in ("private-test-credential", "Bearer token", "https://proxy.example"):
                        self.assertNotIn(sensitive, text)
                    self.assertEqual(sdk.call_count, 1)
