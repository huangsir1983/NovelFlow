"""多模型 API 适配层 — 支持 Responses API 和 OpenAI Chat 两种协议.

用法:
    from model_adapters import call_api_async, MODEL_REGISTRY

    text, cost = await call_api_async(system, user, model_name="gpt-5.4")
"""

import asyncio
import json
import time
from abc import ABC, abstractmethod

import httpx

# ── 配置 ──────────────────────────────────────────────────────────

MAX_RETRIES = 3
RETRY_WAIT_BASE = 10
RATE_LIMIT_WAIT = 30
MAX_CONCURRENT = 8
MAX_RATE_LIMIT_RETRIES = 5  # B3.1: cap consecutive 429 retries

_semaphore = asyncio.Semaphore(MAX_CONCURRENT)


# ── 错误判断 ──────────────────────────────────────────────────────

def is_retryable(exc: Exception) -> bool:
    if isinstance(exc, (httpx.ReadTimeout, httpx.RemoteProtocolError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (500, 502, 524, 503, 504)
    return False


def is_rate_limited(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429
    return False


# ── SSE 流式响应解析 ──────────────────────────────────────────────

def _parse_sse_to_text(body: str) -> tuple[str, dict]:
    """将 SSE 流式响应体拼装为完整文本 + usage。

    某些代理服务器(如 yhgrok)即使 stream=false 也返回 SSE 格式。
    """
    chunks = []
    usage = {}
    for line in body.split("\n"):
        line = line.strip()
        if not line.startswith("data: "):
            continue
        payload = line[6:]  # strip "data: "
        if payload == "[DONE]":
            break
        try:
            obj = json.loads(payload)
            choices = obj.get("choices", [])
            if choices:
                delta = choices[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    chunks.append(content)
            if obj.get("usage"):
                usage = obj["usage"]
        except json.JSONDecodeError:
            continue
    return "".join(chunks), usage


# ── 适配器基类 ────────────────────────────────────────────────────

class ModelAdapter(ABC):
    """模型适配器基类。"""

    def __init__(self, api_base: str, model_id: str, api_key: str,
                 timeout: int = 500, display_name: str = ""):
        self.api_base = api_base
        self.model_id = model_id
        self.api_key = api_key
        self.timeout = timeout
        self.display_name = display_name or model_id

    @abstractmethod
    async def call(self, system: str, user: str,
                   temperature: float = 0.7,
                   max_tokens: int = 4096) -> tuple[str, dict]:
        """调用模型，返回 (text, cost_meta)。"""
        ...


# ── Responses API 适配器（OpenClaudeCode / XuhuanAI） ────────────

class ResponsesAPIAdapter(ModelAdapter):
    """适配 /v1/responses 端点（gpt-5.4, claude-opus-4-6 等）。"""

    async def call(self, system: str, user: str,
                   temperature: float = 0.7,
                   max_tokens: int = 4096) -> tuple[str, dict]:
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

        last_exc = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                async with _semaphore:
                    t0 = time.time()
                    async with httpx.AsyncClient(timeout=self.timeout,
                                                  follow_redirects=True) as client:
                        resp = await client.post(self.api_base, json=body,
                                                  headers=headers)
                        resp.raise_for_status()
                    elapsed = time.time() - t0

                # Guard: empty response body → treat as retryable
                if not resp.text.strip():
                    raise RuntimeError(
                        f"Empty response body from {self.display_name} "
                        f"(status {resp.status_code})")

                data = resp.json()
                output = data.get("output", [])
                text = ""
                if output:
                    content = output[0].get("content", [])
                    if content:
                        text = content[0].get("text", "")

                usage = data.get("usage", {})
                cost_meta = {
                    "model": self.display_name,
                    "input_tokens": usage.get("input_tokens", 0),
                    "output_tokens": usage.get("output_tokens", 0),
                    "elapsed_s": round(elapsed, 2),
                }
                return text, cost_meta

            except Exception as e:
                last_exc = e
                if is_rate_limited(e):
                    rate_limit_count += 1
                    if rate_limit_count > MAX_RATE_LIMIT_RETRIES:
                        raise RuntimeError(
                            f"Rate limit exceeded {MAX_RATE_LIMIT_RETRIES} consecutive times "
                            f"for {self.display_name}") from e
                    print(f"\n    ⚠ 429限流 ({self.display_name})，等待 {RATE_LIMIT_WAIT}s...",
                          flush=True)
                    await asyncio.sleep(RATE_LIMIT_WAIT)
                    continue
                if is_retryable(e) or isinstance(e, (RuntimeError, json.JSONDecodeError)):
                    if attempt < MAX_RETRIES:
                        wait = RETRY_WAIT_BASE * (attempt + 1)
                        code = getattr(getattr(e, 'response', None),
                                       'status_code', type(e).__name__)
                        print(f"\n    ⚠ {code} ({self.display_name})，"
                              f"重试 {attempt+1}/{MAX_RETRIES}，等待 {wait}s...",
                              flush=True)
                        await asyncio.sleep(wait)
                        continue
                raise
        raise last_exc


# ── OpenAI Chat 适配器（Comfly/Gemini/Grok） ─────────────────────

class OpenAIChatAdapter(ModelAdapter):
    """适配 /v1/chat/completions 端点（Gemini, Grok 等）。"""

    async def call(self, system: str, user: str,
                   temperature: float = 0.7,
                   max_tokens: int = 4096) -> tuple[str, dict]:
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

        last_exc = None
        rate_limit_count = 0  # B3.1
        for attempt in range(MAX_RETRIES + 1):
            try:
                async with _semaphore:
                    t0 = time.time()
                    async with httpx.AsyncClient(timeout=self.timeout,
                                                  follow_redirects=True) as client:
                        resp = await client.post(
                            f"{self.api_base}/chat/completions",
                            json=body, headers=headers,
                        )
                        resp.raise_for_status()
                    elapsed = time.time() - t0

                # Guard: empty response body → treat as retryable
                resp_body = resp.text
                if not resp_body.strip():
                    raise RuntimeError(
                        f"Empty response body from {self.display_name} "
                        f"(status {resp.status_code})")

                # Handle SSE-streamed responses (some proxies always stream)
                if resp_body.lstrip().startswith("data: "):
                    text, usage = _parse_sse_to_text(resp_body)
                    inp_tok = (usage.get("prompt_tokens", 0)
                               or usage.get("input_tokens", 0))
                    out_tok = (usage.get("completion_tokens", 0)
                               or usage.get("output_tokens", 0))
                    if not inp_tok and not out_tok and text:
                        out_tok = len(text) // 2
                    cost_meta = {
                        "model": self.display_name,
                        "input_tokens": inp_tok,
                        "output_tokens": out_tok,
                        "elapsed_s": round(elapsed, 2),
                    }
                    return text, cost_meta

                try:
                    data = resp.json()
                except json.JSONDecodeError:
                    raise RuntimeError(
                        f"Invalid JSON from {self.display_name} "
                        f"(body_len={len(resp_body)}, "
                        f"preview={resp_body[:200]!r})")

                choices = data.get("choices", [])
                text = ""
                if choices:
                    text = choices[0].get("message", {}).get("content", "")

                usage = data.get("usage", {})
                inp_tok = (usage.get("prompt_tokens", 0)
                           or usage.get("input_tokens", 0))
                out_tok = (usage.get("completion_tokens", 0)
                           or usage.get("output_tokens", 0))
                # 估算: 若代理不返回 usage，按字符数粗估
                if not inp_tok and not out_tok and text:
                    out_tok = len(text) // 2  # 粗估
                cost_meta = {
                    "model": self.display_name,
                    "input_tokens": inp_tok,
                    "output_tokens": out_tok,
                    "elapsed_s": round(elapsed, 2),
                }
                return text, cost_meta

            except Exception as e:
                last_exc = e
                if is_rate_limited(e):
                    rate_limit_count += 1
                    if rate_limit_count > MAX_RATE_LIMIT_RETRIES:
                        raise RuntimeError(
                            f"Rate limit exceeded {MAX_RATE_LIMIT_RETRIES} consecutive times "
                            f"for {self.display_name}") from e
                    print(f"\n    ⚠ 429限流 ({self.display_name})，等待 {RATE_LIMIT_WAIT}s...",
                          flush=True)
                    await asyncio.sleep(RATE_LIMIT_WAIT)
                    continue
                if is_retryable(e) or isinstance(e, RuntimeError):
                    if attempt < MAX_RETRIES:
                        wait = RETRY_WAIT_BASE * (attempt + 1)
                        print(f"\n    ⚠ {type(e).__name__} ({self.display_name})，"
                              f"重试 {attempt+1}/{MAX_RETRIES}，等待 {wait}s... "
                              f"({e})",
                              flush=True)
                        await asyncio.sleep(wait)
                        continue
                raise
        raise last_exc


# ── 模型注册表 ────────────────────────────────────────────────────

# API Keys
_OCC_KEY = "sk-S2HdTVByFCfJcZ3oM3BUBQio0CGtty7xA2aTHdCP9occt50e"
_COMFLY_KEY = "sk-4f5dNlvbRjwcwjsxGeWU2NqY8Yp4u9SaYZUeuAhQVrofzD6R"
_GCLI_KEY = "ghitavjlksjkvnklghrvjog"
_GROK_KEY = "V378STSBi6jAC9Gk"

MODEL_REGISTRY: dict[str, ModelAdapter] = {
    "gpt-5.4": ResponsesAPIAdapter(
        api_base="https://www.openclaudecode.cn/v1/responses",
        model_id="gpt-5.4",
        api_key=_OCC_KEY,
        timeout=500,
        display_name="gpt-5.4",
    ),
    "claude-opus-4-6": OpenAIChatAdapter(
        api_base="https://ai.comfly.chat/v1",
        model_id="claude-opus-4-6",
        api_key=_COMFLY_KEY,
        timeout=600,  # Claude 较慢，超时加长
        display_name="claude-opus-4-6",
    ),
    "gemini": OpenAIChatAdapter(
        api_base="https://yhgcli.xuhuanai.cn/v1",
        model_id="gemini-3.1-pro-preview",
        api_key=_GCLI_KEY,
        timeout=600,
        display_name="gemini-3.1-pro-preview",
    ),
    "grok": OpenAIChatAdapter(
        api_base="https://yhgrok.xuhuanai.cn/v1",
        model_id="grok-4.20-beta",
        api_key=_GROK_KEY,
        timeout=600,
        display_name="grok-4.20-beta",
    ),
}

# 默认模型
DEFAULT_MODEL = "gpt-5.4"


# ── 统一调用接口 ──────────────────────────────────────────────────

async def call_api_async(system: str, user: str,
                         temperature: float = 0.7,
                         max_tokens: int = 4096,
                         model_name: str = DEFAULT_MODEL) -> tuple[str, dict]:
    """统一异步 API 调用接口。

    Args:
        system: 系统提示词
        user: 用户提示词
        temperature: 温度参数
        max_tokens: 最大输出token数
        model_name: 模型名称（MODEL_REGISTRY 中的 key）

    Returns:
        (text, cost_meta) — 响应文本和成本信息
    """
    adapter = MODEL_REGISTRY.get(model_name)
    if adapter is None:
        raise ValueError(f"未知模型: {model_name}，"
                         f"可用: {list(MODEL_REGISTRY.keys())}")
    return await adapter.call(system, user, temperature, max_tokens)


def call_api_sync(system: str, user: str,
                  temperature: float = 0.7,
                  max_tokens: int = 4096,
                  model_name: str = DEFAULT_MODEL) -> tuple[str, dict]:
    """同步 API 调用（用于非异步上下文）。

    内部通过 Responses API 直接用 httpx.Client 调用。
    """
    adapter = MODEL_REGISTRY.get(model_name)
    if adapter is None:
        raise ValueError(f"未知模型: {model_name}")

    headers = {
        "Authorization": f"Bearer {adapter.api_key}",
        "Content-Type": "application/json",
    }

    # 根据适配器类型构建请求
    if isinstance(adapter, ResponsesAPIAdapter):
        body = {
            "model": adapter.model_id,
            "input": [{"role": "user", "content": user}],
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        if system:
            body["instructions"] = system
        url = adapter.api_base
    else:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        body = {
            "model": adapter.model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        url = f"{adapter.api_base}/chat/completions"

    import time as _time

    last_exc = None
    rate_limit_count = 0  # B3.1
    for attempt in range(MAX_RETRIES + 1):
        try:
            t0 = _time.time()
            with httpx.Client(timeout=adapter.timeout,
                              follow_redirects=True) as client:
                resp = client.post(url, json=body, headers=headers)
                resp.raise_for_status()
            elapsed = _time.time() - t0

            data = resp.json()

            # 提取文本
            if isinstance(adapter, ResponsesAPIAdapter):
                output = data.get("output", [])
                text = ""
                if output:
                    content = output[0].get("content", [])
                    if content:
                        text = content[0].get("text", "")
                usage = data.get("usage", {})
                cost_meta = {
                    "model": adapter.display_name,
                    "input_tokens": usage.get("input_tokens", 0),
                    "output_tokens": usage.get("output_tokens", 0),
                    "elapsed_s": round(elapsed, 2),
                }
            else:
                choices = data.get("choices", [])
                text = choices[0].get("message", {}).get("content", "") if choices else ""
                usage = data.get("usage", {})
                cost_meta = {
                    "model": adapter.display_name,
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "output_tokens": usage.get("completion_tokens", 0),
                    "elapsed_s": round(elapsed, 2),
                }

            return text, cost_meta

        except Exception as e:
            last_exc = e
            if is_rate_limited(e):
                rate_limit_count += 1
                if rate_limit_count > MAX_RATE_LIMIT_RETRIES:
                    raise RuntimeError(
                        f"Rate limit exceeded {MAX_RATE_LIMIT_RETRIES} consecutive times "
                        f"for {adapter.display_name}") from e
                print(f"\n    ⚠ 429限流 ({adapter.display_name})，"
                      f"等待 {RATE_LIMIT_WAIT}s...", flush=True)
                _time.sleep(RATE_LIMIT_WAIT)
                continue
            if is_retryable(e) and attempt < MAX_RETRIES:
                wait = RETRY_WAIT_BASE * (attempt + 1)
                code = getattr(getattr(e, 'response', None),
                               'status_code', type(e).__name__)
                print(f"\n    ⚠ {code} ({adapter.display_name})，"
                      f"重试 {attempt+1}/{MAX_RETRIES}，等待 {wait}s...",
                      flush=True)
                _time.sleep(wait)
                continue
            raise
    raise last_exc


def get_available_models() -> list[str]:
    """返回可用的模型名称列表。"""
    return list(MODEL_REGISTRY.keys())
