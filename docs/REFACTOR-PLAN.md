# 0.2.0：按分组校验的 Images MCP 重构

依据：2026-10-20 用户要求彻底重构，采用 docs/API-ENDPOINT.md；同时支持逆向与官转，默认逆向，官转必须显式声明。保留 Python / uv / 官方 MCP SDK / OpenAI SDK / stdio，不恢复 Responses 工具。

## 契约与验收

| 标识 | 要求 | 实现 / 验证 |
|---|---|---|
| G1 | 四个生成/编辑工具添加 `group: reverse\|official = reverse`；`group` 只做本地声明，不改变供应商账户后台分组 | contracts.py / server.py；协议负面测试 |
| G2 | 逆向仅发送 model、prompt、size、image、quality；显式官转方可使用 `official_options` | 参数白名单、严格类型和跨字段校验；模拟 HTTP 检查实际请求 |
| G3 | 官转按端点处理 n、background、output_format、output_compression、mask、input_fidelity、moderation、response_format、user、safety_identifier、stream、partial_images；未知字段拒绝 | 官方文档及锁定 SDK 接口核对；mask 仅用于编辑；供应商实际权限另验 |
| G4 | 同步 JSON、Images SSE 完成事件、异步 task_id 多种包装、NOT_START / IN_PROGRESS / SUCCESS 正确解析；空 b64 不解码 | provider.py / tasks.py / api.py；受控响应与协议测试 |
| G5 | 失败任务使用 MCP isError；查询暂时失败可恢复；收费 POST、SSE 断流、取消均不自动重提 | 现有与新增协议测试 |
| G6 | 凭据逐字段 `.env → 进程 → Windows 用户级`；空值/非法值不回退，保留成员私有文件 | config.py；更新优先级与缺失/非法来源测试 |
| G7 | 公共输出 schema 与实际结果一致；保持旧工具名及常用参数兼容，资源/提示按发现生成 | TypedDict 契约、SDK discovery / call 检查 |
| G8 | 分离验证、供应商传输、任务解析/元数据和编排；依赖不擅自升级 | 新模块 + API 兼容门面；全部回归 |
| G9 | 提供本地可复现检查、Windows CI 和 Windows 发布验收（按用户明确的平台范围）；默认 GitHub 版本安装，ZIP 可选 | scripts / workflows / README / MANUAL；本地验证，远端状态单独报告 |

## 声明 format def

```text
group := "reverse" | "official"        # omitted => "reverse"
official_options := object | null     # provided only when group == "official"
```

`group` 必须放在工具 arguments 顶层。不会从提示词、模型名、API Key 或环境变量推断。它既不发送给供应商，也不会把供应商后台逆向 Key 转成官转 Key。查询/下载沿用原任务，无须再次声明；提交元数据保存分组及目标目录，不保存密钥和提示词。

用户已补充确认供应商没有 Generations mask 示例：Generations 不实现 multipart mask，精细编辑使用 edits 的 multipart image[]/mask。input_fidelity 等非二进制官转参数按兼容声明透传；模型是否支持由供应商判定。stream=true 消费 Images SSE 并返回最终本地图片，不把 SSE 写到 MCP stdout；与异步任务提交互斥。供应商额外能力以其实际响应为准。

## 执行顺序与边界

1. 已读取新规范、新 API 文档、源码与测试，基线 46 项通过。当前重构分支 refactor/group-aware-images，保留所有既有未提交修改。
2. 写分组/输出契约与传输/任务模块，更新编排、凭据和协议测试。
3. 更新发现清单、使用手册、可复现验证、CI 和受控 Release；修正可选 ZIP 目录布局。
4. 锁定安装、格式/lint/类型、单元/协议、文档/秘密/依赖检查、构建与隔离安装验收。

用户已提供真实仓库 https://github.com/tsyecommercialdesigner-cloud/zhenzhen-gptimagegen2.5-mcp.git，并已核实可读、设置本地 origin；默认分支 main，当前远端 HEAD 为 b629d0dd2d831219a917265564485bcf521f5895（不是本次重构提交）。尚无本次发布标签或远端门禁证据。交付工作流文件与本地结果，不能虚构远端 CI 或发布状态。未经后续明确授权不提交、推送、创建 PR、合并、打标签或发布；本轮不自动发起收费业务。纯本地 stdio 的服务端部署 CD 不适用，版本发布 CD 适用。

## 收敛结果

G1–G8 本地验收通过；G9 的脚本、构建、独立安装与工作流文件已完成，远端 CI/评审/门禁/发布未执行。65 项测试、格式/lint/类型、文档/秘密检查、构建条目审计和依赖审计通过；20 文件的独立空缓存安装、editable/wheel 两种布局及 stdio 检查通过。完整命令、证据及未验证范围见 [VALIDATION.md](VALIDATION.md#2026-10-20020-分组感知-images-重构)。官转供应商实测和真实 Host 联调仍待单独验证，本轮没有收费调用。
