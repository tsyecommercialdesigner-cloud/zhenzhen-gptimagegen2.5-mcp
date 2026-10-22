"""Group-aware public contracts and validation before any billable operation."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import NotRequired, TypedDict

Group = Literal["reverse", "official"]
Model = Literal["gpt-image-2.5-flare", "gpt-image-2.5-sunburst"]
Quality = Literal["auto", "low", "medium", "high", "xhigh", "max"]


class OfficialOptions(BaseModel):
    """Optional official-group fields; unknown fields never reach the provider."""

    model_config = ConfigDict(extra="forbid", strict=True)
    n: int | None = Field(default=None, ge=1, le=10, description="生成图片数量，1–10。")
    background: Literal["auto", "transparent", "opaque"] | None = None
    output_format: Literal["png", "jpeg", "webp"] | None = None
    output_compression: int | None = Field(default=None, ge=0, le=100)
    mask: str | None = Field(
        default=None, description="仅编辑：本机绝对路径/公开 URL/data URL，PNG，<4 MiB，与首张图同尺寸。"
    )
    input_fidelity: Literal["high", "low"] | None = Field(
        default=None, description="官转组兼容透传，模型是否支持以供应商为准。"
    )
    moderation: Literal["auto", "low"] | None = None
    response_format: Literal["url", "b64_json"] | None = Field(
        default=None, description="供应商兼容扩展；不代表官方 GPT Image 支持此字段。"
    )
    user: str | None = Field(default=None, min_length=1, max_length=128)
    safety_identifier: str | None = Field(default=None, min_length=1, max_length=128)
    stream: bool | None = Field(
        default=None, description="Images SSE；工具收集最终结果后返回。不能与异步提交合用。"
    )
    partial_images: int | None = Field(default=None, ge=0, le=3)


class BatchImageTask(BaseModel):
    """One stable caller-assigned task identity inside a checkpoint thread."""

    model_config = ConfigDict(extra="forbid", strict=True)
    task_id: str = Field(
        pattern=r"^[A-Za-z0-9_-]{1,128}$", description="Agent 指定的稳定任务键；重试不能改名。"
    )
    operation: Literal["generate", "edit"] = "generate"
    prompt: str = Field(min_length=1, max_length=32000)
    model: Model
    images: list[str] | None = Field(default=None, min_length=1, max_length=16)
    size: str | None = None
    quality: Quality | None = None
    output_dir: str | None = None
    group: Group = "reverse"
    official_options: OfficialOptions | None = None


CheckpointState = Literal[
    "RESERVED",
    "SUBMITTING",
    "SUBMITTED",
    "SUBMISSION_UNCERTAIN",
    "NOT_START",
    "IN_PROGRESS",
    "SUCCESS",
    "FAILURE",
]


class CheckpointTask(TypedDict):
    task_id: str
    status: CheckpointState
    provider_task_id: str | None
    group: Group
    output_dir: str
    reused: bool
    error: NotRequired[str]
    warning: NotRequired[str]
    result: NotRequired[ImageResult]


class BatchResult(TypedDict):
    checkpointer: str
    thread_id: str
    status: Literal["ACCEPTED", "ATTENTION_REQUIRED", "SNAPSHOT", "COMPLETED"]
    tasks: list[CheckpointTask]
    next_tool: str
    note: str


class CheckpointResult(CheckpointTask):
    checkpointer: str
    thread_id: str


def size_check(size: str | None) -> None:
    if size is None or size == "auto":
        return
    if not re.fullmatch(r"[1-9]\d{0,3}x[1-9]\d{0,3}", size):
        raise ValueError("size must be auto or WIDTHxHEIGHT")
    w, h = map(int, size.split("x"))
    if max(w, h) > 3840 or w % 16 or h % 16 or max(w, h) > 3 * min(w, h) or not 655360 <= w * h <= 8294400:
        raise ValueError("size: edges must be multiples of 16, <=3840; aspect <=3:1; pixels 655360..8294400")


def image_parameters(
    prompt: str,
    model: str,
    size: str | None,
    quality: str | None,
    group: Group,
    options: OfficialOptions | dict[str, Any] | None,
    *,
    edit: bool,
    asynchronous: bool,
) -> tuple[dict[str, Any], str | None]:
    if group not in {"reverse", "official"}:
        raise ValueError('group must be "reverse" or "official"')
    if model not in {"gpt-image-2.5-flare", "gpt-image-2.5-sunburst"}:
        raise ValueError("Select gpt-image-2.5-flare or gpt-image-2.5-sunburst")
    if not prompt.strip() or len(prompt) > 32000:
        raise ValueError("prompt must contain 1..32000 characters and cannot be blank")
    size_check(size)
    allowed = {"auto", "low", "medium", "high"}
    if group == "official":
        allowed |= {"xhigh", "max"}
    if quality is not None and quality not in allowed:
        raise ValueError("quality is not supported for the declared group")
    if group == "reverse" and options is not None:
        raise ValueError('official_options requires explicit group="official"; default group is "reverse"')
    body: dict[str, Any] = {"model": model, "prompt": prompt}
    if size is not None:
        body["size"] = size
    if quality is not None:
        body["quality"] = quality
    extra = (
        options
        if isinstance(options, OfficialOptions)
        else OfficialOptions.model_validate(options if options is not None else {})
    ).model_dump(exclude_none=True)
    if not edit and "mask" in extra:
        raise ValueError("mask requires edit_image or submit_image_edit")
    if asynchronous and extra.get("stream"):
        raise ValueError("stream=true and asynchronous submission are mutually exclusive")
    if "partial_images" in extra and extra.get("stream") is not True:
        raise ValueError("partial_images requires stream=true")
    if extra.get("background") == "transparent" and extra.get("output_format", "png") not in {"png", "webp"}:
        raise ValueError("transparent background requires png or webp output_format")
    if "output_compression" in extra and extra.get("output_format") not in {"jpeg", "webp"}:
        raise ValueError("output_compression requires explicit jpeg or webp output_format")
    mask = extra.pop("mask", None)
    body.update(extra)
    return body, mask


class FileResult(TypedDict):
    path: str
    mime_type: str
    bytes: int
    sha256: str
    reused: bool


class SavedFile(FileResult):
    index: int


class DownloadError(TypedDict):
    index: int
    url: str | None
    error: str


class ImageResult(TypedDict):
    status: Literal["COMPLETED", "SUBMITTED", "NOT_START", "IN_PROGRESS", "SUCCESS", "UNKNOWN"]
    group: NotRequired[Group]
    task_id: NotRequired[str]
    output_dir: NotRequired[str]
    next_tool: NotRequired[str]
    warning: NotRequired[str]
    idempotency_key: NotRequired[str]
    reused: NotRequired[bool]
    auto_poll_interval: NotRequired[int]
    note: NotRequired[str]
    progress: NotRequired[str | int | float | None]
    fail_reason: NotRequired[str]
    wait_timed_out: NotRequired[bool]
    response: NotRequired[dict[str, Any] | None]
    files: NotRequired[list[SavedFile]]
    download_errors: NotRequired[list[DownloadError]]
    save_status: NotRequired[Literal["saved", "partial", "failed", "no_images"]]
    usage: NotRequired[dict[str, Any]]
    cost: NotRequired[int | float | None]


class GuideResult(TypedDict):
    models: list[str]
    advice: str
    base_url: str
    output_dir: str
    key_variable: str
    key_present: bool
    default_group: Group
    official_declaration: dict[str, str]
