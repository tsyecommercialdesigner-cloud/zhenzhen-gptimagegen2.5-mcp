"""Public MCP contracts. No cloud requests during discovery."""

from __future__ import annotations

import json
from contextlib import contextmanager
from functools import wraps
from inspect import iscoroutinefunction
from typing import Annotated, cast

import httpx
import httpx2
from jsonschema import Draft202012Validator
from mcp.server import MCPServer
from mcp.server.mcpserver.context import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult, InputRequiredResult, Tool, ToolAnnotations
from pydantic import Field

from . import __version__, media
from .api import API, safe_error
from .batch import BatchService
from .checkpoints import KEY_PATTERN
from .config import FLARE, KEY_NAME, MODEL_GUIDE, SUNBURST, Settings, api_key
from .contracts import (
    BatchImageTask,
    BatchResult,
    CheckpointResult,
    FileResult,
    Group,
    GuideResult,
    ImageResult,
    Model,
    OfficialOptions,
    Quality,
)

ScopeParam = Annotated[
    str, Field(pattern=f"^{KEY_PATTERN}$", description="稳定的本地检查点命名空间/会话键，1–128字符。")
]
BatchTaskID = Annotated[
    str, Field(pattern=r"^[A-Za-z0-9_-]{1,128}$", description="批量提交时指定的原始 task_id。")
]

ModelParam = Annotated[Model, Field(description=MODEL_GUIDE + "请结合用户意图选择并告知所用模型。")]
GroupParam = Annotated[
    Group,
    Field(
        description="分组声明：默认 reverse（逆向）；仅用户明确使用官转时传 official。此字段不发送上游、不改变密钥后台分组。"
    ),
]
OptionsParam = Annotated[
    OfficialOptions | None,
    Field(description='仅 group="official" 可用的官转扩展参数。未声明官转时传入此对象会在收费前拒绝。'),
]
SizeParam = Annotated[
    str | None,
    Field(
        description="可选 auto 或 WIDTHxHEIGHT；两边为16倍数、最大3840、比例不超过3:1、总像素655360..8294400。省略时不发送。"
    ),
]
OutputParam = Annotated[
    str | None, Field(description="可选绝对输出目录；默认配置目录。异步任务查询默认沿用提交目录。")
]
ImageSources = Annotated[
    list[str],
    Field(
        min_length=1,
        max_length=16,
        description="本机绝对图片路径、公开 HTTP(S) 图片 URL 或 base64 data URL；PNG/JPEG/WebP。",
    ),
]


class ValidatedMCPServer(MCPServer):
    """Enforce advertised schemas before SDK convenience coercion or billable calls."""

    async def list_tools(self) -> list[Tool]:
        return [
            tool.model_copy(update={"input_schema": {**tool.input_schema, "additionalProperties": False}})
            for tool in await super().list_tools()
        ]

    async def call_tool(
        self, name: str, arguments: dict, context: Context | None = None
    ) -> CallToolResult | InputRequiredResult:
        tool = next((tool for tool in await self.list_tools() if tool.name == name), None)
        if tool is not None:
            error = next(Draft202012Validator(tool.input_schema).iter_errors(arguments), None)
            if error is not None:
                field = ".".join(map(str, error.absolute_path)) or "arguments"
                raise ToolError(f"Invalid tool arguments at {field}; check the declared input schema")
        return await super().call_tool(name, arguments, context)


mcp = ValidatedMCPServer(
    "zhenzhen-gptimagegen2-5-mcp",
    version=__version__,
    log_level="WARNING",
    instructions=(
        MODEL_GUIDE + "先说明模型选择；生成或精细编辑优先使用 Images 工具。"
        "绘图和编辑会产生供应商费用，提交失败或超时不得自动重提。"
        "长耗时优先 submit_*，保留 task_id 后查询；wait 超时仅结束本地等待。"
        "返回文件路径可供展示；云端 SUCCESS 不等于保存成功，检查 save_status。"
        "精细编辑使用 Sunburst 的 edit_image 或 submit_image_edit，通过 Images edits 接口上传参考图。"
        '默认逆向 group="reverse"。仅用户明确声明官转时传 group="official"，扩展参数放 official_options。'
        "不要根据提示词、模型名或网络失败自行切换分组，也不要自动尝试另一分组。"
        "多图规划使用 submit_image_batch：固定 checkpointer/thread_id/各 task_id，一次最多10项。"
        "用 get_image_batch 恢复本地记录，get_batch_image_task 查询单项。不要改变幂等键规避错误；SUBMITTING/SUBMISSION_UNCERTAIN 禁止自动重提。"
    ),
)
READ = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)
WRITE = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=True
)
BATCH = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=True
)


@contextmanager
def expected_errors():
    try:
        yield
    except (
        ValueError,
        OSError,
        httpx.HTTPError,
        httpx2.HTTPError,
        httpx.InvalidURL,
        httpx2.InvalidURL,
    ) as exc:
        try:
            secret = api_key()
        except ValueError:
            secret = ""
        raise ToolError(safe_error(exc, secret)) from None


def tool_errors(fn):
    """Keep signatures for discovery; expose only sanitized anticipated failures."""
    if iscoroutinefunction(fn):

        @wraps(fn)
        async def wrapped(*args, **kwargs):
            with expected_errors():
                return await fn(*args, **kwargs)
    else:

        @wraps(fn)
        def wrapped(*args, **kwargs):
            with expected_errors():
                return fn(*args, **kwargs)

    return wrapped


@mcp.tool(annotations=READ)
@tool_errors
def get_model_guide() -> GuideResult:
    """免费本地模型选择建议和配置状态；只检查密钥是否存在，不显示密钥、不请求云端。"""
    settings = Settings.load()
    try:
        api_key()
        present = True
    except ValueError:
        present = False
    return {
        "models": [FLARE, SUNBURST],
        "advice": MODEL_GUIDE,
        "base_url": settings.base_url,
        "output_dir": str(settings.output_dir),
        "key_variable": KEY_NAME,
        "key_present": present,
        "default_group": "reverse",
        "official_declaration": {"group": "official", "options_field": "official_options"},
    }


@mcp.tool(annotations=WRITE)
@tool_errors
async def generate_image(
    prompt: Annotated[str, Field(min_length=1)],
    model: ModelParam,
    images: ImageSources | None = None,
    size: SizeParam = None,
    quality: Quality | None = None,
    output_dir: OutputParam = None,
    group: GroupParam = "reverse",
    official_options: OptionsParam = None,
) -> ImageResult:
    """同步生成并落盘。默认逆向五参数；官转须显式 group=official。收费，POST 不自动重试。"""
    return cast(
        ImageResult,
        await API().images(
            prompt,
            model,
            images,
            size,
            quality,
            output_dir=output_dir,
            group=group,
            official_options=official_options,
        ),
    )


@mcp.tool(annotations=WRITE)
@tool_errors
async def edit_image(
    prompt: Annotated[str, Field(min_length=1)],
    model: ModelParam,
    images: ImageSources,
    size: SizeParam = None,
    quality: Quality | None = None,
    output_dir: OutputParam = None,
    group: GroupParam = "reverse",
    official_options: OptionsParam = None,
) -> ImageResult:
    """同步图像编辑并落盘；多图以 image[] 上传。高编辑精度场景建议 Sunburst。收费。"""
    return cast(
        ImageResult,
        await API().images(
            prompt,
            model,
            images,
            size,
            quality,
            edit=True,
            output_dir=output_dir,
            group=group,
            official_options=official_options,
        ),
    )


@mcp.tool(annotations=WRITE)
@tool_errors
async def submit_image_generation(
    prompt: Annotated[str, Field(min_length=1)],
    model: ModelParam,
    images: ImageSources | None = None,
    size: SizeParam = None,
    quality: Quality | None = None,
    output_dir: OutputParam = None,
    group: GroupParam = "reverse",
    official_options: OptionsParam = None,
) -> ImageResult:
    """POST generations?async=true 提交收费异步绘图，立即返回 task_id。必须继续查询才能自动落盘。"""
    return cast(
        ImageResult,
        await API().images(
            prompt,
            model,
            images,
            size,
            quality,
            asynchronous=True,
            output_dir=output_dir,
            group=group,
            official_options=official_options,
        ),
    )


@mcp.tool(annotations=WRITE)
@tool_errors
async def submit_image_edit(
    prompt: Annotated[str, Field(min_length=1)],
    model: ModelParam,
    images: ImageSources,
    size: SizeParam = None,
    quality: Quality | None = None,
    output_dir: OutputParam = None,
    group: GroupParam = "reverse",
    official_options: OptionsParam = None,
) -> ImageResult:
    """POST edits?async=true 提交收费异步编辑，以 image[] 上传；返回 task_id，之后查询并落盘。"""
    return cast(
        ImageResult,
        await API().images(
            prompt,
            model,
            images,
            size,
            quality,
            asynchronous=True,
            edit=True,
            output_dir=output_dir,
            group=group,
            official_options=official_options,
        ),
    )


@mcp.tool(annotations=BATCH)
@tool_errors
async def submit_image_batch(
    checkpointer: ScopeParam,
    thread_id: ScopeParam,
    tasks: Annotated[list[BatchImageTask], Field(min_length=1, max_length=10)],
    max_concurrency: Annotated[int, Field(ge=1, le=10)] = 3,
) -> BatchResult:
    """一次并发提交1–10项收费异步生成/编辑，默认并发3。收到任务编号即返回，不等待成图。同一(checkpointer,thread_id,task_id)及参数复用记录，参数冲突在提交前拒绝；不确定提交永不自动重发。"""
    return cast(BatchResult, await BatchService().submit(checkpointer, thread_id, tasks, max_concurrency))


@mcp.tool(annotations=READ)
@tool_errors
async def get_image_batch(checkpointer: ScopeParam, thread_id: ScopeParam) -> BatchResult:
    """免费读取本地持久化检查点，恢复该会话所有 task_id/provider_task_id/最后观察状态；不查询供应商、不提交、不等待成图。"""
    return cast(BatchResult, await BatchService().snapshot(checkpointer, thread_id))


@mcp.tool(annotations=BATCH)
@tool_errors
async def get_batch_image_task(
    checkpointer: ScopeParam,
    thread_id: ScopeParam,
    task_id: BatchTaskID,
    output_dir: OutputParam = None,
    save: bool = True,
) -> CheckpointResult:
    """按原(checkpointer,thread_id,task_id)查询供应商异步结果并自动落盘；只读HTTP有限重试。没有供应商编号时返回本地状态，不重新提交。云端失败为工具错误；检查 result.save_status。"""
    return cast(
        CheckpointResult, await BatchService().query(checkpointer, thread_id, task_id, output_dir, save)
    )


@mcp.tool(
    annotations=ToolAnnotations(
        read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=True
    )
)
@tool_errors
async def get_image_task(task_id: str, output_dir: OutputParam = None, save: bool = True) -> ImageResult:
    """查询 NOT_START（排队）/IN_PROGRESS/FAILURE/SUCCESS；暂时性查询故障最多尝试3次。save=true 时成功图片自动落盘；false 仅查询。不重新提交。"""
    return cast(ImageResult, await API().query(task_id, output_dir, save))


@mcp.tool(
    annotations=ToolAnnotations(
        read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=True
    )
)
@tool_errors
async def wait_image_task(
    task_id: str,
    timeout_seconds: Annotated[float, Field(ge=1, le=300)] = 60,
    poll_interval: Annotated[float, Field(ge=1, le=60)] = 5,
    output_dir: OutputParam = None,
) -> ImageResult:
    """有界轮询，NOT_START 排队和 IN_PROGRESS 处理中继续等待，成功后落盘；只读查询有限重试计入等待时限。超时返回 task_id/wait_timed_out，云端任务继续；可稍后再次查询。"""
    return cast(ImageResult, await API().wait(task_id, timeout_seconds, poll_interval, output_dir))


@mcp.tool(
    annotations=ToolAnnotations(
        read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=True
    )
)
@tool_errors
async def download_image(
    url: Annotated[str, Field(description="公开 HTTP(S) 图片 URL")], output_dir: OutputParam = None
) -> FileResult:
    """按图片 URL 下载并校验 PNG/JPEG/WebP，自动落盘返回绝对路径；不会附带供应商 API Key。"""
    directory = API().destination(output_dir)
    return cast(FileResult, media.save_image(await media.download(url), directory))


@mcp.resource("zhenzhen://models", mime_type="application/json")
def model_resource() -> str:
    """Static model advice and compatibility statement; no secrets or cloud calls."""
    return json.dumps({"models": [FLARE, SUNBURST], "advice": MODEL_GUIDE}, ensure_ascii=False)


@mcp.prompt()
def image_workflow(request: str) -> str:
    """根据用户需求选择模型与同步/异步绘图流程；模板本身不收费。"""
    return (
        f"用户绘图需求：{request}\n{MODEL_GUIDE}\n"
        "解释所选模型，确认编辑时所需参考图片。不要擅自修改需保留的细节。"
        '未声明官转时使用默认 reverse；用户明确声明官转时传 group="official"，并将扩展参数放在 official_options。'
        "优先异步提交并保存 task_id，查询成功后检查文件保存状态，展示返回的绝对路径。"
        "规划多张图片时用 submit_image_batch，一次最多10项，固定checkpointer/thread_id/task_id，"
        "随后使用get_image_batch/get_batch_image_task恢复和查询；不要为了重试更换幂等键。"
        "精细编辑使用 edit_image 或 submit_image_edit，优先 Sunburst；连续编辑时传入上一步结果图片和新的修改要求。失败或等待超时不应自动重新生成。"
    )


def main() -> None:
    import logging
    import sys

    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    # Avoid HTTP request/header debug logs even if a Host enables SDK debug mode.
    for name in ("openai", "httpx", "httpx2", "httpcore", "httpcore2"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
    Settings.load()
    mcp.run(transport="stdio")
