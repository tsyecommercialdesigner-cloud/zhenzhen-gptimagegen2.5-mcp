# 项目收尾记录（2026-10-21）

适用项目：zhenzhen-gptimagegen2.5-mcp。此记录汇总开发、发布、D 盘迁移、Host 验收、手册重写和分支同步后的状态；不是新版本发布说明。当前基线为 PR #7 合入后的 dfacf02，本地及远端 main/dev 已快进对齐。本快照在提交前编写；下表 CI 对应已提交的基线，不包含本文后续交付改动，其提交、PR 及合入后的 CI 以对应 GitHub 记录为准。历史业务验收与本轮只读复核分别说明。

## 1. 当前版本与安装

| 对象 | 当前状态 |
|---|---|
| 最新正式 Release | [v0.3.1](https://github.com/tsyecommercialdesigner-cloud/zhenzhen-gptimagegen2.5-mcp/releases/tag/v0.3.1)，非草稿、非预发布 |
| 发布提交 | `f5011efcb0a9bd4353c106811d71645e02ff74fe` |
| main/dev 基线提交 | `dfacf02e943585bc671643a16021935256b25b4c`，PR #7 合并提交 |
| 包/模块版本 | 开发源码及本机安装均为 0.3.1 |
| 本机运行安装 | `D:\MCP\zhenzhen-gptimagegen2.5-mcp`，固定 v0.3.1 发布提交，独立 `.venv` |
| 运行入口 | Codex 通过 uv 的 `--directory` 指向 D 盘，`run --no-sync python -m zhenzhen_image_mcp`，stdio |
| 凭据策略 | 实际项目根 `.env` → 进程环境 → Windows 用户环境；本记录不包含凭据值或私有配置内容 |
| 任务数据库 | D 盘安装根目录 `.runtime/checkpoints.sqlite3`，保留历史验收任务及后续任务数据；本轮不提交或查询供应商任务 |
| 图片输出 | 沿用 `%USERPROFILE%\Pictures\ZhenzhenImage`，与安装盘符分开；历史图片保持原位置 |

从发布提交到当前基线，main 的差异仅涉及文档：PR #5 的三份验收/任务文档、PR #6 的本收尾记录，以及 PR #7 的 MANUAL.md、README.md 和手册规范重写；没有业务源码差异。D 盘安装停留在已发布提交是预期状态，不需要为文档合并重新安装或发布。

## 2. 分支与工作区

本轮通过本地 ref、远端跟踪 ref 及 `git ls-remote --heads origin` 核对：

| 引用 | 完整 SHA |
|---|---|
| 本地 main / origin/main | `dfacf02e943585bc671643a16021935256b25b4c` |
| 本地 dev / origin/dev | `dfacf02e943585bc671643a16021935256b25b4c` |
| GitHub main / dev | `dfacf02e943585bc671643a16021935256b25b4c` |

- 当前工作分支为 dev；本地 main 快进至 origin/main，再将 dev 快进至 main 并正常推送；没有强推或新增合并提交。本地、远端均只保留 main/dev。
- PR #5 分支和两个 release 准备分支已删除；四个同指向旧根提交 c4206bd 的本地分支也按用户授权舍弃，未另建归档。
- 私有 `issues/`、`outputs/` 保持未跟踪；分支同步前后摘要校验通过，D 盘安装配置、运行数据、输出及安装 Git SHA 保留检查通过。未执行 git clean、工作区硬重置或私有目录删除。
- 快照编写阶段仅更新本收尾记录，当时未提交、暂存或推送；上表引用描述该阶段的基线。后续按用户授权通过 dev 和 PR 交付，不将交付后的分支指针冒充快照时状态。

## 3. Windows CI 与合并结果

| 阶段 | 目标提交 | 运行 | 结果 |
|---|---|---|---|
| PR #5 最新 head | `5a4bf696221ffc860f59175dd7c4f9685da730a2` | [39547734722](https://github.com/tsyecommercialdesigner-cloud/zhenzhen-gptimagegen2.5-mcp/actions/runs/39547734722) | success |
| PR #5 分支 push | 同上 | [39547730558](https://github.com/tsyecommercialdesigner-cloud/zhenzhen-gptimagegen2.5-mcp/actions/runs/39547730558) | success |
| PR #5 合入 main 后 push | `5edfb1ba1fdc79cd578bd0e0a2be2c4db8a9e5bf` | [39548512082](https://github.com/tsyecommercialdesigner-cloud/zhenzhen-gptimagegen2.5-mcp/actions/runs/39548512082) | success |
| PR #6 合入 main 后 push | `56cf700ff247c74dc4f6f8b9a1c6000b8e7dce12` | [39550941044](https://github.com/tsyecommercialdesigner-cloud/zhenzhen-gptimagegen2.5-mcp/actions/runs/39550941044) | success |
| PR #7 head / dev push | `b045778399087dc36b520bd5301228269efa073f` | [39564654025](https://github.com/tsyecommercialdesigner-cloud/zhenzhen-gptimagegen2.5-mcp/actions/runs/39564654025) | success |
| PR #7 pull_request | 同上 | [39564903338](https://github.com/tsyecommercialdesigner-cloud/zhenzhen-gptimagegen2.5-mcp/actions/runs/39564903338) | success |
| PR #7 合入 main 后 push | `dfacf02e943585bc671643a16021935256b25b4c` | [39565318458](https://github.com/tsyecommercialdesigner-cloud/zhenzhen-gptimagegen2.5-mcp/actions/runs/39565318458) | success |
| dev 快进同步后 push | 同上 | [39566367303](https://github.com/tsyecommercialdesigner-cloud/zhenzhen-gptimagegen2.5-mcp/actions/runs/39566367303) | success |

支持范围为 Windows。quality (windows-latest) 全部步骤成功：锁定安装、格式/lint/类型、秘密和文档检查、88 项测试、真实 stdio 发现、构建及依赖审计、全新运行安装、PowerShell 文档语法检查和报告上传。PR #7 日志确认发现 11 Tools / 1 Prompt / 1 Resource，paid_calls=0。本轮重新只读查询确认当前 main/dev 对应运行均 completed/success，不用旧 PR 的结果代替合入或快进后的检查。

[PR #7](https://github.com/tsyecommercialdesigner-cloud/zhenzhen-gptimagegen2.5-mcp/pull/7) 已审查并合并，未发现阻塞问题；审查为当前 Agent 执行，不冒称独立维护者批准。仓库审批数量为 0 的单维护者流程不等于已有独立审批。本轮未更改任何门禁。

### 手册重写与交付检查

- PR #7 仅修改 MANUAL.md、README.md、docs/MANUAL-WRITING-GUIDE.md；固定 v0.3.1 标签及提交的安装步骤、默认 D 盘路径、凭据和任务数据保留策略，并补全 DSH web、desktop、multica 三类 profile 的备份、配置和启用说明。
- 重写时通过 21 段 JSON、3 段 TOML、3 段 YAML 检查，23 段 PowerShell 语法检查、秘密扫描及 4 项打包测试。
- 三 profile 快捷命令在临时目录模拟验证：正常情形完成三份备份，缺失任一 profile 时在备份或打开前停止。模拟未打开真实编辑器或修改用户 profile。
- stdio 与 HTTP 代理两份 DSH 示例通过本机 0.2.1-rc.2 客户端配置 schema；这不等于 Desktop、Multica 或其他 Host 已完成实际连接复验。
- 当前基线仍为 0.3.1；没有新建、修改或重复发布 Release，也没有新增收费接口调用。

### GitHub Actions 用量边界

2026-10-21 只读核实仓库为 PUBLIC，工作流使用标准 `windows-latest`。根据 [GitHub 官方 runner 文档](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)，公开仓库标准 runner 的运行分钟免费且不限量；当前 CI 不受私有仓库按套餐提供的月度分钟额度限制。

账户级账单 API 因现有授权缺少 user scope 未能返回用量，因此未确认账户整体套餐、其他私有仓库剩余额度或总账单。本轮没有扩展登录权限或调整预算。大型 runner、存储和其他计费资源须按各自规则核对，不能把公开仓库计算分钟免费扩大为所有资源免费；详见 [GitHub Actions 计费说明](https://docs.github.com/en/billing/concepts/product-billing/github-actions)。

## 4. 本机 MCP 验收

### 免费连接与发现

- 锁定运行依赖安装及独立 SDK stdio 检查通过，发现 11 Tools / 1 Prompt / 1 Resource。
- Codex 桌面内置 app-server 0.163.0-alpha.10.2 的独立临时会话：connected，serverInfo.version=0.3.1。
- 用户重启后，实际当前 Codex 会话已发现全部 11 工具并成功调用 get_model_guide；升级期间 Transport closed 已恢复。
- 默认 reverse；官转须工具参数显式 `group=official`，扩展字段位于 official_options；声明不改变供应商后台分组。create_response 已按用户要求移除。
- 上述为已完成的验收，本收尾轮次未重新调用 Host 工具或供应商接口。历史收尾轮次只读核实过安装 Git SHA、发行包/模块版本及 SQLite 任务记录；本轮未重测 Host 或业务接口，沿用历史验收并核对保留检查结果。

### 已授权的两图真实验收

模型 gpt-image-2.5-flare，reverse，max_concurrency=2；一次 submit_image_batch，约 9.354 秒收到两个独立编号后返回，未等待全部成图。查询沿用固定 checkpointer、thread_id 和 task_id；本汇总不重复列出本机任务身份或供应商编号。

| 验收图 | 结果 | 实际尺寸 |
|---|---|---|
| 蓝色抽绳垃圾袋 | SUCCESS / saved | 1254×1254 |
| 蓝色卷筒垃圾袋 | NOT_START → SUCCESS / saved | 1024×1024 |

两项均请求 1024×1024；文件存在、PNG 解码和 SHA-256 校验通过，无下载错误。查询只访问原任务，无重复收费提交；供应商 cost 各 0.15、合计 0.30，响应未标明币种。本地并发实现由 22 项批量协议测试佐证；未抓取生产请求时间线，不宣称实测供应商同时执行两项。

两图摘要、四项历史同步/异步生成及编辑结果见 [D-DRIVE-ACCEPTANCE.md](D-DRIVE-ACCEPTANCE.md)。历史结果复核不冒充 v0.3.1 本轮同步/编辑重测；受控十图协议测试不等于真实收费十图验收。

### 迁移与清理

旧 C 盘安装、两个 D 盘旧版本备份和两份 Codex 迁移配置备份已按授权删除。旧 C 盘删除使用 UAC 管理员权限，没有改变 ACL；当前安装、配置、数据库及图片保留并通过清理后复验。删除分支只清理 Git 引用，没有删除运行目录或数据库。旧备份已不存在；未来更新前应重新备份当前用户配置和任务数据。

## 5. 尚未处理的问题与验证缺口

| 类别 | 当前状态 | 后续建议 |
|---|---|---|
| 供应商尺寸偏差 | 已确认：请求 1024×1024，首图实际 1254×1254；服务原样保存 | 向供应商核实 reverse 组 size 语义；确定需求后再决定是否提示偏差，不默认裁图或重新收费 |
| GitHub Actions 运行时警告 | CI 成功，但固定版本 Actions 声明 Node 20，由 runner 强制使用 Node 24 | 单独维护 PR 核对新版 Actions SHA 并回归，不在收尾时浮动升级 |
| 其他 Host 与 Shell | 新版 Cherry Studio、DSH/代理、Claude 等未完成全面真实复验；Bash/Zsh 示例执行范围仍有限 | 按实际使用 Host 分别验收；不将静态配置检查当作连接成功 |
| 官转高级参数、Images SSE | 有契约和受控测试，本次未做真实供应商复验 | 有业务需要时另行授权并按固定任务记录验证 |
| 真实大批量与限流 | 历史真实验收两项，本轮未新增；十项真实成图、供应商并发上限及账号全局配额未确认 | 先取得供应商限制；没有全局并发控制的保证，不盲目扩大收费测试 |
| 计费币种 | 响应 cost 无币种 | 以供应商账单/后台说明核对，不把 0.30 直接标作人民币或美元 |

历史问题不再作为未修复源码缺陷：NOT_START 已兼容并真实验证；带方括号 IPv6 的 NO_PROXY 规范化及 InvalidURL 错误反馈已实现；Codex env:VAR 不展开的配置问题已更正并记录 env_vars 兼容方式。DSH 原始 issue 的现场结果与手册修正不代表最新版完整链路已再次通过，保留此验证边界。

Responses 移除、Windows-only、仅本地检查点幂等、SUBMITTING/SUBMISSION_UNCERTAIN 不自动重提属于已确认的产品/安全边界，不是待恢复功能。没有供应商原子幂等保证，也不宣称跨机器恰好一次成功。

## 6. 证据位置与本次交付边界

- 可共享资料：[D-DRIVE-ACCEPTANCE.md](D-DRIVE-ACCEPTANCE.md)、[VALIDATION.md](VALIDATION.md)、[ASYNC-BATCH-PLAN.md](ASYNC-BATCH-PLAN.md)，以及上表 GitHub Actions 链接。
- 本机忽略目录 `.runtime/reports/`：local-v031-mcp-discovery.json、local-v031-host-result.json、d-drive-live-batch-acceptance.json、d-drive-cleanup-result.json、PR-5-MERGE-CI.md、old-branches-discard-dev-fast-forward.json，以及 manual-pr-completion.json、manual-pr-preservation-after.json、dev-fast-forward-completion.json、branch-sync-preservation-after.json；它们是执行证据，不保证随 clone 取得。
- 私有 issues、原始 outputs、真实配置、图片与任务库不复制进收尾文档或 Git。旧记录中“未发布”“待重启”等描述保留其历史轮次含义，以本记录说明的当前状态为准。
- 快照编写阶段仅更新本收尾记录，执行本地文档检查及 GitHub 只读查询；交付阶段按用户另行授权提交 dev、推送并创建 PR，通过 Windows CI 后合并，再复核合入提交 CI。交付结果以该 PR 和 Actions 记录为准。未新增收费调用、未新建或修改 Release/版本标签，未改变 D 盘安装和任务数据。
