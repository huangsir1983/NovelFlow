# Mode C — 流式渐进导出模式 (Streaming + Progressive Export)

## 流程概述

使用 Mode B 的合并提示词，但以 **SSE 流式** 接收响应，在流式过程中 **实时检测并导出** 每张完成的角色卡。用户在等待全部完成前就能看到第一个角色。

```
合并指令(stream=true) → SSE chunks → ProgressiveParser 逐块检测 →
发现完整角色JSON → 立即导出角色卡 → 继续接收 → 直到流结束 → 解析场景
```

## 这是最强方案的原因

| 维度 | Mode A | Mode B | **Mode C** |
|------|--------|--------|-----------|
| API 调用次数 | 2 | 1 | 1 |
| 首个结果可见时间 | 需等全部完成 | 需等全部完成 | **15-50s** |
| 用户体验 | 长等待 | 长等待 | **渐进反馈** |
| 总耗时 | 最长 | 中等 | 与B相当或更快 |
| Token | 最高 | 低 | 与B相同 |
| 健壮性 | 中 | 高 | **最高（流式保活）** |

## 详细实现步骤

### Step 1: 初始化渐进解析器

```python
class ProgressiveCharacterParser:
    """在流式 buffer 中实时检测完整的角色 JSON 对象"""

    def __init__(self):
        self.buffer = ""
        self.found_chars = []

    def feed(self, chunk: str) -> list[dict]:
        """喂入新的流式 chunk，返回新发现的完整角色对象"""
        self.buffer += chunk
        return self._scan()

    def _clean(self, text: str) -> str:
        """清洗 think 标签（Grok 专用）"""
        c = re.sub(r'<think>[\s\S]*?</think>', ' ', text)
        c = re.sub(r'\[Agent\s*\d*\]\[AgentThink\][\s\S]*?\[/AgentThink\]', ' ', c)
        return c

    def _fix_json_str(self, s: str) -> str:
        """修复裸换行符和断裂数字"""
        fixed = s
        for _ in range(10):
            prev = fixed
            fixed = re.sub(r'("(?:[^"\\]|\\.)*?)\n((?:[^"\\]|\\.)*?")', r'\1 \2', fixed)
            if fixed == prev: break
        fixed = re.sub(r'(\d)\s+\.(\d)', r'\1.\2', fixed)
        return fixed

    def _scan(self) -> list[dict]:
        """扫描 buffer，找到所有已完成的角色对象"""
        clean = self._clean(self.buffer)

        # 找到 "characters": [ 的位置
        pat = re.search(r'"characters"\s*:\s*\[', clean)
        if not pat:
            return []

        pos = pat.end()
        found = []
        while pos < len(clean):
            # 跳过空白和逗号
            while pos < len(clean) and clean[pos] in ' \t\n\r,':
                pos += 1
            if pos >= len(clean) or clean[pos] == ']':
                break
            if clean[pos] != '{':
                pos += 1
                continue

            # 用 depth 计数器找闭合的 }
            depth = 0
            in_str = False
            esc = False
            obj_start = pos
            found_end = False

            for i in range(pos, len(clean)):
                ch = clean[i]
                if esc: esc = False; continue
                if ch == '\\' and in_str: esc = True; continue
                if ch == '"': in_str = not in_str; continue
                if in_str: continue
                if ch == '{': depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        obj_str = self._fix_json_str(clean[obj_start:i+1])
                        try:
                            obj = json.loads(obj_str)
                            found.append(obj)
                        except json.JSONDecodeError:
                            pass
                        pos = i + 1
                        found_end = True
                        break

            if not found_end:
                break  # 对象未闭合，等待更多 chunk

        # 只返回新发现的角色
        new = found[len(self.found_chars):]
        self.found_chars = found
        return new
```

### Step 2: 流式请求 + 渐进解析

```python
async def test_mode_c(model_name, novel_text, out_dir):
    parser = ProgressiveCharacterParser()
    full_text = ""
    chunk_count = 0
    t0 = time.time()
    char_export_log = []

    try:
        async for chunk in stream_api_call(
            model_name,
            COMBINED_SYSTEM,
            COMBINED_USER.format(text=novel_text),
            temperature=0.5,
            max_tokens=32000,
        ):
            full_text += chunk
            chunk_count += 1

            # 每个 chunk 喂给解析器
            new_chars = parser.feed(chunk)
            for ch in new_chars:
                elapsed = time.time() - t0
                name = ch.get("name", "?")
                print(f"  角色卡导出: {name} @ {elapsed:.1f}s")
                char_export_log.append({"name": name, "time_s": round(elapsed, 2)})

                # 立即写入文件！用户马上能看到
                idx = len(char_export_log) - 1
                with open(out_dir / f"char_{idx:02d}_{name}.json", "w", encoding="utf-8") as f:
                    json.dump(ch, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"  流式异常: {e}")

    total_time = time.time() - t0

    # 流式结束后，从完整文本中解析场景
    result = extract_json(full_text)
    if isinstance(result, dict):
        characters = result.get("characters", [])
        scenes = result.get("scenes", [])
    else:
        characters = parser.found_chars
        scenes = []
```

### Step 3: 降级方案（代理不支持流式时）

某些代理（如 Gemini 的 yhgcli）不支持 SSE 流式。检测方法：

```python
if chunk_count == 0:
    raise RuntimeError("流式返回空内容 (0 chunks)")
```

降级到 **模拟渐进解析**：

```python
async def _mode_c_simulated(model_name, novel_text, out_dir):
    """非流式请求 + 按文本位置模拟渐进导出时间"""
    t0 = time.time()
    raw, cost = await smart_call(
        model_name, COMBINED_SYSTEM, COMBINED_USER.format(text=novel_text),
        temperature=0.5, max_tokens=32000,
    )
    total_time = time.time() - t0

    # 解析完整文本
    result = extract_json(raw)
    characters = result.get("characters", [])

    # 按每个角色在文本中的位置，模拟"如果是流式会在什么时候出现"
    char_export_log = []
    for ch in characters:
        name = ch.get("name", "?")
        # 在原始文本中找到该角色名的位置
        pos = raw.find(f'"name": "{name}"')
        if pos < 0:
            pos = raw.find(name)
        position_pct = pos / len(raw) if pos >= 0 else 0.5
        simulated_time = total_time * position_pct
        char_export_log.append({
            "name": name,
            "time_s": round(simulated_time, 2),
            "position_pct": round(position_pct * 100, 1),
        })
        print(f"  角色卡(模拟): {name} @ ~{simulated_time:.1f}s ({position_pct*100:.1f}%位置)")
```

## stream_api_call 统一接口

支持三种 API 协议的流式 SSE 解析：

```python
async def stream_api_call(model_name, system, user, temperature=0.5, max_tokens=32000):
    adapter = MODEL_REGISTRY[model_name]

    # 根据 adapter 类型构建不同的请求体和 URL
    # ... (见各模型 API 文档)

    async with httpx.AsyncClient(timeout=adapter.timeout, follow_redirects=True) as client:
        async with client.stream("POST", url, json=body, headers=headers) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                line = line.strip()
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload == "[DONE]":
                    break
                data = json.loads(payload)

                # OpenAI Chat 格式 (Claude/Gemini/Grok)
                if "choices" in data:
                    content = data["choices"][0].get("delta", {}).get("content", "")
                    if content: yield content

                # Responses API 格式 (ChatGPT)
                elif data.get("type") == "response.output_text.delta":
                    if data.get("delta"): yield data["delta"]

                # Anthropic Messages 格式 (直连 Claude 时)
                elif data.get("type") == "content_block_delta":
                    delta = data.get("delta", {})
                    if delta.get("type") == "text_delta":
                        if delta.get("text"): yield delta["text"]
```

## R10 跨模型对比

| 模型 | 总耗时 | 角色数 | 首卡时间 | 流式类型 | 渐进导出数 |
|------|--------|--------|---------|---------|-----------|
| **Claude** | **105s** | 9 | **15.8s** | 真流式 | 9张 |
| Grok | 120s | 8 | 50.2s | 真流式 | 7张 |
| ChatGPT | 262s | 15 | 28.1s | 真流式 | 15张 |
| Gemini | 177s | 7 | 18.1s* | 模拟 | 7张 |

\* Gemini 为模拟流式（按位置估算）

## 渐进导出时间线示例

### Claude（最快首卡 15.8s）
```
 15.8s → 高令宁
 24.6s → 沈词
 30.7s → 陆姝仪
 35.9s → 沈睿
 39.8s → 昭昭
 43.8s → 高父
 48.5s → 沈母
 54.0s → 蒋晟
 55.0s → 媒人
```

### ChatGPT（最多角色 15张）
```
 28.1s → 高令宁
 48.9s → 沈词
 63.7s → 陆姝仪
 78.5s → 高父
 90.6s → 蒋晟
102.5s → 沈母
112.2s → 沈睿
123.8s → 昭昭
129.7s → 媒人
133.7s → 沈府小厮
137.7s → 陆姝仪婢女
143.6s → 稳婆
147.8s → 太医
153.4s → 伯爵娘子
159.9s → 赘婿候选们
```

## 评级：⭐⭐⭐⭐⭐ 最强推荐

Mode C 是**生产环境的最佳方案**：
1. **用户体验最好**：15-28s 看到第一个结果，而不是等 2-4 分钟
2. **最健壮**：流式保活避免 Cloudflare/代理超时
3. **效率与 Mode B 相同**：同样的提示词、同样的 token 消耗
4. **渐进导出 = 前端可以逐步渲染**：完美契合 UI 进度条设计
5. **降级兜底**：即使代理不支持流式，也能用模拟渐进降级

**建议在产品中采用 Mode C 作为默认管道。**
