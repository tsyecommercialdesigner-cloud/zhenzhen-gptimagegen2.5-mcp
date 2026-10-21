"""Audited allowlist packaging; publish only after clean online install + handshake."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
import tomllib
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PROJECT_NAME = "zhenzhen-gptimagegen2.5-mcp"
PROHIBITED = {
    ".git",
    ".agents",
    "output",
    "outputs",
    "tests",
    "examples",
    "docs",
    ".venv",
    "node_modules",
    "offline",
    "__pycache__",
    "build",
    "dist",
}
TOP = {
    ".env.example",
    "pyproject.toml",
    "uv.lock",
    ".python-version",
    ".mcp.json.example",
    ".cherrystudiomcpproxy.mcp.json.example",
    "LICENSE",
    "README.md",
    "MANUAL.md",
    "user-files.json",
}


def audited_files(root: Path = ROOT) -> list[str]:
    names = json.loads((root / "user-files.json").read_text(encoding="utf-8"))
    if not isinstance(names, list) or not names or any(not isinstance(x, str) for x in names):
        raise ValueError("user-files.json must be a nonempty array of paths")
    if len({x.casefold() for x in names}) != len(names):
        raise ValueError("Duplicate member paths")
    for name in names:
        if name.casefold().startswith(".env") and name != ".env.example":
            raise ValueError("Secret env file must not enter the member archive")
        p = PurePosixPath(name)
        if p.is_absolute() or "\\" in name or ":" in name or ".." in p.parts or str(p) != name:
            raise ValueError(f"Unsafe member path: {name}")
        if any(x.casefold() in PROHIBITED for x in p.parts):
            raise ValueError(f"Prohibited member path: {name}")
        allowed = (
            name in TOP
            or name == "scripts/smoke-test.ps1"
            or (name.startswith("src/zhenzhen_image_mcp/") and p.suffix == ".py")
        )
        if not allowed:
            raise ValueError(f"File is not a runtime/install necessity: {name}")
        full = root / name
        if not full.is_file() or not full.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Missing/escaping member file: {name}")
        for ancestor in [full, *full.parents]:
            if ancestor == root:
                break
            if ancestor.is_symlink() or ancestor.is_junction():
                raise ValueError(f"Reparse point in member path: {name}")
    required = (
        TOP
        | {"scripts/smoke-test.ps1"}
        | {x.relative_to(root).as_posix() for x in (root / "src/zhenzhen_image_mcp").glob("*.py")}
    )
    if set(names) != required:
        raise ValueError("Allowlist differs from complete runtime/install file list")
    manual = (root / "MANUAL.md").read_text(encoding="utf-8")
    documented = manual.split("<!-- MEMBER_FILES_START -->", 1)[1].split("<!-- MEMBER_FILES_END -->", 1)[0]
    if set(re.findall(r"^- `([^`]+)`$", documented, re.M)) != set(names):
        raise ValueError("MANUAL member list differs from allowlist")
    for name in (".mcp.json.example", ".cherrystudiomcpproxy.mcp.json.example"):
        raw = (root / name).read_text(encoding="utf-8")
        data = json.loads(raw)
        if raw.rstrip() != json.dumps(data, ensure_ascii=False, indent=2):
            raise ValueError("Configuration formatting is not canonical two-space JSON")
        if raw.rstrip() not in manual:
            raise ValueError("MANUAL configuration differs from template")
        for entry in data["mcpServers"].values():
            if "cwd" in entry or "env" in entry:
                raise ValueError("Template contains prohibited cwd/env")
        if re.search(r"\b(?:sk|cs-sk)-[A-Za-z0-9]{8,}", raw):
            raise ValueError("Possible credential in template")
    # Check distributable sources/docs for accidental token literals, too.
    for name in names:
        if re.search(r"\b(?:sk|cs-sk)-[A-Za-z0-9_-]{20,}", (root / name).read_text(encoding="utf-8")):
            raise ValueError(f"Possible credential in {name}")
    template_lines = [
        line.strip()
        for line in (root / ".env.example").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if template_lines != ["ZHENZHEN_GPTIMAGEGEN_API_KEY="]:
        raise ValueError("Environment template must contain only an empty API key")
    return names


def write_archive(root: Path, archive: Path, names: list[str], project_name: str = PROJECT_NAME) -> None:
    if (
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", project_name)
        or project_name.endswith(".")
        or project_name.split(".")[0].upper()
        in {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            *{f"COM{i}" for i in range(1, 10)},
            *{f"LPT{i}" for i in range(1, 10)},
        }
    ):
        raise ValueError("Unsafe project directory name")
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as z:
        for name in names:
            z.write(root / name, f"{project_name}/{name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    names = audited_files()
    meta = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    for value in (meta["name"], meta["version"]):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", value):
            raise ValueError("Unsafe metadata name/version")
    target = ROOT / "output" / f"{PROJECT_NAME}-{meta['version']}-user.zip"
    if not args.verify_only and target.exists():
        raise FileExistsError("Release already exists; refusing to overwrite")
    subprocess.run(["uv", "build"], cwd=ROOT, check=True, timeout=300)
    print("Verification requires online registry access and an empty dedicated uv cache.", flush=True)
    with tempfile.TemporaryDirectory(prefix="zhenzhen-member-verify-") as temporary:
        temp = Path(temporary).resolve()
        if not temp.is_relative_to(Path(tempfile.gettempdir()).resolve()) or temp.is_relative_to(ROOT):
            raise ValueError("Unexpected verification directory")
        archive = temp / target.name
        write_archive(ROOT, archive, names)
        with zipfile.ZipFile(archive) as z:
            expected = [f"{PROJECT_NAME}/{name}" for name in names]
            if sorted(z.namelist()) != sorted(expected) or z.testzip() is not None:
                raise ValueError("Archive content validation failed")
            z.extractall(temp)
        extracted = temp / PROJECT_NAME
        audited_files(extracted)
        env = dict(os.environ)
        # Isolate installation from caller project/env/cache settings.
        for key in list(env):
            if key.startswith("UV_") or key in {"VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME"}:
                env.pop(key)
        env["UV_CACHE_DIR"] = str(temp / "empty-cache")
        env["UV_LINK_MODE"] = "copy"
        subprocess.run(
            ["uv", "sync", "--locked", "--no-dev", "--python", "3.12.14"],
            cwd=extracted,
            env=env,
            check=True,
            timeout=600,
        )
        # Use installed interpreter from a different CWD; no ancestor environment.
        python = extracted / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run(
            [str(python), "-m", "zhenzhen_image_mcp.smoke"], cwd=temp, env=env, check=True, timeout=60
        )
        # Verify the fixed root also works when the package is a wheel in the project venv.
        subprocess.run(
            ["uv", "sync", "--locked", "--no-dev", "--no-editable"],
            cwd=extracted,
            env=env,
            check=True,
            timeout=600,
        )
        subprocess.run(
            [str(python), "-m", "zhenzhen_image_mcp.smoke"], cwd=temp, env=env, check=True, timeout=60
        )
        # Reproduce the Host's proxy environment in the extracted member runtime.
        # Client construction/routing only: no provider request and no real credential.
        proxy_check = r"""
import asyncio
import httpx2
from zhenzhen_image_mcp.api import API
from zhenzhen_image_mcp.batch import BatchService
from zhenzhen_image_mcp.checkpoints import CheckpointStore
from zhenzhen_image_mcp.config import PROJECT_DIR, KEY_NAME, api_key
path = PROJECT_DIR / '.env'
assert not path.exists()
try:
    path.write_text(KEY_NAME + '=member-test-placeholder\n', encoding='utf-8-sig')
    assert api_key() == 'member-test-placeholder'
finally:
    path.unlink(missing_ok=True)
async def check():
    async with API().sdk('member-validation-placeholder') as sdk:
        client = sdk._client
        assert sdk.max_retries == 0
        assert client._transport_for_url(httpx2.URL('http://[::1]/')) is client._transport
        assert client._transport_for_url(httpx2.URL('https://provider.example/')) is not client._transport
asyncio.run(check())
store = CheckpointStore()
assert store.path == PROJECT_DIR / '.runtime' / 'checkpoints.sqlite3'
assert not store.path.exists()
assert asyncio.run(BatchService().snapshot('install-probe', 'thread'))['tasks'] == []
assert not store.path.exists()
store.reserve('install-probe', 'thread', [{
    'task_id': 'page_01', 'fingerprint': 'installation-probe',
    'base_url': 'https://provider.example/v1',
    'output_dir': str(PROJECT_DIR), 'group': 'reverse',
}])
assert store.claim('install-probe', 'thread', 'page_01')
store.finish('install-probe', 'thread', 'page_01', 'installation_provider_01')
assert not CheckpointStore().claim('install-probe', 'thread', 'page_01')
assert CheckpointStore().get('install-probe', 'thread', 'page_01')['provider_task_id'] == 'installation_provider_01'
print('PASS: member checkpoint root, SQLite persistence and duplicate claim guard; no cloud request.')
print('PASS: member SDK construction and IPv6 proxy bypass; no cloud request.')
"""
        proxy_env = {
            **env,
            "NO_PROXY": "localhost,127.0.0.1,::1,[::1]",
            "HTTP_PROXY": "http://127.0.0.1:9",
            "HTTPS_PROXY": "http://127.0.0.1:9",
            "ALL_PROXY": "",
        }
        # Avoid two conflicting spellings on platforms with case-sensitive environments.
        proxy_env.pop("no_proxy", None)
        subprocess.run([str(python), "-c", proxy_check], cwd=temp, env=proxy_env, check=True, timeout=60)
        if not args.verify_only:
            target.parent.mkdir(exist_ok=True)
            # Exclusive create across volumes; unlink an incomplete copy only on failure.
            with target.open("xb") as out:
                try:
                    out.write(archive.read_bytes())
                except BaseException:
                    out.close()
                    target.unlink()
                    raise
            print(f"Verified release: {target}")
        else:
            print(
                "PASS: exact archive entries, fresh online installation and MCP handshake. No member ZIP retained."
            )


if __name__ == "__main__":
    main()
