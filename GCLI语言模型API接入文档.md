# GCLI 语言模型 API 接入文档

本文档只描述 `gcli` 语言模型接口。

- 只做大语言模型
- 不做图片
- 不做视频
- 对接方式按最通用的 OpenAI Chat 接口

## 1. 基础信息

- `BASE_URL`: 你的接口地址
- `API_KEY`: 你的密钥
- 请求地址:

```http
POST {BASE_URL}/v1/chat/completions
```

## 2. 请求头

```http
Authorization: Bearer {API_KEY}
Content-Type: application/json
```

## 3. 请求体

最常用写法如下：

```json
{
  "model": "gemini-3.1-pro-preview",
  "messages": [
    {
      "role": "user",
      "content": "你好，做个自我介绍"
    }
  ],
  "stream": true
}
```

说明：

- `model`: 请求模型名
- `messages`: 正常 OpenAI Chat 格式
- `stream`: 建议传 `true`，走流式

## 4. 支持的消息格式

单轮最常见：

```json
[
  {
    "role": "user",
    "content": "帮我把这句话改写成适合 AI 绘图的英文提示词"
  }
]
```

多轮对话也支持：

```json
[
  {
    "role": "system",
    "content": "你是一个提示词优化助手"
  },
  {
    "role": "user",
    "content": "把'一只站在雨夜街头的机械狐狸'改写成英文提示词"
  }
]
```

## 5. 流式返回

当 `stream=true` 时，返回格式是标准 SSE：

```text
data: {...}

data: {...}

data: [DONE]
```

下游正常按 OpenAI 流式方式读取即可。

## 6. 示例请求

### curl

```bash
curl -N -X POST "{BASE_URL}/v1/chat/completions" \
  -H "Authorization: Bearer {API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-3.1-pro-preview",
    "messages": [
      {
        "role": "user",
        "content": "请输出一句简短的英文欢迎语"
      }
    ],
    "stream": true
  }'
```

### JavaScript

```javascript
const resp = await fetch(`${BASE_URL}/v1/chat/completions`, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${API_KEY}`,
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    model: "gemini-3.1-pro-preview",
    messages: [
      {
        role: "user",
        content: "请输出一句简短的英文欢迎语"
      }
    ],
    stream: true
  })
});
```

## 7. 可用模型

下游直接传模型名即可。

当前可用的是 `gcli` 语言模型，不要拿它请求图片或视频。

常用示例：

- `gemini-2.5-flash`
- `gemini-2.5-pro`
- `gemini-3-flash-preview`
- `gemini-3-pro-preview`
- `gemini-3.1-pro-preview`

如果你那边要做模型下拉，可以额外调用：

```http
GET {BASE_URL}/v1/models
Authorization: Bearer {API_KEY}
```

## 8. 最简接入结论

客户只需要改两样东西：

1. `BASE_URL`
2. `API_KEY`

然后按标准 OpenAI Chat 流式请求发送：

```http
POST /v1/chat/completions
```

请求里正常传：

1. `model`
2. `messages`
3. `stream=true`

这样就可以直接用了。
