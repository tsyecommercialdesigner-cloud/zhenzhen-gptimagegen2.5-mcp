"""Images API and durable task destination metadata."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import ipaddress
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
import httpx2
from openai import APIConnectionError, APIStatusError, AsyncOpenAI, DefaultAsyncHttpxClient

from . import media
from .config import Settings, absolute_directory, api_key
from .contracts import Group, OfficialOptions, image_parameters
from .contracts import size_check as size_check
from .provider import ProviderTransport
from .runtime import submission_slots
from .tasks import PENDING, TaskStore, submitted_task_id, task_payload
from .tasks import task_id_check as task_id_check


def normalize_no_proxy(value: str) -> str:
    """Adapt bracketed IPv6 bypass entries to the pinned httpx2 parser."""
    entries = []
    for entry in value.split(","):
        token = entry.strip()
        match = re.fullmatch(r"\[([^\]]+)\](?::([0-9]+))?", token)
        if match:
            try:
                ipaddress.IPv6Address(match[1])
            except ValueError:
                pass  # Leave invalid configuration visible rather than silently dropping it.
            else:
                # Bare IPv6 matches every port. URL form preserves an explicit port.
                token = f"all://[{match[1]}]:{match[2]}" if match[2] else match[1]
        entries.append(token)
    return ",".join(entries)


def sanitize_proxy_env() -> None:
    """Normalize this MCP process only; retain proxy URLs and bypass semantics."""
    for name in ("no_proxy", "NO_PROXY"):
        raw = os.environ.get(name)
        if raw is not None:
            cleaned = normalize_no_proxy(raw)
            if cleaned != raw:
                os.environ[name] = cleaned


def safe_error(exc: BaseException, secret: str = "") -> str:
    value = str(exc)
    if secret:
        value = value.replace(secret, "[REDACTED]")
    value = re.sub(r"https?://[^\s\"<>]+", "[URL omitted]", value)
    value = re.sub(r"(?i)Bearer\s+\S+|\b(?:sk|cs-sk)-[\w-]+", "[REDACTED]", value)
    return value[:800] or type(exc).__name__


def redact_payload(value: Any) -> Any:
    if isinstance(value, list):
        return [redact_payload(x) for x in value]
    if isinstance(value, dict):
        return {
            k: (
                "[image data omitted]"
                if k == "b64_json" or (k == "result" and value.get("type") == "image_generation_call")
                else redact_payload(v)
            )
            for k, v in value.items()
        }
    if isinstance(value, str) and value.startswith("data:image/"):
        return "[image data omitted]"
    return value


def image_items(payload: dict) -> list[dict]:
    result: list[dict] = []
    # Images API object; asynchronous envelope is unwrapped by query().
    if isinstance(payload.get("data"), list):
        result.extend(
            x for x in payload["data"] if isinstance(x, dict) and (x.get("url") or x.get("b64_json"))
        )
    return result


class TransientQueryError(ValueError):
    """Only read-only task requests may be retried."""


def result_manifest(result: dict) -> dict:
    """Persist only local result metadata, never upstream prompts, URLs or image bodies."""
    return {
        k: result[k]
        for k in ("status", "task_id", "group", "output_dir", "files", "save_status")
        if k in result
    }


def verify_manifest(result: dict) -> None:
    for file in result.get("files", []):
        path = Path(file["path"])
        if path.is_symlink() or not path.is_file() or path.stat().st_size != file["bytes"]:
            raise ValueError("Saved result file missing or changed; do not resubmit the paid task")
        if hashlib.sha256(path.read_bytes()).hexdigest() != file["sha256"]:
            raise ValueError("Saved result file hash mismatch; do not resubmit the paid task")


@dataclass
class PreparedImages:
    endpoint: str
    kwargs: dict[str, Any]
    directory: Path
    group: Group
    fingerprint: str
    input_bytes: int


class API:
    """Image workflow orchestration; provider protocol and task state are separate."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings.load()

    def destination(self, output_dir: str | None) -> Path:
        return media.prepare_directory(
            absolute_directory(output_dir) if output_dir else self.settings.output_dir
        )

    def sdk(self, key: str) -> AsyncOpenAI:
        # Explicitly disable SDK retries: a timeout does not prove non-submission.
        sanitize_proxy_env()
        return AsyncOpenAI(
            api_key=key,
            base_url=self.settings.base_url + "/",
            timeout=self.settings.timeout,
            max_retries=0,
            http_client=DefaultAsyncHttpxClient(follow_redirects=False),
        )

    async def request(self, method: str, endpoint: str, **kwargs: Any) -> dict:
        key = api_key()
        try:
            async with asyncio.timeout(self.settings.timeout):
                return await ProviderTransport(self.sdk).request(method, endpoint, key, **kwargs)
        except APIStatusError as exc:
            if method == "GET" and exc.status_code in {408, 429, 500, 502, 503, 504}:
                raise TransientQueryError(f"Provider HTTP {exc.status_code}") from None
            raise ValueError(
                f"Provider HTTP {exc.status_code}; check credentials, group, model and parameters. Request is not retried."
            ) from None
        except (APIConnectionError, httpx.HTTPError, httpx2.HTTPError, TimeoutError) as exc:
            if method == "GET":
                raise TransientQueryError("Provider query timed out or failed in transit") from None
            raise ValueError(
                "Provider request timed out or failed in transit; submission outcome may be unknown. Do not automatically resubmit."
            ) from exc
        except (ValueError, TypeError, httpx.InvalidURL, httpx2.InvalidURL) as exc:
            raise ValueError(safe_error(exc, key)) from None

    async def store_images(self, payload: dict, directory: Path) -> dict:
        from .batch import checkpoint_io

        files, failures = [], []
        items = image_items(payload)
        if len(items) > media.MAX_IMAGES:
            raise ValueError("Response contains more than the local 16-image limit")
        if not items:
            raise ValueError("Provider completed without usable images; do not resubmit automatically")
        for index, item in enumerate(items):
            try:
                data = (
                    media.decode_image(item["b64_json"])
                    if item.get("b64_json")
                    else await media.download(item["url"])
                )
                files.append({"index": index, **await checkpoint_io(media.save_image, data, directory)})
            except (ValueError, OSError, httpx.HTTPError, TimeoutError) as exc:
                failures.append({"index": index, "url": item.get("url"), "error": safe_error(exc)})
        return {
            "files": files,
            "download_errors": failures,
            "save_status": "partial"
            if failures and files
            else "failed"
            if failures
            else "saved"
            if files
            else "no_images",
        }

    async def prepare_images(
        self,
        prompt: str,
        model: str,
        images: list[str] | None = None,
        size: str | None = None,
        quality: str | None = None,
        asynchronous: bool = False,
        edit: bool = False,
        output_dir: str | None = None,
        group: Group = "reverse",
        official_options: OfficialOptions | dict[str, Any] | None = None,
    ) -> PreparedImages:
        payload, mask_source = image_parameters(
            prompt, model, size, quality, group, official_options, edit=edit, asynchronous=asynchronous
        )
        images = images or []
        if len(images) > media.MAX_IMAGES or (edit and not images):
            raise ValueError("Editing requires 1..16 images; generation accepts 0..16")
        # Validate credentials and destination before uploading data or incurring charges.
        api_key()
        directory = self.destination(output_dir)
        blobs = [await media.read_image(source) for source in images]
        if sum(map(len, blobs)) > 100 * 1024 * 1024:
            raise ValueError("Combined input images exceed the local 100 MiB limit")
        suffix = "?async=true" if asynchronous else ""
        identity = {
            "version": 1,
            "base_url": self.settings.base_url,
            "edit": edit,
            "asynchronous": asynchronous,
            "group": group,
            "payload": dict(payload),
            "output_dir": str(directory),
            "images": [hashlib.sha256(blob).hexdigest() for blob in blobs],
        }
        input_bytes = sum(map(len, blobs))
        if edit:
            files = [
                ("image[]", (f"reference-{i}{media.image_info(b)[0]}", b, media.image_info(b)[1]))
                for i, b in enumerate(blobs)
            ]
            kwargs: dict[str, Any] = {}
            if mask_source is not None:
                mask = await media.read_image(mask_source)
                media.validate_mask(mask, blobs[0])
                identity["mask"] = hashlib.sha256(mask).hexdigest()
                input_bytes += len(mask)
                kwargs["mask"] = ("mask.png", mask, "image/png")
            endpoint = "/images/edits" + suffix
            kwargs.update(data=payload, files=files)
        else:
            if blobs:
                payload["image"] = [
                    f"data:{media.image_info(b)[1]};base64," + base64.b64encode(b).decode("ascii")
                    for b in blobs
                ]
            endpoint = "/images/generations" + suffix
            kwargs = {"json": payload}
        fingerprint = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        return PreparedImages(endpoint, kwargs, directory, group, fingerprint, input_bytes)

    async def send_images(self, prepared: PreparedImages, asynchronous: bool) -> dict:
        async with submission_slots(asynchronous):
            return await self._send_images(prepared, asynchronous)

    async def _send_images(self, prepared: PreparedImages, asynchronous: bool) -> dict:
        response = await self.request("POST", prepared.endpoint, **prepared.kwargs)
        directory, group = prepared.directory, prepared.group
        if asynchronous:
            task_id = submitted_task_id(response)
            result = {
                "task_id": task_id,
                "status": "SUBMITTED",
                "group": group,
                "output_dir": str(directory),
                "next_tool": "get_image_task or wait_image_task",
                "auto_poll_interval": 90,
            }
            try:
                TaskStore(self.settings.output_dir).record(task_id, directory, group)
            except OSError:
                result["warning"] = (
                    "Task submitted; destination metadata could not be saved. Pass output_dir when polling."
                )
            from .batch import checkpoint_io
            from .checkpoints import CheckpointStore

            try:
                await checkpoint_io(
                    CheckpointStore().watch, self.settings.base_url, task_id, str(directory), group
                )
            except (ValueError, OSError):
                result["warning"] = (
                    "Task accepted but automatic polling registration failed; preserve task_id and query manually."
                )
            return result
        return {
            "status": "COMPLETED",
            "group": group,
            **await self.store_images(response, directory),
            "response": redact_payload(response),
        }

    async def images(
        self,
        prompt: str,
        model: str,
        images: list[str] | None = None,
        size: str | None = None,
        quality: str | None = None,
        asynchronous: bool = False,
        edit: bool = False,
        output_dir: str | None = None,
        group: Group = "reverse",
        official_options: OfficialOptions | dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        prepared = await self.prepare_images(
            prompt, model, images, size, quality, asynchronous, edit, output_dir, group, official_options
        )
        if idempotency_key is not None:
            from .batch import BatchService, checkpoint_io
            from .contracts import BatchImageTask

            task = BatchImageTask(
                task_id=idempotency_key,
                prompt=prompt,
                model=model,  # type: ignore[arg-type]
                operation="edit" if edit else "generate",
            )
            batch = await BatchService(api=self).execute(
                "single", "default", [task], [prepared], 1, asynchronous
            )
            row = batch["tasks"][0]
            if row["status"] == "FAILURE":
                raise ValueError(f"Task {idempotency_key}: FAILURE; do not resubmit")
            if row.get("result"):
                await checkpoint_io(verify_manifest, row["result"])
                return {
                    **row["result"],
                    "idempotency_key": idempotency_key,
                    "reused": row["reused"],
                    **({"warning": row["warning"]} if row.get("warning") else {}),
                }
            if asynchronous and row["provider_task_id"]:
                return {
                    "status": "SUBMITTED",
                    "task_id": row["provider_task_id"],
                    "group": group,
                    "output_dir": str(prepared.directory),
                    "auto_poll_interval": 90,
                    "idempotency_key": idempotency_key,
                    "reused": row["reused"],
                }
            raise ValueError(
                f"Task {idempotency_key}: {row['status']}; do not resubmit or change the idempotency key"
            )
        return await self.send_images(prepared, asynchronous)

    async def fetch_task(self, task_id: str, *, attempts: int = 3) -> dict:
        task_id_check(task_id)
        tried = 0
        try:
            # This budget includes all attempts and backoff, not one budget per retry.
            async with asyncio.timeout(self.settings.timeout):
                for attempt in range(attempts):
                    tried += 1
                    try:
                        envelope = await self.request("GET", "/images/tasks/" + quote(task_id, safe=""))
                        break
                    except TransientQueryError:
                        if attempt == attempts - 1:
                            raise
                        await asyncio.sleep(2**attempt)
        except (ValueError, TimeoutError) as exc:
            reason = str(exc) or "Query time budget exceeded"
            raise ValueError(
                f"Task {task_id}: query failed after {tried} attempt(s): {reason}. "
                "Use get_image_task or wait_image_task with the same task_id; do not resubmit."
            ) from None
        return task_payload(envelope, task_id)

    async def query(self, task_id: str, output_dir: str | None = None, save: bool = True) -> dict:
        return await self.task_result(task_id, await self.fetch_task(task_id), output_dir, save)

    async def task_result(
        self, task_id: str, task: dict, output_dir: str | None, save: bool, *, record: bool = True
    ) -> dict:
        from .batch import checkpoint_io
        from .checkpoints import CheckpointStore

        if task["status"] == "FAILURE":
            if record:
                await checkpoint_io(
                    CheckpointStore().observe_provider, self.settings.base_url, task_id, "FAILURE", None
                )
            reason = safe_error(ValueError(str(task.get("fail_reason") or "Provider task failed")))
            raise ValueError(f"Task {task_id}: FAILURE: {reason}; do not resubmit automatically")
        result = {
            "task_id": task_id,
            "status": task["status"],
            "progress": task.get("progress"),
            "fail_reason": "",
            "response": redact_payload(task.get("data")),
        }
        if "cost" in task:
            result["cost"] = task["cost"]
        if isinstance(task.get("data"), dict) and "usage" in task["data"]:
            result["usage"] = task["data"]["usage"]
        if task["status"] == "SUCCESS" and save:
            if not output_dir:
                metadata = TaskStore(self.settings.output_dir).load(task_id)
                output_dir = metadata.get("output_dir")
                if "group" in metadata:
                    result["group"] = metadata["group"]
            payload = task.get("data")
            if not isinstance(payload, dict):
                raise ValueError("Successful task has no image result object")
            result.update(await self.store_images(payload, self.destination(output_dir)))
        if record:
            await checkpoint_io(
                CheckpointStore().observe_provider,
                self.settings.base_url,
                task_id,
                task["status"],
                result_manifest(result),
            )
        return result

    async def wait(
        self, task_id: str, timeout_seconds: float, poll_interval: float, output_dir: str | None
    ) -> dict:
        if not 1 <= timeout_seconds <= 300 or not 1 <= poll_interval <= 300:
            raise ValueError("timeout_seconds must be 1..300 and poll_interval 1..300")
        deadline = time.monotonic() + timeout_seconds
        last = {"task_id": task_id, "status": "UNKNOWN"}
        try:
            async with asyncio.timeout(timeout_seconds):
                while True:
                    task = await self.fetch_task(task_id)
                    last = await self.task_result(task_id, task, output_dir, save=False)
                    if last["status"] not in PENDING:
                        break
                    await asyncio.sleep(min(poll_interval, max(0, deadline - time.monotonic())))
        except TimeoutError:
            return {
                **last,
                "wait_timed_out": True,
                "next_tool": "get_image_task or wait_image_task",
                "note": "Cloud task was not cancelled; do not resubmit.",
            }
        # Saving has its own bounded timeout, separate from the polling budget.
        return (
            await self.task_result(task_id, task, output_dir, save=True)
            if last["status"] == "SUCCESS"
            else last
        )
