"""Per-event-loop limits shared by single calls and concurrent batches in this process."""

from __future__ import annotations

import asyncio
from weakref import WeakKeyDictionary

SYNC_CONCURRENCY = 5
ASYNC_CONCURRENCY = 20
_slots: WeakKeyDictionary = WeakKeyDictionary()


def submission_slots(asynchronous: bool) -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    if loop not in _slots:
        _slots[loop] = (asyncio.Semaphore(SYNC_CONCURRENCY), asyncio.Semaphore(ASYNC_CONCURRENCY))
    return _slots[loop][int(asynchronous)]
