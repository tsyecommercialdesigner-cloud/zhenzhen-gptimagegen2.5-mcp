# Zhenzhen Image MCP 交付与使用手册

适用版本 **v0.4.0**。默认从 [项目 GitHub](https://github.com/tsyecommercialdesigner-cloud/zhenzhen-gptimagegen2.5-mcp) 的已发布版本安装到 D 盘。首次使用按第 1–4 节操作；已有安装按第 5 节更新。所有安装、编辑配置和业务示例都需用户自行按需执行，阅读本手册不会触发它们。

本版新增同步批量与自动轮询，升级会迁移本地数据库到 schema 2。升级前停止全部相关 MCP 进程，备份 `.env`、整个 `.runtime`（含 WAL/SHM）及图片；旧程序不能直接读取新库。历史五项真实同步请求的保存失败根因仍未确认，详见[发布与迁移说明](docs/RELEASE-v0.4.0.md)。

## 1. 环境准备

### 部署方式与参数表

本项目只提供 Python stdio 后端，没有原生 HTTP 监听入口。直接使用的成员在实际运行 MCP 的 Windows 机器上安装；仅消费已部署代理的 Host 只连接 URL，不 clone 后端、不安装 uv，也不持有供应商 API Key。Cherry Studio 的网关是可选外部组件。

| 参数 | 本项目的值与来源 |
|---|---|
| 项目目录原名 | zhenzhen-gptimagegen2.5-mcp，用户约定 |
| GitHub origin | https://github.com/tsyecommercialdesigner-cloud/zhenzhen-gptimagegen2.5-mcp.git |
| 发布安装目标 | [v0.4.0](https://github.com/tsyecommercialdesigner-cloud/zhenzhen-gptimagegen2.5-mcp/releases/tag/v0.4.0)，公开后使用以下命令 |
| 标签完整提交 | 固定 v0.4.0 的 `release-evidence.json` 中 `commit` 字段；安装前读取完整 40 位 SHA 并与标签核对 |
| 默认安装 / 密钥文件 | `D:\MCP\zhenzhen-gptimagegen2.5-mcp` / 该目录 `.env` |
| 发行包 / 版本 | `zhenzhen-image` / `0.4.0`，来自 pyproject.toml |
| 模块与入口 | `zhenzhen_image_mcp` / `python -m zhenzhen_image_mcp` |
| 本地服务名 | `zhenzhen-gptimagegen2-5-mcp` |
| 通用消费代理服务名 | `zhenzhen-gptimagegen2-5-mcp-proxy` |
| DSH 消费代理别名 | `zhenzhen-gptimagegen2-5-proxy`，与通用代理一对一映射，满足 32 字符上限 |
| 供应商地址 / 后端密钥 | `https://ai.t8star.org/v1` / `ZHENZHEN_GPTIMAGEGEN_API_KEY` |
| 可选网关令牌变量 | `CHERRYSTUDIO_API_GATEWAY_API_KEY`，原始令牌，不包含 `Bearer ` |

仅服务名将点号换成连字符，安装目录保留 `2.5`；不要全局替换版本、模块、文件名或 URL。serverInfo.name 与本地服务名一致。主分支包含后续改动时，不将其 SHA 当作 v0.4.0 的发布 SHA。发布准备阶段如果固定标签的证据附件尚未公开，安装命令会失败，应等待发布完成，不能改用浮动 main。

### 前置条件与验证范围

| 项目 | 要求 / 证据 |
|---|---|
| 平台 | Windows；PowerShell 7；其他系统不在项目支持及 CI 范围内 |
| Python / 包管理器 | Python `>=3.12,<3.13`；项目固定 3.12.14；uv 0.12.9 已验证；另需 Git |
| 构建与依赖 | hatchling 1.27.0，mcp 2.2.0，openai 3.13.0；全部依赖由 uv.lock 锁定，无 SDK extra、Node.js 或 npm 后端安装步骤 |
| 协议 / 传输 | 实际 SDK legacy stdio 客户端协商 2025-11-25，验证 initialize/initialized；不从 SDK 主版本推断协议版本 |
| 已验证 Host | Codex 桌面内置 app-server 0.163.0-alpha.10.2 独立会话与用户重启后的实际 Codex 会话，11 工具及免费指南通过 |
| CLI 命令依据 | 2026-10-21 本机帮助：Codex 0.153.0、Claude Code 2.1.303、DSH 0.2.1-rc.2；只读检查帮助不等于完成注册或连接 |
| DSH YAML 依据 | 本机 `@deepseek-ai/dsh-mcp-client` 0.2.1-rc.2 的 schema/源码；App 和 Multica 自带运行时版本须分别核对 |
| 未验证范围 | 新版 Cherry Studio/代理、DSH 三客户端、Claude/Claude-3p 的全面真实联调，九种 CLI/Shell 执行，以及 MCP 2026-07-28 请求级元数据模式 |

安装前确认 D 盘空间及实际运行账号权限。获取源码需访问 GitHub，uv 安装需访问锁定包源及必要的 Python 下载源；绘图和图片下载分别需要供应商 API 与公开图片域名联网。使用自己的 Git 授权，不在 URL 放令牌；不关闭 TLS 校验或删锁排障。GUI 使用的 PATH/环境来自它的父进程，修改后需要重启相关 Host。

### 凭据与可选设置

默认从 **实际项目根 `.env` → MCP 进程环境 → Windows 当前用户环境** 逐字段读取 API Key。源码/editable 从模块位置定位；项目 venv wheel 从安装布局定位并核对本项目 pyproject.toml，不搜索 Host 工作目录，也不支持无项目根的全局安装。

| 状态 | 行为 |
|---|---|
| `.env` 有有效字段 | 使用文件值，覆盖环境值 |
| 文件或字段缺失 | 查进程变量，真正未定义时再查当前运行账号 HKCU 用户变量 |
| 字段为空/重复/非法，文件不可读/解析失败 | 明确失败，不回退旧密钥；指南只返回 key_present=false，不显示值 |
| 全部来源缺失 | 业务请求失败；免费发现/协议检查仍可进行 |

`.env` 使用 UTF-8（可带 BOM），最大 64 KiB，允许注释和引号；不执行内容，不展开 `${VAR}`。密钥填供应商原值，不自行加 Bearer，内部不能含空白或控制字符；环境来源被选中后同样不能以空值继续回退。只有 API Key 从 `.env` 读取，其他可选设置来自 MCP 进程环境：

| 变量 | 默认值与限制 |
|---|---|
| ZHENZHEN_GPTIMAGEGEN_BASE_URL | https://ai.t8star.org/v1；HTTPS、/v1，无凭据、query、fragment |
| ZHENZHEN_GPTIMAGEGEN_OUTPUT_DIR | 当前运行账号 Pictures\ZhenzhenImage，必须为绝对本地目录 |
| ZHENZHEN_GPTIMAGEGEN_TIMEOUT | 180 秒，可设 10–600 秒 |

`.env` 修改后重启实际 MCP 子进程，不承诺热加载。不因迁移到文件配置自动删除已有环境变量；有效文件仍优先。Host 默认不传后端密钥；网关认证另行设置。

## 2. 项目初始化

### 固定发布版本 clone 与锁定安装

下例固定实际仓库与 v0.4.0，从该版本的 release-evidence.json 读取完整发布 SHA，再与 clone 的提交核对；附件同时记录目标 main CI、发布流程和全新安装验收。标签与附件未公开时停止，不跳过校验。它只创建父目录，clone 自动创建项目目录；目标已存在则走第 5 节。仓库不使用必须额外初始化的 submodule/LFS 运行文件。

```powershell
$ErrorActionPreference = 'Stop'
$RepositoryUrl = 'https://github.com/tsyecommercialdesigner-cloud/zhenzhen-gptimagegen2.5-mcp.git'
$ReleaseTag = 'v0.4.0'
$ReleaseEvidence = Invoke-RestMethod -Uri "https://github.com/tsyecommercialdesigner-cloud/zhenzhen-gptimagegen2.5-mcp/releases/download/$ReleaseTag/release-evidence.json" -ErrorAction Stop
if ($ReleaseEvidence -is [string]) { $ReleaseEvidence = $ReleaseEvidence | ConvertFrom-Json -ErrorAction Stop }
if ($ReleaseEvidence.tag -ne $ReleaseTag -or $ReleaseEvidence.version -ne '0.4.0' -or $ReleaseEvidence.commit -notmatch '^[a-f0-9]{40}$') { throw '发布证据无效，停止安装。' }
$ExpectedSha = $ReleaseEvidence.commit
$InstallRoot = 'D:\MCP'
$ProjectDir = Join-Path $InstallRoot 'zhenzhen-gptimagegen2.5-mcp'
if (Test-Path -LiteralPath $ProjectDir) { throw '目录已存在，请按更新流程处理。' }
New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
git clone --branch $ReleaseTag --single-branch $RepositoryUrl $ProjectDir
if ($LASTEXITCODE -ne 0) { throw '仓库获取失败，停止安装。' }
$ActualSha = git -C $ProjectDir rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $ActualSha -ne $ExpectedSha) { throw '发布 SHA 不符，停止安装。' }
Set-Location -LiteralPath $ProjectDir
uv sync --locked --no-dev
if ($LASTEXITCODE -ne 0) { throw '锁定依赖安装失败，停止启动。' }
```

应用和依赖安装到项目 `.venv`；固定标签处于 detached HEAD 正常。没有 `uv init`、全局 pip 或可选 extra 步骤，也不在日常启动时重新安装。源码仓库包含测试和开发文档，不应为模拟成员 ZIP 而删除它们。仅收到明确提供的可选 ZIP 时使用第 6 节。

### 创建私有 `.env` 与权限

只在文件不存在时复制空模板，已有文件保持原样。在编辑器中填写真实 Key，保存 UTF-8；不要将值粘贴进聊天、公共脚本或命令参数。

```powershell
$ErrorActionPreference = 'Stop'
$ProjectDir = 'D:\MCP\zhenzhen-gptimagegen2.5-mcp'
$EnvPath = Join-Path $ProjectDir '.env'
$ExamplePath = Join-Path $ProjectDir '.env.example'
if (Test-Path -LiteralPath $EnvPath) {
  Write-Host '保留已有 .env，请核对字段。'
} else {
  if (!(Test-Path -LiteralPath $ExamplePath -PathType Leaf)) { throw '缺少空密钥模板。' }
  [IO.File]::Copy($ExamplePath, $EnvPath, $false)
}
Start-Process -FilePath 'notepad.exe' -ArgumentList ('"{0}"' -f $EnvPath) -ErrorAction Stop
```

模板只有一个空字段，私有文件中必须填值；复制后直接留空会明确失败，不会退回环境旧值。

```ini
ZHENZHEN_GPTIMAGEGEN_API_KEY=
```

`.env` 是明文，应仅对实际运行 MCP 的账号和必要管理账号开放。先检查 ACL；以下可选调整只适用于当前终端账号就是服务账号的情况，保留必要显式权限，不给 Everyone 授权。不同服务账号须由管理员按实际账号调整，不能照抄账号名。

```powershell
$ErrorActionPreference = 'Stop'
$EnvPath = 'D:\MCP\zhenzhen-gptimagegen2.5-mcp\.env'
$McpAccount = [Security.Principal.WindowsIdentity]::GetCurrent().Name
icacls $EnvPath
if ($LASTEXITCODE -ne 0) { throw 'ACL 检查失败。' }
# 仅确认当前账号就是运行账号、且已核对必要显式权限后执行：
icacls $EnvPath /grant:r "${McpAccount}:(R,W)" /inheritance:r
if ($LASTEXITCODE -ne 0) { throw 'ACL 修改失败。' }
icacls $EnvPath
if ($LASTEXITCODE -ne 0) { throw 'ACL 复核失败。' }
```

## 3. 可用性测试

后端安装者执行实际存在的免费检查脚本，不向供应商发请求：

```powershell
pwsh -NoProfile -File 'D:\MCP\zhenzhen-gptimagegen2.5-mcp\scripts\smoke-test.ps1' -TimeoutSeconds 30
if ($LASTEXITCODE -ne 0) { throw '协议检查失败，请先排障。' }
```

v0.4.0 成功退出码 0，输出含 passed=true、transport=stdio、tools=12、prompts=1、resources=1、paid_calls=0；历史 v0.3.1 为 11 个工具。它在不同工作目录下启动实际子进程，检查 legacy 初始化、发现、资源/提示访问、免费指南及非法模型在联网前拒绝；失败非零并返回脱敏诊断。缺少 Key 不妨碍发现，key_present=true 也不证明供应商鉴权成功。

代理维护者可在当前 shell 输入网关原始令牌后运行完整能力检查；本脚本需要本地后端运行环境，仅连接远端的用户直接在自己的 Host 检查工具与免费指南即可：

```powershell
$ErrorActionPreference = 'Stop'
$ProxyUrl = Read-Host '输入网关实际 MCP URL（含真实服务器 ID）'
$GatewayKey = Read-Host '输入原始网关令牌（不含 Bearer）' -MaskInput
if ([string]::IsNullOrWhiteSpace($ProxyUrl) -or [string]::IsNullOrWhiteSpace($GatewayKey)) { throw 'URL 和令牌不能为空。' }
$env:CHERRYSTUDIO_API_GATEWAY_API_KEY = $GatewayKey
Remove-Variable GatewayKey
pwsh -NoProfile -File 'D:\MCP\zhenzhen-gptimagegen2.5-mcp\scripts\smoke-test.ps1' -ProxyUrl $ProxyUrl -TimeoutSeconds 30
if ($LASTEXITCODE -ne 0) { throw '代理协议检查失败。' }
```

此脚本的网关令牌读取为 Windows 用户变量优先、再进程变量，区别于业务 Key；如存在旧用户变量，先核对实际来源，不打印值或自动删除。它要求代理也桥接 Prompt/Resource；Tools-only 桥接不应据此判定后端不可用。

| 证据类别 | 已验证与未验证边界 |
|---|---|
| 静态 | JSON/TOML/YAML、PowerShell AST、模板一致性与秘密扫描；不执行配置示例 |
| 隔离/协议 | 88 项既有回归、11 工具发现，10 项有界并发、幂等、故障恢复和配置优先级；用受控上游，无费用 |
| 真实 Host | v0.3.1 本机 Codex stdio 与免费指南已验收；其他 Host/代理未全面复验 |
| 真实供应商 | 已授权 Flare 两项异步文生图均 SUCCESS/saved，含 NOT_START 恢复；未新增收费测试，十图真实并发及官转高级参数仍未验证 |

验收标识 G1–G9 见 [重构方案](docs/REFACTOR-PLAN.md)，B1–B8 见 [批量契约](docs/ASYNC-BATCH-PLAN.md)，历史证据见 [验证记录](docs/VALIDATION.md) 与 [D 盘验收](docs/D-DRIVE-ACCEPTANCE.md)。88 项和真实 Host/业务是已完成记录，不冒充每次文档修改都重新执行。开发检查入口为 `uv run --no-sync python scripts/check.py --build --audit`，需开发环境先 `uv sync --locked`；成员不必安装开发依赖执行回归。

## 4. 客户端配置

同一 Agent 会话选择直接 stdio 或消费代理，避免同一后端重复启用。添加后都要保存、启用、发现 v0.4.0 的 12 个工具（历史 v0.3.1 为 11 个）、绑定目标助手/Agent、按需授权工具，再免费调用 get_model_guide。真正绘图需要另行明确授权。

| 六项覆盖 | 本项目说明 |
|---|---|
| 本地 MCP JSON | 完整模板见 4.1，用于接受该 schema 的 Host |
| HTTP/代理 JSON | 完整模板见 4.2；只有外部代理，本项目无原生 HTTP |
| Codex TOML | 直接 stdio 与消费代理二选一 |
| Claude Code / Claude-3p JSON | 先给两配置文件快捷打开；Claude Code 给完整 JSON，Claude-3p schema 未核实，明确不冒称支持 |
| DSH YAML | web、desktop、multica 三种独立 profile；每种传输共用一份实例 |
| CLI 三种 Shell | Codex、Claude Code、DSH × PowerShell 7/Bash/Zsh；帮助已核对，九种真实执行未全面验证 |

### 4.1 本地 MCP JSON

<!-- LOCAL_CONFIG_START -->
```json
{
  "mcpServers": {
    "zhenzhen-gptimagegen2-5-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "D:\\MCP\\zhenzhen-gptimagegen2.5-mcp",
        "run",
        "--no-sync",
        "python",
        "-m",
        "zhenzhen_image_mcp"
      ]
    }
  }
}
```
<!-- LOCAL_CONFIG_END -->


### 4.2 消费代理 Host 的 MCP JSON

<!-- PROXY_CONFIG_START -->
```json
{
  "mcpServers": {
    "zhenzhen-gptimagegen2-5-mcp-proxy": {
      "type": "streamableHTTP",
      "url": "http://127.0.0.1:23333/v1/mcps/<cherrystudio_mcp_proxy_server_id>/mcp",
      "headers": {
        "Authorization": "Bearer ${CHERRYSTUDIO_API_GATEWAY_API_KEY}"
      }
    }
  }
}
```
<!-- PROXY_CONFIG_END -->

把 `<cherrystudio_mcp_proxy_server_id>` 换成网关界面分配的真实路由 ID，不从服务显示名推导。23333 和该路径仅适用于提供此路由的 Cherry Studio 版本，端口与完整 URL 以网关实际设置为准。

`${CHERRYSTUDIO_API_GATEWAY_API_KEY}` 需要消费 Host 明确支持展开；JSON 本身不插值。不支持时使用该 Host 的私有认证界面，或后文 Codex 的 bearer_token_env_var、DSH 的 !!js；不要把表达式原样当令牌发出。Authorization 只加一次 Bearer，HTTP Host 不设置后端 command/args/env/cwd。

在后端项目中安全复制模板到私有配置，只用一种时删去另一项；已存在时停止并手工合并：

```powershell
$ErrorActionPreference = 'Stop'
$ProjectDir = 'D:\MCP\zhenzhen-gptimagegen2.5-mcp'
$Names = @('.mcp.json', '.cherrystudiomcpproxy.mcp.json')
foreach ($Name in $Names) {
  if (Test-Path -LiteralPath (Join-Path $ProjectDir $Name)) { throw "已有配置，请先备份并手工合并：$Name" }
}
foreach ($Name in $Names) {
  [IO.File]::Copy((Join-Path $ProjectDir "$Name.example"), (Join-Path $ProjectDir $Name), $false)
}
```

### Cherry Studio：后端与消费代理的操作

1. 在设置的 MCP 服务器入口新增 stdio，名称与 command/逐行 args 按本地模板；支持相应 JSON 导入时导入模板，无 cwd、无业务 Key env。界面命名因版本而异，本轮未重测 GUI。
2. 保存、启用并检查 v0.4.0 的 12 个工具（v0.3.1 为 11 个）；在目标助手/Agent 中选择此服务，调用 get_model_guide，必要时修复项目 .env 后重启实际 MCP。
3. 需要代理才在兼容版本启用 API Gateway/MCP Proxy，记录实际 URL、路由 ID、原始网关令牌。先完成后端验收，再连接代理。
4. 消费 Host 选择 HTTP/Streamable HTTP，填实际 URL 和该 Host 支持的私有认证；保存、启用、绑定助手并发现工具，调用免费指南。仅开启网关不能代替消费 Host 配置；只消费远端的人不安装后端。

### Codex：用户级 config.toml

优先实际 CODEX_HOME，否则 `%USERPROFILE%\.codex\config.toml`。只合并目标服务表，不覆盖其他设置；命令先检查、唯一备份、再打开文件：

```powershell
$ErrorActionPreference = 'Stop'
$CodexRoot = if ([string]::IsNullOrWhiteSpace($env:CODEX_HOME)) { Join-Path $env:USERPROFILE '.codex' } else { $env:CODEX_HOME }
$ConfigPath = Join-Path $CodexRoot 'config.toml'
if (!(Test-Path -LiteralPath $ConfigPath -PathType Leaf)) { throw '请先初始化 Codex 并核对 CODEX_HOME。' }
[IO.File]::Copy($ConfigPath, "$ConfigPath.$([guid]::NewGuid().ToString('N')).bak", $false)
Start-Process -FilePath 'notepad.exe' -ArgumentList ('"{0}"' -f $ConfigPath) -ErrorAction Stop
```

直接 stdio：

```toml
[mcp_servers."zhenzhen-gptimagegen2-5-mcp"]
command = "uv"
args = [
  "--directory",
  "D:\\MCP\\zhenzhen-gptimagegen2.5-mcp",
  "run",
  "--no-sync",
  "python",
  "-m",
  "zhenzhen_image_mcp"
]
startup_timeout_sec = 30
tool_timeout_sec = 600
```

消费代理使用另一个服务表：

```toml
[mcp_servers."zhenzhen-gptimagegen2-5-mcp-proxy"]
url = "http://127.0.0.1:23333/v1/mcps/<cherrystudio_mcp_proxy_server_id>/mcp"
bearer_token_env_var = "CHERRYSTUDIO_API_GATEWAY_API_KEY"
startup_timeout_sec = 30
tool_timeout_sec = 600
```

bearer_token_env_var 填环境变量名，变量值为不含 Bearer 的原始网关令牌。以下只设置当前父进程，从同一 shell 启动 Host；桌面 App 要完全退出再从该环境启动，或用该版本支持的私有认证设置，不能假定已运行 GUI 自动继承：

```powershell
$GatewayKey = Read-Host '原始网关令牌（不含 Bearer）' -MaskInput
if ([string]::IsNullOrWhiteSpace($GatewayKey)) { throw '令牌不能为空。' }
$env:CHERRYSTUDIO_API_GATEWAY_API_KEY = $GatewayKey
Remove-Variable GatewayKey
codex
```

保存后重启/重新加载该 MCP，检查启用状态、v0.4.0 的 12 个工具与权限，调用 get_model_guide。Codex 不自动将模板 .mcp.json 当作 TOML 配置。

**环境兼容例外：**默认后端自己读取 .env；仅文件未定义 Key 时，需要转发父进程环境可在同一个 stdio 表内追加下面字段。不要另建重复实例，不将空 .env 当作缺失：

```toml
env_vars = [
  "ZHENZHEN_GPTIMAGEGEN_API_KEY",
  "ZHENZHEN_GPTIMAGEGEN_BASE_URL",
  "ZHENZHEN_GPTIMAGEGEN_OUTPUT_DIR",
  "ZHENZHEN_GPTIMAGEGEN_TIMEOUT"
]
```

```powershell
$ApiKey = Read-Host '后端 API Key（仅环境兼容模式）' -MaskInput
if ([string]::IsNullOrWhiteSpace($ApiKey)) { throw '密钥不能为空。' }
$env:ZHENZHEN_GPTIMAGEGEN_API_KEY = $ApiKey
Remove-Variable ApiKey
codex
```

仅在明确需要持久用户环境的兼容模式下执行下面命令；它写入当前用户的一个业务变量并同时设置当前父进程，其他设置不变。默认 .env 安装不需要它；不要用它覆盖文件中的空值或错误。保存后从同一 shell 启动 CLI；GUI 要完全退出后重新启动并核对实际继承环境，不保证已运行进程自动刷新。

```powershell
$ApiKey = Read-Host '后端 API Key（将保存到当前用户环境）' -MaskInput
if ([string]::IsNullOrWhiteSpace($ApiKey)) { throw '密钥不能为空。' }
[Environment]::SetEnvironmentVariable('ZHENZHEN_GPTIMAGEGEN_API_KEY', $ApiKey, 'User')
$env:ZHENZHEN_GPTIMAGEGEN_API_KEY = $ApiKey
Remove-Variable ApiKey
```

2026-10-15 隔离 Codex 0.162.0-alpha.17.2 验证 env:VAR 原样传入而 env_vars 可转发；原生 env 表的空字符串、`${VAR}` 也不应当作通用继承语法。不自动删除或清空已有环境变量。

### Claude Code / Claude-3p：先打开配置

以下先同时检查、备份并打开两个客户端已有配置；只使用一种时删去另一项，缺失则先按客户端初始化，不创建空文件覆盖配置：

```powershell
$ErrorActionPreference = 'Stop'
$ConfigFiles = @(
  (Join-Path $env:USERPROFILE '.claude.json')
  (Join-Path $env:LOCALAPPDATA 'Claude-3p\claude_desktop_config.json')
)
foreach ($ConfigFile in $ConfigFiles) {
  if (Test-Path -LiteralPath $ConfigFile -PathType Leaf) {
    [IO.File]::Copy($ConfigFile, "$ConfigFile.$([guid]::NewGuid().ToString('N')).bak", $false)
    Start-Process -FilePath 'notepad.exe' -ArgumentList ('"{0}"' -f $ConfigFile) -ErrorAction Stop
  } else {
    Write-Warning "配置不存在，请先初始化对应客户端：$ConfigFile"
  }
}
```

Claude Code 用户作用域 `.claude.json`：只合并 mcpServers 中该服务项，保留认证与其他设置。项目作用域由 Claude Code 的项目 .mcp.json 管理，不混为同一文件。

```json
{
  "mcpServers": {
    "zhenzhen-gptimagegen2-5-mcp": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "--directory",
        "D:\\MCP\\zhenzhen-gptimagegen2.5-mcp",
        "run",
        "--no-sync",
        "python",
        "-m",
        "zhenzhen_image_mcp"
      ]
    }
  }
}
```

保存后重启 Claude Code，用 `claude mcp list` 或会话 `/mcp` 检查服务，按客户端批准工具权限，在目标会话调用 get_model_guide。user 作用域 CLI 注册见下文。

Claude-3p 已提供路径和快捷操作，但缺少该客户端当前 schema 与连接证据；暂不列为已验证接入，不把 Claude Code JSON 原封套用到它，也不虚构专属代理语法。核对该客户端版本与文档后再配置。

### DSH：原生 web、App desktop、Multica multica

三种 profile 同等适用，但文件相互独立；默认根目录为当前用户 `.dsh`。实际客户端指定 DSH_HOME 或自定义目录时按它的设置调整，不固定用户名、不要求管理员身份：

| 客户端 | profile | 默认补丁路径 |
|---|---|---|
| 原生 DSH（npm/CLI） | web | `%USERPROFILE%\.dsh\profiles\web\cordis.patch.yml` |
| DSH App | desktop | `%USERPROFILE%\.dsh\profiles\desktop\cordis.patch.yml` |
| Multica | multica | `%USERPROFILE%\.dsh\profiles\multica\cordis.patch.yml` |

**在 YAML 前先备份并打开。**以下默认三份都处理；仅安装部分客户端时先删去不适用的 Profiles 项。先确认所有文件存在，再全部备份，最后打开；缺失时停止并初始化对应客户端，不自动创建 patch。

```powershell
$ErrorActionPreference = 'Stop'
$DshRoot = if ([string]::IsNullOrWhiteSpace($env:DSH_HOME)) {
  Join-Path $env:USERPROFILE '.dsh'
} else {
  $env:DSH_HOME
}
$Profiles = @('web', 'desktop', 'multica')
$PatchFiles = @($Profiles | ForEach-Object {
  Join-Path $DshRoot "profiles\$_\cordis.patch.yml"
})
foreach ($PatchFile in $PatchFiles) {
  if (!(Test-Path -LiteralPath $PatchFile -PathType Leaf)) {
    throw "配置不存在，请先初始化对应客户端或核对 DSH_HOME：$PatchFile"
  }
}
foreach ($PatchFile in $PatchFiles) {
  $BackupPath = '{0}.{1}.bak' -f $PatchFile, ([guid]::NewGuid().ToString('N'))
  [IO.File]::Copy($PatchFile, $BackupPath, $false)
  Write-Host "备份：$BackupPath"
}
foreach ($PatchFile in $PatchFiles) {
  Start-Process -FilePath 'notepad.exe' -ArgumentList ('"{0}"' -f $PatchFile) -ErrorAction Stop
}
```

下面每种传输只给一份完整补丁，分别合并到三份适用 profile；直连和代理二选一，不为同一 Agent 重复加载。以下字段根据桥接包 0.2.1-rc.2 源码核对，App/Multica 内置插件版本若不同，先核对其 schema，不把本机 npm 版本当作另外两者已验证。

**本地 stdio 的完整 cordis.patch.yml 补丁列表：**

```yaml
- insert:
    - id: mcp-zhenzhen-gptimagegen2-5-mcp
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: zhenzhen-gptimagegen2-5-mcp
        transport: stdio
        command: uv
        args:
          - --directory
          - 'D:\MCP\zhenzhen-gptimagegen2.5-mcp'
          - run
          - --no-sync
          - python
          - -m
          - zhenzhen_image_mcp
        toolCallTimeoutMs: 600000
        failOnStartupError: true
```

**消费代理 Host 的完整 cordis.patch.yml 补丁列表：**

```yaml
- insert:
    - id: mcp-zhenzhen-gptimagegen2-5-proxy
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: zhenzhen-gptimagegen2-5-proxy
        transport: streamable-http
        url: 'http://127.0.0.1:23333/v1/mcps/<cherrystudio_mcp_proxy_server_id>/mcp'
        headers:
          Authorization: !!js '`Bearer ${process.env.CHERRYSTUDIO_API_GATEWAY_API_KEY}`'
        toolCallTimeoutMs: 600000
        failOnStartupError: true
```

合并与激活步骤（两种传输、三个客户端均需完成）：

1. patch 仅为顶层空列表 `[]` 时，以适用的完整 YAML 列表替换；已有 patch 时追加为同一顶层列表条目，或合并到已有 insert 列表。不要在 `[]` 后直接拼接，不另包一层列表；保留原插件、注释、缩进和 `!!js`。
2. 同一目标实例已存在时就地合并，不能重复追加。id 是不冲突的实例 ID，name 是包名，serverName 是命名空间，需匹配 `[A-Za-z0-9_-]{1,32}`。DSH 用 29 字符代理别名，不照搬超过上限的通用代理全名。不要编辑共享 bundle。
3. stdio 先完成后端安装和 .env；HTTP 先完成网关与真实路由 ID 替换，并按前文掩码输入设置启动客户端父进程的网关令牌。DSH 的 `streamable-http` 不等于通用 JSON 的 `streamableHTTP`。`!!js` 由 DSH 解释，普通 YAML 不执行或自动插值；本地静态验证不求值真实凭据。
4. 保存每份实际使用的 profile。原生 DSH 从设置好环境的 shell 执行 `dsh --profile web`；App 完全退出后重启并确认加载 desktop；Multica 在其实际管理入口激活 multica 或重启关联 DSH。后两者界面/运行时未在本轮联调，不能用启动 npm web 的结果替代。
5. 检查插件加载日志，发现 v0.4.0 的 12 个工具且无 create_response。在目标 Agent 预设中启用/允许工具，调用免费 get_model_guide；以实际发现的命名空间为准。Tools 可用不证明 Prompt/Resource 已桥接，600000 毫秒是 Host 等待设置，不取消云端任务。

profile 备份含私有配置，只留本机并限制访问，不提交/打包。本手册不提供会重写现有 YAML 的自动拼接命令。额外 `--patch` 仅叠加到一次启动，不能与持久 profile 重复加载同一实例。

仅采用后端环境兼容模式时，在 stdio config 内加入以下字段；父进程业务变量输入方式同 Codex。默认 .env 流程不需要该段，HTTP 代理不能加入后端业务 env：

```yaml
env:
  ZHENZHEN_GPTIMAGEGEN_API_KEY: !!js process.env.ZHENZHEN_GPTIMAGEGEN_API_KEY
```

### CLI 添加：PowerShell 7、Bash、Zsh

2026-10-21 只读核对本机 Codex 0.153.0、Claude Code 2.1.303、DSH 0.2.1-rc.2 的帮助；CLI 升级后先重新查 `--help`。Codex 用消费代理、Claude Code 用 user 作用域 stdio、DSH 加载已保存的 profile，覆盖三个适用 CLI × 三种 Shell。只注册不会证明连接成功；检查服务列表、允许工具并调用 `get_model_guide` 才完成免费链路检查。本轮未实际运行九种组合，也未修改用户 Host 配置。

先按各 Host 小节备份配置，示例拒绝重复注册同名服务。PowerShell 使用 Windows 绝对路径；Bash/Zsh 示例指能直接启动 Windows uv/Python 且可访问 `D:/MCP/...` 的兼容环境；本项目不据此承诺 WSL/Linux/macOS 支持。Bash 使用 `read -p`，Zsh 使用 `read '变量?提示'`；秘密只通过当前进程环境转发。CLI 是可选 Host 入口，不是后端运行依赖。

#### Codex CLI × PowerShell 7

代理必须已启用；按提示输入含真实服务器 ID 的完整 URL，并通过当前进程网关变量认证，不把真实密钥存入命令参数。

```powershell
$ErrorActionPreference = 'Stop'
Get-Command codex -ErrorAction Stop | Out-Null
$ProxyUrl = Read-Host '输入实际 MCP Proxy 完整 URL（包含服务器 ID）'
if ([string]::IsNullOrWhiteSpace($ProxyUrl)) { throw 'URL 不能为空。' }
$GatewayKey = Read-Host '完整原始网关令牌（不含 Bearer）' -MaskInput
if ([string]::IsNullOrWhiteSpace($GatewayKey)) { throw '网关密钥不能为空。' }
$env:CHERRYSTUDIO_API_GATEWAY_API_KEY = $GatewayKey
Remove-Variable GatewayKey
codex mcp get 'zhenzhen-gptimagegen2-5-mcp-proxy' *> $null
if ($LASTEXITCODE -eq 0) { throw '服务已存在，按配置文件步骤更新。' }
codex mcp add 'zhenzhen-gptimagegen2-5-mcp-proxy' --url $ProxyUrl --bearer-token-env-var CHERRYSTUDIO_API_GATEWAY_API_KEY
if ($LASTEXITCODE -ne 0) { throw 'Codex MCP 注册失败。' }
# 从此 shell 启动 codex，使它继承本次输入的网关变量。
codex
```

#### Codex CLI × Bash

代理必须已启用；按提示输入含真实服务器 ID 的完整 URL，并通过当前进程网关变量认证，不把真实密钥存入命令参数。

```bash
command -v codex >/dev/null || exit 1
read -r -p 'MCP Proxy 完整 URL: ' ProxyUrl
read -r -s -p '完整原始网关令牌（不含 Bearer）: ' GatewayKey
printf '\n'
[[ -n "$ProxyUrl" && -n "$GatewayKey" ]] || exit 1
export CHERRYSTUDIO_API_GATEWAY_API_KEY="$GatewayKey"
unset GatewayKey
if codex mcp get 'zhenzhen-gptimagegen2-5-mcp-proxy' >/dev/null 2>&1; then
  printf '%s\n' '服务已存在，请修改配置文件。'; exit 1
fi
codex mcp add 'zhenzhen-gptimagegen2-5-mcp-proxy' --url "$ProxyUrl" --bearer-token-env-var CHERRYSTUDIO_API_GATEWAY_API_KEY || exit 1
codex
```

#### Codex CLI × Zsh

代理必须已启用；按提示输入含真实服务器 ID 的完整 URL，并通过当前进程网关变量认证，不把真实密钥存入命令参数。

```zsh
command -v codex >/dev/null || exit 1
read -r 'ProxyUrl?MCP Proxy 完整 URL: '
read -r -s 'GatewayKey?完整原始网关令牌（不含 Bearer）: '
printf '\n'
[[ -n "$ProxyUrl" && -n "$GatewayKey" ]] || exit 1
export CHERRYSTUDIO_API_GATEWAY_API_KEY="$GatewayKey"
unset GatewayKey
if codex mcp get 'zhenzhen-gptimagegen2-5-mcp-proxy' >/dev/null 2>&1; then
  printf '%s\n' '服务已存在，请修改配置文件。'; exit 1
fi
codex mcp add 'zhenzhen-gptimagegen2-5-mcp-proxy' --url "$ProxyUrl" --bearer-token-env-var CHERRYSTUDIO_API_GATEWAY_API_KEY || exit 1
codex
```

#### Claude Code CLI × PowerShell 7

成员环境已初始化且 `.env` 已填值；user 作用域写入用户级 Claude Code 配置。不会写入密钥参数。

```powershell
$ErrorActionPreference = 'Stop'
Get-Command claude -ErrorAction Stop | Out-Null
$ProjectDir = 'D:\MCP\zhenzhen-gptimagegen2.5-mcp'
if (!(Test-Path -LiteralPath (Join-Path $ProjectDir '.env') -PathType Leaf)) { throw '请先按第 2 节创建密钥文件。' }
claude mcp get 'zhenzhen-gptimagegen2-5-mcp' *> $null
if ($LASTEXITCODE -eq 0) { throw '服务已存在，请修改配置文件。' }
claude mcp add --scope user --transport stdio 'zhenzhen-gptimagegen2-5-mcp' -- uv --directory $ProjectDir run --no-sync python -m zhenzhen_image_mcp
if ($LASTEXITCODE -ne 0) { throw 'Claude MCP 注册失败。' }
claude
```

#### Claude Code CLI × Bash

成员环境已初始化且 `.env` 已填值；user 作用域写入用户级 Claude Code 配置。不会写入密钥参数。

```bash
command -v claude >/dev/null || exit 1
command -v uv >/dev/null || exit 1
ProjectDir='D:/MCP/zhenzhen-gptimagegen2.5-mcp'
[[ -f "$ProjectDir/.env" ]] || { printf '%s\n' '请先配置 .env'; exit 1; }
if claude mcp get 'zhenzhen-gptimagegen2-5-mcp' >/dev/null 2>&1; then
  printf '%s\n' '服务已存在，请修改配置文件。'; exit 1
fi
claude mcp add --scope user --transport stdio 'zhenzhen-gptimagegen2-5-mcp' -- uv --directory "$ProjectDir" run --no-sync python -m zhenzhen_image_mcp || exit 1
claude
```

#### Claude Code CLI × Zsh

成员环境已初始化且 `.env` 已填值；user 作用域写入用户级 Claude Code 配置。不会写入密钥参数。

```zsh
command -v claude >/dev/null || exit 1
command -v uv >/dev/null || exit 1
ProjectDir='D:/MCP/zhenzhen-gptimagegen2.5-mcp'
[[ -f "$ProjectDir/.env" ]] || { printf '%s\n' '请先配置 .env'; exit 1; }
if claude mcp get 'zhenzhen-gptimagegen2-5-mcp' >/dev/null 2>&1; then
  printf '%s\n' '服务已存在，请修改配置文件。'; exit 1
fi
claude mcp add --scope user --transport stdio 'zhenzhen-gptimagegen2-5-mcp' -- uv --directory "$ProjectDir" run --no-sync python -m zhenzhen_image_mcp || exit 1
claude
```

#### DSH CLI × PowerShell 7

先将 stdio 或代理补丁保存到原生 DSH 的 web profile。以下启动 npm/CLI 版 web；App 使用自己的 desktop 运行时，Multica 使用它实际激活的 multica profile，不用本命令代替另外两个客户端的启动。

```powershell
$ErrorActionPreference = 'Stop'
Get-Command dsh -ErrorAction Stop | Out-Null
$Profile = 'web'
$Mode = Read-Host '已保存的 profile 模式：stdio 或 proxy'
if ($Mode -eq 'stdio') {
  Get-Command uv -ErrorAction Stop | Out-Null
  if (!(Test-Path -LiteralPath 'D:\MCP\zhenzhen-gptimagegen2.5-mcp\.env' -PathType Leaf)) { throw '请先配置项目 .env。' }
} elseif ($Mode -eq 'proxy') {
  $GatewayKey = Read-Host '完整网关令牌（不含 Bearer）' -MaskInput
  if ([string]::IsNullOrWhiteSpace($GatewayKey)) { throw '网关令牌不能为空。' }
  $env:CHERRYSTUDIO_API_GATEWAY_API_KEY = $GatewayKey
  Remove-Variable GatewayKey
} else { throw '模式必须与已保存的 profile 一致。' }
dsh --profile $Profile
if ($LASTEXITCODE -ne 0) { throw 'DSH 启动失败，检查 profile 与插件日志。' }
```

#### DSH CLI × Bash

```bash
command -v dsh >/dev/null || exit 1
Profile='web'
ProjectDir='D:/MCP/zhenzhen-gptimagegen2.5-mcp'
read -r -p '已保存的 profile 模式 stdio/proxy: ' Mode
if [[ "$Mode" == stdio ]]; then
  command -v uv >/dev/null || exit 1
  [[ -f "$ProjectDir/.env" ]] || exit 1
elif [[ "$Mode" == proxy ]]; then
  read -r -s -p '完整网关令牌（不含 Bearer）: ' GatewayKey
  printf '\n'
  [[ -n "$GatewayKey" ]] || exit 1
  export CHERRYSTUDIO_API_GATEWAY_API_KEY="$GatewayKey"
  unset GatewayKey
else
  printf '%s\n' '模式必须与已保存的 profile 一致'
  exit 1
fi
dsh --profile "$Profile" || exit 1
```

#### DSH CLI × Zsh

```zsh
command -v dsh >/dev/null || exit 1
Profile='web'
ProjectDir='D:/MCP/zhenzhen-gptimagegen2.5-mcp'
read -r 'Mode?已保存的 profile 模式 stdio/proxy: '
if [[ "$Mode" == stdio ]]; then
  command -v uv >/dev/null || exit 1
  [[ -f "$ProjectDir/.env" ]] || exit 1
elif [[ "$Mode" == proxy ]]; then
  read -r -s 'GatewayKey?完整网关令牌（不含 Bearer）: '
  printf '\n'
  [[ -n "$GatewayKey" ]] || exit 1
  export CHERRYSTUDIO_API_GATEWAY_API_KEY="$GatewayKey"
  unset GatewayKey
else
  printf '%s\n' '模式必须与已保存的 profile 一致'
  exit 1
fi
dsh --profile "$Profile" || exit 1
```

DSH 没有经核对的 `dsh mcp add` 子命令。独立补丁只对本次运行生效，可使用 `dsh --profile web --patch '补丁的实际完整路径'`；不要同时在 profile 和额外 patch 装入本服务。启动后在日志/工具列表检查并按前述步骤绑定 Agent。PowerShell 若 Claude 包装脚本吞掉 `--`，核对本机 `claude.cmd --help` 并改用正确入口，不删除参数来绕过错误。

## 5. 启动排障

### 日常启动与日志

```powershell
uv --directory 'D:\MCP\zhenzhen-gptimagegen2.5-mcp' run --no-sync python -m zhenzhen_image_mcp
if ($LASTEXITCODE -ne 0) { throw '服务退出失败，请检查 stderr。' }
```

stdio 等待协议输入时没有欢迎输出正常；手工启动可 Ctrl+C 退出，但不能以能启动代替第 3 节协议检查。stdout 仅协议，日志写 stderr。缺少模块返回第 2 节解决安装问题，不在启动参数中偷偷安装/升级。

### 发布版本更新与回滚

更新前停止所有使用此安装的 MCP 子进程，记录当前 SHA，私下备份 `.env`（含 ACL）、整个 `.runtime`、输出目录的 `.tasks` 元数据与图片。不能在 SQLite 活动时复制；升级不覆盖 `.env`，新增字段手工合并，不能删除任务库重置防重。只有 ZIP 的旧安装先迁移到独立 clone，不直接覆盖旧目录或复用移动后的 .venv。

以下固定更新目标为 v0.4.0；发布证据附件公开后才能执行。将来选择新版本时，必须同时从其实际 Release 更新标签及完整 SHA，不能改为浮动 main。命令只允许干净 Git 安装，拒绝覆盖已忽略文件，不自动 stash/reset/clean：

```powershell
$ErrorActionPreference = 'Stop'
$ProjectDir = 'D:\MCP\zhenzhen-gptimagegen2.5-mcp'
$TargetTag = 'v0.4.0'
$ReleaseEvidence = Invoke-RestMethod -Uri "https://github.com/tsyecommercialdesigner-cloud/zhenzhen-gptimagegen2.5-mcp/releases/download/$TargetTag/release-evidence.json" -ErrorAction Stop
if ($ReleaseEvidence -is [string]) { $ReleaseEvidence = $ReleaseEvidence | ConvertFrom-Json -ErrorAction Stop }
if ($ReleaseEvidence.tag -ne $TargetTag -or $ReleaseEvidence.version -ne '0.4.0' -or $ReleaseEvidence.commit -notmatch '^[a-f0-9]{40}$') { throw '发布证据无效，停止安装。' }
$ExpectedSha = $ReleaseEvidence.commit
$RepositoryUrl = 'https://github.com/tsyecommercialdesigner-cloud/zhenzhen-gptimagegen2.5-mcp.git'
$ActualOrigin = git -C $ProjectDir remote get-url origin
if ($LASTEXITCODE -ne 0 -or $ActualOrigin -ne $RepositoryUrl) { throw 'origin 不符，请核对实际仓库后停止。' }
$Changes = @(git -C $ProjectDir status --porcelain)
if ($LASTEXITCODE -ne 0 -or $Changes.Count) { throw '存在本地修改，请先保留并处理。' }
$PreviousCommit = git -C $ProjectDir rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw '无法记录旧提交。' }
Write-Host "回滚提交：$PreviousCommit"
git -C $ProjectDir fetch origin tag $TargetTag
if ($LASTEXITCODE -ne 0) { throw '目标版本获取失败。' }
$TargetCommit = git -C $ProjectDir rev-parse "refs/tags/$TargetTag^{commit}"
if ($LASTEXITCODE -ne 0 -or $TargetCommit -ne $ExpectedSha) { throw '标签 SHA 与发布记录不符。' }
git -C $ProjectDir switch --detach --no-overwrite-ignore $TargetCommit
if ($LASTEXITCODE -ne 0) { throw '版本切换失败，保留文件并停止。' }
Set-Location -LiteralPath $ProjectDir
uv sync --locked --no-dev
if ($LASTEXITCODE -ne 0) { throw '更新安装失败，停止启动。' }
pwsh -NoProfile -File '.\scripts\smoke-test.ps1' -TimeoutSeconds 30
if ($LASTEXITCODE -ne 0) { throw '更新后协议检查失败，停止启用服务。' }
```

成功后重启 Host 的实际 MCP 子进程，刷新工具发现并免费调用指南。origin 使用自己已验证的 SSH 地址时，先人工核对其仓库归属，再相应调整检查值；不要因 URL 拼写差异忽略校验。

回滚也先停止进程，使用此前记录的完整旧 SHA，重新锁定安装和检查。版本切换不会自动回滚业务数据；回滚到没有批量能力的旧版时，保留新数据库，只凭已知 provider_task_id 查询，不用旧工具重复提交：

```powershell
$ErrorActionPreference = 'Stop'
$ProjectDir = 'D:\MCP\zhenzhen-gptimagegen2.5-mcp'
$PreviousCommit = Read-Host '输入此前记录、已验证的完整旧提交 SHA'
if ($PreviousCommit -notmatch '^[a-fA-F0-9]{40}$') { throw '需要完整提交 SHA。' }
if (@(git -C $ProjectDir status --porcelain).Count -or $LASTEXITCODE -ne 0) { throw '先保留并处理工作区修改。' }
git -C $ProjectDir switch --detach --no-overwrite-ignore $PreviousCommit
if ($LASTEXITCODE -ne 0) { throw '回滚切换失败。' }
Set-Location -LiteralPath $ProjectDir
uv sync --locked --no-dev
if ($LASTEXITCODE -ne 0) { throw '回滚依赖安装失败，停止启动。' }
pwsh -NoProfile -File '.\scripts\smoke-test.ps1' -TimeoutSeconds 30
if ($LASTEXITCODE -ne 0) { throw '旧版协议检查失败，停止启动。' }
```

不同目录迁移应重新创建虚拟环境，复制/恢复用户文件时保留 ACL 和任务数据，再统一修改 Host 路径并复验。当前成员安装默认 D 盘，不自动迁移现有 C 盘目录；手册不授权删除旧安装或备份。

## 6. 文件清单与交付

默认从第 2 节实际 GitHub 发布标签安装。跟踪的 src、pyproject.toml、uv.lock、.python-version、LICENSE、模板、README/MANUAL、脚本、测试、契约与 CI 配置均可随 clone 取得。成员本机生成 .venv；.env、.runtime、.tasks、图片、私有 Host 配置和缓存不属于公开交付。没有 Node 构建入口或独立 HTTP 部署产物。

### 可选 ZIP（仅明确需要时）

GitHub Release 默认提供源码/构建产物及校验资料，不保证包含成员 ZIP；只有维护者明确提供并验证时才使用下面的成员包流程。不能将 wheel/sdist 当成成员 ZIP，或绕过项目根 .venv 布局全局安装。

<!-- MEMBER_FILES_START -->
- `.env.example`
- `pyproject.toml`
- `uv.lock`
- `.python-version`
- `.mcp.json.example`
- `.cherrystudiomcpproxy.mcp.json.example`
- `LICENSE`
- `README.md`
- `MANUAL.md`
- `user-files.json`
- `scripts/smoke-test.ps1`
- `src/zhenzhen_image_mcp/__init__.py`
- `src/zhenzhen_image_mcp/__main__.py`
- `src/zhenzhen_image_mcp/api.py`
- `src/zhenzhen_image_mcp/batch.py`
- `src/zhenzhen_image_mcp/checkpoints.py`
- `src/zhenzhen_image_mcp/config.py`
- `src/zhenzhen_image_mcp/contracts.py`
- `src/zhenzhen_image_mcp/media.py`
- `src/zhenzhen_image_mcp/monitor.py`
- `src/zhenzhen_image_mcp/provider.py`
- `src/zhenzhen_image_mcp/runtime.py`
- `src/zhenzhen_image_mcp/server.py`
- `src/zhenzhen_image_mcp/smoke.py`
- `src/zhenzhen_image_mcp/tasks.py`
<!-- MEMBER_FILES_END -->

维护者在已准备开发依赖的项目根目录按需运行：

```powershell
pwsh -NoProfile -File '.\scripts\package-user.ps1'
if ($LASTEXITCODE -ne 0) { throw '打包/独立安装验证失败。' }
```

仅验证、不保留 ZIP 时使用 `pwsh -NoProfile -File '.\scripts\package-user.ps1' -VerifyOnly`。脚本先构建，检查白名单和秘密禁入，再独立临时目录、空缓存在线锁定安装与协议验证；不在日常启动中执行。输出 `output/zhenzhen-gptimagegen2.5-mcp-0.4.0-user.zip`，唯一顶层为 `zhenzhen-gptimagegen2.5-mcp/`，拒绝覆盖同名包。测试/开发规范不入成员 ZIP，但仍保留在 Git。

收到明确的已验包并核对维护者校验摘要后，按提示输入 ZIP 文件路径，解压到父目录，不预建项目目录：

```powershell
$ErrorActionPreference = 'Stop'
$ArchivePath = Read-Host '请输入成员 ZIP 完整文件路径（包含 .zip）'
if (!(Test-Path -LiteralPath $ArchivePath -PathType Leaf)) { throw 'ZIP 文件不存在。' }
$InstallRoot = 'D:\MCP'
$ProjectDir = Join-Path $InstallRoot 'zhenzhen-gptimagegen2.5-mcp'
if (Test-Path -LiteralPath $ProjectDir) { throw '已有安装，请保留配置并使用更新流程。' }
New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
Expand-Archive -LiteralPath $ArchivePath -DestinationPath $InstallRoot -ErrorAction Stop
if (!(Test-Path -LiteralPath (Join-Path $ProjectDir 'pyproject.toml') -PathType Leaf)) { throw '解压层级错误。' }
Set-Location -LiteralPath $ProjectDir
uv sync --locked --no-dev
if ($LASTEXITCODE -ne 0) { throw '依赖安装失败，停止启动。' }
```

随后按第 2 节配置 .env、第 3 节检查协议；不覆盖旧目录或私有文件。ZIP 必须排除真实 .env、秘密备份、私有配置、任务数据库、依赖、缓存及开发资料。通用 clone 更新命令不适用于无 .git 的旧 ZIP 安装。

## 7. 资源清单

以下工具参数、默认值、枚举和调用示例来自当前发现快照 [docs/mcp-inventory.json](docs/mcp-inventory.json)，与源码契约对应。示例路径/结果 URL/任务编号需替换为实际输入，不是已发生的收费请求。JSON 为工具 arguments，不是 Host 配置。

<!-- INVENTORY_START -->
### `get_model_guide`

免费本地模型选择建议和配置状态；只检查密钥是否存在，不显示密钥、不请求云端。

| 参数 | 类型 | 必需 | 默认 | 约束/说明 |
|---|---|---|---|---|
| 无 | — | — | — | 无参数 |

调用工具时的 arguments 示例（路径、URL 和任务 ID 替换为实际值）：

```json
{}
```

### `generate_image`

同步生成并落盘。默认逆向五参数；官转须显式 group=official。收费，POST 不自动重试。

| 参数 | 类型 | 必需 | 默认 | 约束/说明 |
|---|---|---|---|---|
| `prompt` | string | 是 | `—` |  minLength=1 |
| `model` | string | 是 | `—` | GPT Image 2.5 Sunburst 非常适合对编辑精度要求极高的应用场景；GPT Image 2.5 Flare 是目前用于生成高质量图片的最快模型。模型可以接受文本和图片作为输入，然后输出相应的图片。以上为用户提供的供应商选型说明，尚未做速度或质量对比实测。请结合用户意图选择并告知所用模型。 enum=['gpt-image-2.5-flare', 'gpt-image-2.5-sunburst'] |
| `images` | array[string] / null | 否 | `null` |  本机绝对图片路径、公开 HTTP(S) 图片 URL 或 base64 data URL；PNG/JPEG/WebP。; minItems=1; maxItems=16 |
| `size` | string / null | 否 | `null` | 可选 auto 或 WIDTHxHEIGHT；两边为16倍数、最大3840、比例不超过3:1、总像素655360..8294400。省略时不发送。  |
| `quality` | string / null | 否 | `null` |  允许值=auto, low, medium, high, xhigh, max |
| `output_dir` | string / null | 否 | `null` | 可选绝对输出目录；默认配置目录。异步任务查询默认沿用提交目录。  |
| `group` | string | 否 | `"reverse"` | 分组声明：默认 reverse（逆向）；仅用户明确使用官转时传 official。此字段不发送上游、不改变密钥后台分组。 enum=['reverse', 'official'] |
| `official_options` | OfficialOptions / null | 否 | `null` | 仅 group="official" 可用的官转扩展参数。未声明官转时传入此对象会在收费前拒绝。  |
| `idempotency_key` | string / null | 否 | `null` | 可选稳定幂等键；相同参数复用，参数改变拒绝，禁止换键重试未知收费结果。  |

`OfficialOptions` 对象字段：
- `n`：integer / null，可选；生成图片数量，1–10。
- `background`：string / null，可选；
- `output_format`：string / null，可选；
- `output_compression`：integer / null，可选；
- `mask`：string / null，可选；仅编辑：本机绝对路径/公开 URL/data URL，PNG，<4 MiB，与首张图同尺寸。
- `input_fidelity`：string / null，可选；官转组兼容透传，模型是否支持以供应商为准。
- `moderation`：string / null，可选；
- `response_format`：string / null，可选；供应商兼容扩展；不代表官方 GPT Image 支持此字段。
- `user`：string / null，可选；
- `safety_identifier`：string / null，可选；
- `stream`：boolean / null，可选；Images SSE；工具收集最终结果后返回。不能与异步提交合用。
- `partial_images`：integer / null，可选；

调用工具时的 arguments 示例（路径、URL 和任务 ID 替换为实际值）：

```json
{
  "prompt": "一只在窗边看雨的猫，水彩风格",
  "model": "gpt-image-2.5-flare",
  "size": "2048x1152"
}
```

### `edit_image`

同步图像编辑并落盘；多图以 image[] 上传。高编辑精度场景建议 Sunburst。收费。

| 参数 | 类型 | 必需 | 默认 | 约束/说明 |
|---|---|---|---|---|
| `prompt` | string | 是 | `—` |  minLength=1 |
| `model` | string | 是 | `—` | GPT Image 2.5 Sunburst 非常适合对编辑精度要求极高的应用场景；GPT Image 2.5 Flare 是目前用于生成高质量图片的最快模型。模型可以接受文本和图片作为输入，然后输出相应的图片。以上为用户提供的供应商选型说明，尚未做速度或质量对比实测。请结合用户意图选择并告知所用模型。 enum=['gpt-image-2.5-flare', 'gpt-image-2.5-sunburst'] |
| `images` | array[string] | 是 | `—` | 本机绝对图片路径、公开 HTTP(S) 图片 URL 或 base64 data URL；PNG/JPEG/WebP。 minItems=1; maxItems=16 |
| `size` | string / null | 否 | `null` | 可选 auto 或 WIDTHxHEIGHT；两边为16倍数、最大3840、比例不超过3:1、总像素655360..8294400。省略时不发送。  |
| `quality` | string / null | 否 | `null` |  允许值=auto, low, medium, high, xhigh, max |
| `output_dir` | string / null | 否 | `null` | 可选绝对输出目录；默认配置目录。异步任务查询默认沿用提交目录。  |
| `group` | string | 否 | `"reverse"` | 分组声明：默认 reverse（逆向）；仅用户明确使用官转时传 official。此字段不发送上游、不改变密钥后台分组。 enum=['reverse', 'official'] |
| `official_options` | OfficialOptions / null | 否 | `null` | 仅 group="official" 可用的官转扩展参数。未声明官转时传入此对象会在收费前拒绝。  |
| `idempotency_key` | string / null | 否 | `null` | 可选稳定幂等键；相同参数复用，参数改变拒绝，禁止换键重试未知收费结果。  |

`OfficialOptions` 对象字段：
- `n`：integer / null，可选；生成图片数量，1–10。
- `background`：string / null，可选；
- `output_format`：string / null，可选；
- `output_compression`：integer / null，可选；
- `mask`：string / null，可选；仅编辑：本机绝对路径/公开 URL/data URL，PNG，<4 MiB，与首张图同尺寸。
- `input_fidelity`：string / null，可选；官转组兼容透传，模型是否支持以供应商为准。
- `moderation`：string / null，可选；
- `response_format`：string / null，可选；供应商兼容扩展；不代表官方 GPT Image 支持此字段。
- `user`：string / null，可选；
- `safety_identifier`：string / null，可选；
- `stream`：boolean / null，可选；Images SSE；工具收集最终结果后返回。不能与异步提交合用。
- `partial_images`：integer / null，可选；

调用工具时的 arguments 示例（路径、URL 和任务 ID 替换为实际值）：

```json
{
  "prompt": "只给人物添加细框眼镜，保持五官和背景不变",
  "model": "gpt-image-2.5-sunburst",
  "images": [
    "C:\\Pictures\\portrait.png"
  ]
}
```

### `submit_image_generation`

提交收费异步绘图并返回 task_id；服务存活时每90秒自动查询并落盘。可选 idempotency_key 防重。

| 参数 | 类型 | 必需 | 默认 | 约束/说明 |
|---|---|---|---|---|
| `prompt` | string | 是 | `—` |  minLength=1 |
| `model` | string | 是 | `—` | GPT Image 2.5 Sunburst 非常适合对编辑精度要求极高的应用场景；GPT Image 2.5 Flare 是目前用于生成高质量图片的最快模型。模型可以接受文本和图片作为输入，然后输出相应的图片。以上为用户提供的供应商选型说明，尚未做速度或质量对比实测。请结合用户意图选择并告知所用模型。 enum=['gpt-image-2.5-flare', 'gpt-image-2.5-sunburst'] |
| `images` | array[string] / null | 否 | `null` |  本机绝对图片路径、公开 HTTP(S) 图片 URL 或 base64 data URL；PNG/JPEG/WebP。; minItems=1; maxItems=16 |
| `size` | string / null | 否 | `null` | 可选 auto 或 WIDTHxHEIGHT；两边为16倍数、最大3840、比例不超过3:1、总像素655360..8294400。省略时不发送。  |
| `quality` | string / null | 否 | `null` |  允许值=auto, low, medium, high, xhigh, max |
| `output_dir` | string / null | 否 | `null` | 可选绝对输出目录；默认配置目录。异步任务查询默认沿用提交目录。  |
| `group` | string | 否 | `"reverse"` | 分组声明：默认 reverse（逆向）；仅用户明确使用官转时传 official。此字段不发送上游、不改变密钥后台分组。 enum=['reverse', 'official'] |
| `official_options` | OfficialOptions / null | 否 | `null` | 仅 group="official" 可用的官转扩展参数。未声明官转时传入此对象会在收费前拒绝。  |
| `idempotency_key` | string / null | 否 | `null` | 可选稳定幂等键；相同参数复用，参数改变拒绝，禁止换键重试未知收费结果。  |

`OfficialOptions` 对象字段：
- `n`：integer / null，可选；生成图片数量，1–10。
- `background`：string / null，可选；
- `output_format`：string / null，可选；
- `output_compression`：integer / null，可选；
- `mask`：string / null，可选；仅编辑：本机绝对路径/公开 URL/data URL，PNG，<4 MiB，与首张图同尺寸。
- `input_fidelity`：string / null，可选；官转组兼容透传，模型是否支持以供应商为准。
- `moderation`：string / null，可选；
- `response_format`：string / null，可选；供应商兼容扩展；不代表官方 GPT Image 支持此字段。
- `user`：string / null，可选；
- `safety_identifier`：string / null，可选；
- `stream`：boolean / null，可选；Images SSE；工具收集最终结果后返回。不能与异步提交合用。
- `partial_images`：integer / null，可选；

调用工具时的 arguments 示例（路径、URL 和任务 ID 替换为实际值）：

```json
{
  "prompt": "海边灯塔，清晨自然光",
  "model": "gpt-image-2.5-flare",
  "output_dir": "C:\\MCP\\zhenzhen-images"
}
```

### `submit_image_edit`

提交收费异步编辑，以 image[] 上传；每90秒自动查询并落盘。可选 idempotency_key 防重。

| 参数 | 类型 | 必需 | 默认 | 约束/说明 |
|---|---|---|---|---|
| `prompt` | string | 是 | `—` |  minLength=1 |
| `model` | string | 是 | `—` | GPT Image 2.5 Sunburst 非常适合对编辑精度要求极高的应用场景；GPT Image 2.5 Flare 是目前用于生成高质量图片的最快模型。模型可以接受文本和图片作为输入，然后输出相应的图片。以上为用户提供的供应商选型说明，尚未做速度或质量对比实测。请结合用户意图选择并告知所用模型。 enum=['gpt-image-2.5-flare', 'gpt-image-2.5-sunburst'] |
| `images` | array[string] | 是 | `—` | 本机绝对图片路径、公开 HTTP(S) 图片 URL 或 base64 data URL；PNG/JPEG/WebP。 minItems=1; maxItems=16 |
| `size` | string / null | 否 | `null` | 可选 auto 或 WIDTHxHEIGHT；两边为16倍数、最大3840、比例不超过3:1、总像素655360..8294400。省略时不发送。  |
| `quality` | string / null | 否 | `null` |  允许值=auto, low, medium, high, xhigh, max |
| `output_dir` | string / null | 否 | `null` | 可选绝对输出目录；默认配置目录。异步任务查询默认沿用提交目录。  |
| `group` | string | 否 | `"reverse"` | 分组声明：默认 reverse（逆向）；仅用户明确使用官转时传 official。此字段不发送上游、不改变密钥后台分组。 enum=['reverse', 'official'] |
| `official_options` | OfficialOptions / null | 否 | `null` | 仅 group="official" 可用的官转扩展参数。未声明官转时传入此对象会在收费前拒绝。  |
| `idempotency_key` | string / null | 否 | `null` | 可选稳定幂等键；相同参数复用，参数改变拒绝，禁止换键重试未知收费结果。  |

`OfficialOptions` 对象字段：
- `n`：integer / null，可选；生成图片数量，1–10。
- `background`：string / null，可选；
- `output_format`：string / null，可选；
- `output_compression`：integer / null，可选；
- `mask`：string / null，可选；仅编辑：本机绝对路径/公开 URL/data URL，PNG，<4 MiB，与首张图同尺寸。
- `input_fidelity`：string / null，可选；官转组兼容透传，模型是否支持以供应商为准。
- `moderation`：string / null，可选；
- `response_format`：string / null，可选；供应商兼容扩展；不代表官方 GPT Image 支持此字段。
- `user`：string / null，可选；
- `safety_identifier`：string / null，可选；
- `stream`：boolean / null，可选；Images SSE；工具收集最终结果后返回。不能与异步提交合用。
- `partial_images`：integer / null，可选；

调用工具时的 arguments 示例（路径、URL 和任务 ID 替换为实际值）：

```json
{
  "prompt": "保持第一张人物身份，参考第二张的服装颜色",
  "model": "gpt-image-2.5-sunburst",
  "images": [
    "C:\\Pictures\\person.png",
    "C:\\Pictures\\clothing.png"
  ]
}
```

### `submit_image_batch`

一次提交1–20项收费异步生成/编辑，默认并发5、最多20。收到编号即返回，后台每90秒查询并落盘。同一(checkpointer,thread_id,task_id)及参数复用，冲突拒绝；不确定提交永不自动重发。

| 参数 | 类型 | 必需 | 默认 | 约束/说明 |
|---|---|---|---|---|
| `checkpointer` | string | 是 | `—` | 稳定的本地检查点命名空间/会话键，1–128字符。  |
| `thread_id` | string | 是 | `—` | 稳定的本地检查点命名空间/会话键，1–128字符。  |
| `tasks` | array[BatchImageTask] | 是 | `—` |  minItems=1; maxItems=20 |
| `max_concurrency` | integer | 否 | `5` |  minimum=1; maximum=20 |

`BatchImageTask` 对象字段：
- `task_id`：string，必填；Agent 指定的稳定任务键；重试不能改名。
- `operation`：string，可选； ['generate', 'edit']
- `prompt`：string，必填；
- `model`：string，必填； ['gpt-image-2.5-flare', 'gpt-image-2.5-sunburst']
- `images`：array[string] / null，可选；
- `size`：string / null，可选；
- `quality`：string / null，可选；
- `output_dir`：string / null，可选；
- `group`：string，可选； ['reverse', 'official']
- `official_options`：OfficialOptions / null，可选；

`OfficialOptions` 对象字段：
- `n`：integer / null，可选；生成图片数量，1–10。
- `background`：string / null，可选；
- `output_format`：string / null，可选；
- `output_compression`：integer / null，可选；
- `mask`：string / null，可选；仅编辑：本机绝对路径/公开 URL/data URL，PNG，<4 MiB，与首张图同尺寸。
- `input_fidelity`：string / null，可选；官转组兼容透传，模型是否支持以供应商为准。
- `moderation`：string / null，可选；
- `response_format`：string / null，可选；供应商兼容扩展；不代表官方 GPT Image 支持此字段。
- `user`：string / null，可选；
- `safety_identifier`：string / null，可选；
- `stream`：boolean / null，可选；Images SSE；工具收集最终结果后返回。不能与异步提交合用。
- `partial_images`：integer / null，可选；

调用工具时的 arguments 示例（路径、URL 和任务 ID 替换为实际值）：

```json
{
  "checkpointer": "product-detail-pages",
  "thread_id": "blue-bag-20261020",
  "max_concurrency": 5,
  "tasks": [
    {
      "task_id": "page_01",
      "operation": "generate",
      "prompt": "蓝色垃圾袋详情页首图",
      "model": "gpt-image-2.5-flare"
    },
    {
      "task_id": "page_02",
      "operation": "edit",
      "prompt": "保持商品外观，替换为厨房场景",
      "model": "gpt-image-2.5-sunburst",
      "images": [
        "C:\\Pictures\\product.png"
      ]
    }
  ]
}
```

### `run_image_batch`

同步执行1–20项收费生成/编辑，默认并发5，完成并校验落盘后返回。稳定三元组防重；重放验证文件SHA-256，不重复收费；超时/未知结果禁止重发。

| 参数 | 类型 | 必需 | 默认 | 约束/说明 |
|---|---|---|---|---|
| `checkpointer` | string | 是 | `—` | 稳定的本地检查点命名空间/会话键，1–128字符。  |
| `thread_id` | string | 是 | `—` | 稳定的本地检查点命名空间/会话键，1–128字符。  |
| `tasks` | array[BatchImageTask] | 是 | `—` |  minItems=1; maxItems=20 |
| `max_concurrency` | integer | 否 | `5` |  minimum=1; maximum=5 |

`BatchImageTask` 对象字段：
- `task_id`：string，必填；Agent 指定的稳定任务键；重试不能改名。
- `operation`：string，可选； ['generate', 'edit']
- `prompt`：string，必填；
- `model`：string，必填； ['gpt-image-2.5-flare', 'gpt-image-2.5-sunburst']
- `images`：array[string] / null，可选；
- `size`：string / null，可选；
- `quality`：string / null，可选；
- `output_dir`：string / null，可选；
- `group`：string，可选； ['reverse', 'official']
- `official_options`：OfficialOptions / null，可选；

`OfficialOptions` 对象字段：
- `n`：integer / null，可选；生成图片数量，1–10。
- `background`：string / null，可选；
- `output_format`：string / null，可选；
- `output_compression`：integer / null，可选；
- `mask`：string / null，可选；仅编辑：本机绝对路径/公开 URL/data URL，PNG，<4 MiB，与首张图同尺寸。
- `input_fidelity`：string / null，可选；官转组兼容透传，模型是否支持以供应商为准。
- `moderation`：string / null，可选；
- `response_format`：string / null，可选；供应商兼容扩展；不代表官方 GPT Image 支持此字段。
- `user`：string / null，可选；
- `safety_identifier`：string / null，可选；
- `stream`：boolean / null，可选；Images SSE；工具收集最终结果后返回。不能与异步提交合用。
- `partial_images`：integer / null，可选；

调用工具时的 arguments 示例（路径、URL 和任务 ID 替换为实际值）：

```json
{
  "checkpointer": "product-detail-pages",
  "thread_id": "blue-bag-sync-20261021",
  "max_concurrency": 5,
  "tasks": [
    {
      "task_id": "page_01",
      "operation": "generate",
      "prompt": "蓝色垃圾袋详情页首图",
      "model": "gpt-image-2.5-flare"
    },
    {
      "task_id": "page_02",
      "operation": "edit",
      "prompt": "保持商品外观，替换为厨房场景",
      "model": "gpt-image-2.5-sunburst",
      "images": [
        "C:\\Pictures\\product.png"
      ]
    }
  ]
}
```

### `get_image_batch`

免费读取本地持久化检查点，恢复该会话所有 task_id/provider_task_id/最后观察状态；不查询供应商、不提交、不等待成图。

| 参数 | 类型 | 必需 | 默认 | 约束/说明 |
|---|---|---|---|---|
| `checkpointer` | string | 是 | `—` | 稳定的本地检查点命名空间/会话键，1–128字符。  |
| `thread_id` | string | 是 | `—` | 稳定的本地检查点命名空间/会话键，1–128字符。  |

调用工具时的 arguments 示例（路径、URL 和任务 ID 替换为实际值）：

```json
{
  "checkpointer": "product-detail-pages",
  "thread_id": "blue-bag-20261020"
}
```

### `get_batch_image_task`

按原(checkpointer,thread_id,task_id)查询供应商异步结果并自动落盘；只读HTTP有限重试。没有供应商编号时返回本地状态，不重新提交。云端失败为工具错误；检查 result.save_status。

| 参数 | 类型 | 必需 | 默认 | 约束/说明 |
|---|---|---|---|---|
| `checkpointer` | string | 是 | `—` | 稳定的本地检查点命名空间/会话键，1–128字符。  |
| `thread_id` | string | 是 | `—` | 稳定的本地检查点命名空间/会话键，1–128字符。  |
| `task_id` | string | 是 | `—` | 批量提交时指定的原始 task_id。  |
| `output_dir` | string / null | 否 | `null` | 可选绝对输出目录；默认配置目录。异步任务查询默认沿用提交目录。  |
| `save` | boolean | 否 | `true` |   |

调用工具时的 arguments 示例（路径、URL 和任务 ID 替换为实际值）：

```json
{
  "checkpointer": "product-detail-pages",
  "thread_id": "blue-bag-20261020",
  "task_id": "page_01",
  "save": true
}
```

### `get_image_task`

查询 NOT_START（排队）/IN_PROGRESS/FAILURE/SUCCESS；暂时性查询故障最多尝试3次。save=true 时成功图片自动落盘；false 仅查询。不重新提交。

| 参数 | 类型 | 必需 | 默认 | 约束/说明 |
|---|---|---|---|---|
| `task_id` | string | 是 | `—` |   |
| `output_dir` | string / null | 否 | `null` | 可选绝对输出目录；默认配置目录。异步任务查询默认沿用提交目录。  |
| `save` | boolean | 否 | `true` |   |

调用工具时的 arguments 示例（路径、URL 和任务 ID 替换为实际值）：

```json
{
  "task_id": "替换为提交返回的真实任务ID",
  "save": true
}
```

### `wait_image_task`

有界轮询，NOT_START 排队和 IN_PROGRESS 处理中继续等待，成功后落盘；只读查询有限重试计入等待时限。超时返回 task_id/wait_timed_out，云端任务继续；可稍后再次查询。

| 参数 | 类型 | 必需 | 默认 | 约束/说明 |
|---|---|---|---|---|
| `task_id` | string | 是 | `—` |   |
| `timeout_seconds` | number | 否 | `60` |  minimum=1; maximum=300 |
| `poll_interval` | number | 否 | `90` |  minimum=1; maximum=300 |
| `output_dir` | string / null | 否 | `null` | 可选绝对输出目录；默认配置目录。异步任务查询默认沿用提交目录。  |

调用工具时的 arguments 示例（路径、URL 和任务 ID 替换为实际值）：

```json
{
  "task_id": "替换为提交返回的真实任务ID",
  "timeout_seconds": 180,
  "poll_interval": 90
}
```

### `download_image`

按图片 URL 下载并校验 PNG/JPEG/WebP，自动落盘返回绝对路径；不会附带供应商 API Key。

| 参数 | 类型 | 必需 | 默认 | 约束/说明 |
|---|---|---|---|---|
| `url` | string | 是 | `—` | 公开 HTTP(S) 图片 URL  |
| `output_dir` | string / null | 否 | `null` | 可选绝对输出目录；默认配置目录。异步任务查询默认沿用提交目录。  |

调用工具时的 arguments 示例（路径、URL 和任务 ID 替换为实际值）：

```json
{
  "url": "https://example.com/replace-with-real-result.png",
  "output_dir": "C:\\MCP\\zhenzhen-images"
}
```

<!-- INVENTORY_END -->

当前全部工具声明了 `outputSchema`，成功时返回与之匹配的 structuredContent，同时保留文本 JSON 供旧 Host 使用；协议测试校验返回结构。工具执行失败由 SDK 返回 `isError=true`；未知工具、无效 JSON-RPC 等协议错误与业务失败分开处理。

公共返回结构：

| 工具 | 返回字段 |
|---|---|
| `get_model_guide` | `models`、`advice`、`base_url`、`output_dir`、`key_variable`、`key_present`、`default_group`、`official_declaration`；不返回密钥。 |
| `generate_image` / `edit_image` | `status=COMPLETED` 表示收到同步或 Images SSE 最终响应；`group` 为声明分组；`save_status`、`files[]`、`download_errors[]`、`response`（剔除图片 Base64）。检查 save_status 才能判断保存结果。 |
| `submit_image_generation` / `submit_image_edit` | `task_id`、`status=SUBMITTED`、`group`、`output_dir`、`next_tool`，元数据保存失败时有 `warning`。 |
| `submit_image_batch` | `checkpointer`、`thread_id`、`status=ACCEPTED/ATTENTION_REQUIRED`、`tasks[]`、`next_tool`、`note`；每项含逻辑 task_id、status、provider_task_id（可空）、group、output_dir、reused 及可选 error/warning。ACCEPTED 只表示提交确认，不是成图。 |
| `get_image_batch` | `status=SNAPSHOT`、原 checkpointer/thread_id、tasks[] 最后观察状态；未知线程返回空数组，不查询上游；tasks[] 结构同上。 |
| `get_batch_image_task` | 原三元组、任务状态、provider_task_id、group、output_dir、reused；取得上游结果时含 result，结构与单项查询一致，保存状态位于 result.save_status。无编号则只返回本地记录，不补发。 |
| `get_image_task` | `task_id`、`status`、`progress`、`fail_reason`、`response`；FAILURE 返回 isError 和脱敏原因；可用时保留 usage/cost（单位未确认）；SUCCESS 且 save=true 时追加保存字段。 |
| `wait_image_task` | 查询返回结构；本地等待超时时追加 `wait_timed_out=true`、`next_tool`、`note`，不取消云端任务。 |
| `download_image` | `path`、`mime_type`、`bytes`、`sha256`、`reused`。 |

`files[]` 每项为 `index`、`path`（绝对路径）、`mime_type`、`bytes`、`sha256`、`reused`。`save_status` 为 `saved/partial/failed/no_images`；`no_images` 表示响应中未找到可保存的图片，应检查供应商结果。`download_errors[]` 含 `index`、可用时的 `url`、脱敏 `error`。不要把 `SUCCESS` 或 `COMPLETED` 当作文件保存成功。参数/HTTP/协议错误由 MCP 返回工具错误；不把错误伪装成图片结果。

批量结果、幂等重放和自动轮询的持久清单也保留 `download_errors[]`，但其中 `url` 固定为 null，错误文本中的 URL 和常见令牌会脱敏；不持久化上游下载地址。失败清单用于诊断，不表示已保存成功，也不能据此换键重新生成。异步保存后续恢复成功时会更新文件清单并清空旧下载错误；此前已经丢弃的错误无法从新代码补回。

提示 `image_workflow`：必填字符串参数 `request`，无默认值，返回一个包含模型建议和操作顺序的用户消息模板。示例客户端调用 `get_prompt("image_workflow", {"request": "保持人物脸部不变，给人物加眼镜"})`。模板不执行任务。

资源 `zhenzhen://models`：无参数，MIME `application/json`，返回模型数组和选型建议。示例 `read_resource("zhenzhen://models")`。无动态资源模板；不开放任意本地文件读取资源。

## 8. 功能说明

### 选择模型与准备输入

`gpt-image-2.5-sunburst` 适合对编辑精度要求极高的场景；`gpt-image-2.5-flare` 适合追求速度的高质量生成。供应商称 Flare 是其目前生成高质量图片最快的模型，两者接受文本和图片输入；这是用户提供的供应商建议，未做速度/质量对比实测。每次显式传 `model`，Agent 应说明选择。

图片输入接受 MCP 所在机器的绝对路径、公开 HTTP(S) URL 或 Base64 data URL。Generations 将参考图序列化为 JSON `image` 数组，Edits 多图通过重复 `image[]` multipart 字段上传。图片仅支持 PNG/JPEG/WebP，每张最多 50 MiB，1–16 张，总输入上限 100 MiB；公开 URL 下载逐跳校验。

`size` 可选，省略即不发送；允许 `auto` 或自定义 `WIDTHxHEIGHT`，边长为 16 倍数，最大边长 3840，比例不超过 3:1，总像素 655360–8294400。例如 `2048x1152`、`3840x2160`、`2160x3840`。逆向 `quality` 可选 `auto/low/medium/high`；官转另允许 `xhigh/max`。逆向不发送 `n`、`response_format` 或 mask；官转扩展按下节声明并遵守端点约束。不能将尺寸可填写推断为供应商一定有对应模型权限。

### 分组声明 format def

```text
group: "reverse" | "official" = "reverse"
official_options: OfficialOptions | null = null
```

这两个字段是四个生成/编辑工具的顶层 arguments；批量入口则在每个 tasks[] 项内声明。省略 group 即为逆向；要使用官转，必须显式传 **`"group": "official"`**。`official_options` 是对象，不能写成 JSON 字符串，不能放在 prompt 内当作声明。即使只传空对象，未声明官转也会拒绝。不会从模型、提示词、API Key、环境变量或报错推断/切换分组。

逆向示例（`generate_image`，省略 group）：

```json
{
  "prompt": "白色背景上的蓝色垃圾袋，商品摄影",
  "model": "gpt-image-2.5-flare",
  "size": "1024x1024"
}
```

官转示例（`generate_image`）：

```json
{
  "prompt": "蓝色垃圾袋商品图，透明背景",
  "model": "gpt-image-2.5-flare",
  "group": "official",
  "official_options": {
    "n": 1,
    "background": "transparent",
    "output_format": "png"
  }
}
```

官转扩展字段及边界：

| 参数 | 类型 / 约束 |
|---|---|
| n | 整数 1–10，不接受字符串或布尔值 |
| background | auto / opaque / transparent；透明背景仅 png/webp |
| output_format | png / jpeg / webp |
| output_compression | 整数 0–100；须显式 output_format=jpeg/webp |
| mask | 仅编辑；绝对路径、公开 URL 或 data URL；有 alpha 的 PNG、<4 MiB、与首图同尺寸，以 multipart mask 上传 |
| input_fidelity | high / low；官转组兼容透传，模型支持情况以供应商为准 |
| moderation | auto / low |
| response_format | url / b64_json；本供应商兼容扩展，不将其当作官方 GPT Image 通用字段 |
| user / safety_identifier | 非空字符串，最多 128 字符；只传必要的匿名标识 |
| stream | 布尔；true 消费 Images SSE，收集最终图片后返回 MCP 结果，与异步提交互斥 |
| partial_images | 整数 0–3，要求 stream=true；中间预览不落盘、不算最终成功 |

顶层 quality 在逆向仅 auto/low/medium/high，官转另允许 xhigh/max。本项目接受的字段与范围以 contracts.py、锁定 SDK 和供应商说明为准；官方能力不等于供应商已实测支持。未知字段/不合法组合在本地失败，供应商拒绝也不自动换组或重提。用户已确认 Generations 没有 mask 格式示例，因此仅 edits 工具支持 multipart mask；JSON generations 不猜测二进制格式。SSE 属于 Images，不恢复 Responses。

分组声明不会改变供应商后台 Key 权限。异步查询/下载无须重传 group；新任务元数据保存分组和输出目录，旧 metadata 仅含目录的格式仍可读取。

### 同步生成 / 编辑

免费调用 `get_model_guide` 后，使用 `generate_image` 文生图或带参考图生成；精细编辑调用 `edit_image` 并提供图片。例如：

```json
{
  "prompt": "把第一张图中的垃圾袋和卷筒垃圾袋替换为第二张图的米黄色茉莉花款，保留第一张海报布局、文字和背景",
  "model": "gpt-image-2.5-sunburst",
  "images": [
    "D:\\Pictures\\Image Transfer Station\\5.jpg",
    "D:\\Pictures\\Image Transfer Station\\WhiteBase.jpg"
  ],
  "output_dir": "C:\\MCP\\zhenzhen-images"
}
```

同步接口收到响应后下载或解码并保存，检查 `files[]` 和 `save_status`。长耗时优先用下述异步流程；Host 的超时要覆盖实际工具等待。精细编辑不依赖 Responses，`create_response` 已按用户要求移除。连续编辑把上一步实际结果路径再作为输入，不依赖 `previous_response_id`。

### 异步提交、等待、续查

1. 调用 `submit_image_generation` 或 `submit_image_edit`，服务向 Images 路由添加 `?async=true`，立即保存返回的原始 `task_id`。异步提交同样计费。
2. 调用 `wait_image_task`，默认等待 60 秒、间隔 90 秒；范围均为 1–300 秒。需要至少一次完整轮询间隔时将 timeout_seconds 设为 180 或以上。或稍后用 `get_image_task` 只查一次。
3. `NOT_START` 为排队、`IN_PROGRESS` 为处理中，均继续查询；`FAILURE` 返回带 task_id 和脱敏原因的 MCP 工具错误；`SUCCESS` 且 `save=true` 时自动保存。成功状态不等于文件已落盘，要核对 `save_status`。
4. `wait_timed_out=true` 只表示本次本地等待结束，保留 task_id 继续查；不会取消云端任务。MCP 服务存活时后台自动轮询；关闭 Host 后暂停，重启后从数据库恢复，无需重新提交。

```json
{
  "task_id": "替换为原提交返回的真实任务ID",
  "timeout_seconds": 180,
  "poll_interval": 90
}
```

提交目录元数据保存在默认输出目录 `.tasks/<task_id>.json`，包含 version/output_dir/group，不保存提示词或 Key。查询默认沿用提交时的 `output_dir`，显式参数可覆盖；换机器或默认输出目录后可显式指定目标。元数据保存失败不重提任务，返回 warning 和 task_id。

只读 GET 遇到网络中断、超时或 HTTP 408/429/500/502/503/504，每轮最多尝试 3 次，间隔 1、2 秒；其他 HTTP 错误、未知状态或格式错误不自动重试。尝试与间隔受单轮请求及 `wait_image_task` 总预算约束。重试耗尽返回带 task_id 的脱敏工具错误，继续查询原任务；成功结果直接落盘，不额外再查一次。保存有独立下载时限，不保证整个工具耗时只等于轮询预算。

### 批量同步与异步：一轮最多 20 项

同步多图使用 `run_image_batch`，默认并发 5、可设 1–5，等待成图并校验落盘后返回。异步使用 `submit_image_batch`，默认并发 5、可设 1–20，收到提交确认即返回；后台每个任务每 90 秒查询一次并保存。两者均接受 1–20 项，支持混合生成和编辑。同一 MCP 进程跨单项与批量共享同步 5、异步提交 20 的并发上限；多个进程或账号间不共享提交配额，供应商实际容量需另验。

身份的 format def：

```text
checkpointer: string            # 稳定的检查点命名空间，例如 product-detail-pages
thread_id: string               # 稳定的会话/规划键，例如 blue-bag-20261020
tasks[].task_id: string          # Agent 首次提交前指定，例如 page_01；同一线程内唯一
unique_key = (checkpointer, thread_id, task_id)
provider_task_id: string | null  # 供应商返回的另一个编号，不能与逻辑 task_id 混用
```

`checkpointer` 是命名空间字符串，本版内部使用 SQLite，不需要安装 LangGraph 或传入 saver 对象。命名空间和会话键为 1–128 字符，首位字母/数字，其余可用字母、数字、下划线、点、冒号或连字符；`task_id` 仅用 1–128 个字母、数字、下划线或连字符。同一已授权任务的重试必须保留这三个键，不能每次随机生成新键。

先规划稳定任务键，再一次调用 `submit_image_batch`。下面展示两项；同一数组可扩展至 20 项，`operation` 省略时为 `generate`。默认逆向，使用官转时在对应项显式写 `group="official"` 和 `official_options`。

```json
{
  "checkpointer": "product-detail-pages",
  "thread_id": "blue-bag-20261020",
  "max_concurrency": 5,
  "tasks": [
    {
      "task_id": "page_01",
      "operation": "generate",
      "prompt": "蓝色垃圾袋详情页首图",
      "model": "gpt-image-2.5-flare"
    },
    {
      "task_id": "page_02",
      "operation": "edit",
      "prompt": "保持商品外观，替换为厨房场景",
      "model": "gpt-image-2.5-sunburst",
      "images": [
        "C:\\Pictures\\product.png"
      ]
    }
  ]
}
```

返回的 `tasks[]` 保持输入顺序，各项含逻辑 `task_id`、`provider_task_id`、`status`、`output_dir` 和 `reused`。顶层 `ACCEPTED` 只说明提交已被接收/复用，不代表图片生成成功；`ATTENTION_REQUIRED` 表示至少一项提交不确定、仍处于提交状态或已有云端失败。部分提交失败不丢弃其他编号，也不自动补发失败项。

稍后调用 `get_batch_image_task`，只查询需要的一项；有供应商编号时才发 GET，成功且 `save=true` 才保存。检查返回的 `result.save_status` 和 `result.files`；云端 FAILURE 仍为 MCP 工具错误。NOT_START / IN_PROGRESS 稍后再查，查询暂时失败可继续使用原身份查询。

```json
{
  "checkpointer": "product-detail-pages",
  "thread_id": "blue-bag-20261020",
  "task_id": "page_01",
  "save": true
}
```

Agent 会话恢复或 Host 重启后，先调用 `get_image_batch`，免费读取该线程的本地记录和最后观察状态；不会请求供应商或等待成图，未知线程返回空数组。再用原 `task_id` 查询所需项目。若要用旧的 `get_image_task` / `wait_image_task`，传的是 **provider_task_id**。

```json
{
  "checkpointer": "product-detail-pages",
  "thread_id": "blue-bag-20261020"
}
```

同一身份、相同请求指纹会返回已有记录，`reused=true`，不再发送收费 POST。指纹包括操作、模型参数、分组、业务地址、输出目录和参考图/mask 内容摘要；改变任何一项均会冲突并在本轮 POST 前拒绝整批。并发数不影响指纹。重放会重新读取参考图，文件或 URL 内容变更会冲突；参考图已不可用时使用检查点查询恢复，不通过重新提交找回结果。

| 本地/云端状态 | 处理方式 |
|---|---|
| RESERVED | 已保留幂等键但没有开始提交，原参数重放可继续 |
| SUBMITTING | 正在提交或提交进程已中断，不自动重发或按超时抢占 |
| SUBMITTED | 已有 provider_task_id，后续查询 |
| SUBMISSION_UNCERTAIN | 超时、取消或响应缺少编号，不能确认是否已收费；先核对供应商，禁止自动重发 |
| NOT_START / IN_PROGRESS | 排队 / 生成中，继续查询 |
| SUCCESS / FAILURE | 云端成功 / 失败；成功还须核对保存状态，失败不自动生成新任务 |

整批先预检，最多 20 项、每线程最多 1000 条记录，参考图与 mask 合计最多 128 MiB；预检不产生收费 POST，但可能下载参考 URL 和探测输出目录。SQLite 在 POST 前原子记录提交权，同一项目的多个 MCP 进程也只能有一次提交尝试。供应商未给出幂等键契约，无法保证网络故障后“恰好一次成功”；本版保守保留不确定状态，可能冻结实际未发出的任务。若提交后的数据库写入失败，返回 warning，并尽量保留已知 provider_task_id，供 `get_image_task` 直接查询。

数据库固定在实际项目的 `.runtime/checkpoints.sqlite3`，例如 `D:\MCP\zhenzhen-gptimagegen2.5-mcp\.runtime\checkpoints.sqlite3`，不随 Host 工作目录或输出目录变化。保存身份、请求指纹、分组、目录、状态、供应商编号和时间，不保存提示词、原图、mask 或 Key。默认不自动清理；更新需保留整个 `.runtime`，先停止所有使用该项目的 MCP 进程，再在私有位置备份整个目录。删除、恢复旧备份、重装到另一目录或换一组身份键都会失去相应防重历史；多机器之间没有分布式协调，不要借此自动重提。

`generate_image`、`edit_image`、`submit_image_generation`、`submit_image_edit` 新增可选 `idempotency_key`（1–128 个字母/数字/下划线/连字符），映射到 `(single, default, idempotency_key)`，四个工具共用命名空间；与批量身份一样，相同参数复用、修改参数拒绝。同步结果清单持久化，重放验证文件存在及 SHA-256；哈希不匹配时报错，绝不重新收费。未提供键的单项保持原先无提交防重行为。只有一项也可使用批量入口获得保护。同步和异步模式不能共用同一任务身份。回滚旧版后保留新数据库，旧工具须凭 provider_task_id 查询，不要按逻辑任务键重新提交。开发契约和验收标识见 [异步批量方案](docs/ASYNC-BATCH-PLAN.md)。

### 每 90 秒自动查询与数据库恢复

后台轮询绑定 MCP 服务生命周期，单项/批量异步提交确认后登记 `(base_url, provider_task_id)`；首次查询在 90 秒后，每次查询完成后至少再等待 90 秒，调度扫描最多增加约 5 秒延迟。每轮最多 5 个并行查询，一次自动轮询只发一次 GET；网络错误或失败下载在下一轮重试，不执行收费 POST。FAILURE 或 SUCCESS 且全部文件已保存后停止；部分保存失败继续查询原编号并复用已保存文件。主动 `get_*`/`wait_*` 调用独立于自动频率，仍可有限重试。

SQLite schema 1 自动迁移至 2，保留旧批量身份并登记已知供应商编号；旧版未登记到检查点的单项 JSON 元数据不自动导入，仍可凭原编号查询。WAL + FULL、短事务、5秒锁等待、到期索引和带随机令牌的事务租约协调多个进程；不在网络或下载期间占用写事务。服务中断后待租约到期恢复，默认最长约450秒（请求预算180秒+保存180秒+90秒余量）；正常运行不重查已完成保存的任务。不确定提交且无编号的记录保持冻结。

数据库只新增轮询时间/次数、租约与本地结果清单（路径、字节数、SHA-256），不持久化原始响应/图像/提示词/URL/密钥。升级前停止所有 MCP 实例并备份整个 `.runtime`（包含可能存在的 WAL/SHM 文件）；schema2 不支持直接回滚旧服务读取，回滚需保留新数据库并凭供应商编号恢复。此本地负载无需额外数据库服务，无新收费或依赖；跨机器部署需另行设计。

### 下载与恢复

同步/异步成功都处理 URL 或 Base64 图片，返回绝对文件路径。图片校验后按 SHA-256 命名，先写临时文件，再以不覆盖方式发布；重复查询相同内容复用文件。`download_image` 可对已有公开结果 URL 单独补下载，不发送后端 Authorization。

部分下载失败保留其他成功文件。URL 仍有效时用 `download_image`；异步结果可用原 task_id 再查。同步 Base64 结果若保存失败且无 URL，本版不持久化原始响应，不能保证恢复；先修复目录，禁止为恢复而自动重新付费。

尺寸验收边界：已有 Flare 真实测试请求 1024×1024，供应商曾返回 1254×1254。工具保留供应商原图，不自动裁切或重新收费；有严格尺寸要求时，保存后检查实际像素。详细结果见 [D 盘验收记录](docs/D-DRIVE-ACCEPTANCE.md)。

## 9. 注意事项

| 边界 | 实际行为与操作要求 |
|---|---|
| 费用 / 幂等 | 生成、编辑及异步提交会产生费用；SDK `max_retries=0`。批量按稳定三元组、单项可选idempotency_key持久化防重；未传键的单项无防重保证。不确定状态不自动重发；保留检查点和供应商编号 |
| 取消 | 没有云端取消工具；停止等待、关闭 Host 或 Ctrl+C 不保证云端任务取消或退款 |
| 文件权限 | 输入可读取运行账号权限内的绝对文件，输出可指定绝对目录；当前无项目根沙箱或服务端目录白名单，不应向不可信远程用户开放该账号全部文件能力 |
| 下载网络 | 拒绝非公开目标并逐跳验证重定向；校验真实图像类型/大小。下载专用客户端不带业务 Authorization、不继承系统代理；受限网络可能下载失败 |
| 并发 / 限额 | 每批最多20项；进程内跨工具同步并发5、异步提交并发20，批量默认并发5；无跨进程/账号速率配额 |
| 秘密 | `.env`、私有 Host 配置及备份明文保存在受限目录；不进入 Git/ZIP/日志。后端 Key 与网关令牌用途不同 |
| 时间 | 请求默认 180 秒、可设 10–600 秒；wait 预算和 Host 超时分别设置。工具本地超时不等于云端失败 |
| 外部内容 | 文件、图片和供应商返回内容只作数据，不作为 Agent 指令；实际编辑效果与文字准确性需看图验收 |

源代码和协议测试中的权限校验不构成多租户隔离；当前无目录授权、全局速率限制等边界与通用新规范存在差距，扩展公开服务前需另做实现与验收。不要把 Host 的确认框当作服务端权限控制。

本服务器只有 stdio。经代理提供 HTTP 时，网关需校验 Origin（存在且无效应拒绝）、默认只监听回环地址；跨机器需 HTTPS、认证、最小权限和明确可信代理。当前项目未验证 Cherry Studio 网关的这些安全策略，不声称源码已实现它们。没有原生 OAuth 实现；不得把消费方网关令牌直接转给业务 API。网关在 A 机器、Host 在 B 机器时，`127.0.0.1` 指 B 自己，URL 必须换成可达的安全地址；输入/输出路径和 `.env` 则属于实际运行 Python 的 A 机器。

0.1.1 已规范化 `NO_PROXY/no_proxy` 中带方括号的 IPv6 条目：单独 `[::1]` 转为 `::1`，带端口形式保留其绕过语义；保留代理和证书环境。不要照搬“删除所有以 `[` 开头条目”的建议，避免丢失正确规则。未知非法配置明确报错，两种 HTTP 库的 InvalidURL 纳入脱敏错误返回；只清洗当前进程，不改全局用户变量。

## 10. 常见问题

| 问题 | 定位与修复 |
|---|---|
| `uv/pwsh/python` 找不到 | 检查 PATH 和实际运行账号；安装符合第 1 节版本的工具，重启 Host 使其继承 PATH。Python 3.12 下载需要网络 |
| `uv sync --locked` 失败 | 检查 Python、源、网络/代理、证书和缓存权限。锁与元数据不一致由开发者修复，不删除锁或加 `--upgrade` |
| `No module named zhenzhen_image_mcp` | 核对安装目录、`src/`、元数据、初始化退出码和 `--directory`；成员不复用开发机 `.venv` |
| 解压后多套一层目录 | 默认 clone 自动生成项目目录；0.4.0 可选 ZIP 自带项目顶层目录，直接解压到父目录，不再按带版本 ZIP 文件名套目录 |
| 握手过了但绘图报缺少 Key | 协议检查不认证供应商；检查实际项目 `.env` 字段、运行账号和 ACL，调用指南看 `key_present` |
| `.env` 空值 / 格式 / 重复 / 编码错误 | 填实际 Key、保留唯一字段、保存 UTF-8；错误必须修复，不能靠环境旧值掩盖 |
| `.env` 不可读 | 按实际服务账号核对文件与目录 ACL；不要提升整个 Host 为管理员或给 Everyone 读取 |
| 旧环境变量仍生效 | 先确认实际项目根和文件字段；文件有效时优先，无文件时进程先于用户级。空值或非法值必须修复，不回退旧值 |
| 修改 `.env` 后行为未变 | 重启实际 MCP 子进程及必要 Host，确认不是另一安装目录或同名重复实例 |
| Codex `env:VAR` 被原样传递 | 默认用 `.env`；兼容模式用 `env_vars`，先输入父进程变量，再从同一 shell 启动。不要假设任意字符串会插值 |
| DSH 插件未出现 / 工具被拒绝 | 核对实际 profile、唯一 id、serverName 字符与长度、YAML 合并及 Agent 预设；保存后重启，避免 profile 与 --patch 重复加载 |
| 401 / 403 / Origin 拒绝 | 分清网关与供应商响应。检查对应令牌来源、单个 Bearer 前缀、账号权限、Origin 允许策略；不要关闭认证作为修复 |
| 代理 404 / 工具路由不存在 | 从实际网关取得 URL 和服务器 ID，确认该版本提供该路由、后端已启用；不把服务显示名当路由 ID |
| InvalidURL / TLS / 连接失败 | 检查代理 URL、NO_PROXY 与证书链；0.1.1 已处理方括号 IPv6，更新源码后重启。未知非法配置不静默删除 |
| `NOT_START` 或等待超时 | 正常排队状态；用原 task_id 继续查，不重新提交。wait 超时不取消任务 |
| 查询暂时失败 | 只读查询有有限重试；耗尽后保留 task_id 续查，401 等永久错误先修复认证。不要重复生成 |
| SUCCESS / COMPLETED 却无文件 | 检查 `save_status/files/download_errors` 和目录写权限；公开下载域名可能受限，按第 8 节补下载 |
| Host 协议/SDK 不兼容 | SDK 版本与协议版本分开核对；已有证据验证 stdio legacy 2025-11-25 路径，Tools-only 桥接不适用完整能力检查 |
| stdio 没反应 / 协议解析失败 | 无输出可正常；用检查脚本判定。stdout 只保留协议，调试日志改 stderr，核对实际模块入口 |
| 是否支持 Responses / 流式模型响应 | 当前不提供，已按用户要求移除；用 Images 编辑与异步工具，不能凭供应商通用文档恢复已删除能力 |
| GitHub CI/发布是否已生效 | PR #1 已合入 main 并通过合入提交的 Windows CI；各版本的发布运行及证据见实际 Release。发布前已配置 main 的 PR/CI 检查、v* 标签不可修改/删除及 release 环境维护者审批（仅 main）；单维护者无需独立 approving review，不能视为独立同行评审。当前设置以 GitHub 为准 |
| 默认逆向却传官转参数报错 | 在工具 arguments 顶层显式写 group=official，参数放 official_options；同时核对 Key 后台分组。服务不会自动换组 |
