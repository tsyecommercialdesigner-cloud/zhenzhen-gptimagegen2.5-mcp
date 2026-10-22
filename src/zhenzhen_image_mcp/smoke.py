"""Member-facing, no-cost MCP handshake and discovery validation."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx2
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp.client.streamable_http import streamable_http_client

from .api import safe_error, sanitize_proxy_env
from .config import user_variable

EXPECTED_TOOLS = {
    "get_model_guide",
    "generate_image",
    "edit_image",
    "submit_image_generation",
    "submit_image_edit",
    "submit_image_batch",
    "run_image_batch",
    "get_image_batch",
    "get_batch_image_task",
    "get_image_task",
    "wait_image_task",
    "download_image",
}


@asynccontextmanager
async def proxy_transport(url: str, token: str):
    sanitize_proxy_env()
    async with httpx2.AsyncClient(
        headers={"Authorization": f"Bearer {token}"}, follow_redirects=False
    ) as http:
        async with streamable_http_client(url, http_client=http) as streams:
            yield streams


async def check(args: argparse.Namespace) -> dict:
    target: Any
    if args.proxy_url:
        token = user_variable(args.token_env) or os.environ.get(args.token_env, "")
        if not token:
            raise ValueError(f"{args.token_env} is missing")
        target = proxy_transport(args.proxy_url, token)
    else:
        target = StdioServerParameters(
            command=sys.executable,
            args=["-m", "zhenzhen_image_mcp"],
            cwd=str(Path.home()),
            env=dict(os.environ),
        )
    async with asyncio.timeout(args.timeout):
        # Legacy mode explicitly verifies initialize + initialized, also used by older Hosts.
        async with Client(target, mode="legacy", read_timeout_seconds=args.timeout) as client:
            tools = await client.list_tools()
            prompts = await client.list_prompts()
            resources = await client.list_resources()
            templates = await client.list_resource_templates()
            assert {x.name for x in tools.tools} == EXPECTED_TOOLS, "Tool inventory mismatch"
            assert {x.name for x in prompts.prompts} == {"image_workflow"}, "Prompt inventory mismatch"
            assert {str(x.uri) for x in resources.resources} == {"zhenzhen://models"}, (
                "Resource inventory mismatch"
            )
            assert not templates.resource_templates, "Unexpected resource templates"
            resource = await client.read_resource("zhenzhen://models")
            assert resource.contents, "Resource unreadable"
            prompt = await client.get_prompt("image_workflow", {"request": "测试模型建议，不执行绘图"})
            assert prompt.messages, "Prompt unavailable"
            guide = await client.call_tool("get_model_guide", {})
            assert not guide.is_error, "Local guide failed"
            # Validation must reject an unsupported model without an upstream request.
            invalid = await client.call_tool("generate_image", {"prompt": "test", "model": "invalid-model"})
            assert invalid.is_error, "Model enum validation failed"
            if args.inventory:
                Path(args.inventory).write_text(
                    json.dumps(
                        {
                            "tools": [x.model_dump(mode="json", by_alias=True) for x in tools.tools],
                            "prompts": [x.model_dump(mode="json", by_alias=True) for x in prompts.prompts],
                            "resources": [
                                x.model_dump(mode="json", by_alias=True) for x in resources.resources
                            ],
                            "resource_templates": [],
                        },
                        indent=2,
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
            return {
                "passed": True,
                "transport": "proxy" if args.proxy_url else "stdio",
                "tools": len(tools.tools),
                "prompts": len(prompts.prompts),
                "resources": len(resources.resources),
                "paid_calls": 0,
            }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proxy-url")
    parser.add_argument("--token-env", default="CHERRYSTUDIO_API_GATEWAY_API_KEY")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--inventory")
    args = parser.parse_args()
    if not 1 <= args.timeout <= 300:
        parser.error("timeout must be 1..300")
    logging.basicConfig(level=logging.CRITICAL)
    try:
        print(json.dumps(asyncio.run(check(args)), ensure_ascii=False))
    except Exception as exc:
        # Do not print traceback, HTTP headers or third-party exception bodies.
        print(f"Smoke test failed: {type(exc).__name__}: {safe_error(exc)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
