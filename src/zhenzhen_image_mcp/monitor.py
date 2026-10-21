"""Read-only provider polling with durable, cross-process 90-second scheduling."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from .api import API, result_manifest
from .batch import checkpoint_io
from .checkpoints import CheckpointStore

logger = logging.getLogger(__name__)


class TaskMonitor:
    def __init__(self, api: API | None = None, store: CheckpointStore | None = None):
        self.api = api if api is not None else API()
        self.store = store if store is not None else CheckpointStore()

    async def tick(self) -> None:
        budget = self.api.settings.timeout + 180
        rows = await checkpoint_io(self.store.claim_polls, self.api.settings.base_url, 5, budget + 90)

        async def poll(row: dict) -> None:
            status = None
            result = None
            try:
                async with asyncio.timeout(budget):
                    # Automatic retries occur on the next 90s schedule, never in a burst.
                    task = await self.api.fetch_task(row["provider_task_id"], attempts=1)
                    if row["status"] == "SUCCESS" and task["status"] != "SUCCESS":
                        raise ValueError("Provider returned a regressed terminal state")
                    status = task["status"]
                    if status != "FAILURE":
                        result = result_manifest(
                            await self.api.task_result(
                                row["provider_task_id"], task, row["output_dir"], True, record=False
                            )
                        )
            except asyncio.CancelledError:
                raise  # Keep the durable lease: restarting cannot double-poll this task.
            except Exception:
                logger.warning("Automatic task retrieval failed; retry scheduled, no submission repeated")
            await checkpoint_io(self.store.finish_poll, row, status, result)

        async with asyncio.TaskGroup() as group:
            for row in rows:
                group.create_task(poll(row))

    async def run(self) -> None:
        while True:
            try:
                await self.tick()
            except Exception:
                logger.warning("Automatic polling storage unavailable; retaining all task identities")
            await asyncio.sleep(5)


@asynccontextmanager
async def monitor_lifespan(_server):
    """Bound to the MCP server, rather than an individual tool or client request."""
    worker = asyncio.create_task(TaskMonitor().run())
    try:
        yield {}
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
