# 验证记录

验证日期：2026-09-11。开发分支：`feature/stdio-mcp`。目录原先没有 Git 仓库，已本地初始化；没有配置远程仓库，不执行推送或伪造 PR。

## 历史验证（移除 Responses 前）

- 锁定依赖在线安装：CPython 3.12.14，uv 0.12.9，MCP SDK 2.2.0，官方 OpenAI SDK 3.13.0；完整版本见 `uv.lock`。
- `uv run --no-sync python -m unittest discover -s tests -v`：27 项通过。HTTP 流量使用 MockTransport，不调用真实供应商。
- `pwsh -NoProfile -File './scripts/smoke-test.ps1' -InventoryPath './docs/mcp-inventory.json'`：真实子进程 stdio 初始化及能力发现通过，9 Tools / 1 Prompt / 1 Resource / 0 Resource templates；资源读取、提示获取、本地建议工具调用和无效模型拒绝通过。
- `pwsh -NoProfile -File './scripts/package-user.ps1' -VerifyOnly`：临时 ZIP 16 个显式成员文件与清单、手册一致；dotfile 保留；开发树之外解压，空专用 uv 缓存在线安装成功，从不同工作目录使用新环境运行真实 MCP 握手成功。临时文件清理，不保留第二份成员交付 ZIP。
- 模拟业务测试覆盖：两种 Images POST 路由、`async=true`、官方 SDK 实際序列化 `image[]`、自定义尺寸、逆向分组字段限制、任务重启后目录恢复、三种任务状态、轮询超时可续查、普通 Responses、SSE 完成/失败/断流、Base64 落盘、重复查询复用、部分下载失败、跳转逐跳检查、不向下载主机发送 Authorization、收费 POST 的 HTTP 429 不重试、API 重定向不跟随、用户级密钥覆盖旧进程值。
- 打包负面检查覆盖重复、穿越、绝对、秘密/开发路径、缺失运行文件；文档 JSON 全部可解析且采用两空格格式。

## 初始验证边界（历史记录）

- 未提交收费绘图、编辑、Responses 任务，不能将模拟测试视为供应商业务验证。
- Flare / Sunburst 的实际分组权限、生成质量、延迟和计费未实测。
- Responses 对这两个图片模型、逆向分组、图片内容块、tools 和 previous_response_id 的支持按用户明确要求假定支持，尚未供应商确认。
- Cherry Studio / MCP Proxy / Codex GUI 版本、真实路由与端到端密钥读取尚未实测；手册有配置映射和代理握手命令，未声称连接通过。
- Windows 用户变量读取优先级由模拟测试验证；开发 stdio 握手不是实际 Host 链路验证。

本项目不包含用户真实密钥。收费 POST 不自动重试；只读任务 GET 对暂时性故障最多尝试 3 次；发生结果不明确的超时，不能自动重复付费提交。

## DeepSeek Harness 反馈后的修复验证

- 通过 MCP SDK `Client(mcp, mode="legacy")` 执行 JSON-RPC 工具调用；预期异常转换为脱敏 ToolError，客户端可见错误类别/HTTP 状态及原 task_id，而非只有通用错误。未知异常仍由 SDK 处理。
- 新增 `tests/test_protocol.py` 的 7 项协议测试：503 → IN_PROGRESS → SUCCESS 并校验落盘 PNG；连接失败 → 429 → SUCCESS；三次查询失败后的错误与续查提示；401 不重试；重试期间等待超时保留 task_id；收费提交和普通/流式 Responses 不重试；错误中的密钥、Bearer 及 URL 脱敏。
- 成功轮询复用已取得的原始结果落盘，不再发起额外 GET。只读重试与退避受查询总预算及 wait 总预算约束，图片保存仍使用独立下载时限。
- 本次新增测试全部使用模拟供应商 HTTP，无收费调用；不能替代实际 DeepSeek Harness 与供应商链路复测。现有成员安装目录及运行中的 Host 未修改，需部署修复后的成员文件并重启服务才能生效。

## 当前版本：统一使用 Images 接口

- 按用户明确要求移除 `create_response`、Responses 请求实现和 SSE 解析；移除对应测试及工具参数示例。保留供应商原始文档作为历史参考。
- 当前 `uv run --no-sync python -m unittest discover -s tests -v`：26 项通过，其中 9 项 MCP 协议测试。覆盖同步/异步 Sunburst 编辑的实际 multipart `image[]` 序列化、正确的 `/v1/images/edits` 路由与 async 参数、查询及保存；验证 Responses 不再被发现，并保留暂时性查询故障恢复与收费 POST 不重试测试。
- 真实子进程 stdio 握手通过：8 Tools / 1 Prompt / 1 Resource / 0 Resource templates。README、MANUAL、AGENTS、烟雾测试及 discovery 清单同步更新。
- 此前使用成员 MCP 查询已有真实任务获得 SUCCESS；使用 Sunburst 测试 Responses 普通/流式请求，在用户声明切换到逆向、官转、官方分组的对应测试中返回 HTTP 404。并非每种分组都测试了两种模式；分组归属由用户确认，未通过后台 API 独立读取。404 不能证明供应商所有模型均不支持 Responses。
- 本次代码修改没有发起收费绘图或编辑，不声称已实测精细编辑质量。完成代码修改时尚未部署；后续成员更新验证见下节。

## 成员更新后的复验

- 用户更新后，成员目录的 api.py、server.py、smoke.py、pyproject.toml、uv.lock 与开发版逐文件 SHA-256 一致。
- 成员环境真实 stdio 握手及工具调用通过：8 Tools / 1 Prompt / 1 Resource；create_response 不再被发现，密钥存在检查通过，非法 task_id 返回明确工具错误。
- 使用成员环境与成员源码运行 9 项协议测试，全部通过；包含同步/异步编辑、查询暂时失败后恢复成功并落盘、查询超时与收费 POST 不重试。
- README.md、MANUAL.md 及两个 JSON 配置模板在成员目录与开发目录的 SHA-256 一致。DSH 的两份 profile 路径和快捷编辑命令仍保留在 MANUAL 中。
- 本轮没有收费供应商请求，未直接验证正在运行的 DSH 界面或工具缓存，也未实测编辑质量。

## NOT_START 排队状态兼容修复

- 依据真实 Sunburst 异步编辑和 Flare 异步文生图返回的 NOT_START / 0%，增加该状态为合法未完成状态。get_image_task 保留原始状态，wait_image_task 对 NOT_START 和 IN_PROGRESS 继续轮询；仍拒绝未知状态。
- 新增 4 项 MCP 协议测试：排队查询且 data=null 时不保存；NOT_START → IN_PROGRESS → SUCCESS 保存；排队超时保留 task_id/状态并续查成功；排队转 FAILURE 返回失败原因且不保存。
- 当前全套 30 项测试通过（含 13 项协议测试），真实 stdio 握手发现 8 Tools / 1 Prompt / 1 Resource。工具说明、MANUAL 和 discovery 清单已同步。
- 修复验证使用模拟上游响应，未额外发起收费请求。修改在开发项目中，成员安装需更新后重启 Host。

## 2026-10-12：0.1.1 IPv6 NO_PROXY 修复

- 读取问题记录后，在锁定 httpx2 2.12.0 / OpenAI 3.13.0 中独立复现 `[::1]` 导致 SDK 构造抛出 InvalidURL，未发送供应商请求。
- 开发项目新增 normalize_no_proxy / sanitize_proxy_env，在业务 SDK 及代理握手客户端构造前调用。单独 `[::1]` 转为 `::1`，带端口条目转为 `all://[::1]:8080`；保留代理地址和证书环境变量，未修改 Host profile 或用户级环境变量。
- 两类 httpx InvalidURL 纳入脱敏错误边界；收费请求仍不自动重试。未知非法配置保留为错误，不静默删除。
- 6 项新增测试通过；全套 36 项测试通过。包含真实 SDK 原始异常复现、绕过/代理传输选择、端口限定、大小写变量以及真实 SDK 构造配合模拟 HTTP 的 MCP 提交/查询。
- 开发项目真实 stdio 握手通过，能力仍为 8 Tools / 1 Prompt / 1 Resource。版本统一更新为 0.1.1；uv.lock 只更新本项目版本，第三方锁定依赖未升级。README、MANUAL、AGENTS 和问题记录同步更新。
- 发布脚本增加从解压后的成员环境构造 SDK 的回归验证，注入 DSH 风格 NO_PROXY，并确认环回直连、供应商域名走代理。此验证不访问云端、不使用真实凭据。
- 本次不发起收费请求；真实 DSH/代理网络环境和供应商业务仍需部署后复验。

- 成员发布实际通过：显式清单 16 个文件逐字节与开发文件一致；空专用缓存在线安装、独立工作目录 stdio 握手及 DSH 风格 IPv6 SDK 构造验证通过。临时验证目录已清理。
- 发布包：`output/zhenzhen-image-0.1.1-user.zip`；SHA-256：`c4a0c983d0caf782e73619c6f38ecb5c6cf5a4215179a59b16fe661e5cb6ea5a`。成员安装目录未自动更新。

## 2026-10-14：0.1.2 本地 .env 配置

- 业务密钥固定读取模块所属项目根目录的 .env，优先级为本地字段 → Windows 用户变量 → 进程变量。仅字段缺失时回退；空值/重复/不可读/非 UTF-8/格式错误/插值/超限配置均返回脱敏错误。每次调用重新读取，不导出到 os.environ。
- 新增 python-dotenv 1.2.1 为锁定运行依赖，其他第三方依赖未升级。成员仅新增空 .env.example，真实文件及备份仍禁止发布。
- 10 项新增配置/协议测试通过，全套 46 项通过；真实 stdio 握手通过，仍为 8 Tools / 1 Prompt / 1 Resource。
- README 和 MANUAL 更新本地配置创建/备份/打开/验证/升级保留及环境变量兼容说明。MANUAL-WRITING-GUIDE 校正其他项目字段与密钥方案；AGENTS 改为引用该开发规范。指南不进入成员包。
- 对新规范补齐 Codex、Claude Code 和 DSH 的九种 CLI/Shell 组合，并核对本机 CLI help；PowerShell 20 段语法解析通过。Bash/Zsh 执行、真实 GUI/Host 连接未验证，不修改用户的实际 Host 配置。
- 验证不会创建实际密钥文件或提交收费请求；成员安装尚未自动更新。本次仅验证临时交付，不额外保留 ZIP。

- 干净成员验证实际通过：17 个显式成员文件（新增空 .env.example），空缓存在线安装 38 个运行包；解压后的独立目录 stdio 握手、本地 .env 测试值读取及 IPv6 代理绕过回归通过。临时目录已清理，不保留成员 ZIP。
- 发布审计同时拒绝 .env/备份及含非空或重复凭证字段的 .env.example；对应负面测试通过。文档 JSON 和两段 TOML 可解析，九种 CLI/Shell 组合已列出。实际 DSH/Cherry Studio/Claude/Codex 链路及 Bash/Zsh 未在本轮实测。

## 2026-10-15：Codex / DSH 手册配置问题

- 阅读两份新增 issue；仅修改 MANUAL、写作规范及 issue/验证记录，无源码或真实用户配置改动，也无发布包重建。
- 本机 PATH 中 npm Codex 因安装目录访问错误不能运行；使用桌面随附原生 Codex 0.162.0-alpha.17.2，在临时 CODEX_HOME 配置一个假 MCP，调用 app-server 的 initialize 和 mcpServerStatus/list。env:VAR 被原样传递，env_vars 成功传递假业务 Key 和 BASE_URL，用户已确认采用 env_vars。临时配置/进程已清理，不使用真实凭据、不发起模型请求。
- DSH stdio 完整 YAML 显式传入业务环境变量；HTTP 代理 YAML 无业务 env。补齐设置用户/进程变量、存在性检查、GUI/服务重启、本地 .env 优先级及缺失密钥与握手区别。规范同步更新。
- 两段 TOML 和两段 DSH YAML 可解析、命名空间和字段校验通过；DSH JS 表达式用假值求值通过；20 段 PowerShell 示例语法检查通过；现有 2 项文档/打包审计测试通过。PyYAML 6.0.3 仅用于临时静态检查，未加入运行依赖或改变锁文件。
- 真实 DSH/GUI/代理链路未实测；注册和静态校验不等于供应商业务通过。

## 2026-10-20：按新版约定重写使用手册

- 完整读取新版 AGENTS.md 与 docs/MANUAL-WRITING-GUIDE.md，按十节结构重写 MANUAL，并同步 README、两个 JSON 模板和文档生成器。默认由 MCP 加载项目 .env；Codex env_vars / DSH 显式环境仅作为兼容例外，保留既有 env:VAR 字面值实测限制。
- 配置服务标识统一点号转连字符；成员目录、发行包名、版本和模块保持原映射。DSH 采用 desktop/web 默认 profile，记录历史 multica 自定义路径，补齐备份打开、patch 合并、激活、发现和 Agent 权限步骤；DSH 代理使用 29 字符别名。
- 六项配置清单覆盖本地/代理 JSON、Codex TOML、Claude Code / Claude-3p、DSH YAML 和九种 CLI/Shell 示例。Claude-3p 缺少当前 schema/连接证据，明确标为待核实，未虚构已支持配置。
- 静态检查通过：13 段严格 JSON 且为两空格格式、3 段 TOML、3 段 YAML（!!js 只作为标量解析，未执行）、21 段 PowerShell AST。两个交付模板与手册逐字一致；17 个成员文件的白名单审计与现有两项文档/打包测试通过。git diff --check 对本轮相关文件通过。
- 使用真实子进程及 SDK legacy 客户端完成免费 stdio 协议检查，协商协议 2025-11-25、serverInfo.version=0.1.2，发现 8 Tools / 1 Prompt / 1 Resource / 0 Resource templates。重新发现的完整清单与 docs/mcp-inventory.json 相同；不从 SDK 2.2.0 推导协议版本。
- 用无秘密临时 ZIP 实际执行手册中的解压部分，平铺和带唯一项目顶层目录的两种布局均落到预期路径；重复执行均拒绝已有项目目录。没有执行其中的依赖安装、真实 .env 编辑或用户 Host 配置步骤。
- 与新规范尚有实现差异：当前凭据回退为 .env → Windows 用户级 → 进程；当前打包名使用发行包名、ZIP 平铺、没有单独发布前构建及保留 .env/ACL 的自动升级验收。手册明确记录实际状态和目标，未通过改写规范或宣称修复掩盖差异。当前任意绝对路径访问与无全局配额的安全边界也如实说明。
- 此轮为文档与配置模板调整，未修改业务源码、依赖或实际用户配置，未发布成员 ZIP、未提交收费请求；未重跑全部业务回归，未验证 GUI/代理、Claude-3p、Bash/Zsh 执行或 MCP 2026-07-28 请求级元数据模式。

## 2026-10-20：0.2.0 分组感知 Images 重构

### 已完成的实现与契约

- 用户确认同时支持逆向/官转，默认逆向、官转必须显式声明。四个收费工具采用顶层 `group: reverse|official = reverse`，扩展字段放 `official_options` 对象；声明只控制本地校验，不更改供应商后台 Key 分组，不发送 group/official_options 到上游，不自动换组。
- 新 contracts.py 定义严格参数与输出契约；provider.py 通过官方 OpenAI SDK 处理有界 JSON / Images SSE；tasks.py 规范化 task_id、状态与重启元数据；api.py 负责编排。保留原有八个工具名及常用参数，全部声明 outputSchema，并兼容旧 Host 的文本 JSON。
- 在 MCPServer 公共 list_tools/call_tool 边界校验实际发现的完整 JSON schema，拒绝未知顶层字段、字符串形式的对象/数组和非法参数，避免 SDK 的方便转换或忽略字段导致意外收费。
- 官转支持 n/background/output_format/output_compression/input_fidelity/moderation/response_format/user/safety_identifier/stream/partial_images，编辑另支持 multipart mask；未知字段、透明 jpeg、压缩参数无对应格式、async+stream 等非法组合在 POST 前拒绝。用户进一步确认没有 Generations mask 示例，故仅 edits 上传 multipart mask；非二进制 input_fidelity 按兼容声明透传，实际模型权限不作实测保证。
- 兼容顶层 task_id 和旧 data 包装；冲突任务 ID 报错且不重提。NOT_START、空 b64_json、嵌套结果、usage/cost、恢复查询和目录元数据保留。供应商 FAILURE 或空完成结果返回 MCP isError；POST/SSE 错误和取消不自动重提。Images SSE 只保存最终完成图，不把预览或 SSE 写到 stdio stdout。
- 凭据优先级修正为 `.env → 进程 → Windows 用户级`，已定义但为空/非法不回退。源码/editable 固定模块根，项目 venv 的 wheel 固定 sys.prefix 父目录并验证本项目 pyproject；不搜索 Host CWD，不支持无项目根的全局安装。

### 本地验证证据

- 基线 46 项通过；重构后 **65 项 unittest/协议/交付测试通过**。新增覆盖两类分组、未声明拒绝、实际 JSON/multipart 序列化、mask、严格输入、输出 schema/structuredContent、异步任务分组记录、SSE 分块/完成/失败、空结果、wheel 根目录、ZIP 顶层和私有 `.env`/Windows ACL 保留。
- `uv run --no-sync python scripts/check.py --build --audit` 共用检查通过：Ruff format/check、mypy（全部 10 个源码模块）、项目秘密与空模板审计、文档 JSON/TOML/YAML、65 项测试及 XML 报告、真实子进程 stdio、wheel/sdist 构建与条目审计、锁定运行依赖联网审计。发现快照与当前协议发现逐项比较，不允许静态文档漂移。
- 文档静态检查：16 段严格两空格 JSON、3 段 TOML、3 段 YAML；!!js 不执行。PowerShell 脚本实际解析 22 段示例，不执行修改用户配置的命令。两份模板与 MANUAL 逐字一致，真实发现仍为 8 Tools / 1 Prompt / 1 Resource / 0 resource templates，legacy stdio 协议路径与锁定 SDK 保持兼容。
- 构建显式限定 source distribution 输入，另行审计 wheel/sdist 的路径、运行入口与秘密禁入；不携带 outputs、缓存、真实 .env 或运行数据。构建时 uv 对位于源码内缓存的通用警告不作为验收结果，实际归档条目检查已通过。
- 初次联网审计发现 PyJWT 2.13.0 和 python-dotenv 1.2.1 共 15 个公告；核对上游后仅更新为 PyJWT 2.15.0 / python-dotenv 1.2.2，未升级 MCP/OpenAI/httpx 两套 SDK。修复后的完整运行依赖审计为 0 个已知漏洞，未配置忽略项。参考 [PyJWT 公告](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-gvp8-978c-rx2q) 与 [python-dotenv 公告](https://github.com/theskumar/python-dotenv/security/advisories/GHSA-mf9w-mj56-hr94)；审计结果仅代表当次数据库覆盖。
- `uv run --no-sync python scripts/package_user.py --verify-only` 实际通过：20 个运行文件精确映射为唯一项目顶层目录，空缓存联网安装锁定运行依赖；从不同 CWD 验证 editable 和项目 venv wheel 两种布局的真实 stdio、私有 .env 假值读取及 IPv6 代理绕过。临时目录已正常清理，不保留成员 ZIP；开发 .venv 和真实配置未清理。
- 本地报告保存在忽略的 `.runtime/reports/`：final-check.log、dependency-audit.json、XML 报告、isolated-install.log。测试与检查源码、锁、模板、工作流和共享规范均保留为可提交资料；没有执行 git add/commit。

### GitHub 与真实业务边界

- 用户提供实际仓库 https://github.com/tsyecommercialdesigner-cloud/zhenzhen-gptimagegen2.5-mcp.git，已核实可访问并设置本地 origin；远端 main HEAD b629d0dd2d831219a917265564485bcf521f5895，不是本次重构提交。工作分支 refactor/group-aware-images，既有未提交修改保留。
- 新增 Windows/Linux CI 与手动受控 draft Release 工作流，Actions 使用当次核对的完整提交 SHA，权限按 job 限定；发布脚本校验目标 tag、元数据、默认分支归属和同 SHA 的成功 push CI，再生成校验值与发布证据。没有提交、推送、创建 PR、合并、打标签、运行远端 CI 或发布。真实 ruleset、评审与 release 环境审批未配置/未验证，不能把工作流文件当作已生效门禁。
- 没有发起收费生成/编辑或真实供应商查询；官转高级参数及供应商 SSE 的真实可用性未在此轮验证。未修改成员 C:\MCP 安装或用户 Host 配置；实际 GUI/DSH/代理、Bash/Zsh 执行、Claude-3p 与 MCP 2026-07-28 模式仍未验证。

## 2026-10-20：0.3.0 异步批量并发与检查点幂等

需求、身份和状态契约见 [ASYNC-BATCH-PLAN.md](ASYNC-BATCH-PLAN.md)，验收标识 B1–B8。保留上一轮和用户已有修改，本轮在 `feature/batch-async-checkpoints` 分支工作，未执行 add、commit、push、PR、合并或发布。

### 实现与使用边界

- 新增 `submit_image_batch`、`get_image_batch`、`get_batch_image_task`；一次 1–10 项生成/编辑，默认并发 3、可选 1–10。批量工具仅等待上游提交确认，不等待生成、不自动下载。并发上限按单次工具调用计算，不是账号全局配额。
- Agent 指定稳定 `(checkpointer, thread_id, task_id)` 三元组，供应商编号单独返回 `provider_task_id`。checkpointer 在本版是 SQLite 命名空间，不引入 LangGraph 依赖。每项延续默认逆向、官转显式声明和严格参数校验。
- 预检整批输入并计算规范化参数、目标目录、base URL、参考图和 mask 内容摘要；相同身份不同指纹整批拒绝并回滚新预留记录。整批图片/mask 128 MiB、每线程最多 1000 条记录。SQL 全部使用参数绑定；身份不拼接文件路径。
- 数据固定为实际项目 `.runtime/checkpoints.sqlite3`，与 CWD 和默认图片目录无关；SQLite FULL 同步，事务原子取得提交权后才允许 POST，数据库操作移到线程池，网络期间不持有事务。没有增加运行依赖。
- RESERVED 明确未开始，可原参数继续；SUBMITTING / SUBMISSION_UNCERTAIN 不按超时抢占、不自动重发。仅接收确认编号后进入 SUBMITTED。取消、异常响应、缺编号、HTTP 拒绝保守保留不确定状态；部分失败保留其他成功编号，返回 ATTENTION_REQUIRED。
- 首次全量回归暴露 gather 取消传播早于子任务数据库收尾的问题；补齐子任务取消回收和 SQLite 线程任务等待，再用人为延迟检查点写入验证工具不会提前退出。修复后全量通过，未降低断言或隐藏失败。
- 新查询沿用三次只读 GET 重试、NOT_START、原目录保存和业务 FAILURE 工具错误；查询耗尽不会丢任务编号。数据库仅保存身份、摘要、路由、目录、分组、状态、编号、固定错误和时间，不保存提示词、原图或 Key；本地空查询不创建数据库。
- 原有单项工具保持兼容，没有新增提交防重；需防重时使用批量入口，即使只有一项。没有供应商幂等契约，不能声称网络异常下保证“恰好一次成功”。本地数据库丢失、回滚或更换身份会丢失相应防重历史，多机器不进行分布式协调。

### 本地验收结果

- **87 项测试通过**：原 65 项加 22 项新批量协议/状态/进程测试。B1–B7 覆盖单次调用 10 项和并发峰值、并发/顺序重放、参数冲突整批回滚、三元组隔离、两独立进程争用提交权、非法输入、超时/取消/无编号/部分失败、数据库写入失败与损坏、参考图内容变化、查询恢复及秘密不落库。
- `uv run --no-sync python scripts/check.py --build --audit` 通过：Ruff、mypy（12 源码模块）、秘密/模板检查、文档配置解析、XML 测试、真实 stdio 子进程、发现快照逐项比较、wheel/sdist 构建和条目审计、锁定依赖审计（0 已知漏洞，无忽略项）。
- 真实 stdio legacy 协商路径发现 **11 Tools / 1 Prompt / 1 Resource / 0 templates**，paid_calls=0；全量发现及 input/outputSchema 保存到 `docs/mcp-inventory.json`。README、MANUAL、生成脚本、smoke 工具数、候选版本/锁文件和 22 文件成员白名单均同步。
- 补强可选交付覆盖测试，实际 SQLite 幂等记录与 `.env`、文件权限/Windows ACL 在解压覆盖后保持，提交权仍不可重复取得；4 项交付测试再次通过。可选归档未包含检查点、用户 .env 或其他运行数据。
- `scripts/package_user.py --verify-only` 通过：临时目录、空缓存在线锁定安装，无开发依赖；不同 CWD 下 editable 与项目 venv wheel 均发现 11 工具。成员 wheel 进一步验证 SQLite 可用、检查点根目录固定、同文件重新打开保留编号并拒绝第二次提交权；IPv6 代理绕过与测试 .env 读取维持通过。临时目录已清理，不保留 ZIP，没有清理开发环境或用户数据。
- 本轮 22 段 PowerShell 文档示例 AST 检查通过；不执行修改真实 Host 配置的命令。报告存于忽略目录 `.runtime/reports/batch-final-check.log`、`batch-tests.log`、`batch-isolated-install.log` 及 XML/审计 JSON；源码、测试和契约均可跟踪。

### 尚未验证或交付

没有调用真实供应商、没有产生绘图费用；实际并发速率限制、任务接收延迟和图片效果未验证。没有更新 `C:\MCP` 实际安装或重启用户 Host；GUI/DSH/代理联调、远端 CI、评审与发布仍未进行。0.3.0 是本地候选版本，不能作为已发布标签提供给成员。

## 2026-10-20：按用户范围采用 Windows CI 与发布验收

- 用户明确实际用户仅使用 Windows，要求 CI 只检查 Windows，提交/推送 dev、更新 PR 并确认新 CI；不合并或发布。这是支持平台范围调整，保留前述历史 Linux 失败证据，不将其记录成已经修复。
- CI 矩阵仅保留 windows-latest，质量检查名称维持 quality (windows-latest)。全部格式/lint/类型、秘密、文档、87 项测试、构建、依赖审计、独立安装、协议与 PowerShell 示例检查继续执行；未删除测试、跳过检查或添加 continue-on-error。
- 手动 Release 工作流调用同套验收脚本，因此执行环境同步为 windows-latest；手动触发、默认分支限制、release 环境、权限、标签校验和 draft Release 行为不变。本轮不触发 Release。
- 对变更前后 YAML 解析结构比较，确认 CI 只改变 OS 矩阵、Release 只改变 runner；脚本和检查步骤保持一致。本地文档 JSON/TOML/YAML、秘密检查、22 段 PowerShell AST 与差异格式检查通过。
- 之前 Windows 路径断言修复 e24decc 已在 PR CI 39411511709 和 push CI 39411505913 的 Windows 作业通过：87 项测试、独立安装与 11 工具 stdio 等检查成功。其 Ubuntu 作业失败保留为历史结果。
- README、MANUAL 和重构契约同步 Windows 支持/验收范围，并纠正候选版本已推送 dev / PR #1、尚未合并发布的状态。当前提交的远端结果以 [PR #1](https://github.com/tsyecommercialdesigner-cloud/zhenzhen-gptimagegen2.5-mcp/pull/1) 实际 Actions 结果为准；CI 通过不表示真实 Host、收费接口或发布审批已验收。


## 0.3.0 发布前复验（2026-10-21）

- 发布准备补齐 MIT 元数据、wheel/sdist 和可选成员 ZIP 的 LICENSE，校验发行物与仓库许可证逐字节一致；成员运行子集为 23 个文件。
- 发布门禁只认可目标完整 SHA 在实际默认分支上已完成且成功的 push CI；新增回归测试排除其他分支、旧 SHA、PR、进行中、失败和取消结果，不硬编码默认分支名。
- 当日审计报告原锁定 Pillow 12.3.0 和 certifi 2026.7.22 共 9 条漏洞。定向升级为 Pillow 13.0.0 和 certifi 2026.10.19，保留其余依赖版本。依据：[Pillow 13.0.0](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html)、[certifi 公告](https://github.com/advisories/GHSA-6q48-6c7w-9gw2)。升级后本地完整检查通过：88 项测试、11 工具 stdio、格式/lint/类型/秘密/文档检查、构建及发行物审计，依赖审计零已知漏洞。
- 发布使用受保护 v* 标签（禁止更新和删除）及 release 环境（限定 main，由仓库维护者审批，允许维护者审批自己的运行）。main 要求 PR、最新 quality (windows-latest) 成功、解决评审讨论、禁止强推和删除。当前为单维护者流程，GitHub 必需独立 approving reviews 数为 0；这不等于已经过另一位维护者的独立评审。
- 正式发布证据由发布工作流关联实际标签、完整提交、默认分支 CI 与发布运行，包含全新运行依赖安装及协议验收。此处本地检查不能替代该目标提交的远端 CI/CD。
- 本轮未调用收费接口，未修改用户实际 Host 配置；新版本真实 Host 联调、供应商收费接口和视觉业务验收仍未覆盖。


## 0.3.1 默认 D 盘安装发布验收（2026-10-21）

- 默认成员目录为 `D:\MCP\zhenzhen-gptimagegen2.5-mcp`，安装/启动/升级、Host 模板及开发约定按 D 盘统一；服务标识、模块名、API 契约及目录层级保持不变。新版本为 0.3.1，不修改已有发布标签或产物。
- 用户重启 MCP 后，本次实际 Codex 会话已发现全部 11 个工具，并成功调用 `get_model_guide`：返回 Flare/Sunburst、默认 reverse 及 official 显式声明说明，`isError=false`、Key 配置存在。此为已安装 0.3.0 的迁移后 Host 验收；0.3.1 的发行与安装另由目标提交 CI/CD 验证，不混称为当前 Host 已升级到 0.3.1。
- 本轮没有调用生成、编辑、异步提交、供应商查询或图片下载；Host 验收只读取本地模型说明。同步模型速度/质量与官转高级参数的真实业务效果仍未验证。
