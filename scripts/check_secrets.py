"""A project-scoped secret guard; never reads private .env or Host configurations."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKEN = re.compile(r"\b(?:sk|cs-sk)-[A-Za-z0-9_-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")


def check() -> None:
    for folder in ("src", "scripts", "tests", "docs", ".github"):
        for path in (ROOT / folder).rglob("*"):
            if path.is_file() and path.suffix in {".py", ".md", ".json", ".toml", ".yml", ".yaml"}:
                if TOKEN.search(path.read_text(encoding="utf-8")):
                    raise ValueError(f"Possible credential in {path.relative_to(ROOT)}; value suppressed")
    for path in (ROOT / "README.md", ROOT / "MANUAL.md"):
        if TOKEN.search(path.read_text(encoding="utf-8")):
            raise ValueError(f"Possible credential in {path.name}; value suppressed")
    example = [
        line.strip()
        for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    if example != ["ZHENZHEN_GPTIMAGEGEN_API_KEY="]:
        raise ValueError("Only an empty credential example can be shared")
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    for name in tracked:
        if Path(name).name.startswith(".env") and Path(name).name != ".env.example":
            raise ValueError("Private environment file is tracked; stop delivery")
        if name in {".mcp.json", ".cherrystudiomcpproxy.mcp.json"}:
            raise ValueError("Private Host configuration is tracked; stop delivery")


if __name__ == "__main__":
    check()
    print("PASS: project credential patterns and empty .env.example; private files were not read.")
