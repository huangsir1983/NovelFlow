# GPT Responses API 对接文档（给下游 AI 直接接入）

> 你只需要替换 `BASE_URL` 和 `API_KEY` 即可接入。

## 1. 基础信息

- 协议：HTTP/HTTPS
- 鉴权：`Authorization: Bearer <API_KEY>`
- 内容类型：`Content-Type: application/json`
- 基础地址：`BASE_URL`（由服务方单独提供）

## 2. 可用接口

### 2.1 获取模型列表

- 方法：`GET`
- 路径：`/v1/models`

示例：

```bash
curl -s "{{BASE_URL}}/v1/models" \
  -H "Authorization: Bearer {{API_KEY}}"
```

---

### 2.2 文本对话（核心接口）

- 方法：`POST`
- 路径：`/v1/responses`

> 注意：`input` 必须是**数组**（list），不是纯字符串。

推荐请求体：

```json
{
  "model": "gpt-5.4",
  "input": [
    {
      "role": "user",
      "content": [
        { "type": "input_text", "text": "你好，请介绍一下你自己" }
      ]
    }
  ],
  "max_output_tokens": 300
}
```

示例：

```bash
curl -s "{{BASE_URL}}/v1/responses" \
  -H "Authorization: Bearer {{API_KEY}}" \
  -H "Content-Type: application/json" \
  -d '{
    "model":"gpt-5.4",
    "input":[
      {
        "role":"user",
        "content":[{"type":"input_text","text":"你好，回复一个 pong"}]
      }
    ],
    "max_output_tokens":80
  }'
```

## 3. 多轮对话（上下文）

### 3.1 推荐方式：客户端携带完整历史（强烈推荐）

每次请求都带上历史消息：

```json
{
  "model": "gpt-5.4",
  "input": [
    {
      "role": "user",
      "content": [{ "type": "input_text", "text": "记住口令 ORANGE-77" }]
    },
    {
      "role": "assistant",
      "content": [{ "type": "output_text", "text": "好的" }]
    },
    {
      "role": "user",
      "content": [{ "type": "input_text", "text": "我刚才的口令是什么？" }]
    }
  ]
}
```

### 3.2 `previous_response_id` 方式

可选支持，但不同上游实现稳定性可能不同。
为了最稳，建议优先使用 **3.1 客户端历史模式**。

## 4. 返回结果解析

返回通常包含以下字段：

- `id`: 响应 ID
- `status`: 一般为 `completed`
- `output_text` 或 `output[].content[].text`: 模型输出文本

解析建议：

1. 优先读 `output_text`
2. 若无 `output_text`，拼接 `output[].content[].text`

## 5. 常见错误与处理

- `{"error":{"type":"invalid_request_error","message":"..."}}`
  - 常见原因：`input` 不是数组
- `{"code":"INSUFFICIENT_BALANCE","message":"Insufficient account balance"}`
  - 常见原因：API Key 配额为 0、用户余额不足、或未绑定有效订阅/分组
- `{"error":{"type":"api_error","message":"Service temporarily unavailable"}}`
  - 常见原因：上游临时不可用，建议重试
- `{"error":{"type":"upstream_error","message":"Upstream request failed"}}`
  - 常见原因：上游返回 4xx/5xx，建议记录 `request_id` 并排查

重试建议：

- 仅对临时错误重试（如 `api_error` / 部分 `upstream_error`）
- 指数退避：1s -> 2s -> 4s（最多 3 次）

## 6. 给下游 AI 的实现约束（可直接复制）

你要对接一个 Responses API 网关：

1. 鉴权固定：`Authorization: Bearer {{API_KEY}}`
2. 获取模型：`GET {{BASE_URL}}/v1/models`
3. 对话接口：`POST {{BASE_URL}}/v1/responses`
4. `input` 必须是数组，元素格式为：
   - `role`: `system|user|assistant`
   - `content`: 数组，文本项使用 `{ "type": "input_text", "text": "..." }`
5. 多轮对话请采用“客户端传完整历史”模式，不依赖服务端会话记忆。
6. 解析返回时优先 `output_text`，否则拼接 `output[].content[].text`。

## 7. 不支持的路径（当前部署）

- `POST /v1/chat/completions`
  - 当前会返回：`Unsupported legacy protocol: /v1/chat/completions is not supported. Please use /v1/responses.`

本链路以 `POST /v1/responses` 为主，请按本文档接入。

## 8. 实测结果（2026-03-07）

- 测试地址：`https://yhsub.xuhuanai.cn`
- 测试接口：`GET /v1/models`、`POST /v1/responses`
- 测试结论：已打通，可正常返回 `id/status/model/output`
- 模型建议：优先传 `gpt-5.4`（`gpt5.4` 也可兼容，但建议统一为标准模型名）

## 9. 能力边界（当前账号/当前网关）

- 文本/代码：支持（`/v1/responses`）
- 图片生成：当前不支持（`POST /v1/images/generations` 返回 `404`）
- 音频接口：当前不支持（`/v1/audio/*` 返回 `404`）
