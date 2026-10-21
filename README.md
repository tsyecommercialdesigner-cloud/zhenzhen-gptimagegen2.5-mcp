# Zhenzhen GPT Image MCP

Windows 上的 Python stdio MCP Server，为 Agent 提供 GPT Image 2.5 Flare / Sunburst 同步生成与编辑、批量异步提交、持久化防重、任务查询和图片自动落盘。Flare 偏向快速生成，Sunburst 偏向精细编辑；选型建议来自供应商，未作模型速度/质量对比保证。精细编辑使用 Images edits，不提供 Responses 工具。

## 安装 v0.3.1

准备 Git、PowerShell 7、uv；Python 支持 3.12，项目固定 3.12.14。默认目录 `D:\MCP\zhenzhen-gptimagegen2.5-mcp`，已有目录请使用 [更新流程](MANUAL.md#5-启动排障)，不能覆盖安装。

```powershell
$ErrorActionPreference = 'Stop'
$ProjectDir = 'D:\MCP\zhenzhen-gptimagegen2.5-mcp'
if (Test-Path -LiteralPath $ProjectDir) { throw '目录已存在，请使用手册更新流程。' }
New-Item -ItemType Directory -Path 'D:\MCP' -Force | Out-Null
git clone --branch v0.3.1 --single-branch 'https://github.com/tsyecommercialdesigner-cloud/zhenzhen-gptimagegen2.5-mcp.git' $ProjectDir
if ($LASTEXITCODE -ne 0) { throw '仓库获取失败。' }
$ActualSha = git -C $ProjectDir rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $ActualSha -ne 'f5011efcb0a9bd4353c106811d71645e02ff74fe') { throw '发布 SHA 不符。' }
Set-Location -LiteralPath $ProjectDir
uv sync --locked --no-dev
if ($LASTEXITCODE -ne 0) { throw '依赖安装失败。' }
$EnvPath = Join-Path $ProjectDir '.env'
if (!(Test-Path -LiteralPath $EnvPath)) { [IO.File]::Copy((Join-Path $ProjectDir '.env.example'), $EnvPath, $false) }
Start-Process -FilePath 'notepad.exe' -ArgumentList ('"{0}"' -f $EnvPath) -ErrorAction Stop
```

在打开的私有 `.env` 中填写 `ZHENZHEN_GPTIMAGEGEN_API_KEY`，保存 UTF-8 并限制读取权限。API Key 由 MCP 固定读取实际项目根 `.env`，仅缺失才按进程 → Windows 用户环境回退，空值或损坏明确失败；默认不向 Host 配置复制业务密钥。修改后重启实际 MCP 子进程。ACL、环境兼容与网络要求见 [MANUAL 第 1–2 节](MANUAL.md#1-环境准备)。

保存后执行免费协议检查，再配置 Host：

```powershell
pwsh -NoProfile -File 'D:\MCP\zhenzhen-gptimagegen2.5-mcp\scripts\smoke-test.ps1' -TimeoutSeconds 30
if ($LASTEXITCODE -ne 0) { throw '协议检查失败，请先排障。' }
```

预期 11 Tools、1 Prompt、1 Resource、paid_calls=0。协议可用与供应商鉴权/实际绘图分别验收。发布依据为 [v0.3.1 Release](https://github.com/tsyecommercialdesigner-cloud/zhenzhen-gptimagegen2.5-mcp/releases/tag/v0.3.1) 的完整 SHA 与 CI/安装证据，不自动跟随 main 或在启动时安装依赖。

## 连接与使用

Host 服务名 `zhenzhen-gptimagegen2-5-mcp`；目录仍保留 `2.5`。日常由 Host 启动：

```powershell
uv --directory 'D:\MCP\zhenzhen-gptimagegen2.5-mcp' run --no-sync python -m zhenzhen_image_mcp
if ($LASTEXITCODE -ne 0) { throw '服务退出失败，请查看 stderr。' }
```

[完整手册](MANUAL.md) 提供本地/消费代理 JSON、Codex TOML、Claude Code 与 Claude-3p 适用性、DSH 三种 profile（原生 web、App desktop、Multica multica）的备份打开及两种传输 YAML，以及三类 CLI × PowerShell/Bash/Zsh 的操作和验证边界。DSH 三份文件分别合并，避免重复实例。仅连接远程代理的用户不安装后端。

先调用免费 `get_model_guide`。默认逆向 `group="reverse"`；使用官转须在工具参数中显式 `group="official"`，扩展参数放 `official_options`，批量则逐项声明。声明不更改供应商 Key 后台分组，非法组合在收费前拒绝，详见 [参数与流程](MANUAL.md#8-功能说明)。

多图用 `submit_image_batch`：最多 10 项、默认并发 3，等待提交确认后返回；固定 `(checkpointer, thread_id, task_id)`，`get_image_batch` 恢复本地记录，`get_batch_image_task` 查询并保存。升级保留整个 `.runtime` 和用户 `.env`，不要删除数据库或换身份绕过防重。不确定提交禁止自动重发；原有单项提交工具没有检查点防重保证。

生成/编辑收费，免费指南和协议检查不收费。NOT_START 是排队；继续查询原任务，云端 SUCCESS 后还需检查 save_status/files。实际像素可能与请求 size 不同，必须验图，不自动重新收费。本项目仅支持 Windows；其他 Host、官转高级参数与真实十图并发的未验证项见 [验收记录](docs/D-DRIVE-ACCEPTANCE.md)。

## 开发与追溯

开发者在独立 `.venv` 中先 `uv sync --locked`，再运行 `uv run --no-sync python scripts/check.py --build --audit`；CI 使用同一入口，仅 Windows。成员安装不需要开发依赖。源码、测试、锁和文档随仓库跟踪，秘密、运行数据和缓存不入 Git。成员 ZIP 仅明确需要时按 [手册第 6 节](MANUAL.md#6-文件清单与交付) 交付。

需求与检查点语义见 [异步批量契约](docs/ASYNC-BATCH-PLAN.md)，历史记录见 [VALIDATION](docs/VALIDATION.md)，许可证为 [MIT](LICENSE)。
