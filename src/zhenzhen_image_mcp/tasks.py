"""Provider response normalization and restart-safe local task destinations."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .contracts import Group

PENDING = {"NOT_START", "IN_PROGRESS"}
STATES = PENDING | {"FAILURE", "SUCCESS"}


def task_id_check(task_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", task_id):
        raise ValueError("Invalid task_id; expected 1..128 letters, digits, underscores or hyphens")
    return task_id


def submitted_task_id(response: dict[str, Any]) -> str:
    candidates = [response.get("task_id")]
    data = response.get("data")
    candidates.append(data.get("task_id") if isinstance(data, dict) else data)
    ids = [task_id_check(value) for value in candidates if isinstance(value, str) and value]
    if not ids:
        raise ValueError("Async submission response has no task ID; do not automatically resubmit")
    if len(set(ids)) != 1:
        raise ValueError("Conflicting task IDs in submission response; do not resubmit")
    return ids[0]


def task_payload(envelope: dict[str, Any], task_id: str) -> dict[str, Any]:
    task = envelope.get("data")
    if not isinstance(task, dict) or task.get("status") not in STATES:
        raise ValueError("Unknown task response/status; refusing to infer success")
    if task.get("task_id") and task["task_id"] != task_id:
        raise ValueError("Provider returned a different task ID")
    return task


class TaskStore:
    def __init__(self, root: Path):
        self.root = root / ".tasks"

    def record(self, task_id: str, destination: Path, group: Group) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{task_id_check(task_id)}.json"
        with path.open("x", encoding="utf-8") as stream:
            json.dump({"version": 2, "output_dir": str(destination), "group": group}, stream)

    def load(self, task_id: str) -> dict[str, Any]:
        path = self.root / f"{task_id_check(task_id)}.json"
        try:
            if path.is_symlink() or path.is_junction():
                raise ValueError("Task metadata cannot be a link")
            with path.open("rb") as stream:
                raw = stream.read(65537)
        except FileNotFoundError:
            return {}
        except OSError:
            raise ValueError("Cannot read task destination metadata; supply output_dir explicitly") from None
        try:
            if len(raw) > 65536:
                raise ValueError("Oversized metadata")
            value = json.loads(raw)
            if not isinstance(value, dict) or not isinstance(value.get("output_dir"), str):
                raise ValueError("Invalid metadata")
            if "group" in value and value["group"] not in {"reverse", "official"}:
                raise ValueError("Invalid group")
            return value
        except (ValueError, UnicodeError):
            raise ValueError("Invalid task destination metadata; supply output_dir explicitly") from None
