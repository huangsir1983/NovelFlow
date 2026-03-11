# GROK对话模型API接入文档

下游只需要替换 `BASE_URL` 和 `API_KEY` 即可接入。

## 1. 接口信息

- `BASE_URL`: `https://yhgrok.xuhuanai.cn`
- 鉴权：

```http
Authorization: Bearer {API_KEY}
Content-Type: application/json
```

- 对话接口：

```http
POST /v1/chat/completions
```

## 2. 支持的对话模型

当前可用的对话模型包括：

- `grok-3`
- `grok-3-mini`
- `grok-3-thinking`
- `grok-4`
- `grok-4-mini`
- `grok-4-thinking`
- `grok-4-heavy`
- `grok-4.1-mini`
- `grok-4.1-fast`
- `grok-4.1-expert`
- `grok-4.1-thinking`
- `grok-4.20-beta`

如果只是正常文本对答，建议优先用：

- `grok-4`
- `grok-4.1-fast`
- `grok-3`

## 3. 请求格式

最常用字段只有这几个：

- `model`: 模型名
- `messages`: 对话消息数组
- `stream`: 是否流式返回，`true` 或 `false`

消息格式：

```json
[
  {
    "role": "user",
    "content": "你好，做个自我介绍"
  }
]
```

支持多轮对话，直接把历史消息一起传上来即可。

## 4. 非流式示例

```bash
curl -X POST "https://yhgrok.xuhuanai.cn/v1/chat/completions" \
  -H "Authorization: Bearer {API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "grok-4",
    "messages": [
      {
        "role": "user",
        "content": "你好，做个自我介绍"
      }
    ],
    "stream": false
  }'
```

返回格式与 OpenAI `chat.completions` 基本一致，重点读取：

- `choices[0].message.content`

## 5. 流式示例

```bash
curl -N -X POST "https://yhgrok.xuhuanai.cn/v1/chat/completions" \
  -H "Authorization: Bearer {API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "grok-4",
    "messages": [
      {
        "role": "user",
        "content": "用三句话介绍你自己"
      }
    ],
    "stream": true
  }'
```

流式返回是标准 SSE，读取：

- `choices[0].delta.content`
- 直到收到 `data: [DONE]`

## 6. 多轮对话示例

```bash
curl -X POST "https://yhgrok.xuhuanai.cn/v1/chat/completions" \
  -H "Authorization: Bearer {API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "grok-4",
    "messages": [
      {
        "role": "user",
        "content": "我叫小王"
      },
      {
        "role": "assistant",
        "content": "你好，小王。"
      },
      {
        "role": "user",
        "content": "记住我的名字，然后再说一遍"
      }
    ],
    "stream": false
  }'
```

## 7. 下游接入要点

下游只需要保证：

1. 请求地址改成 `https://yhgrok.xuhuanai.cn/v1/chat/completions`
2. 请求头带 `Authorization: Bearer {API_KEY}`
3. 请求体传 `model`、`messages`、`stream`

不要把图片、视频、工具调用混在这份文档里。这份文档只用于对话模型接入。
