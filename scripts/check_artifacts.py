"""Verify build contents separately from Git ignore and optional ZIP allowlists."""

from __future__ import annotations

import re
import tarfile
import tomllib
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PROHIBITED = {"outputs", "output", ".venv", ".git", ".runtime", "__pycache__", "node_modules"}


def safe(name: str) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or ":" in name or "\\" in name:
        raise ValueError("Unsafe build archive path")
    if any(part in PROHIBITED for part in path.parts):
        raise ValueError(f"Generated or private data in artifact: {name}")
    if any(part.startswith(".env") and part != ".env.example" for part in path.parts):
        raise ValueError("Private environment file in artifact")


def check() -> None:
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    wheel = ROOT / "dist" / f"zhenzhen_image-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            safe(name)
        required = {
            "zhenzhen_image_mcp/" + name
            for name in (
                "__main__.py",
                "contracts.py",
                "provider.py",
                "tasks.py",
                "batch.py",
                "checkpoints.py",
            )
        }
        if not required <= set(archive.namelist()):
            raise ValueError("Incomplete wheel entry points")
    with tarfile.open(ROOT / "dist" / f"zhenzhen_image-{version}.tar.gz") as archive:
        for entry in archive.getmembers():
            safe(entry.name)
            if entry.issym() or entry.islnk():
                raise ValueError("Links are not permitted in source distribution")
            if entry.isfile() and re.search(
                r"\b(?:sk|cs-sk)-[A-Za-z0-9_-]{20,}",
                archive.extractfile(entry).read().decode("utf-8", errors="ignore"),
            ):
                raise ValueError("Possible credential in source distribution; value suppressed")


if __name__ == "__main__":
    check()
    print("PASS: wheel/sdist entries and secret guard; no generated caches or private env.")
