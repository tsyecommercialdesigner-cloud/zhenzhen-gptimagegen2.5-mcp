# Zhenzhen Image MCP 使用手册

适用版本：0.3.0；是否已公开发布，以实际 GitHub Release 记录为准。本文按当前源码、锁文件及协议发现结果说明实际行为；验证范围见第 3 节。正式版本发布后，首次使用按第 1–4 节操作，已有安装按第 5 节升级。

## 1. 环境准备

### 部署与名称

实际仓库：<https://github.com/tsyecommercialdesigner-cloud/zhenzhen-gptimagegen2.5-mcp>。源码已由 [PR #1](https://github.com/tsyecommercialdesigner-cloud/zhenzhen-gptimagegen2.5-mcp/pull/1) 合入 main；各发布版本的远端 CI 以 Release 证据所链接的实际提交为准。正式安装必须选该仓库 Releases 中已通过检查的版本及完整 SHA，不能将下文候选号当作已存在标签。

本项目是 Python **stdio MCP Server**。本地成员在运行 Host 的机器安装它；也可由 Cherry Studio 启动后，通过其 MCP Proxy 供其他 Host 使用。仅连接代理的用户不安装后端、不执行 uv、不复制后端 API Key。项目没有独立 HTTP 监听服务或容器部署入口，代理的部署与安全由网关维护者负责。

| 项目 | 本项目的值 |
|---|---|
| 开发目录 | `E:\collaborative-workspace\zhenzhen-gptimage2.5-mcp`；不因成员命名改动而迁移 |
| 成员项目目录原名 | `zhenzhen-gptimagegen2.5-mcp`（用户约定） |
| Windows 默认安装目录 | `C:\MCP\zhenzhen-gptimagegen2.5-mcp` |
| Python 发行包 / 版本 | `zhenzhen-image` / `0.3.0`，来自 `pyproject.toml` |
| Python 模块 / 入口 | `zhenzhen_image_mcp` / `python -m zhenzhen_image_mcp` |
| 本地配置服务标识 | `zhenzhen-gptimagegen2-5-mcp` |
| 通用代理配置服务标识 | `zhenzhen-gptimagegen2-5-mcp-proxy` |
| DSH 代理别名 | `zhenzhen-gptimagegen2-5-proxy`；一对一映射上述代理标识，满足 32 字符限制 |
| MCP 内部 serverInfo.name | `zhenzhen-gptimagegen2-5-mcp`，与本地配置名称一致 |
| 业务 API | `https://ai.t8star.org/v1`；OpenAI 兼容 Images 接口 |
| 后端密钥字段 | `ZHENZHEN_GPTIMAGEGEN_API_KEY` |
| 后端密钥文件 | `C:\MCP\zhenzhen-gptimagegen2.5-mcp\.env` |
| 代理网关令牌变量 | `CHERRYSTUDIO_API_GATEWAY_API_KEY`；保存完整原始令牌，不含 `Bearer ` |

服务配置名称统一将点号换为连字符；安装目录、版本、模型、模块、URL 和网关实际路由 ID 保持各自原值。更新旧配置时先检查新旧名称是否同时存在，合并为一个实例，避免重复启动或重复付费；不要通过全局替换修改整个配置文件。

### 运行环境与兼容范围

| 项目 | 要求 / 已验证范围 |
|---|---|
| 平台 | 当前支持范围为 Windows / PowerShell 7；CI 与发布验收仅使用 Windows，其他系统不在当前支持范围 |
| Python | `>=3.12,<3.13`；`.python-version` 固定 `3.12.14` |
| Git / 包管理器 | Git（获取发布版本）、uv 0.12.9（本轮实测）；需能访问 Python 包源，安装时联网，日常启动 `--no-sync` |
| 构建 | hatchling `1.27.0`；纯 Python `src/` 布局，不需要 Node.js、npm 或额外 SDK extra |
| MCP SDK | 官方 Python SDK `mcp==2.2.0`，使用 `MCPServer` |
| 业务 / HTTP SDK | `openai==3.13.0`、`httpx==0.28.1`、`httpx2==2.12.0` |
| 其他主要运行依赖 | Pillow `13.0.0`、python-dotenv `1.2.2`、PyJWT `2.15.0`；TLS 证书依赖 certifi 锁定 `2026.10.19`，这些依赖按安全公告修复，全部版本以 `uv.lock` 为准 |
| 协议与传输 | 本轮实际 stdio legacy 客户端协商 `2025-11-25`，检查 initialize/initialized；SDK 主版本不等于协议版本 |
| Host | Cherry Studio 本地 / 代理、Codex、Claude Code、DSH 的配置见第 4 节；GUI 与代理实际连接未在本轮验证 |
| CLI 依据 | 2026-10-14 历史 help 核对：Codex `0.153.0`、Claude Code `2.1.258`、DSH `0.1.1-rc.2`；升级后重新核对帮助 |
| Codex 特定实测 | 2026-10-15 原生 Codex `0.162.0-alpha.17.2` 隔离测试确认 `env_vars` 转发；不代表全部版本 |

这里只承诺上述实际验证的旧协议兼容路径；未验证 MCP `2026-07-28` 请求级元数据模式，未声明完整协议版本矩阵。DSH 桥接仅按 Tools 使用，不推定它暴露 Prompts 或 Resources。Claude-3p 的 schema/连接尚未核实，见第 4 节适用性说明。

依赖安装与业务联网是两件事：安装需访问锁定包源及可能的 Python 下载源；绘图需访问业务 API，落盘还需访问供应商返回的公开图片域名。沿用成员已批准的代理、TLS 证书与包源配置，不为排障关闭证书验证或自动升级锁文件。Windows 用户级变量的兼容读取使用当前运行账号的 `HKCU\Environment`；默认 `.env` 流程不写注册表，也不需要管理员权限。

### 配置读取与当前差异

默认把 API Key 放进后端项目 `.env`，由 MCP 自己读取；Host 的 JSON/TOML/YAML 默认不传后端密钥。源码/editable 按模块所属根目录定位；项目 `.venv` 中的 wheel 按固定虚拟环境父目录定位，并核对 pyproject.toml 存在。不搜索 Host 工作目录或祖先文件，不支持无项目根的全局 wheel 安装。

| 来源 / 状态 | 当前 0.3.0 行为 |
|---|---|
| 项目 `.env` 定义有效 Key | 使用文件值，覆盖环境中的值 |
| 文件不存在 / 未定义字段 | 先读进程变量，仅其未定义时再兼容 Windows 当前用户级变量；非 Windows 读进程变量 |
| 文件字段为空、重复、格式错误、不可读 | 明确失败，不回退旧密钥；`get_model_guide` 用 `key_present=false` 表示校验未通过 |
| 所有来源缺失 | 绘图请求失败；本地发现及不访问业务的协议检查仍可运行 |

优先级已统一为 **项目 `.env → MCP 进程 → Windows 当前用户级`**。任一选中来源已定义但为空或非法时均报错，不继续找旧值；只有真正缺失才回退。0.1.2 的“用户级先于进程”行为已变更，环境兼容模式升级时请核对。

`.env` 需为 UTF-8（可带 BOM），最大 64 KiB；允许注释、单/双引号，不执行其中内容、不展开 `${VAR}`。密钥按实际供应商原值填写，内部不得含空白或控制字符；不自行加 `Bearer `。只有 API Key 从 `.env` 读取；下列可选设置来自 **MCP 进程环境**，不要误写进 `.env` 后期待生效：

| 变量 | 默认 / 约束 |
|---|---|
| `ZHENZHEN_GPTIMAGEGEN_BASE_URL` | `https://ai.t8star.org/v1`；HTTPS、路径为 `/v1`，无账号密码、query 或 fragment |
| `ZHENZHEN_GPTIMAGEGEN_OUTPUT_DIR` | 当前运行用户 `Pictures\ZhenzhenImage`；绝对本地目录 |
| `ZHENZHEN_GPTIMAGEGEN_TIMEOUT` | 180 秒；10–600 秒 |

每次生成/编辑调用的 `group` 默认 `reverse`。用户使用官转时必须显式传 `group="official"`，扩展参数放 `official_options`；格式定义见第 8 节。该声明只控制本地参数校验，不发送上游、不改变 Key 的供应商后台分组；账户权限仍以实际响应为准。

## 2. 项目初始化

### 从 GitHub 固定版本安装

默认从上述实际仓库取得发布版本，私有仓库使用成员自己的 Git 凭据管理/SSH 授权，不把令牌写入 URL。以下命令仅用于 Releases 中已公开的版本；如尚无目标版本，请勿猜测标签。维护者须在 Release 提供通过 CI 的版本标签、完整提交 SHA 和安装验证记录；从该 Release 的 `release-evidence.json` 取得值，不猜测 `v0.3.0` 已存在。

```powershell
$ErrorActionPreference = 'Stop'
$RepositoryUrl = 'https://github.com/tsyecommercialdesigner-cloud/zhenzhen-gptimagegen2.5-mcp.git'
$ReleaseTag = Read-Host '输入 Releases 中已通过 CI 的实际版本标签'
$ExpectedSha = Read-Host '输入该 Release 记录的完整 40 位提交 SHA'
if ($ReleaseTag -notmatch '^v\d+\.\d+\.\d+$' -or $ExpectedSha -notmatch '^[a-fA-F0-9]{40}$') { throw '版本或 SHA 格式不正确。' }
$InstallRoot = 'C:\MCP'
$ProjectDir = Join-Path $InstallRoot 'zhenzhen-gptimagegen2.5-mcp'
if (Test-Path -LiteralPath $ProjectDir) { throw '项目目录已存在，请按第 5 节更新，不能覆盖安装。' }
New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
git clone --branch $ReleaseTag --single-branch $RepositoryUrl $ProjectDir
if ($LASTEXITCODE -ne 0) { throw '获取发布版本失败，停止安装。' }
$ActualSha = git -C $ProjectDir rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $ActualSha -ne $ExpectedSha) { throw '提交 SHA 与发布记录不符，停止安装。' }
Set-Location -LiteralPath $ProjectDir
uv sync --locked --no-dev
if ($LASTEXITCODE -ne 0) { throw '锁定依赖安装失败，请先解决安装错误再启动 MCP。' }
```

clone 自动创建项目目录，根目录直接包含 `src/`、`pyproject.toml`、`uv.lock`、版本文件、手册、模板及检查脚本。源码仓库同时有开发文档和测试是正常行为；运行依赖安装到成员自己的 `.venv`。Python 安装阶段由 hatchling 构建应用，不运行 `uv init`、不用裸 pip、不添加不存在的 SDK extra。日常启动不构建或安装。Linux/macOS 须使用该机器绝对路径；本轮未实测跨平台成员安装。

仅当明确收到可选 ZIP 时，使用第 6 节流程；ZIP 不再是默认初始化的前提。已有旧版平铺包请按其版本手册操作，不与 0.3.0 的唯一顶层目录结构混用。

### 创建并填写私有 `.env`

以下命令保留已有文件；只在缺失时复制空值模板。记事本打开后，填写真实值、保存，再继续可用性检查。不要把密钥贴到聊天、共享脚本或命令参数里。

```powershell
$ErrorActionPreference = 'Stop'
$ProjectDir = 'C:\MCP\zhenzhen-gptimagegen2.5-mcp'
$EnvPath = Join-Path $ProjectDir '.env'
$ExamplePath = Join-Path $ProjectDir '.env.example'
if (Test-Path -LiteralPath $EnvPath) {
  Write-Host '保留已有 .env，请核对所需字段。'
} else {
  if (!(Test-Path -LiteralPath $ExamplePath -PathType Leaf)) { throw '缺少 .env.example，请核对交付文件。' }
  [IO.File]::Copy($ExamplePath, $EnvPath, $false)
}
notepad.exe $EnvPath
```

空值模板的字段如下，仅私有 `.env` 填真实值：

```ini
ZHENZHEN_GPTIMAGEGEN_API_KEY=
```

`.env` 为明文。检查文件 ACL；确认当前账号确为运行 MCP 的账号后，可授予其读写并移除继承，仅保留必要管理员/服务账号的显式权限。先核对输出，勿给 Everyone 或无关账号授权；不同账号启动的 Host 需按实际账号安排权限。

```powershell
$EnvPath = 'C:\MCP\zhenzhen-gptimagegen2.5-mcp\.env'
$McpAccount = [Security.Principal.WindowsIdentity]::GetCurrent().Name
Get-Acl -LiteralPath $EnvPath | Format-List Owner, AccessToString
# 仅确认上述账号就是 MCP 运行账号后执行；不删除已有显式权限：
icacls.exe $EnvPath /grant:r "${McpAccount}:(R,W)"
if ($LASTEXITCODE -ne 0) { throw '设置文件权限失败。' }
icacls.exe $EnvPath /inheritance:r
if ($LASTEXITCODE -ne 0) { throw '移除继承失败，请检查 ACL。' }
Get-Acl -LiteralPath $EnvPath | Format-List Owner, AccessToString
```

修改后重启实际 MCP 子进程：在 Host 停用/启用该服务，必要时退出并重启 Host。无需重新设置全局环境变量。升级、回滚与清理均保留 `.env` 及其 ACL；私有备份也必须有相同访问限制，禁止进入 ZIP 或 Git。

## 3. 可用性测试

成员运行以下脚本，默认总检查超时 30 秒，可选范围 1–300 秒：

```powershell
pwsh -NoProfile -File 'C:\MCP\zhenzhen-gptimagegen2.5-mcp\scripts\smoke-test.ps1' -TimeoutSeconds 30
if ($LASTEXITCODE -ne 0) { throw 'MCP 可用性检查失败，请先排障。' }
```

成功退出码为 0，输出包含 `passed=true`、`transport=stdio`、`tools=11`、`prompts=1`、`resources=1`、`paid_calls=0`；失败返回非零并输出脱敏诊断。脚本从不同工作目录启动真实子进程，检查旧协议初始化、能力发现、Prompt/Resource 访问、免费模型建议及非法模型拒绝，无绘图费用。它不证明 Key 已获供应商授权；`get_model_guide.key_present=true` 也只说明凭据校验通过。

需要检查已运行的代理时，先按第 4 节向当前 shell 输入网关令牌，然后运行：

```powershell
$ProxyUrl = Read-Host '输入实际 MCP Proxy 完整 URL（包含真实服务器 ID）'
if ([string]::IsNullOrWhiteSpace($ProxyUrl)) { throw 'URL 不能为空。' }
pwsh -NoProfile -File 'C:\MCP\zhenzhen-gptimagegen2.5-mcp\scripts\smoke-test.ps1' -ProxyUrl $ProxyUrl -TimeoutSeconds 30
if ($LASTEXITCODE -ne 0) { throw '代理协议检查失败。' }
```

此脚本需要本地成员运行环境，供后端维护者使用；仅连接远端的用户在自己的 Host 验证发现与 `get_model_guide`，不为检查而安装整个后端。不同代理是否桥接 Prompt/Resource 需先核对；本脚本要求完整能力，Tools-only 桥接不能据此判定后端故障。

| 验收内容 | 证据与界限 |
|---|---|
| 源码与资源契约 | 第 7 节来自 `docs/mcp-inventory.json` 的发现清单；本轮核对实际发现 |
| 文档配置 | JSON/TOML/YAML 与 PowerShell 语法检查，模板与文档逐字一致；详见开发文件 `docs/VALIDATION.md` |
| SDK 协议与错误 | `tests/test_protocol.py` 覆盖暂时查询失败后恢复、NOT_START、等待预算、保存及收费 POST 不重试；使用受控替身 |
| 批量并发与幂等 | `tests/test_batch.py` 通过真实 MCP SDK 与替身 HTTP 验证 10 项并发提交、持久化防重、跨进程提交权、取消/不确定状态和查询恢复；不代表供应商实测 |
| 凭据加载 | `tests/test_config_env.py` 覆盖文件优先、非法文件失败、工作目录隔离等；文件/进程/用户级优先顺序、空值失败和工作目录隔离已覆盖 |
| Host / 业务 | 本轮没有真实 GUI/代理联调、Bash/Zsh 执行或收费生成；不将静态检查等同于连接或业务通过 |

开发环境先 `uv sync --locked`；本地与 CI 共用 `uv run --no-sync python scripts/check.py --build --audit`，包含格式/lint、类型、文档、秘密、单元/协议、构建及联网依赖审计。单独测试可用 `uv run --no-sync python -m unittest discover -s tests -v`。未启用 spec-kit / Beads，本次沿用源码、问题记录和测试作为追溯依据，不虚构需求或任务标识。

## 4. 客户端配置

选择 **直接 stdio** 或 **消费代理**；同一会话避免同时启用两条重复能力。下表覆盖六项配置要求，后续按 Host 操作。

| 配置项 | 使用范围 |
|---|---|
| 本地 MCP JSON | Cherry Studio 等支持相应 JSON schema 的 Host；模板一 |
| HTTP / 代理 JSON | 支持 `streamableHTTP` 及相应认证机制的 Host；模板二 |
| Codex TOML | 本地 stdio 与代理各一份，无须假定 Codex 自动读取 `.mcp.json` |
| Claude Code / Claude-3p JSON | Claude Code 用户作用域配置；Claude-3p 路径与快捷打开提供，schema 未核实不冒充已支持 |
| DSH profile YAML | `desktop` / `web` 共用一种配置结构，分别给直连和消费代理版本 |
| CLI × 三种 Shell | Codex、Claude Code、DSH 九种示例；按已核对 CLI 选项编写，未声明九种执行均通过 |

### 模板一：本地 MCP JSON

<!-- LOCAL_CONFIG_START -->
```json
{
  "mcpServers": {
    "zhenzhen-gptimagegen2-5-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "C:\\MCP\\zhenzhen-gptimagegen2.5-mcp",
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

### 模板二：消费代理 Host 的 MCP JSON

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

将 `<cherrystudio_mcp_proxy_server_id>` 替换为网关为该后端分配的真实 ID，不能用服务显示名推导。端口 `23333` 和 `/v1/mcps/<id>/mcp` 仅用于确实提供该路由的 Cherry Studio 版本；从其界面取得实际地址，不自动退回 SSE。`${CHERRYSTUDIO_API_GATEWAY_API_KEY}` **只是要求 Host 解析的占位表达式**，JSON 本身不插值；不支持此语法时，用 Host 的私有请求头设置填入完整 `Bearer 原始令牌`，或采用后文 Codex / DSH 的专用机制。不要将占位字符串直接发给网关，也不要重复添加 Authorization。

保护已有配置，复制两个模板到本地私有配置：

```powershell
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath 'C:\MCP\zhenzhen-gptimagegen2.5-mcp'
$ConfigNames = @('.mcp.json', '.cherrystudiomcpproxy.mcp.json')
foreach ($Name in $ConfigNames) {
  if (Test-Path -LiteralPath $Name) { throw "配置已存在，请备份并手工合并：$Name" }
}
foreach ($Name in $ConfigNames) {
  [IO.File]::Copy((Join-Path $PWD "$Name.example"), (Join-Path $PWD $Name), $false)
}
```

只需其中一种时删去另一项。Host 不一定自动读取这些文件，应通过其导入功能或逐项填写。真实配置可含秘密，不随项目交付。

### Cherry Studio：添加、启用与代理

1. 在设置的 MCP 服务器入口添加 stdio 服务。名称 `zhenzhen-gptimagegen2-5-mcp`，command `uv`，args 按模板一逐项填写；支持 JSON 导入时可导入本地配置。无 `cwd`，无后端密钥 `env`。
2. 保存并启用，确认发现 11 个工具，将它绑定目标助手/Agent；调用 `get_model_guide` 检查模型建议和 `key_present`。若 Key 不存在，回后端项目编辑 `.env` 并重启服务。
3. 需要代理时，在兼容版本启用 API Gateway / MCP Proxy，取得完整网关令牌及该服务实际路由 ID。后端先保持可用，再验证代理；当前安装的 GUI 入口名称、版本能力与实际代理连接未在本轮实测。
4. 消费代理的 Host 添加 HTTP/Streamable HTTP 服务，填写实际 URL，按该 Host 机制设置一个 Authorization，保存、启用并绑定助手，再检查工具与免费调用。仅开启网关不代表消费方已配置完成。

### Codex：config.toml

用户作用域路径为 `$CODEX_HOME/config.toml`，未自定义时为 `%USERPROFILE%\.codex\config.toml`。在已有文件中合并服务表；下面命令先备份并打开，不覆盖其他设置：

```powershell
$ErrorActionPreference = 'Stop'
$CodexDir = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$ConfigPath = Join-Path $CodexDir 'config.toml'
if (!(Test-Path -LiteralPath $ConfigPath -PathType Leaf)) { throw '配置尚不存在，请先初始化 Codex 并核对实际 CODEX_HOME。' }
Copy-Item -LiteralPath $ConfigPath -Destination "$ConfigPath.$([Guid]::NewGuid().ToString('N')).bak" -ErrorAction Stop
notepad.exe $ConfigPath
```

本地 stdio：

```toml
[mcp_servers."zhenzhen-gptimagegen2-5-mcp"]
command = "uv"
args = [
  "--directory",
  "C:\\MCP\\zhenzhen-gptimagegen2.5-mcp",
  "run",
  "--no-sync",
  "python",
  "-m",
  "zhenzhen_image_mcp"
]
startup_timeout_sec = 30
tool_timeout_sec = 600
```

消费代理：

```toml
[mcp_servers."zhenzhen-gptimagegen2-5-mcp-proxy"]
url = "http://127.0.0.1:23333/v1/mcps/<cherrystudio_mcp_proxy_server_id>/mcp"
bearer_token_env_var = "CHERRYSTUDIO_API_GATEWAY_API_KEY"
startup_timeout_sec = 30
tool_timeout_sec = 600
```

HTTP 表不设置 `command/args/cwd/env`。`bearer_token_env_var` 填变量名；变量值是完整原始网关令牌，由 Codex 添加一次 `Bearer `。当前 shell 安全输入后从同一 shell 启动 Codex，避免 GUI 父进程没有继承变量：

```powershell
$GatewayKey = Read-Host '输入完整网关令牌（不含 Bearer 前缀）' -MaskInput
if ([string]::IsNullOrWhiteSpace($GatewayKey)) { throw '网关令牌不能为空。' }
$env:CHERRYSTUDIO_API_GATEWAY_API_KEY = $GatewayKey
Remove-Variable GatewayKey
codex
```

保存后重新加载 MCP 或重启实际 Host，会话中用 MCP 列表 / `/mcp`（若版本支持）检查启用状态、11 个工具与权限，再调用 `get_model_guide`。桌面 GUI 若不能从该 shell 继承，应使用该版本明确支持的私有认证设置；不默认写用户级全局变量。

**环境兼容方案（非默认）：**只有刻意不在项目 `.env` 定义密钥字段时，才需要给 stdio 表追加 `env_vars`。先检查第 1 节优先级；有效进程值先于用户级值，空值或非法值不回退。以下是同一服务表的可选字段片段，不是额外服务器：

```toml
env_vars = [
  "ZHENZHEN_GPTIMAGEGEN_API_KEY",
  "ZHENZHEN_GPTIMAGEGEN_BASE_URL",
  "ZHENZHEN_GPTIMAGEGEN_OUTPUT_DIR",
  "ZHENZHEN_GPTIMAGEGEN_TIMEOUT"
]
```

临时输入父进程业务变量的 PowerShell 命令如下；不要用它试图覆盖空值/损坏的 `.env`，也不要擅自删除已有用户级值：

```powershell
$ApiKey = Read-Host '输入后端 API Key（环境兼容模式）' -MaskInput
if ([string]::IsNullOrWhiteSpace($ApiKey)) { throw 'API Key 不能为空。' }
$env:ZHENZHEN_GPTIMAGEGEN_API_KEY = $ApiKey
Remove-Variable ApiKey
# 可选非秘密设置；不需要时省略：
$env:ZHENZHEN_GPTIMAGEGEN_OUTPUT_DIR = 'C:\MCP\zhenzhen-images'
$env:ZHENZHEN_GPTIMAGEGEN_TIMEOUT = '180'
codex
```

2026-10-15 隔离测试中，原生 Codex `0.162.0-alpha.17.2` 把 `env:VAR` 作为字面值传入子进程，`env_vars` 才成功转发假值。因此不要用 `[mcp_servers.*.env]` 中的 `"env:VAR"` 或 `${VAR}` 当作原生 Codex 通用变量语法。字段依据见 [Codex 配置参考](https://learn.chatgpt.com/docs/config-file/config-reference)；不同 Host 的引用语法不能互相套用。

### Claude Code / Claude-3p：先打开配置，再合并

先核对两个配置位置，同时备份并打开已经存在的文件。缺失时先初始化对应客户端，不创建空文件覆盖它的初始化流程。只使用一种客户端时可删去另一项：

```powershell
$ErrorActionPreference = 'Stop'
$ClaudeConfigs = @(
  (Join-Path $env:USERPROFILE '.claude.json')
  (Join-Path $env:LOCALAPPDATA 'Claude-3p\claude_desktop_config.json')
)
foreach ($ConfigFile in $ClaudeConfigs) {
  if (!(Test-Path -LiteralPath $ConfigFile -PathType Leaf)) {
    Write-Warning "配置不存在，请先初始化对应客户端并核对目录：$ConfigFile"
    continue
  }
  Copy-Item -LiteralPath $ConfigFile -Destination "$ConfigFile.$([Guid]::NewGuid().ToString('N')).bak" -ErrorAction Stop
  notepad.exe $ConfigFile
}
```

Claude Code 用户作用域 `.claude.json` 中合并下面完整配置对象的 `mcpServers` 项，保留其他键；使用项目作用域时通过 Claude Code 对应流程管理 `.mcp.json`，不要混淆作用域：

```json
{
  "mcpServers": {
    "zhenzhen-gptimagegen2-5-mcp": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "--directory",
        "C:\\MCP\\zhenzhen-gptimagegen2.5-mcp",
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

保存后重启 Claude Code，运行 `claude mcp list` 或会话 `/mcp` 检查服务，按客户端要求批准 MCP 工具权限，在目标会话调用 `get_model_guide`。CLI 用户作用域注册见后面的三种 Shell。

**Claude-3p：待核实。**已提供规范要求的配置路径和快捷打开步骤，但本项目没有该客户端当前版本的 schema 与连接证据，不能保证它接受 Claude Code 的 `type` 字段或代理语法。此项暂不列为已支持配置，不复制真实用户配置、不虚构另一份 JSON；接入前先核对该客户端文档，再补充验证。

### DSH：desktop / web 两个 profile

按新指南，App 使用 `desktop`，原生 DSH 使用 `web`；默认路径分别为：

- `%USERPROFILE%\.dsh\profiles\desktop\cordis.patch.yml`
- `%USERPROFILE%\.dsh\profiles\web\cordis.patch.yml`

设置 `DSH_HOME` 时以该目录为根。历史 Multica 若仍使用自定义 `multica` profile，其补丁在 `%USERPROFILE%\.dsh\profiles\multica\cordis.patch.yml`；请按实际启动 profile 修改路径，不自动迁移、重命名或同时加载。两种默认 profile 的备份与打开命令如下，仅使用一个时删去另一项：

```powershell
$ErrorActionPreference = 'Stop'
$DshDir = if ($env:DSH_HOME) { $env:DSH_HOME } else { Join-Path $env:USERPROFILE '.dsh' }
$ProfileFiles = @(
  (Join-Path $DshDir 'profiles\desktop\cordis.patch.yml')
  (Join-Path $DshDir 'profiles\web\cordis.patch.yml')
)
foreach ($ProfileFile in $ProfileFiles) {
  if (!(Test-Path -LiteralPath $ProfileFile -PathType Leaf)) { throw "找不到 profile 补丁，请核对 DSH_HOME 和实际 profile：$ProfileFile" }
}
foreach ($ProfileFile in $ProfileFiles) {
  $BackupFile = "$ProfileFile.$([Guid]::NewGuid().ToString('N')).bak"
  Copy-Item -LiteralPath $ProfileFile -Destination $BackupFile -ErrorAction Stop
  notepad.exe $ProfileFile
}
```

本地 stdio profile 的完整补丁实例：

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
          - 'C:\MCP\zhenzhen-gptimagegen2.5-mcp'
          - run
          - --no-sync
          - python
          - -m
          - zhenzhen_image_mcp
        toolCallTimeoutMs: 600000
        failOnStartupError: true
```

消费代理 Host 的完整补丁实例：

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

`id` 是唯一插件实例标识；`name` 是桥接包标识；`serverName` 是 Agent 可见命名空间，按已核对 schema 使用 `[A-Za-z0-9_-]{1,32}`。DSH 代理别名为 29 字符；通用代理全名超过 32 字符，不能直接照搬。DSH 使用 `streamable-http`，通用 JSON 使用 `streamableHTTP`；它们不是可交换字段值。`!!js` 由 DSH 解释，普通 YAML 不会执行，也不能用字符串 `${VAR}` 替代它。

两类 profile 的操作步骤同等适用：

1. 备份并打开实际使用的 profile。内容是 `[]` 时整体替换为所选补丁；已有 patch 列表时合并一个 `insert` 项或向既有 insert 列表加入唯一实例，保留其他插件，不在 `[]` 后直接追加 YAML。不编辑共享 bundle。
2. stdio 模式先在后端完成安装与 `.env` 配置；代理模式先确认 Cherry Studio 后端和网关可用，替换 URL 真实 ID，并向将启动 DSH 的父进程设置原始网关令牌。HTTP 配置不含后端 `command/args/env`。
3. 保存后重新激活该 App profile 或退出重启对应 DSH。CLI 使用 `dsh --profile desktop` / `dsh --profile web`；旧自定义 profile 以实际值为准。额外 `--patch` 只对那次启动有效，不能与 profile 重复装入同一实例。
4. 检查插件日志和可用工具，应发现 11 个工具且没有 `create_response`。本地命名空间例 `mcp__zhenzhen-gptimagegen2-5-mcp__get_model_guide`，代理例 `mcp__zhenzhen-gptimagegen2-5-proxy__get_model_guide`，以实际发现名称为准。
5. 在目标 Agent 预设中允许这些工具，调用免费指南确认链路，再按授权执行业务。DSH Tools 可用不代表 Prompt/Resource 被桥接；超时 600000 毫秒也不改变云端任务状态。

若确需 DSH 的后端环境兼容模式，在 stdio 的 `config` 内增加下列片段，父进程按前面的掩码命令输入业务变量后从该 shell 启动 DSH。默认 `.env` 路径不需要此段；它同样不能覆盖损坏文件；有效进程值优先于用户级值：

```yaml
env:
  ZHENZHEN_GPTIMAGEGEN_API_KEY: !!js process.env.ZHENZHEN_GPTIMAGEGEN_API_KEY
```

### CLI 添加：PowerShell 7、Bash、Zsh

以下使用前述历史核对版本的参数，CLI 升级后先查 `--help`。Codex 用消费代理、Claude Code 用 user 作用域 stdio、DSH 加载已保存的 profile，覆盖三个适用 CLI × 三种 Shell。只注册不会证明连接成功；检查服务列表、允许工具并调用 `get_model_guide` 才完成免费链路检查。本轮未实际运行九种组合，也未修改用户 Host 配置。

先按各 Host 小节备份配置，示例拒绝重复注册同名服务。PowerShell 使用 Windows 绝对路径；Bash/Zsh 中 `C:/MCP/...` 仅适用于能访问该路径的 Windows shell，Linux/macOS 应改为那台机器已初始化的绝对项目目录。Bash 使用 `read -p`，Zsh 使用 `read '变量?提示'`；秘密只通过当前进程环境转发。CLI 是可选 Host 入口，不是后端运行依赖。

#### Codex CLI × PowerShell 7

代理必须已启用；按提示输入含真实服务器 ID 的完整 URL，并通过当前进程网关变量认证，不把真实密钥存入命令参数。

```powershell
$ErrorActionPreference = 'Stop'
Get-Command codex -ErrorAction Stop | Out-Null
$ProxyUrl = Read-Host '输入实际 MCP Proxy 完整 URL（包含服务器 ID）'
if ([string]::IsNullOrWhiteSpace($ProxyUrl)) { throw 'URL 不能为空。' }
$GatewayKey = Read-Host '完整 cs-sk- 网关密钥' -MaskInput
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
read -r -s -p '完整 cs-sk- 网关密钥: ' GatewayKey
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
read -r -s 'GatewayKey?完整 cs-sk- 网关密钥: '
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
$ProjectDir = 'C:\MCP\zhenzhen-gptimagegen2.5-mcp'
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
ProjectDir='C:/MCP/zhenzhen-gptimagegen2.5-mcp'
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
ProjectDir='C:/MCP/zhenzhen-gptimagegen2.5-mcp'
[[ -f "$ProjectDir/.env" ]] || { printf '%s\n' '请先配置 .env'; exit 1; }
if claude mcp get 'zhenzhen-gptimagegen2-5-mcp' >/dev/null 2>&1; then
  printf '%s\n' '服务已存在，请修改配置文件。'; exit 1
fi
claude mcp add --scope user --transport stdio 'zhenzhen-gptimagegen2-5-mcp' -- uv --directory "$ProjectDir" run --no-sync python -m zhenzhen_image_mcp || exit 1
claude
```

#### DSH CLI × PowerShell 7

先保存所选 profile 的 stdio 或代理补丁；App 的 Profile 改为 `desktop`，示例使用原生 `web`。

```powershell
$ErrorActionPreference = 'Stop'
Get-Command dsh -ErrorAction Stop | Out-Null
$Profile = 'web'
$Mode = Read-Host '已保存的 profile 模式：stdio 或 proxy'
if ($Mode -eq 'stdio') {
  Get-Command uv -ErrorAction Stop | Out-Null
  if (!(Test-Path -LiteralPath 'C:\MCP\zhenzhen-gptimagegen2.5-mcp\.env' -PathType Leaf)) { throw '请先配置项目 .env。' }
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
ProjectDir='C:/MCP/zhenzhen-gptimagegen2.5-mcp'
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
ProjectDir='C:/MCP/zhenzhen-gptimagegen2.5-mcp'
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

日常启动与配置模板一致，复用已安装环境：

```powershell
uv --directory 'C:\MCP\zhenzhen-gptimagegen2.5-mcp' run --no-sync python -m zhenzhen_image_mcp
```

stdio 等待 Host 输入时没有欢迎输出属正常；手工启动后用 Ctrl+C 结束，实际可用性用第 3 节脚本判断。stdout 只写 MCP 协议，日志/异常走 stderr，不向 stdout 插入调试文本。图像输出目录以工具返回的绝对路径为准。

更新前先停用 MCP，确认所有使用该项目的子进程退出并备份当前版本与私有配置；保留 `.env` 及 ACL。使用过批量工具时，还须私有备份并保留整个 `.runtime` 检查点目录，不在数据库活动时复制，不通过删除它重置任务。新版本应来自实际仓库已通过 CI 的 Release，不在启动时自动拉代码。命令拒绝有源码修改的工作区，不执行 reset/clean、强制覆盖或自动 stash；旧版 ZIP 用户先按手册迁移到独立 clone，不覆盖原安装。

```powershell
$ErrorActionPreference = 'Stop'
$ProjectDir = 'C:\MCP\zhenzhen-gptimagegen2.5-mcp'
Set-Location -LiteralPath $ProjectDir
$Changes = @(git status --porcelain)
if ($LASTEXITCODE -ne 0 -or $Changes.Count) { throw '不是干净的 Git 安装，请先检查并保留本地修改。' }
$OldSha = git rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw '无法记录原版本。' }
Write-Host "回滚提交：$OldSha"
$ReleaseTag = Read-Host '输入已通过 CI 的目标发布标签'
$ExpectedSha = Read-Host '输入该版本发布记录中的完整提交 SHA'
if ($ReleaseTag -notmatch '^v\d+\.\d+\.\d+$' -or $ExpectedSha -notmatch '^[a-fA-F0-9]{40}$') { throw '版本或 SHA 格式不正确。' }
git fetch origin --tags
if ($LASTEXITCODE -ne 0) { throw '获取标签失败。' }
$TargetSha = git rev-parse "$ReleaseTag^{commit}"
if ($LASTEXITCODE -ne 0 -or $TargetSha -ne $ExpectedSha) { throw '标签提交与发布记录不符。' }
git switch --detach $TargetSha
if ($LASTEXITCODE -ne 0) { throw '切换版本失败，保留错误信息。' }
uv sync --locked --no-dev
if ($LASTEXITCODE -ne 0) { throw '更新依赖失败，停止启动。' }
pwsh -NoProfile -File '.\scripts\smoke-test.ps1'
if ($LASTEXITCODE -ne 0) { throw '升级后协议检查失败，先回滚再启用服务。' }
```

固定发布版本处于 detached HEAD 属正常。通过后重新启用 Host、刷新工具缓存。回滚时停止服务，输入之前记录的完整旧 SHA，执行 `git switch --detach 旧SHA`，再 `uv sync --locked --no-dev` 和协议检查；保留原 `.env`、ACL、图片及任务元数据，不覆盖私有文件。新增必需字段只手工合并。修改 `.env` 也须重启实际 MCP 子进程，默认不承诺热加载。

若 uv 输出 `Built zhenzhen-image @ file:///.../Temp/zhenzhen-member-verify-.../project`，这通常是打包器在临时目录执行安装验证；不能仅凭该行断言日常安装目录错误。正常成员 `uv --directory ...` 应定位成员项目。打包临时目录按脚本上下文清理，uv 共享缓存可能保留包；不要因此删除整个用户 Temp 或开发 `.venv`。缓存访问被拒绝时先查当前运行账号、目录权限和 `UV_CACHE_DIR`，需要时选该账号可写的专用缓存，不默认管理员启动。

## 6. 文件清单与交付

### GitHub 源码、运行入口与本地生成物

实际仓库为 `https://github.com/tsyecommercialdesigner-cloud/zhenzhen-gptimagegen2.5-mcp`，运行入口为 `python -m zhenzhen_image_mcp`，元数据版本为 0.3.0。发布流程核对标签与元数据一致、目标提交属于默认分支且通过该分支 push CI，再构建、验证并生成发布草稿。核对草稿中的标签、完整 SHA、默认分支 CI、安装证据及 SHA256SUMS 后公开；成员只安装已公开的发布版本。

仓库维护 `src/`、元数据与锁、`.python-version`、空 `.env.example`、模板、README/MANUAL、`tests/`、`scripts/`、开发规范/契约以及 `.github/workflows/`。新模块分别负责分组契约（contracts）、供应商 JSON/SSE（provider）、任务响应与元数据（tasks）、工作流编排（api）。`.venv/`、`dist/`、缓存、测试报告和私有配置由安装/验证生成，不随源码跟踪。

本地与 CI 的共用检查入口为 `uv run --no-sync python scripts/check.py --build --audit`；报告写入 `.runtime/reports/`。按 Windows 用户范围，PR 与 push CI 仅使用 `windows-latest`，保留全部格式/lint/类型、秘密、文档、测试、构建、依赖、独立安装和协议检查。受控 Release 同样在 Windows 运行，只从默认分支手动触发，核对既有版本标签、元数据、同提交成功的 push CI，并重新构建/安装验证后生成带 SHA256SUMS 和证据的 **draft Release**。发布前还需维护者配置真实 ruleset/必需评审和 release 环境审批，再审阅草稿并批准公开。CI 运行成功不等于远端合并/发布门禁已配置。

### 可选 ZIP

沿用显式白名单作可选交付，当前共 23 个运行/初始化文件；GitHub clone 不受这个运行子集限制：

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
- `src/zhenzhen_image_mcp/provider.py`
- `src/zhenzhen_image_mcp/server.py`
- `src/zhenzhen_image_mcp/smoke.py`
- `src/zhenzhen_image_mcp/tasks.py`
<!-- MEMBER_FILES_END -->

开发者有明确 ZIP 需求时，从项目根运行：

```powershell
pwsh -NoProfile -File '.\scripts\package-user.ps1'
if ($LASTEXITCODE -ne 0) { throw '打包或独立安装验证失败。' }
```

只验证、不保留 ZIP：

```powershell
pwsh -NoProfile -File '.\scripts\package-user.ps1' -VerifyOnly
if ($LASTEXITCODE -ne 0) { throw '成员安装验证失败。' }
```

输出为 `output/zhenzhen-gptimagegen2.5-mcp-0.3.0-user.zip`，内部只有 `zhenzhen-gptimagegen2.5-mcp/` 顶层目录。脚本先构建 wheel/sdist，审计白名单及秘密禁入，再在独立临时目录和空缓存中解压、联网锁定安装、执行 stdio/IPv6 回归，成功后才保留包；已有同名包拒绝覆盖。本轮只验证临时归档，不额外交付 ZIP。0.1.x 的发行包名/平铺布局不再适用。

收到该结构的 ZIP 后，直接解压到父目录，不预建项目目录：

```powershell
$ErrorActionPreference = 'Stop'
$ArchivePath = Read-Host '输入可选成员 ZIP 的完整文件路径（包含 .zip）'
if (!(Test-Path -LiteralPath $ArchivePath -PathType Leaf)) { throw 'ZIP 文件不存在。' }
$ProjectDir = 'C:\MCP\zhenzhen-gptimagegen2.5-mcp'
if (Test-Path -LiteralPath $ProjectDir) { throw '安装目录已存在，请保留私有配置并按升级流程处理。' }
Expand-Archive -LiteralPath $ArchivePath -DestinationPath 'C:\MCP' -ErrorAction Stop
if (!(Test-Path -LiteralPath (Join-Path $ProjectDir 'pyproject.toml'))) { throw 'ZIP 结构错误。' }
Set-Location -LiteralPath $ProjectDir
uv sync --locked --no-dev
if ($LASTEXITCODE -ne 0) { throw '锁定安装失败，停止启动。' }
```

仅使用实际维护者已验证、提供校验值的包。真实 `.env`、秘密备份、私有 Host 配置、依赖、缓存、开发规范/测试不入 ZIP；升级时不清空安装目录，也不覆盖成员 `.env`。新文件布局与保存私有配置/ACL 的场景由打包测试覆盖。

## 7. 资源清单

当前发现 **8 Tools、1 Prompt、1 Resource、0 Resource templates**。以下工具参数来自发现快照；业务约束还在第 8、9 节说明。JSON 示例是工具 arguments，使用前替换明确标出的本地路径、结果 URL 和 task_id；它们不会自行执行。

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

POST generations?async=true 提交收费异步绘图，立即返回 task_id。必须继续查询才能自动落盘。

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

POST edits?async=true 提交收费异步编辑，以 image[] 上传；返回 task_id，之后查询并落盘。

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

一次并发提交1–10项收费异步生成/编辑，默认并发3。收到任务编号即返回，不等待成图。同一(checkpointer,thread_id,task_id)及参数复用记录，参数冲突在提交前拒绝；不确定提交永不自动重发。

| 参数 | 类型 | 必需 | 默认 | 约束/说明 |
|---|---|---|---|---|
| `checkpointer` | string | 是 | `—` | 稳定的本地检查点命名空间/会话键，1–128字符。  |
| `thread_id` | string | 是 | `—` | 稳定的本地检查点命名空间/会话键，1–128字符。  |
| `tasks` | array[BatchImageTask] | 是 | `—` |  minItems=1; maxItems=10 |
| `max_concurrency` | integer | 否 | `3` |  minimum=1; maximum=10 |

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
  "max_concurrency": 3,
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
| `poll_interval` | number | 否 | `5` |  minimum=1; maximum=60 |
| `output_dir` | string / null | 否 | `null` | 可选绝对输出目录；默认配置目录。异步任务查询默认沿用提交目录。  |

调用工具时的 arguments 示例（路径、URL 和任务 ID 替换为实际值）：

```json
{
  "task_id": "替换为提交返回的真实任务ID",
  "timeout_seconds": 60,
  "poll_interval": 5
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
| `get_image_task` | `task_id`、`status`、`progress`、`fail_reason`、`response`；FAILURE 返回 isError 和脱敏原因；可用时保留 usage/cost（单位未确认）；SUCCESS 且 save=true 时追加保存字段。 |
| `wait_image_task` | 查询返回结构；本地等待超时时追加 `wait_timed_out=true`、`next_tool`、`note`，不取消云端任务。 |
| `download_image` | `path`、`mime_type`、`bytes`、`sha256`、`reused`。 |

`files[]` 每项为 `index`、`path`（绝对路径）、`mime_type`、`bytes`、`sha256`、`reused`。`save_status` 为 `saved/partial/failed/no_images`；`no_images` 表示响应中未找到可保存的图片，应检查供应商结果。`download_errors[]` 含 `index`、可用时的 `url`、脱敏 `error`。不要把 `SUCCESS` 或 `COMPLETED` 当作文件保存成功。参数/HTTP/协议错误由 MCP 返回工具错误；不把错误伪装成图片结果。

提示 `image_workflow`：必填字符串参数 `request`，无默认值，返回一个包含模型建议和操作顺序的用户消息模板。示例客户端调用 `get_prompt("image_workflow", {"request": "保持人物脸部不变，给人物加眼镜"})`。模板不执行任务。

资源 `zhenzhen://models`：无参数，MIME `application/json`，返回模型数组和选型建议。示例 `read_resource("zhenzhen://models")`。无动态资源模板；不开放任意本地文件读取资源。

## 8. 功能说明

### 选择模型与准备输入

`gpt-image-2.5-sunburst` 适合对编辑精度要求极高的场景；`gpt-image-2.5-flare` 适合追求速度的高质量生成。供应商称 Flare 是其目前生成高质量图片最快的模型，两者接受文本和图片输入；这是用户提供的供应商建议，未做速度/质量对比实测。每次显式传 `model`，Agent 应说明选择。

图片输入接受 MCP 所在机器的绝对路径、公开 HTTP(S) URL 或 Base64 data URL。Generations 将参考图序列化为 JSON `image` 数组，Edits 多图通过重复 `image[]` multipart 字段上传。图片仅支持 PNG/JPEG/WebP，每张最多 50 MiB，1–16 张，总输入上限 100 MiB；公开 URL 下载逐跳校验。

`size` 可选，省略即不发送；允许 `auto` 或自定义 `WIDTHxHEIGHT`，边长为 16 倍数，最大边长 3840，比例不超过 3:1，总像素 655360–8294400。例如 `2048x1152`、`3840x2160`、`2160x3840`。`quality` 可选 `auto/low/medium/high`。逆向不发送 `n`、`response_format` 或 mask；官转扩展按下节声明并遵守端点约束。不能将尺寸可填写推断为供应商一定有对应模型权限。

### 分组声明 format def

```text
group: "reverse" | "official" = "reverse"
official_options: OfficialOptions | null = null
```

这两个字段是四个生成/编辑工具的顶层 arguments。省略 group 即为逆向；要使用官转，必须显式传 **`"group": "official"`**。`official_options` 是对象，不能写成 JSON 字符串，不能放在 prompt 内当作声明。即使只传空对象，未声明官转也会拒绝。不会从模型、提示词、API Key、环境变量或报错推断/切换分组。

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

顶层 quality 在逆向仅 auto/low/medium/high，官转另允许 xhigh/max。字段与范围来自 [OpenAI Images 参考](https://developers.openai.com/api/reference/resources/images/methods/edit)、锁定 SDK 和供应商说明；官方能力不等于供应商已实测支持。未知字段/不合法组合在本地失败，供应商拒绝也不自动换组或重提。用户已确认 Generations 没有 mask 格式示例，因此仅 edits 工具支持 multipart mask；JSON generations 不猜测二进制格式。SSE 属于 Images，不恢复 Responses。

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
2. 调用 `wait_image_task`，默认等待 60 秒、间隔 5 秒；范围分别为 1–300 秒和 1–60 秒。或稍后用 `get_image_task` 只查一次。
3. `NOT_START` 为排队、`IN_PROGRESS` 为处理中，均继续查询；`FAILURE` 返回带 task_id 和脱敏原因的 MCP 工具错误；`SUCCESS` 且 `save=true` 时自动保存。成功状态不等于文件已落盘，要核对 `save_status`。
4. `wait_timed_out=true` 只表示本次本地等待结束，保留 task_id 继续查；不会取消云端任务。关闭 Host 后没有独立后台轮询服务，云端可能继续运行，重新打开后续查原任务。

```json
{
  "task_id": "替换为原提交返回的真实任务ID",
  "timeout_seconds": 60,
  "poll_interval": 5
}
```

提交目录元数据保存在默认输出目录 `.tasks/<task_id>.json`，包含 version/output_dir/group，不保存提示词或 Key。查询默认沿用提交时的 `output_dir`，显式参数可覆盖；换机器或默认输出目录后可显式指定目标。元数据保存失败不重提任务，返回 warning 和 task_id。

只读 GET 遇到网络中断、超时或 HTTP 408/429/500/502/503/504，每轮最多尝试 3 次，间隔 1、2 秒；其他 HTTP 错误、未知状态或格式错误不自动重试。尝试与间隔受单轮请求及 `wait_image_task` 总预算约束。重试耗尽返回带 task_id 的脱敏工具错误，继续查询原任务；成功结果直接落盘，不额外再查一次。保存有独立下载时限，不保证整个工具耗时只等于轮询预算。

### 批量异步：一轮工具调用提交最多 10 项

详情页多图规划使用 `submit_image_batch`，可以混合文生图和图像编辑。每项是独立的供应商异步任务；默认并发 3，`max_concurrency` 可设 1–10。工具等待这一轮的提交响应后返回，不等待上游成图，也不自动轮询或下载。上传参考图及等待提交确认仍需时间；不同批次的并发数可以叠加，没有账号全局配额控制。

身份的 format def：

```text
checkpointer: string            # 稳定的检查点命名空间，例如 product-detail-pages
thread_id: string               # 稳定的会话/规划键，例如 blue-bag-20261020
tasks[].task_id: string          # Agent 首次提交前指定，例如 page_01；同一线程内唯一
unique_key = (checkpointer, thread_id, task_id)
provider_task_id: string | null  # 供应商返回的另一个编号，不能与逻辑 task_id 混用
```

`checkpointer` 是命名空间字符串，本版内部使用 SQLite，不需要安装 LangGraph 或传入 saver 对象。命名空间和会话键为 1–128 字符，首位字母/数字，其余可用字母、数字、下划线、点、冒号或连字符；`task_id` 仅用 1–128 个字母、数字、下划线或连字符。同一已授权任务的重试必须保留这三个键，不能每次随机生成新键。

先规划稳定任务键，再一次调用 `submit_image_batch`。下面展示两项；同一数组可扩展至 10 项，`operation` 省略时为 `generate`。默认逆向，使用官转时在对应项显式写 `group="official"` 和 `official_options`。

```json
{
  "checkpointer": "product-detail-pages",
  "thread_id": "blue-bag-20261020",
  "max_concurrency": 3,
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

整批先预检，最多 10 项、每线程最多 1000 条记录，参考图与 mask 合计最多 128 MiB；预检不产生收费 POST，但可能下载参考 URL 和探测输出目录。SQLite 在 POST 前原子记录提交权，同一项目的多个 MCP 进程也只能有一次提交尝试。供应商未给出幂等键契约，无法保证网络故障后“恰好一次成功”；本版保守保留不确定状态，可能冻结实际未发出的任务。若提交后的数据库写入失败，返回 warning，并尽量保留已知 provider_task_id，供 `get_image_task` 直接查询。

数据库固定在实际项目的 `.runtime/checkpoints.sqlite3`，例如 `C:\MCP\zhenzhen-gptimagegen2.5-mcp\.runtime\checkpoints.sqlite3`，不随 Host 工作目录或输出目录变化。保存身份、请求指纹、分组、目录、状态、供应商编号和时间，不保存提示词、原图、mask 或 Key。默认不自动清理；更新需保留整个 `.runtime`，先停止所有使用该项目的 MCP 进程，再在私有位置备份整个目录。删除、恢复旧备份、重装到另一目录或换一组身份键都会失去相应防重历史；多机器之间没有分布式协调，不要借此自动重提。

原有 `generate_image`、`edit_image`、`submit_image_generation`、`submit_image_edit` 保持原行为，没有这套提交防重保证。只有一项也可以使用 `submit_image_batch` 获得检查点保护。回滚旧版后保留新数据库，旧工具须凭 provider_task_id 查询，不要按逻辑任务键重新提交。开发契约和验收标识见 [异步批量方案](docs/ASYNC-BATCH-PLAN.md)。

### 下载与恢复

同步/异步成功都处理 URL 或 Base64 图片，返回绝对文件路径。图片校验后按 SHA-256 命名，先写临时文件，再以不覆盖方式发布；重复查询相同内容复用文件。`download_image` 可对已有公开结果 URL 单独补下载，不发送后端 Authorization。

部分下载失败保留其他成功文件。URL 仍有效时用 `download_image`；异步结果可用原 task_id 再查。同步 Base64 结果若保存失败且无 URL，本版不持久化原始响应，不能保证恢复；先修复目录，禁止为恢复而自动重新付费。

## 9. 注意事项

| 边界 | 实际行为与操作要求 |
|---|---|
| 费用 / 幂等 | 生成、编辑及异步提交会产生费用；SDK `max_retries=0`。批量入口按稳定三元组持久化防重，不确定状态不自动重发；原有单项工具没有提交防重保证。保留检查点和供应商编号 |
| 取消 | 没有云端取消工具；停止等待、关闭 Host 或 Ctrl+C 不保证云端任务取消或退款 |
| 文件权限 | 输入可读取运行账号权限内的绝对文件，输出可指定绝对目录；当前无项目根沙箱或服务端目录白名单，不应向不可信远程用户开放该账号全部文件能力 |
| 下载网络 | 拒绝非公开目标并逐跳验证重定向；校验真实图像类型/大小。下载专用客户端不带业务 Authorization、不继承系统代理；受限网络可能下载失败 |
| 并发 / 限额 | 单次图片数量与字节数有界，未提供跨工具全局并发/速率配额；Host 和网关按账户与实际负载限制调用 |
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
| 解压后多套一层目录 | 默认 clone 自动生成项目目录；可选 0.3.0 ZIP 自带项目顶层目录，直接解压到父目录，不再按带版本 ZIP 文件名套目录 |
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
| Host 协议/SDK 不兼容 | SDK 版本与协议版本分开核对；本轮证明的是 stdio legacy 2025-11-25 路径，Tools-only 桥接不适用完整能力检查 |
| stdio 没反应 / 协议解析失败 | 无输出可正常；用检查脚本判定。stdout 只保留协议，调试日志改 stderr，核对实际模块入口 |
| 是否支持 Responses / 流式模型响应 | 当前不提供，已按用户要求移除；用 Images 编辑与异步工具，不能凭供应商通用文档恢复已删除能力 |
| GitHub CI/发布是否已生效 | PR #1 已合入 main 并通过合入提交的 Windows CI；各版本的发布运行及证据见实际 Release。发布前已配置 main 的 PR/CI 检查、v* 标签不可修改/删除及 release 环境维护者审批（仅 main）；单维护者无需独立 approving review，不能视为独立同行评审。当前设置以 GitHub 为准 |
| 默认逆向却传官转参数报错 | 在工具 arguments 顶层显式写 group=official，参数放 official_options；同时核对 Key 后台分组。服务不会自动换组 |
