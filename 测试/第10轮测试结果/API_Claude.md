# Claude (claude-opus-4-6) API 对接文档

## 基本信息

| 项目 | 值 |
|------|-----|
| 模型名 | `claude-opus-4-6` |
| 代理网站 | `https://ai.comfly.chat` |
| API协议 | **OpenAI Chat Completions** (`/v1/chat/completions`) |
| API Key | `sk-4f5dNlvbRjwcwjsxGeWU2NqY8Yp4u9SaYZUeuAhQVrofzD6R` |
| 超时设置 | 600s |

## 重要限制

- comfly.chat 代理用 **OpenAI Chat 格式** 封装 Claude（不是 Anthropic Messages API）
- 大文本请求可能触发 `RemoteProtocolError: Server disconnected` — **建议使用流式保活**
- 代理偶尔会断连，需要重试机制（3次重试，递增等待10/20/30s）

## 非流式请求

```python
import httpx

url = "https://ai.comfly.chat/v1/chat/completions"
headers = {
    "Authorization": "Bearer sk-4f5dNlvbRjwcwjsxGeWU2NqY8Yp4u9SaYZUeuAhQVrofzD6R",
    "Content-Type": "application/json",
}
body = {
    "model": "claude-opus-4-6",
    "messages": [
        {"role": "system", "content": "你的系统提示词"},
        {"role": "user", "content": "你的用户提示词"}
    ],
    "temperature": 0.5,
    "max_tokens": 32000,
}

resp = httpx.post(url, json=body, headers=headers, timeout=600)
data = resp.json()

# 解析响应
choices = data.get("choices", [])
text = choices[0].get("message", {}).get("content", "") if choices else ""

# Token 统计
usage = data.get("usage", {})
input_tokens = usage.get("prompt_tokens", 0)
output_tokens = usage.get("completion_tokens", 0)
```

## 流式请求（推荐，避免代理断连）

```python
import httpx
import json

url = "https://ai.comfly.chat/v1/chat/completions"
headers = {
    "Authorization": "Bearer sk-4f5dNlvbRjwcwjsxGeWU2NqY8Yp4u9SaYZUeuAhQVrofzD6R",
    "Content-Type": "application/json",
}
body = {
    "model": "claude-opus-4-6",
    "messages": [
        {"role": "system", "content": "系统提示词"},
        {"role": "user", "content": "用户提示词"}
    ],
    "temperature": 0.5,
    "max_tokens": 32000,
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

            # OpenAI Chat 流式格式
            if "choices" in data:
                delta = data["choices"][0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    full_text += content
                    print(content, end="", flush=True)
```

## 适配器类（Python）

```python
class ClaudeAdapter:
    """Claude via comfly.chat — OpenAI Chat 格式"""

    def __init__(self):
        self.api_base = "https://ai.comfly.chat/v1"
        self.model_id = "claude-opus-4-6"
        self.api_key = "sk-4f5dNlvbRjwcwjsxGeWU2NqY8Yp4u9SaYZUeuAhQVrofzD6R"
        self.timeout = 600

    async def call(self, system: str, user: str,
                   temperature=0.5, max_tokens=32000):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        body = {
            "model": self.model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=self.timeout,
                                      follow_redirects=True) as client:
            resp = await client.post(
                f"{self.api_base}/chat/completions",
                json=body, headers=headers,
            )
            resp.raise_for_status()

        data = resp.json()
        choices = data.get("choices", [])
        text = choices[0]["message"]["content"] if choices else ""

        usage = data.get("usage", {})
        return text, {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        }
```

## R10 测试结果

| 模式 | 耗时 | 角色数 | 场景数 | Token | 首卡时间 |
|------|------|--------|--------|-------|---------|
| Mode A (分离) | 293s | 10 | 20 | 10,190 | - |
| Mode B (合并) | 108s | 8 | 18 | 8,033 | - |
| Mode C (流式) | 105s | 9 | 18 | ~1,121 chunks | 15.8s |

## 踩坑记录

1. **comfly 用 OpenAI Chat 格式**：不是 Anthropic Messages API，是代理转换层
2. **大请求断连**：13K 全文一次性发送可能导致 `RemoteProtocolError`，流式模式可缓解
3. **重试必备**：代理不稳定，第 1 次可能断连，重试 2-3 次通常能成功
4. **max_tokens 要给足**：Claude 输出非常详细结构化，16K 会截断 → 建议 32000
5. **Token 最省**：同样任务 Claude 的 token 消耗约为其他模型的 50-60%
6. **openclaudecode.cn 不可用**：该站 Claude 账号池限制 "only Claude Code clients"，不能用
