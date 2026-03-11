# ChatGPT (gpt-5.4) API 对接文档

## 基本信息

| 项目 | 值 |
|------|-----|
| 模型名 | `gpt-5.4` |
| 代理网站 | `https://www.openclaudecode.cn` |
| API协议 | **OpenAI Responses API** (`/v1/responses`) |
| API Key | `sk-S2HdTVByFCfJcZ3oM3BUBQio0CGtty7xA2aTHdCP9occt50e` |
| 超时设置 | 600s |

## 重要限制

- 该代理 **不支持** OpenAI Chat Completions (`/v1/chat/completions`)，只支持 Responses API 格式
- 大文本请求（>10K chars）会触发 Cloudflare 524 网关超时 — **必须使用流式(stream: true)** 保活连接
- 非流式请求只适合小文本

## 非流式请求

```python
import httpx

url = "https://www.openclaudecode.cn/v1/responses"
headers = {
    "Authorization": "Bearer sk-S2HdTVByFCfJcZ3oM3BUBQio0CGtty7xA2aTHdCP9occt50e",
    "Content-Type": "application/json",
}
body = {
    "model": "gpt-5.4",
    "input": [
        {"role": "user", "content": "你的提示词内容"}
    ],
    "instructions": "你的系统提示词（可选）",
    "temperature": 0.5,
    "max_output_tokens": 8192,
}

resp = httpx.post(url, json=body, headers=headers, timeout=600)
data = resp.json()

# 解析响应
output = data.get("output", [])
text = ""
if output:
    content = output[0].get("content", [])
    if content:
        text = content[0].get("text", "")

# Token 统计
usage = data.get("usage", {})
input_tokens = usage.get("input_tokens", 0)
output_tokens = usage.get("output_tokens", 0)
```

## 流式请求（推荐，避免 Cloudflare 超时）

```python
import httpx
import json

url = "https://www.openclaudecode.cn/v1/responses"
headers = {
    "Authorization": "Bearer sk-S2HdTVByFCfJcZ3oM3BUBQio0CGtty7xA2aTHdCP9occt50e",
    "Content-Type": "application/json",
}
body = {
    "model": "gpt-5.4",
    "input": [
        {"role": "user", "content": "你的提示词内容"}
    ],
    "instructions": "系统提示词（可选）",
    "temperature": 0.5,
    "max_output_tokens": 8192,
    "stream": True,  # 关键：开启流式
}

full_text = ""
async with httpx.AsyncClient(timeout=600, follow_redirects=True) as client:
    async with client.stream("POST", url, json=body, headers=headers) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            line = line.strip()
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload == "[DONE]":
                break
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                continue

            # Responses API 流式格式
            if data.get("type") == "response.output_text.delta":
                delta_text = data.get("delta", "")
                if delta_text:
                    full_text += delta_text
                    print(delta_text, end="", flush=True)
```

## 适配器类（Python）

```python
class ResponsesAPIAdapter:
    """适配 /v1/responses 端点"""

    def __init__(self):
        self.api_base = "https://www.openclaudecode.cn/v1/responses"
        self.model_id = "gpt-5.4"
        self.api_key = "sk-S2HdTVByFCfJcZ3oM3BUBQio0CGtty7xA2aTHdCP9occt50e"
        self.timeout = 600

    async def call(self, system: str, user: str,
                   temperature=0.5, max_tokens=8192):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model_id,
            "input": [{"role": "user", "content": user}],
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        if system:
            body["instructions"] = system

        async with httpx.AsyncClient(timeout=self.timeout,
                                      follow_redirects=True) as client:
            resp = await client.post(self.api_base, json=body, headers=headers)
            resp.raise_for_status()

        data = resp.json()
        output = data.get("output", [])
        text = ""
        if output:
            content = output[0].get("content", [])
            if content:
                text = content[0].get("text", "")

        usage = data.get("usage", {})
        return text, {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
        }
```

## R10 测试结果

| 模式 | 耗时 | 角色数 | 场景数 | Token | 首卡时间 |
|------|------|--------|--------|-------|---------|
| Mode A (分离) | 277s | 13 | 27 | 15,638 | - |
| Mode B (合并) | 258s | 14 | 25 | 15,932 | - |
| Mode C (流式) | 262s | 15 | 25 | ~13,793 chunks | 28.1s |

## 踩坑记录

1. **必须用 Responses API 格式**：该代理对 `/v1/chat/completions` 返回 400 "Unsupported legacy protocol"
2. **大文本必须流式**：>10K 输入文本 + 大输出 → Cloudflare 524 超时（~100s 网关限制）
3. **流式保活方案**：`stream: True` 让 SSE 连接持续发送 chunk，绕过 Cloudflare 超时
4. **Token 统计**：流式模式下代理可能不返回 usage，需要用输出字符数估算 `len(text)//2`
