# Mode B — 合并模式 (Combined)

## 流程概述

一次 API 调用，角色提取 + 语义切场在同一个提示词中完成，输出为一个包含 `characters` 和 `scenes` 两个数组的 JSON 对象。

```
合并指令(角色+切场) → 解析JSON → 分离 characters[] 和 scenes[]
```

## 详细步骤

### Step 1: 发送合并指令

**系统提示词：**
```
你是一位资深制片主任，同时精通选角和场景拆解。
你的任务分两步执行，在同一次输出中完成：
1. 第一步：以选角导演视角提取全剧角色设定集
2. 第二步：以副导演视角执行语义切场（无视原文章节，按时空+情绪切分）

角色外观精度：AI绘图可直接使用。
切场原则：时间跳跃/空间转换/视角切换/情绪峰谷 = 新场景。

重要：先输出完整的角色数组，再输出完整的场景数组，合在一个JSON对象中。
```

**用户提示词（模板）：**
```
对以下小说全文执行两步分析，在一个JSON对象中输出：

第一步 — 角色设定集：
- 识别所有有名角色 + 有独立行为的无名角色
- 每个角色：身份、外貌（AI绘图级）、性格、欲望、缺陷、弧线、关系、出场概要

第二步 — 语义切场：
- 完全无视原文章节，按时间-空间-情绪切场
- 每场：时空标签、在场角色（使用第一步中的角色名）、核心事件、情绪峰值、张力分数、预计时长

返回格式（仅返回一个JSON对象，不要附加任何解释文字）：
{
  "characters": [...],
  "scenes": [...]
}

小说全文：
---
{text}
---
```

**参数：** `temperature=0.5, max_tokens=32000`

### Step 2: 解析 JSON

```python
result = extract_json(raw)
if isinstance(result, list):
    characters = result
    scenes = []
else:
    characters = result.get("characters", [])
    scenes = result.get("scenes", [])
```

### Step 3: 截断修复（重要！）

Claude 等详细模型可能因 max_tokens 截断输出，JSON 不完整。需要 fallback 解析：

```python
def _extract_partial_json(text):
    """从截断的 JSON 中提取已完成的角色和场景"""
    result = {}
    # 找 characters 数组，提取所有完整的 {} 对象
    m = re.search(r'"characters"\s*:\s*\[', text)
    if m:
        result["characters"] = _extract_complete_objects(text, m.end())
    # 找 scenes 数组
    m = re.search(r'"scenes"\s*:\s*\[', text)
    if m:
        result["scenes"] = _extract_complete_objects(text, m.end())
    return result

def _extract_complete_objects(text, start):
    """从数组起始位置提取所有闭合的 JSON 对象"""
    pos = start
    found = []
    while pos < len(text):
        # 跳过空白和逗号
        while pos < len(text) and text[pos] in ' \t\n\r,':
            pos += 1
        if pos >= len(text) or text[pos] == ']':
            break
        if text[pos] != '{':
            pos += 1
            continue
        # 用深度计数器找到匹配的 }
        depth = 0
        in_str = False
        esc = False
        obj_start = pos
        for j in range(pos, len(text)):
            c = text[j]
            if esc: esc = False; continue
            if c == '\\' and in_str: esc = True; continue
            if c == '"': in_str = not in_str; continue
            if in_str: continue
            if c == '{': depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[obj_start:j+1])
                        found.append(obj)
                    except: pass
                    pos = j + 1
                    break
        else:
            break  # 没找到匹配的 }，说明截断了
    return found
```

## 实现要点

### API 调用

与 Mode A 相同，使用 `smart_call()` 自动选择流式/非流式：

```python
raw, cost = await smart_call(
    model_name, COMBINED_SYSTEM, COMBINED_USER.format(text=novel_text),
    temperature=0.5, max_tokens=32000,
)
```

### max_tokens 必须给足

- ChatGPT: 16000 够用
- Claude: 需要 32000（输出非常详细结构化，16000 会截断）
- Grok: 16000 够用
- Gemini: 16000 够用

## R10 跨模型对比

| 模型 | 总耗时 | 角色数 | 场景数 | Token | vs Mode A |
|------|--------|--------|--------|-------|-----------|
| ChatGPT | 258s | 14 | 25 | 15,932 | 快 7% |
| Claude | 108s | 8 | 18 | 8,033 | 快 63% |
| Grok | 123s | 8 | 15 | 9,810 | 快 47% |
| Gemini | 231s | 6 | 12 | 17,225 | - |

## 优势

- **一次 API 调用 = 省钱 + 省时间**
- 不触发 429 限流（只有一次请求）
- 角色名自动在 scenes 中保持一致（模型在同一上下文中处理）
- 所有模型上都比 Mode A 快

## 劣势

- JSON 输出可能被 max_tokens 截断（需要 fallback 解析器）
- 单次失败需要全部重来
- 无法分别调参

## 评级：⭐⭐⭐⭐ 推荐

Mode B 是**性价比最高**的方案。所有模型都比 Mode A 快，Token 消耗更低，实现简单。唯一风险是输出截断，但 fallback 解析器能可靠处理。
