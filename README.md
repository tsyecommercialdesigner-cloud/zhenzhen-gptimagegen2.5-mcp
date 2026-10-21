# Zhenzhen Image MCP

Python stdio MCP，面向 GPT Image 2.5 Flare / Sunburst，支持同步生成/编辑、Images 流式结果、批量异步并发、持久化防重、恢复查询和图片自动落盘。Sunburst 用于高精度编辑、Flare 用于追求速度的生成；选型建议来自供应商，质量和速度需实际验收。

版本 **0.3.0**。源码已通过 [PR #1](https://github.com/tsyecommercialdesigner-cloud/zhenzhen-gptimagegen2.5-mcp/pull/1) 合入 `main`；正式成员以实际 [Releases](https://github.com/tsyecommercialdesigner-cloud/zhenzhen-gptimagegen2.5-mcp/releases) 中的版本标签、完整 SHA 和验证证据为准，按 [MANUAL 第 2 节](MANUAL.md#2-项目初始化) clone、核对提交并 `uv sync --locked --no-dev`。元数据版本本身不证明该版本已公开发布。

本项目面向 Windows 用户。PR / push CI 仅在 `windows-latest` 验收，手动发布工作流也使用 Windows；保留全部测试、构建、协议、安装与依赖检查。其他操作系统不在当前支持和 CI 验收范围内。

默认安装目录 `D:\MCP\zhenzhen-gptimagegen2.5-mcp`。API Key 由 MCP 固定读取该目录 `.env`：从空 `.env.example` 安全复制、填写并限制权限；仅缺失时按“进程 → Windows 用户级”回退，空值或损坏配置失败。升级保留 `.env` 与权限，修改后重启实际 MCP 子进程。完整初始化、ACL、Host 配置及升级见 [MANUAL.md](MANUAL.md)。

默认是逆向分组；官转必须在每次生成/编辑调用显式声明：

```json
{
  "prompt": "透明背景的蓝色垃圾袋商品图",
  "model": "gpt-image-2.5-flare",
  "group": "official",
  "official_options": {
    "n": 1,
    "background": "transparent",
    "output_format": "png"
  }
}
```

省略 group 即 reverse；未声明 official 却传 official_options 会在收费前失败。该字段只控制本地参数校验，不更改供应商 Key 后台分组。完整 format def 与参数表见手册第 8 节。精细编辑使用 Images edits，不提供 create_response。

安装后正常启动复用环境：

```powershell
uv --directory 'D:\MCP\zhenzhen-gptimagegen2.5-mcp' run --no-sync python -m zhenzhen_image_mcp
```

免费协议检查：

```powershell
pwsh -NoProfile -File 'D:\MCP\zhenzhen-gptimagegen2.5-mcp\scripts\smoke-test.ps1'
if ($LASTEXITCODE -ne 0) { throw 'MCP 协议检查失败。' }
```

Host 配置服务名为 `zhenzhen-gptimagegen2-5-mcp`，目录仍保留 `2.5`；默认不用在 Host 转发后端 Key。Codex、Cherry Studio、Claude Code、DSH desktop/web 与消费代理的完整步骤、适用范围和未验证项见手册第 4 节。

开发与 CI 共用检查（先在开发目录 `uv sync --locked`）：

```powershell
uv run --no-sync python scripts/check.py --build --audit
if ($LASTEXITCODE -ne 0) { throw '开发检查失败，请查看具体失败项。' }
```

多图规划用 `submit_image_batch`，一次最多 10 项，默认并发 3；在收到提交编号后返回，不等待生成。使用稳定 `(checkpointer, thread_id, tasks[].task_id)` 幂等键，相同参数复用已有记录；供应商编号另存为 `provider_task_id`。`get_image_batch` 恢复本地会话记录，`get_batch_image_task` 查询指定逻辑任务并落盘。完整示例和状态见 [MANUAL 第 8 节](MANUAL.md#8-功能说明)。

防重历史保存在实际项目 `.runtime/checkpoints.sqlite3`，升级须保留；不确定提交不会自动重发。原有单项提交工具没有检查点防重，需要防重时即使只有一项也用批量入口。收费 POST 不自动重试；排队或查询失败续查原任务，云端 SUCCESS 后检查保存状态。协议测试不收费；本轮没有发布或交付 ZIP。
