# v0.3.1：D 盘迁移与 Codex 会话验收

验收日期：2026-10-21。用户授权两项 Flare 异步文生图、归档历史结果、更新任务、提交推送，以及验收后清理旧安装和迁移备份。本轮不发布 Release、不合并默认分支。

## 安装与 Host

| 项目 | 结果 |
|---|---|
| 当前安装 | `D:\MCP\zhenzhen-gptimagegen2.5-mcp`，标签 `v0.3.1` |
| 完整 SHA | `f5011efcb0a9bd4353c106811d71645e02ff74fe` |
| 原安装 | C 盘 0.1.0 ZIP 安装；迁移时没有 `.env`、`.runtime` 或 `.tasks` |
| 迁移与更新 | D 盘新建虚拟环境、锁定安装；0.3.0 后升级到 0.3.1；未创建空 `.env`，原环境变量兼容凭据仍可读取 |
| 配置 | Codex stdio 指向 D 盘，其他配置保留 |
| SDK / 传输 | MCP 2.2.0、OpenAI 3.13.0，stdio；独立 SDK 检查使用 legacy 客户端路径 |
| 独立 Host | Codex 桌面内置 app-server 0.163.0-alpha.10.2，connected，serverInfo.version=0.3.1 |
| 当前会话 | 用户重启后发现全部 11 工具，`get_model_guide` 成功；升级期间的 Transport closed 已恢复 |
| 其他能力 | 独立 stdio 发现 1 Prompt、1 Resource；不等于当前会话已逐项访问 |

11 工具为：`download_image`、`edit_image`、`generate_image`、`get_batch_image_task`、`get_image_batch`、`get_image_task`、`get_model_guide`、`submit_image_batch`、`submit_image_edit`、`submit_image_generation`、`wait_image_task`。

安装迁至 D 盘不改变图片输出设置。本轮沿用 `%USERPROFILE%\Pictures\ZhenzhenImage`；检查点为 D 盘实际项目 `.runtime/checkpoints.sqlite3`，保留防重历史。

## 本轮真实异步批次

当前会话调用一次 `submit_image_batch`：`model=gpt-image-2.5-flare`、`group=reverse`、`max_concurrency=2`。两项均为 generate、size=1024x1024、无参考图，分别生成蓝色抽绳垃圾袋和三卷蓝色卷筒垃圾袋白底产品图。

- checkpointer：`codex-v031-acceptance`。
- thread_id：`d-drive-20261021`。
- 约 9.354 秒返回 ACCEPTED，两项 SUBMITTED、两个独立供应商编号，没有等待全部成图。
- 后续只用 `get_image_batch` 恢复和 `get_batch_image_task(save=true)` 查询原任务；未重放提交、换任务键或自动重新生成。工具既有只读 GET 有界重试不等于重提收费 POST。

| task_id | provider_task_id | 观察状态 | 保存 | 像素 | 字节 |
|---|---|---|---|---|---|
| flare-blue-drawstring-01 | 1b391a94c8b2463ba818c819090ce877 | SUBMITTED → SUCCESS | saved，无下载错误 | 1254×1254 | 1449175 |
| flare-blue-rolls-02 | 4c05160825b3490d95dffe6563555cf8 | SUBMITTED → NOT_START → SUCCESS | saved，无下载错误 | 1024×1024 | 1221520 |

落盘文件位于上述图片目录，文件名包含完整 SHA-256：

- `image-5c22358e0f51fb021d07a3760adf60248e711844458b47c70dc8a28aff951772.png`
- `image-b02a4d17520e4da445ffa6c847e1c568789bc1d721a289044efd358c59162157.png`

重新计算摘要与工具返回一致，Pillow 校验和解码通过，目视符合两种蓝色垃圾袋主题。第一项实际像素与请求 size 不同，记录为供应商尺寸偏差，服务保留原图，不自动改尺寸或重新收费。供应商 cost 各 0.15、合计 0.30，响应没有币种。

真实调用验证两项异步接收、查询、排队兼容、持久化恢复和自动保存。没有抓取生产请求时间线，不能仅凭耗时断言上游同时执行两项；本地在途并发上限由既有隔离协议测试测量，供应商仍可排队。10 项、默认峰值 3 的既有测试使用受控传输，不冒充真实供应商十图验收。

## 当前会话的历史验收批次

下表来自既有记录及本机结果文件。本轮仅复核历史文件与图片摘要，不重跑收费接口。原始 `outputs/` 和图片保持本地，不纳入 Git。旧四项不是新版 SQLite 批次，不补造三元组。

| 场景 | 历史结果 | 图片 SHA-256 |
|---|---|---|
| 异步参考图编辑 | 任务 `2f71f9be3b664a97b816c0834b50155c` 最终 SUCCESS/saved | dd76c4d36b3a66e9330dcdc3c93b31966c6d52ab8eb4fdf6ea3531ab660c08db |
| 同步参考图编辑 | COMPLETED/saved，历史耗时 53.62 秒 | 5d868446b73633fa529cc884bf5702ff85eaad7b1a7a38b12858440b8737f0d8 |
| Flare 异步文生图 | 任务 `eca4ed3636264d22ba07f3f3f868418a` 最终 SUCCESS/saved | 305daad072e22d53de34d09ae9841d2c6bce01a0cead86bed3300049f3366489 |
| Flare 同步蓝色垃圾袋 | COMPLETED/saved，历史耗时 30.81 秒 | b6a4ba4fc47b8484b0d3659e2f433c65d8f11c3e1288094b7a8a03784e206913 |

旧异步编辑和生成均曾暴露 NOT_START 未兼容，随后原任务查询保存成功；不能声称修复前轮询全程通过。本轮 v0.3.1 的真实 NOT_START → SUCCESS 已通过。旧同步结果不冒充本轮同步复测。

v0.3.0 迁移、v0.3.1 更新此前完成独立 SDK/Host 免费验证；原升级报告等待当前会话重启的状态现已解决。迁移与免费验证当时收费调用为 0；本轮另行获准并新增两项收费生成。

## 清理与边界

仅清理旧 `C:\MCP\zhenzhen-gptimagegen2.5-mcp`、两个 D 盘旧版本备份（before-v0.3.0-20261021-103158、before-v0.3.1-20261021-124329）和两份 Codex 迁移配置备份。删除前检查绝对路径、链接、运行进程、私有内容及当前 D 盘数据；清理回执保留于本机忽略的 `.runtime/reports/`。当前安装、检查点、全部新旧图片、开发目录和无关 MCP 不清理。

本轮不改 API、源码、依赖、版本或标签，不发布/重发任何 Release。官转参数、十项真实收费并发及其他 Host 均未在本轮复测。
