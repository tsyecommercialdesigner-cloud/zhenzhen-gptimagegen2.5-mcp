"""Bounded JSON / Images SSE transport through the locked official OpenAI SDK."""

from __future__ import annotations

import codecs
import json
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx2
from openai import AsyncOpenAI

MAX_RESPONSE_BYTES = 256 * 1024 * 1024
COMMON_FIELDS = {
    "prompt",
    "model",
    "size",
    "quality",
    "n",
    "background",
    "output_format",
    "output_compression",
    "response_format",
    "user",
    "stream",
    "partial_images",
}


def checked_object(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Provider returned a non-object JSON response")
    if data.get("error"):
        raise ValueError("Provider returned an error object; request is not retried")
    if "code" in data and data["code"] not in {"success", "SUCCESS", 0, 200}:
        raise ValueError("Provider returned a non-success business code")
    return data


async def read_json(chunks: AsyncIterator[bytes]) -> dict[str, Any]:
    raw = bytearray()
    async for chunk in chunks:
        raw.extend(chunk)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError("Provider response exceeds the local 256 MiB limit")
    try:
        return checked_object(json.loads(raw))
    except (json.JSONDecodeError, UnicodeError):
        raise ValueError("Provider returned invalid JSON; request is not retried") from None


async def read_image_events(chunks: AsyncIterator[bytes]) -> dict[str, Any]:
    decoder = codecs.getincrementaldecoder("utf-8")()
    pending = ""
    data_lines: list[str] = []
    result: dict[str, Any] = {"data": []}
    consumed = 0

    def event() -> None:
        if not data_lines:
            return
        text = "\n".join(data_lines)
        data_lines.clear()
        if text == "[DONE]":
            return
        try:
            item = json.loads(text)
        except json.JSONDecodeError:
            raise ValueError("Invalid image streaming event; do not resubmit") from None
        if (
            not isinstance(item, dict)
            or item.get("error")
            or item.get("type") in {"error", "image_generation.failed", "image_edit.failed"}
        ):
            raise ValueError("Provider image stream failed; do not resubmit")
        kind = item.get("type", "")
        if kind in {"image_generation.partial_image", "image_edit.partial_image"}:
            return
        if kind not in {"image_generation.completed", "image_edit.completed"}:
            raise ValueError("Unknown image streaming event; do not resubmit")
        if not (item.get("b64_json") or item.get("url")):
            raise ValueError("Image completion event has no final image; do not resubmit")
        if len(result["data"]) >= 16:
            raise ValueError("Too many completed images in stream")
        result["data"].append(
            {key: item[key] for key in ("b64_json", "url", "revised_prompt") if key in item}
        )
        for key in ("usage", "background", "output_format", "quality", "size"):
            if key in item:
                result[key] = item[key]
        if "created_at" in item:
            result["created"] = item["created_at"]

    def line(text: str) -> None:
        if not text:
            event()
        elif text.startswith("data:"):
            data_lines.append(text[5:].lstrip(" "))

    try:
        async for chunk in chunks:
            consumed += len(chunk)
            if consumed > MAX_RESPONSE_BYTES:
                raise ValueError("Provider response exceeds the local 256 MiB limit")
            pending += decoder.decode(chunk)
            while "\n" in pending:
                part, pending = pending.split("\n", 1)
                line(part.rstrip("\r"))
        pending += decoder.decode(b"", final=True)
        if pending:
            line(pending.rstrip("\r"))
        event()
    except UnicodeError:
        raise ValueError("Invalid UTF-8 in image stream; do not resubmit") from None
    if not result["data"]:
        raise ValueError("Image stream ended without a completed image; do not resubmit")
    return result


class ProviderTransport:
    def __init__(self, sdk: Callable[[str], AsyncOpenAI]):
        self.sdk = sdk

    async def request(self, method: str, endpoint: str, key: str, **kwargs: Any) -> dict[str, Any]:
        route, _, query = endpoint.partition("?")
        if query and query != "async=true":
            raise ValueError("Unsupported provider query")
        async with self.sdk(key) as client:
            if method == "GET":
                response = await client.get(route, cast_to=httpx2.Response, stream=True)
                try:
                    return await read_json(response.aiter_bytes())
                finally:
                    await response.aclose()
            if method != "POST" or route not in {"/images/generations", "/images/edits"}:
                raise ValueError("Unsupported endpoint")
            body = dict(kwargs["data"] if route.endswith("edits") else kwargs["json"])
            fields = COMMON_FIELDS | ({"input_fidelity"} if route.endswith("edits") else {"moderation"})
            regular = {name: value for name, value in body.items() if name in fields}
            extra = {name: value for name, value in body.items() if name not in fields}
            extra_query = {"async": "true"} if query else {}
            if route.endswith("edits"):
                if "mask" in kwargs:
                    regular["mask"] = kwargs["mask"]
                context = client.images.with_streaming_response.edit(
                    **regular,
                    image=[entry[1] for entry in kwargs["files"]],
                    extra_query=extra_query,
                    extra_body=extra or None,
                )
            else:
                context = client.images.with_streaming_response.generate(
                    **regular, extra_query=extra_query, extra_body=extra or None
                )
            async with context as response:
                chunks = response.iter_bytes()
                if "text/event-stream" in response.headers.get("content-type", ""):
                    if not body.get("stream") or query:
                        raise ValueError("Unexpected streaming response; do not resubmit")
                    return await read_image_events(chunks)
                return await read_json(chunks)
