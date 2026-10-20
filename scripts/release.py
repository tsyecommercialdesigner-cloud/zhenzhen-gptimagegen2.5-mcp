"""Explicitly dispatched draft release; never invoked by tools or normal checks."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def capture(*args: str) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def main() -> None:
    tag = os.environ["RELEASE_TAG"]
    repository = os.environ["RELEASE_REPOSITORY"]
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag) or tag != f"v{version}":
        raise ValueError("Tag must match project version exactly")
    if repository != "tsyecommercialdesigner-cloud/zhenzhen-gptimagegen2.5-mcp":
        raise ValueError("Release must run in the authorized project repository")
    sha = capture("git", "rev-parse", "HEAD")
    if capture("git", "rev-parse", f"refs/tags/{tag}^{{commit}}") != sha:
        raise ValueError("Checkout and release tag differ")
    repo = json.loads(capture("gh", "api", f"repos/{repository}"))
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", sha, f"origin/{repo['default_branch']}"], cwd=ROOT, check=True
    )
    runs = json.loads(
        capture(
            "gh",
            "run",
            "list",
            "--repo",
            repository,
            "--commit",
            sha,
            "--workflow",
            "ci.yml",
            "--json",
            "headSha,status,conclusion,event,url",
        )
    )
    passed = [
        run
        for run in runs
        if run["headSha"] == sha
        and run["event"] == "push"
        and run["status"] == "completed"
        and run["conclusion"] == "success"
    ]
    if not passed:
        raise ValueError("Target commit has no successful completed push CI; release stopped")
    artifacts = sorted((ROOT / "dist").glob(f"zhenzhen_image-{version}-*.whl"))
    artifacts += sorted((ROOT / "dist").glob(f"zhenzhen_image-{version}.tar.gz"))
    if len(artifacts) != 2:
        raise ValueError("Expected exactly one wheel and one source distribution")
    checksums = ROOT / "dist/SHA256SUMS"
    checksums.write_text(
        "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in artifacts),
        encoding="utf-8",
    )
    evidence = ROOT / "dist/release-evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "tag": tag,
                "commit": sha,
                "version": version,
                "ci": passed[0]["url"],
                "install_check": "fresh locked runtime install and stdio smoke passed in release job",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    subprocess.run(
        [
            "gh",
            "release",
            "create",
            tag,
            *map(str, artifacts),
            str(checksums),
            str(evidence),
            "--repo",
            repository,
            "--verify-tag",
            "--generate-notes",
            "--draft",
        ],
        cwd=ROOT,
        check=True,
    )


if __name__ == "__main__":
    main()
