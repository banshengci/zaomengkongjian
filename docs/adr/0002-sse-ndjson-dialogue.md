# ADR-0002：对话通道采用 SSE，模型侧沿用 NDJSON

## 状态

已接受

## 背景

造梦主实现的多角色对话使用「模型侧 NDJSON → 服务端投影 → 客户端 SSE」链路，事件为 `status / delta / reset / complete / error`。造梦空间剧场需要流式打字与断线恢复。

## 决策

1. 对外剧场 API 使用 **SSE**（`text/event-stream`），事件名与造梦对齐。
2. LLM 调用侧继续使用 **NDJSON 多角色协议**（每行 `{speaker, message, inner_thought?}`），不声明 `response_format=json_object`。
3. 用 `operation_id` 标识一次用户发送，用于幂等与断线重放；`complete` 返回轻量 session + 本轮 `appended_transcript`。
4. 提供非流式 `POST .../turns` 作为降级路径（代理不支持 SSE 时）。

## 后果

- 正面：与造梦协议同构，便于桥接；SSE 在 HTTP/1.1 与常见代理下更稳。
- 负面：SSE 只支持服务器→客户端单向；用户输入仍走普通 POST。
- 备选（已否决）：WebSocket —— 断线重放、代理兼容、与造梦对齐成本更高。
