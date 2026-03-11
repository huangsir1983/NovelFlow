# Gemini (gemini-3.1-pro-preview) API 对接文档

## 基本信息

| 项目 | 值 |
|------|-----|
| 模型名 | `gemini-3.1-pro-preview` |
| 代理网站 | `https://yhgcli.xuhuanai.cn` |
| API协议 | **OpenAI Chat Completions** (`/v1/chat/completions`) |
| API Key | `ghitavjlksjkvnklghrvjog` |
| 超时设置 | 600s |

## 重要限制

- 该代理有 **429 限流保护**，连续请求会触发（等待 30s 后重试）
- **不支持 SSE 流式**：`stream: true` 会返回空内容 → 需要降级到非流式 + 模拟渐进解析
- Mode A 两次连续请求容易触发 429

## 非流式请求

```python
import httpx

url = "https://yhgcli.xuhuanai.cn/v1/chat/completions"
headers = {
    "Authorization": "Bearer ghitavjlksjkvnklghrvjog",
    "Content-Type": "application/json",
}
body = {
    "model": "gemini-3.1-pro-preview",
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
input_tokens = usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0)
output_tokens = usage.get("completion_tokens", 0) or usage.get("output_tokens", 0)
```

## 流式请求（该代理不支持，会返回空）

```
⚠ yhgcli 代理不支持流式输出！
stream: true 会返回 0 chunks，需要降级处理：
1. 检测流式返回 0 chunks
2. 抛出 RuntimeError
3. 降级到非流式请求 + 模拟渐进解析
```

### 模拟渐进解析方案

```python
import time
import json
import re

def simulated_progressive_parse(raw_text: str, total_time: float):
    """非流式返回后，按文本位置模拟渐进导出时间"""
    # 找到 characters 数组中每个对象的位置
    total_len = len(raw_text)
    pattern = re.compile(r'"name"\s*:\s*"([^"]+)"')

    for match in pattern.finditer(raw_text):
        name = match.group(1)
        position_pct = match.start() / total_len
        simulated_time = total_time * position_pct
        print(f"  角色卡(模拟): {name} @ ~{simulated_time:.1f}s ({position_pct*100:.1f}%位置)")
```

## 适配器类（Python）

```python
class GeminiAdapter:
    """Gemini via yhgcli — OpenAI Chat 格式"""

    def __init__(self):
        self.api_base = "https://yhgcli.xuhuanai.cn/v1"
        self.model_id = "gemini-3.1-pro-preview"
        self.api_key = "ghitavjlksjkvnklghrvjog"
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

        # 处理可能的 SSE 格式响应
        resp_body = resp.text
        if resp_body.lstrip().startswith("data: "):
            # 代理返回了 SSE 格式（即使没请求流式）
            text, usage = _parse_sse_to_text(resp_body)
        else:
            data = resp.json()
            choices = data.get("choices", [])
            text = choices[0]["message"]["content"] if choices else ""
            usage = data.get("usage", {})

        return text, {
            "input_tokens": usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0) or usage.get("output_tokens", 0),
        }
```

## 备选代理（comfly.chat）

如果 yhgcli 持续 429 限流，可切换到 comfly.chat：

```python
# 备选配置
api_base = "https://ai.comfly.chat/v1"
model_id = "gemini-2.5-pro"  # 注意：comfly 上的模型名不同
api_key = "sk-4f5dNlvbRjwcwjsxGeWU2NqY8Yp4u9SaYZUeuAhQVrofzD6R"
```

## R10 测试结果

| 模式 | 耗时 | 角色数 | 场景数 | Token | 首卡时间 |
|------|------|--------|--------|-------|---------|
| Mode A (分离) | ❌ 429限流 | - | - | - | - |
| Mode B (合并) | 231s | 6 | 12 | 17,225 | - |
| Mode C (模拟流式) | 177s | 7 | 13 | 18,461 | 18.1s* |

\* 模拟流式：基于文本位置推算的时间，非真实流式

## 踩坑记录

1. **429 限流频繁**：Mode A 两次连续请求几乎必中 429，需要 30s 冷却
2. **流式返回空**：`stream: true` 返回 0 chunks → 必须降级到非流式
3. **SSE 格式响应**：即使不请求流式，代理有时也返回 SSE 格式，需要双模式解析
4. **建议用 Mode B/C**：合并模式只发一次请求，避免 429
5. **comfly 备选**：如果 yhgcli 不稳定，comfly.chat 上有 `gemini-2.5-pro`
