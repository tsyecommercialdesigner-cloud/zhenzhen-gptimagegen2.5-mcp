"""Bounded async submission and restart-safe, scoped idempotency."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from .api import API, PreparedImages, safe_error
from .checkpoints import UNCERTAIN, CheckpointStore, scope_check
from .contracts import BatchImageTask, image_parameters


async def checkpoint_io(method: Callable[..., Any], *args: Any) -> Any:
    """A cancelled coroutine must not leave a SQLite worker using files after exit."""
    worker = asyncio.create_task(asyncio.to_thread(method, *args))
    cancelled = False
    while True:
        try:
            result = await asyncio.shield(worker)
            break
        except asyncio.CancelledError:
            if worker.cancelled():
                raise
            cancelled = True
    if cancelled:
        raise asyncio.CancelledError
    return result


def public_task(row: dict[str, Any], *, reused: bool = True) -> dict[str, Any]:
    result = {
        "task_id": row["task_id"],
        "status": row["status"],
        "provider_task_id": row["provider_task_id"],
        "group": row["group_name"],
        "output_dir": row["output_dir"],
        "reused": reused,
    }
    if row["error"]:
        result["error"] = row["error"]
    if row["status"] == "SUBMITTING":
        result["warning"] = "Submission active or interrupted. Never reclaim or resubmit automatically."
    return result


class BatchService:
    def __init__(self, api: API | None = None, store: CheckpointStore | None = None):
        self.api = api if api is not None else API()
        self.store = store if store is not None else CheckpointStore()

    async def submit(
        self, checkpointer: str, thread_id: str, tasks: list[BatchImageTask], max_concurrency: int = 3
    ) -> dict:
        scope_check(checkpointer, thread_id)
        if not 1 <= len(tasks) <= 10 or not 1 <= max_concurrency <= 10:
            raise ValueError("Batch size and max_concurrency must be 1..10")
        if len({task.task_id for task in tasks}) != len(tasks):
            raise ValueError("Duplicate task_id within the batch; no POST sent")
        # Validate every item's parameter contract before any file/URL preparation or paid request.
        for task in tasks:
            image_parameters(
                task.prompt,
                task.model,
                task.size,
                task.quality,
                task.group,
                task.official_options,
                edit=task.operation == "edit",
                asynchronous=True,
            )
            if task.operation == "edit" and not task.images:
                raise ValueError(f"Editing requires images for task_id={task.task_id}; no POST sent")
        prepared: list[PreparedImages] = []
        total_bytes = 0
        for task in tasks:
            request = await self.api.prepare_images(
                task.prompt,
                task.model,
                task.images,
                task.size,
                task.quality,
                asynchronous=True,
                edit=task.operation == "edit",
                output_dir=task.output_dir,
                group=task.group,
                official_options=task.official_options,
            )
            total_bytes += request.input_bytes
            if total_bytes > 128 * 1024 * 1024:
                raise ValueError("Batch input images/masks exceed 128 MiB; no POST sent")
            prepared.append(request)
        await checkpoint_io(
            self.store.reserve,
            checkpointer,
            thread_id,
            [
                {
                    "task_id": task.task_id,
                    "fingerprint": request.fingerprint,
                    "base_url": self.api.settings.base_url,
                    "output_dir": str(request.directory),
                    "group": request.group,
                }
                for task, request in zip(tasks, prepared, strict=True)
            ],
        )
        semaphore = asyncio.Semaphore(max_concurrency)

        async def submit_one(task: BatchImageTask, request: PreparedImages) -> dict:
            async with semaphore:
                claimed = await checkpoint_io(self.store.claim, checkpointer, thread_id, task.task_id)
                if not claimed:
                    return public_task(
                        await checkpoint_io(self.store.get, checkpointer, thread_id, task.task_id)
                    )
                provider_id = None
                error = None
                try:
                    response = await self.api.send_images(request, asynchronous=True)
                    provider_id = response["task_id"]
                except asyncio.CancelledError:
                    try:
                        await checkpoint_io(self.store.finish, checkpointer, thread_id, task.task_id, None)
                    except (ValueError, OSError):
                        pass  # The durable SUBMITTING claim still prevents resubmission.
                    raise
                except Exception as exc:
                    # Conservative after the durable claim: even malformed 200s may be billable.
                    error = safe_error(exc) if isinstance(exc, ValueError) else type(exc).__name__
                try:
                    await checkpoint_io(self.store.finish, checkpointer, thread_id, task.task_id, provider_id)
                except (ValueError, OSError):
                    # Return an acknowledged ID even if its checkpoint could not be committed.
                    return {
                        "task_id": task.task_id,
                        "status": "SUBMISSION_UNCERTAIN",
                        "provider_task_id": provider_id,
                        "output_dir": str(request.directory),
                        "group": request.group,
                        "reused": False,
                        "error": UNCERTAIN,
                        "warning": "Checkpoint write failed. Preserve provider_task_id and query get_image_task directly.",
                    }
                result = public_task(
                    await checkpoint_io(self.store.get, checkpointer, thread_id, task.task_id),
                    reused=False,
                )
                if error:
                    result["warning"] = error
                return result

        jobs = [asyncio.create_task(submit_one(t, p)) for t, p in zip(tasks, prepared, strict=True)]
        try:
            results = await asyncio.gather(*jobs)
        except BaseException:
            for job in jobs:
                if not job.done() and not job.cancelling():
                    job.cancel()
            # gather may propagate one cancellation before sibling checkpoint cleanup finishes.
            await asyncio.gather(*jobs, return_exceptions=True)
            raise
        return {
            "checkpointer": checkpointer,
            "thread_id": thread_id,
            "status": "ATTENTION_REQUIRED"
            if any(row["status"] in {"SUBMISSION_UNCERTAIN", "SUBMITTING", "FAILURE"} for row in results)
            else "ACCEPTED",
            "tasks": results,
            "next_tool": "get_batch_image_task",
            "note": "Only submission acknowledgements were awaited; image generation continues upstream. Reuse all identity keys.",
        }

    async def snapshot(self, checkpointer: str, thread_id: str) -> dict:
        rows = await checkpoint_io(self.store.list, checkpointer, thread_id)
        return {
            "checkpointer": checkpointer,
            "thread_id": thread_id,
            "status": "SNAPSHOT",
            "tasks": [public_task(row) for row in rows],
            "next_tool": "get_batch_image_task",
            "note": "Local checkpoint snapshot only; no provider queries or submissions were made.",
        }

    async def query(
        self,
        checkpointer: str,
        thread_id: str,
        task_id: str,
        output_dir: str | None = None,
        save: bool = True,
    ) -> dict:
        row = await checkpoint_io(self.store.get, checkpointer, thread_id, task_id)
        if row["provider_task_id"] is None:
            return {"checkpointer": checkpointer, "thread_id": thread_id, **public_task(row)}
        if row["base_url"] != self.api.settings.base_url:
            raise ValueError(
                "Checkpoint provider base URL differs; restore the original configuration to query"
            )
        task = await self.api.fetch_task(row["provider_task_id"])
        await checkpoint_io(self.store.observe, checkpointer, thread_id, task_id, task["status"])
        result = await self.api.task_result(
            row["provider_task_id"],
            task,
            output_dir or row["output_dir"],
            save,
        )
        result["group"] = row["group_name"]
        row["status"] = task["status"]
        return {
            "checkpointer": checkpointer,
            "thread_id": thread_id,
            **public_task(row),
            "result": result,
        }
