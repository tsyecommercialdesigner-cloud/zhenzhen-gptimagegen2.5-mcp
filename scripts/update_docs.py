"""Regenerate manual contracts from smoke-test protocol discovery."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
names = [
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
    "scripts/smoke-test.ps1",
] + sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "src/zhenzhen_image_mcp").glob("*.py"))
(ROOT / "user-files.json").write_text(json.dumps(names, indent=2) + "\n", encoding="utf-8")
manual_path = ROOT / "MANUAL.md"
manual = manual_path.read_text(encoding="utf-8")


def replace(marker, content):
    global manual
    manual = re.sub(
        rf"<!-- {marker}_START -->.*?<!-- {marker}_END -->",
        lambda _: f"<!-- {marker}_START -->\n{content}\n<!-- {marker}_END -->",
        manual,
        flags=re.S,
    )


for marker, name in (
    ("LOCAL_CONFIG", ".mcp.json.example"),
    ("PROXY_CONFIG", ".cherrystudiomcpproxy.mcp.json.example"),
):
    replace(marker, "```json\n" + (ROOT / name).read_text(encoding="utf-8").strip() + "\n```")
replace("MEMBER_FILES", "\n".join(f"- `{name}`" for name in names))
inventory = json.loads((ROOT / "docs/mcp-inventory.json").read_text(encoding="utf-8"))


def typ(s):
    if "$ref" in s:
        return s["$ref"].split("/")[-1]
    if "anyOf" in s:
        return " / ".join(typ(x) for x in s["anyOf"])
    if s.get("type") == "array":
        return "array[" + typ(s.get("items", {})) + "]"
    return s.get("type", "object")


def cell(x):
    return str(x).replace("|", " / ").replace("\n", " ")


examples = {
    "get_model_guide": {},
    "generate_image": {
        "prompt": "一只在窗边看雨的猫，水彩风格",
        "model": "gpt-image-2.5-flare",
        "size": "2048x1152",
    },
    "edit_image": {
        "prompt": "只给人物添加细框眼镜，保持五官和背景不变",
        "model": "gpt-image-2.5-sunburst",
        "images": ["C:\\Pictures\\portrait.png"],
    },
    "submit_image_generation": {
        "prompt": "海边灯塔，清晨自然光",
        "model": "gpt-image-2.5-flare",
        "output_dir": "C:\\MCP\\zhenzhen-images",
    },
    "submit_image_edit": {
        "prompt": "保持第一张人物身份，参考第二张的服装颜色",
        "model": "gpt-image-2.5-sunburst",
        "images": ["C:\\Pictures\\person.png", "C:\\Pictures\\clothing.png"],
    },
    "submit_image_batch": {
        "checkpointer": "product-detail-pages",
        "thread_id": "blue-bag-20261020",
        "max_concurrency": 5,
        "tasks": [
            {
                "task_id": "page_01",
                "operation": "generate",
                "prompt": "蓝色垃圾袋详情页首图",
                "model": "gpt-image-2.5-flare",
            },
            {
                "task_id": "page_02",
                "operation": "edit",
                "prompt": "保持商品外观，替换为厨房场景",
                "model": "gpt-image-2.5-sunburst",
                "images": ["C:\\Pictures\\product.png"],
            },
        ],
    },
    "get_image_batch": {"checkpointer": "product-detail-pages", "thread_id": "blue-bag-20261020"},
    "get_batch_image_task": {
        "checkpointer": "product-detail-pages",
        "thread_id": "blue-bag-20261020",
        "task_id": "page_01",
        "save": True,
    },
    "get_image_task": {"task_id": "替换为提交返回的真实任务ID", "save": True},
    "wait_image_task": {"task_id": "替换为提交返回的真实任务ID", "timeout_seconds": 180, "poll_interval": 90},
    "download_image": {
        "url": "https://example.com/replace-with-real-result.png",
        "output_dir": "C:\\MCP\\zhenzhen-images",
    },
}
examples["run_image_batch"] = {**examples["submit_image_batch"], "thread_id": "blue-bag-sync-20261021"}
sections = []
for tool in inventory["tools"]:
    s = tool["inputSchema"]
    sections.extend(
        [
            f"### `{tool['name']}`",
            "",
            tool.get("description", ""),
            "",
            "| 参数 | 类型 | 必需 | 默认 | 约束/说明 |",
            "|---|---|---|---|---|",
        ]
    )
    if not s.get("properties"):
        sections.append("| 无 | — | — | — | 无参数 |")
    for name, prop in s.get("properties", {}).items():
        constraints = []
        for k in ("enum", "minimum", "maximum", "minLength", "maxLength", "minItems", "maxItems"):
            if k in prop:
                constraints.append(f"{k}={prop[k]}")
        for branch in prop.get("anyOf", []):
            if "enum" in branch:
                constraints.append("允许值=" + ", ".join(map(str, branch["enum"])))
            if "description" in branch:
                constraints.append(branch["description"])
            for k in ("minItems", "maxItems"):
                if k in branch:
                    constraints.append(f"{k}={branch[k]}")
        desc = prop.get("description", "") + " " + "; ".join(constraints)
        default = json.dumps(prop["default"], ensure_ascii=False) if "default" in prop else "—"
        sections.append(
            f"| `{name}` | {cell(typ(prop))} | {'是' if name in s.get('required', []) else '否'} | `{default}` | {cell(desc)} |"
        )
    if "$defs" in s:
        for name, definition in s["$defs"].items():
            sections.extend(["", f"`{name}` 对象字段："])
            for field, prop in definition.get("properties", {}).items():
                sections.append(
                    f"- `{field}`：{cell(typ(prop))}，{'必填' if field in definition.get('required', []) else '可选'}；{cell(prop.get('description', ''))} {cell(prop.get('enum', ''))}".rstrip()
                )
    sections.extend(
        [
            "",
            "调用工具时的 arguments 示例（路径、URL 和任务 ID 替换为实际值）：",
            "",
            "```json",
            json.dumps(examples[tool["name"]], indent=2, ensure_ascii=False),
            "```",
            "",
        ]
    )
replace("INVENTORY", "\n".join(sections))
manual_path.write_text(manual, encoding="utf-8")
print("Updated member allowlist, exact templates and discovery-derived tool arguments.")
