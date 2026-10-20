"""Configuration without embedding or displaying credentials."""

from __future__ import annotations

import io
import os
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from dotenv.parser import parse_stream

KEY_NAME = "ZHENZHEN_GPTIMAGEGEN_API_KEY"


def project_directory() -> Path:
    """One deterministic root for source/editable and project-venv wheel installs."""
    module = Path(__file__).resolve()
    if module.parent.parent.name == "site-packages":
        if sys.prefix == sys.base_prefix:
            raise ValueError("Install MCP in its project virtual environment, not global site-packages")
        root = Path(sys.prefix).resolve().parent
    else:
        root = module.parents[2]
    if not (root / "pyproject.toml").is_file():
        raise ValueError("Cannot locate the installed MCP project root; check the project .venv layout")
    try:
        metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        if metadata.get("project", {}).get("name") != "zhenzhen-image":
            raise ValueError("Foreign project")
    except (OSError, UnicodeError, ValueError):
        raise ValueError("MCP root must contain this project's valid pyproject.toml") from None
    return root


PROJECT_DIR = project_directory()
BASE_URL = "https://ai.t8star.org/v1"
FLARE = "gpt-image-2.5-flare"
SUNBURST = "gpt-image-2.5-sunburst"
MODEL_GUIDE = (
    "GPT Image 2.5 Sunburst 非常适合对编辑精度要求极高的应用场景；"
    "GPT Image 2.5 Flare 是目前用于生成高质量图片的最快模型。"
    "模型可以接受文本和图片作为输入，然后输出相应的图片。"
    "以上为用户提供的供应商选型说明，尚未做速度或质量对比实测。"
)


def user_variable(name: str) -> str | None:
    """Read Windows HKCU, even when a GUI inherited stale environment values."""
    if os.name == "nt":
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                value, _ = winreg.QueryValueEx(key, name)
                return value if isinstance(value, str) else None
        except FileNotFoundError:
            return None
    return None


def local_api_key() -> str | None:
    """Read only the project's .env, without interpolation or environment mutation."""
    path = PROJECT_DIR / ".env"
    try:
        with path.open("rb") as stream:
            raw = stream.read(65537)
    except FileNotFoundError:
        return None
    except OSError:
        raise ValueError("Cannot read project .env; check file permissions") from None
    if len(raw) > 65536:
        raise ValueError("Project .env exceeds the 64 KiB limit")
    try:
        contents = raw.decode("utf-8-sig")
    except UnicodeError:
        raise ValueError("Project .env must be UTF-8") from None
    values = {}
    for entry in parse_stream(io.StringIO(contents)):
        if entry.error:
            raise ValueError(f"Invalid project .env syntax at line {entry.original.line}")
        if entry.key == KEY_NAME:
            if entry.key in values:
                raise ValueError(f"Duplicate {KEY_NAME} in project .env")
            values[entry.key] = entry.value
    if KEY_NAME not in values:
        return None
    value = values[KEY_NAME]
    if value is None:
        raise ValueError(f"{KEY_NAME} in project .env has no value")
    if "${" in value:
        raise ValueError("Project .env API key must be a literal value; interpolation is disabled")
    return value


def api_key() -> str:
    value = local_api_key()
    if value is None:
        value = os.environ.get(KEY_NAME)
    if value is None:
        value = user_variable(KEY_NAME)
    if value is None:
        raise ValueError(f"{KEY_NAME} is missing; configure project .env or environment variables")
    value = value.strip()
    if not value or re.search(r"[\s\x00-\x1f\x7f]", value):
        raise ValueError(f"{KEY_NAME} is missing or invalid; configure project .env or environment variables")
    return value


def absolute_directory(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError("output_dir must be an absolute local path")
    return path.resolve()


@dataclass(frozen=True)
class Settings:
    base_url: str
    output_dir: Path
    timeout: float = 180.0

    @classmethod
    def load(cls) -> Settings:
        base = os.environ.get("ZHENZHEN_GPTIMAGEGEN_BASE_URL", BASE_URL).rstrip("/")
        u = urlsplit(base)
        if u.scheme != "https" or not u.hostname or u.username or u.password or u.query or u.fragment:
            raise ValueError("Base URL must be HTTPS without credentials, query or fragment")
        if u.path.rstrip("/") != "/v1":
            raise ValueError("Base URL must end in /v1")
        output = absolute_directory(
            os.environ.get("ZHENZHEN_GPTIMAGEGEN_OUTPUT_DIR", str(Path.home() / "Pictures" / "ZhenzhenImage"))
        )
        timeout = float(os.environ.get("ZHENZHEN_GPTIMAGEGEN_TIMEOUT", "180"))
        if not 10 <= timeout <= 600:
            raise ValueError("ZHENZHEN_GPTIMAGEGEN_TIMEOUT must be between 10 and 600 seconds")
        return cls(base, output, timeout)
