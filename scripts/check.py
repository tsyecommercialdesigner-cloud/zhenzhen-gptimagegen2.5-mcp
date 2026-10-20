"""One local/CI entry point; never installs dependencies or calls paid endpoints."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Query public vulnerability advisories for locked runtime dependencies",
    )
    parser.add_argument("--build", action="store_true", help="Build the wheel and source distribution")
    args = parser.parse_args()
    run(sys.executable, "-m", "ruff", "format", "--check", "src", "tests", "scripts")
    run(sys.executable, "-m", "ruff", "check", "src", "tests", "scripts")
    run(sys.executable, "-m", "mypy", "src")
    run(sys.executable, "scripts/check_secrets.py")
    run(sys.executable, "scripts/check_docs.py")
    reports = ROOT / ".runtime/reports"
    reports.mkdir(parents=True, exist_ok=True)
    run(sys.executable, "-m", "xmlrunner", "discover", "-s", "tests", "-o", str(reports), "-v")
    discovered = reports / "mcp-inventory.json"
    run(sys.executable, "-m", "zhenzhen_image_mcp.smoke", "--timeout", "30", "--inventory", str(discovered))
    if json.loads(discovered.read_text(encoding="utf-8")) != json.loads(
        (ROOT / "docs/mcp-inventory.json").read_text(encoding="utf-8")
    ):
        raise ValueError("Live discovery differs from documented contracts; update inventory and MANUAL")
    if args.build:
        run("uv", "build")
        run(sys.executable, "scripts/check_artifacts.py")
    if args.audit:
        requirements = str(reports / "runtime-requirements.txt")
        run(
            "uv",
            "export",
            "--locked",
            "--no-dev",
            "--no-emit-project",
            "--format",
            "requirements-txt",
            "--output-file",
            requirements,
            "--quiet",
        )
        run(
            sys.executable,
            "-m",
            "pip_audit",
            "--require-hashes",
            "--disable-pip",
            "-r",
            requirements,
            "-f",
            "json",
            "-o",
            str(reports / "dependency-audit.json"),
        )
    print("PASS: local checks completed; no paid provider calls.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
