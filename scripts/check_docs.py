"""Validate exact templates, public contracts, all doc configs and workflow syntax."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


class DocumentationLoader(yaml.SafeLoader):
    pass


DocumentationLoader.add_constructor(
    "tag:yaml.org,2002:js", lambda loader, node: loader.construct_scalar(node)
)


def check() -> dict[str, int]:
    counts = {"json": 0, "toml": 0, "yaml": 0}
    for name in ("README.md", "MANUAL.md", "docs/REFACTOR-PLAN.md", "docs/ASYNC-BATCH-PLAN.md"):
        document = (ROOT / name).read_text(encoding="utf-8")
        for lang, body in re.findall(r"^```(json|toml|yaml)\n(.*?)\n```", document, re.M | re.S):
            if lang == "json":
                if body != json.dumps(json.loads(body), indent=2, ensure_ascii=False):
                    raise ValueError(f"Noncanonical JSON in {name}")
            elif lang == "toml":
                tomllib.loads(body)
            else:
                yaml.load(body, Loader=DocumentationLoader)
            counts[lang] += 1
    manual = (ROOT / "MANUAL.md").read_text(encoding="utf-8")
    if len(re.findall(r"^## \d+\.", manual, re.M)) != 10:
        raise ValueError("MANUAL must contain ten numbered sections")
    for name in (".mcp.json.example", ".cherrystudiomcpproxy.mcp.json.example"):
        raw = (ROOT / name).read_text(encoding="utf-8").strip()
        if raw not in manual:
            raise ValueError(f"Template differs from MANUAL: {name}")
        for service, config in json.loads(raw)["mcpServers"].items():
            if "." in service or "cwd" in config or "env" in config:
                raise ValueError(f"Invalid default stdio/HTTP template: {name}")
    for path in (ROOT / ".github/workflows").glob("*.yml"):
        workflow = yaml.load(path.read_text(encoding="utf-8"), Loader=DocumentationLoader)
        for job in workflow["jobs"].values():
            for step in job.get("steps", []):
                action = step.get("uses", "")
                if action and not action.startswith("./") and not re.search(r"@[a-f0-9]{40}$", action):
                    raise ValueError(f"Action must use a full verified SHA: {action}")
    return counts


if __name__ == "__main__":
    print(json.dumps({"passed": True, "blocks": check(), "javascript_executed": False}))
