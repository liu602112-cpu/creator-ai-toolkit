# 飞影接口参考

核验日期：2026-09-22。实际执行前读取当前工具 schema，使用直接 API 时核对官方文档，避免将此摘要当作永不变化的契约。

- API V2 文档：https://api.hifly.cc/hifly.html
- MCP 接入说明：https://hifly.cc/study/vocation/all/codex-hifly-mcp.html
- MCP 地址：https://hifly.cc/mcp
- REST 基址：`https://hfw-api.hifly.cc`
- 认证：`Authorization: Bearer <HIFLY_API_TOKEN>`。HTTP 200 仍需检查业务 `code`；401 是认证失败。

## 音频驱动视频

`POST /api/v2/hifly/video/create_by_audio`

| 字段 | 用途 |
| --- | --- |
| `file_id` 或 `audio_url` | 二选一，驱动音频。文档支持 mp3、m4a、wav 等，100 MB 以内，5 秒至 30 分钟。 |
| `video_file_id` 或 `avatar` | 至少一个，用户形象视频上传后的 ID 或已存在的数字人 ID。优先使用用户此次指定来源。 |
| `title` | 作品名称，不超过 20 个字。 |
| `video_start_msec` | 可选，开始驱动的视频毫秒位置，用户未指定时省略。 |
| `aigc_flag` | 默认为 0，跟随账户设置；不要为了消除标识自动设置为 2。 |

返回 `task_id` 和 `request_id`，只代表任务已提交。此接口会消耗积分。

API 还支持创建持久数字人 `POST /api/v2/hifly/avatar/create_by_video`；视频规范为 mp4/mov、H.264、500 MB 内、360p 至 4K、5 秒至 30 分钟。不要误以为每次声音驱动必须先创建持久数字人；具体上传与生成限制按对应接口核验。

## MCP 使用边界

先读取已连接服务器的工具列表，再读取所需参数。账户查询可用 `get_account_capabilities`；任务状态用当前暴露的查询工具。不要假定 MCP 包含 REST 的全部功能；例如 REST 文档提供自己的声音及数字人列表，而之前连接的 MCP 工具未必提供这些列表。

上传工具返回 `upload_url`、`content_type`、`file_id` 后，还要实际完成 PUT；不能把申请上传成功当作素材已经上传。严格按返回 content_type 发送，上传请求不附带 API Token。

## 授权兼容情况

本机曾遇到 OAuth 动态注册回调拒绝 `invalid_redirect_uri`；后来通过官方支持的 Bearer 环境变量方式成功完成账户查询。当前任务不应为了使用服务而重新折腾 OAuth；先验证现有认证。历史套餐和积分不作为当前余额依据。
