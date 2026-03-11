# Grok (grok-4.20-beta) API 对接文档

## 基本信息

| 项目 | 值 |
|------|-----|
| 模型名 | `grok-4.20-beta` |
| 代理网站 | `https://yhgrok.xuhuanai.cn` |
| API协议 | **OpenAI Chat Completions** (`/v1/chat/completions`) |
| API Key | `V378STSBi6jAC9Gk` |
| 超时设置 | 600s |

## 重要限制

- Grok 是思考型模型，输出中夹带 `<think>...</think>` 标签，**会破坏 JSON 解析**
- 代理有时不返回 usage 统计 → 需要用输出字符数估算 token
- 支持真实 SSE 流式，但 `<think>` 标签也会出现在流式 chunk 中

## 非流式请求

```python
import httpx

url = "https://yhgrok.xuhuanai.cn/v1/chat/completions"
headers = {
    "Authorization": "Bearer V378STSBi6jAC9Gk",
    "Content-Type": "application/json",
}
body = {
    "model": "grok-4.20-beta",
    "messages": [
        {"role": "system", "content": "你的系统提示词"},
        {"role": "user", "content": "你的用户提示词"}
    ],
    "temperature": 0.5,
    "max_tokens": 32000,
}

resp = httpx.post(url, json=body, headers=headers, timeout=600)

# ⚠ 该代理可能返回 SSE 格式（即使没请求流式）
resp_body = resp.text
if resp_body.lstrip().startswith("data: "):
    text, usage = parse_sse_to_text(resp_body)
else:
    data = resp.json()
    choices = data.get("choices", [])
    text = choices[0]["message"]["content"] if choices else ""
    usage = data.get("usage", {})
```

## 流式请求（推荐）

```python
import httpx
import json

url = "https://yhgrok.xuhuanai.cn/v1/chat/completions"
headers = {
    "Authorization": "Bearer V378STSBi6jAC9Gk",
    "Content-Type": "application/json",
}
body = {
    "model": "grok-4.20-beta",
    "messages": [
        {"role": "system", "content": "系统提示词"},
        {"role": "user", "content": "用户提示词"}
    ],
    "temperature": 0.5,
    "max_tokens": 32000,
    "stream": True,
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

            if "choices" in data:
                delta = data["choices"][0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    full_text += content
```

## 关键：`<think>` 标签清洗

Grok 是思考型模型，JSON 输出中会嵌入思考过程，**必须在解析 JSON 前清洗**：

```python
import re

def clean_grok_output(raw: str) -> str:
    """清洗 Grok 的 <think> 标签 — JSON 解析前必须调用"""
    # 1. 移除 <think> 标签（替换为空格，不是空字符串！）
    text = re.sub(r'<think>[\s\S]*?</think>', ' ', raw)

    # 2. 移除 Agent 思考标签
    text = re.sub(r'\[Agent\s*\d*\]\[AgentThink\][\s\S]*?\[/AgentThink\]', ' ', text)

    # 3. 提取最后一个 code block（思考过程可能包含误导性的 code block）
    blocks = list(re.finditer(r'```(?:json)?\s*([\s\S]*?)```', text))
    if blocks:
        text = blocks[-1].group(1).strip()  # ⚠ 用最后一个，不是第一个！

    # 4. 修复因标签移除导致的 JSON 损坏
    # 4a. 修复 JSON 字符串值中的裸换行符
    for _ in range(10):
        prev = text
        text = re.sub(r'("(?:[^"\\]|\\.)*?)\n((?:[^"\\]|\\.)*?")', r'\1 \2', text)
        if text == prev:
            break

    # 4b. 修复断裂的数字（如 "0  .65" → "0.65"）
    text = re.sub(r'(\d)\s+\.(\d)', r'\1.\2', text)

    return text
```

### 为什么这么复杂？

Grok 的 `<think>` 标签会出现在 JSON 字符串值的**中间**，例如：
```
"body": "苗<think>这个角色需要纤细的身材...</think>条纤细"
```
移除标签后变成 `"body": "苗 条纤细"`（带空格但结构完整）。如果用空字符串替换会变成 `"body": "苗条纤细"` 但有些情况会产生裸换行符破坏 JSON。

## 适配器类（Python）

```python
class GrokAdapter:
    """Grok via yhgrok — OpenAI Chat 格式 + think 标签清洗"""

    def __init__(self):
        self.api_base = "https://yhgrok.xuhuanai.cn/v1"
        self.model_id = "grok-4.20-beta"
        self.api_key = "V378STSBi6jAC9Gk"
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

        # 处理可能的 SSE 格式
        resp_body = resp.text
        if resp_body.lstrip().startswith("data: "):
            text, usage = _parse_sse_to_text(resp_body)
        else:
            data = resp.json()
            choices = data.get("choices", [])
            text = choices[0]["message"]["content"] if choices else ""
            usage = data.get("usage", {})

        # Token 估算（代理可能不返回 usage）
        inp = usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0)
        out = usage.get("completion_tokens", 0) or usage.get("output_tokens", 0)
        if not inp and not out and text:
            out = len(text) // 2

        return text, {"input_tokens": inp, "output_tokens": out}
```

## R10 测试结果

| 模式 | 耗时 | 角色数 | 场景数 | Token | 首卡时间 |
|------|------|--------|--------|-------|---------|
| Mode A (分离) | 233s | 8 | 15 | 28,476 | - |
| Mode B (合并) | 123s | 8 | 15 | 9,810 | - |
| Mode C (流式) | 120s | 8 | 15 | ~5,310 chunks | 50.2s |

## 踩坑记录

1. **`<think>` 标签破坏 JSON**：这是 Grok 最大的坑，必须在 JSON 解析前清洗
2. **用最后一个 code block**：思考过程中的 partial code block 会误导 regex
3. **裸换行符修复**：标签移除后 JSON 字符串中出现裸 `\n`，需要替换为空格
4. **断裂数字修复**：标签移除后 `0.65` 变成 `0  .65`，需要 regex 修复
5. **SSE 双模式**：代理可能在非流式请求时返回 SSE 格式
6. **Token 估算**：代理经常返回 `input_tokens: 0`，用字符数 ÷ 2 估算
7. **首卡较慢**：Grok 思考时间长，流式首卡 50s（其他模型 15-28s）
