# Mode C 风险分析与加固方案

## 6 个风险点

### 风险 1: 流式中途断连 — 已导出的角色卡丢失

**严重度: 高**

| 项目 | 说明 |
|------|------|
| 触发条件 | 代理断连 (`RemoteProtocolError`)、网络波动、Cloudflare 重启 |
| 实测复现 | Claude via comfly.chat — 第 1 次请求经常断连 |
| 当前行为 | try/except 捕获异常后 `full_text` 不完整，前面已渐进导出的角色卡虽然写了文件，但结果 JSON 里没体现 |

**加固方案: Checkpoint + 断点续传**

```python
class ProgressiveCharacterParser:
    def __init__(self):
        self.buffer = ""
        self.found_chars = []         # 已完成的角色对象
        self.exported_files = []      # 已写入磁盘的文件路径

    def get_checkpoint(self) -> dict:
        """导出当前进度，用于断连后恢复"""
        return {
            "found_chars": self.found_chars,
            "exported_files": self.exported_files,
            "buffer_len": len(self.buffer),
        }
```

```python
async def test_mode_c_robust(model_name, novel_text, out_dir):
    parser = ProgressiveCharacterParser()
    full_text = ""
    t0 = time.time()
    char_export_log = []

    MAX_STREAM_RETRIES = 3

    for attempt in range(MAX_STREAM_RETRIES):
        try:
            async for chunk in stream_api_call(model_name, ...):
                full_text += chunk
                new_chars = parser.feed(chunk)
                for ch in new_chars:
                    # 立即写入磁盘 — 这是 checkpoint
                    _export_char(ch, out_dir, char_export_log, t0)
            break  # 流式正常结束

        except Exception as e:
            print(f"  ⚠ 流式断连 (attempt {attempt+1}): {e}")

            # 已导出的角色卡保留！
            if parser.found_chars:
                print(f"    保留已导出 {len(parser.found_chars)} 张角色卡")

            if attempt < MAX_STREAM_RETRIES - 1:
                # 检查: 角色部分是否已完整？
                if _has_complete_characters(full_text):
                    # 只缺场景 → 单独请求场景（降级为 Mode A 的指令2）
                    print("    → 角色已完整，单独补跑场景...")
                    char_names = [c.get("name","?") for c in parser.found_chars]
                    scenes = await _retry_scenes_only(model_name, novel_text, char_names)
                    break
                else:
                    # 角色也不完整 → 全部重跑
                    print(f"    → 等待 {10*(attempt+1)}s 后重试...")
                    await asyncio.sleep(10 * (attempt + 1))
                    full_text = ""
                    parser = ProgressiveCharacterParser()
                    char_export_log = []

def _has_complete_characters(text: str) -> bool:
    """检测 characters 数组是否已闭合"""
    # 找到 "characters": [...] 的闭合 ]
    m = re.search(r'"characters"\s*:\s*\[', text)
    if not m:
        return False
    depth = 1
    for i in range(m.end(), len(text)):
        if text[i] == '[': depth += 1
        elif text[i] == ']': depth -= 1
        if depth == 0:
            return True
    return False
```

---

### 风险 2: `<think>` 标签跨 chunk 切割（Grok）

**严重度: 中**

| 项目 | 说明 |
|------|------|
| 触发条件 | Grok 的思考标签被 SSE 切割到两个 chunk |
| 现象 | `_clean()` 正则匹配不到不完整的 `<think>`，think 内容中的 `{}` 干扰 depth 计数器 |
| 后果 | 某个角色对象无法被正确检测 |

**加固方案: 延迟清洗 + 未闭合标签保护**

```python
def _clean(self, text: str) -> str:
    # 1. 正常清洗已闭合的 think 标签
    c = re.sub(r'<think>[\s\S]*?</think>', ' ', text)
    c = re.sub(r'\[Agent\s*\d*\]\[AgentThink\][\s\S]*?\[/AgentThink\]', ' ', c)

    # 2. 关键加固：如果存在未闭合的 <think>，截断到 <think> 之前
    #    因为未闭合说明 </think> 还没到达，后面的内容不可信
    unclosed = c.rfind('<think>')
    if unclosed >= 0:
        # 检查这个 <think> 后面有没有 </think>
        closing = c.find('</think>', unclosed)
        if closing < 0:
            c = c[:unclosed]  # 截断到 <think> 之前，等更多 chunk 到达

    # 同样处理 [AgentThink]
    unclosed2 = c.rfind('[AgentThink]')
    if unclosed2 >= 0:
        closing2 = c.find('[/AgentThink]', unclosed2)
        if closing2 < 0:
            c = c[:unclosed2]

    return c
```

---

### 风险 3: Buffer 无限增长 + 重复扫描

**严重度: 低（但影响性能）**

| 项目 | 说明 |
|------|------|
| 触发条件 | 长输出（ChatGPT 13,793 chunks，~32K chars） |
| 现象 | 每个 chunk 到达时从头扫描整个 buffer |
| 后果 | O(chunks × buffer_len) 的计算量，后期变慢 |

**加固方案: 增量扫描 + buffer 窗口**

```python
class ProgressiveCharacterParser:
    def __init__(self):
        self.buffer = ""
        self.found_chars = []
        self._scan_start = 0        # 上次扫描停止的位置
        self._chars_closed = False   # characters 数组是否已闭合

    def feed(self, chunk: str) -> list[dict]:
        self.buffer += chunk

        # 如果 characters 数组已闭合，不再扫描
        if self._chars_closed:
            return []

        return self._scan()

    def _scan(self) -> list[dict]:
        clean = self._clean(self.buffer)

        pat = re.search(r'"characters"\s*:\s*\[', clean)
        if not pat:
            return []

        # 从上次停止的位置开始扫描（增量）
        pos = max(pat.end(), self._scan_start)
        found_before = len(self.found_chars)
        # ... 扫描逻辑 ...

        # 如果遇到 ]，标记 characters 数组已闭合
        if pos < len(clean) and clean[pos] == ']':
            self._chars_closed = True

        self._scan_start = pos  # 记住位置
        return self.found_chars[found_before:]
```

---

### 风险 4: max_tokens 截断

**严重度: 高（已实际发生）**

| 项目 | 说明 |
|------|------|
| 触发条件 | Claude 输出非常详细，超过 max_tokens 限制 |
| 实测复现 | 16K tokens → JSON 被截断，最后一场戏丢失 |
| 影响范围 | 长小说(>20K chars)更容易触发 |

**加固方案: 自适应 max_tokens + 截断检测 + 补跑**

```python
# 根据输入长度动态计算 max_tokens
def estimate_max_tokens(novel_len: int, model_name: str) -> int:
    """根据小说长度估算需要的 output tokens"""
    # 经验公式：每 1K 输入字符约产出 1.5K-3K output tokens
    base = int(novel_len * 2.5)

    # Claude 输出最详细，需要更多空间
    if "claude" in model_name:
        base = int(base * 1.5)

    # 最小 16K，最大 64K
    return max(16000, min(64000, base))

# 截断检测
def is_truncated(raw: str) -> bool:
    """检测 JSON 是否被截断"""
    stripped = raw.rstrip()
    # 正常的完整 JSON 应该以 } 或 ] 或 ``` 结尾
    if stripped.endswith('}') or stripped.endswith(']') or stripped.endswith('```'):
        return False
    return True

# 截断后补跑场景
async def retry_missing_scenes(model_name, novel_text, characters, out_dir):
    """角色卡完整但场景被截断 → 单独跑指令2补场景"""
    char_names = [c.get("name","?") for c in characters]
    raw, cost = await smart_call(
        model_name, INST2_SYSTEM,
        INST2_USER.format(text=novel_text, character_names=", ".join(char_names)),
        temperature=0.5, max_tokens=16000,
    )
    return extract_json(raw)
```

---

### 风险 5: 场景部分完全丢失

**严重度: 中**

| 项目 | 说明 |
|------|------|
| 触发条件 | 流式在角色输出完、场景还没开始时断连 |
| 后果 | 角色卡全有，场景数 = 0 |

**加固方案: 场景兜底补跑**

```python
# 在 Mode C 流程末尾加一个检查
if len(scenes) == 0 and len(characters) > 0:
    print("  ⚠ 场景为空，补跑指令2...")
    char_names = [c.get("name","?") for c in characters]
    scenes = await retry_missing_scenes(model_name, novel_text, characters, out_dir)
    print(f"  ✓ 补跑成功: {len(scenes)} 场戏")
```

---

### 风险 6: 代理完全不支持流式

**严重度: 低（已有降级）**

| 项目 | 说明 |
|------|------|
| 触发条件 | Gemini yhgcli 代理返回 0 chunks |
| 当前处理 | 降级到模拟渐进（非流式 + 按位置推算） |
| 问题 | 模拟渐进只是视觉效果，没有真正的渐进导出 |

**加固方案: 无需额外加固，当前降级已够用**

---

## 加固后的完整 Mode C 流程

```
Step 0: 估算 max_tokens = f(novel_len, model)
Step 1: 尝试流式请求 (stream=true)
  ├─ 成功 → ProgressiveParser 逐 chunk 解析
  │    ├─ 发现完整角色 → 立即写文件(checkpoint)
  │    ├─ characters 数组闭合 → 停止角色扫描
  │    └─ 流结束 → 解析场景
  │
  ├─ 0 chunks → 降级: 非流式 + 模拟渐进
  │
  └─ 中途断连 →
       ├─ 已有角色卡? →
       │    ├─ characters 数组闭合 → 保留角色，单独补跑场景
       │    └─ characters 不完整 → 保留已导出的，重试整个请求
       └─ 无角色卡 → 重试整个请求 (max 3次)

Step 2: 截断检测
  ├─ 角色完整 + 场景被截断 → 用已有角色名补跑指令2
  ├─ 场景数 = 0 → 补跑指令2
  └─ 全部完整 → 正常输出

Step 3: 输出结果
  ├─ characters[] 来自: 渐进解析器 (最全)
  ├─ scenes[] 来自: 完整文本解析 或 补跑
  └─ 结果合并写入 results.json
```

## 加固前后对比

| 风险场景 | 加固前 | 加固后 |
|---------|--------|--------|
| 流式断连 @ 第5张角色卡 | 全部丢失，返回空 | 保留前5张，重试或补跑场景 |
| Grok `<think>` 跨 chunk | 可能漏掉 1 个角色 | 截断到安全位置，等更多数据 |
| Claude 32K 截断 | 最后几场戏丢失 | 检测截断 → 补跑指令2 |
| 角色完整 + 场景丢失 | scenes=0 静默失败 | 自动补跑场景 |
| 13K chunks 性能下降 | O(n²) 全量扫描 | 增量扫描 + 提前停止 |

## 一句话总结

**核心原则：已导出的角色卡是 checkpoint，永远不丢弃；缺失的部分用降级/补跑恢复。**

把 Mode C 从"一次性赌注"变成"渐进式收集 + 智能补全"。
