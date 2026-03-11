# Mode A — 分离顺序模式 (Sequential)

## 流程概述

两次独立 API 调用，先提取角色，再用角色列表做语义切场。

```
指令1(角色提取) → 解析角色JSON → 提取角色名列表 → 指令2(语义切场，传入角色名) → 解析场景JSON
```

## 详细步骤

### Step 1: 角色提取（指令1）

**系统提示词：**
```
你是一位顶级选角导演兼概念设计师，精通影视角色拆解和AI视觉档案构建。
分析融合荣格原型理论和角色五维模型（身份/性格/欲望/创伤/能力边界）。

识别阈值：有名字的角色 + 有独立台词或影响剧情的无名角色。
外观描述精度：Stable Diffusion/Midjourney 可直接使用。
关系分析：标注功能属性（助攻/镜像/引导/阻碍）。
```

**用户提示词（模板）：**
```
分析以下小说全文，提取所有角色的完整设定档案（Casting档案）。

要求：
1. 识别所有有名角色 + 有独立行为的无名角色
2. 每个角色包含：身份、外貌（AI绘图级）、性格（行为模式）、欲望、缺陷、弧线
3. 角色关系图：标注关系类型和叙事功能
4. 标注每个角色的出场场次概要

返回格式（仅返回JSON数组，不要附加任何解释文字）：
[角色JSON模板...]

小说全文：
---
{text}
---
```

**参数：** `temperature=0.5, max_tokens=8192`

**输出：** JSON 数组，每个元素是一个角色对象

### Step 2: 解析角色 + 提取角色名列表

```python
characters = extract_json(raw1)
if isinstance(characters, dict):
    characters = characters.get("characters", [characters])
char_names = [c.get("name", "?") for c in characters]
```

### Step 3: 语义切场（指令2）

**系统提示词：**
```
你是一位资深副导演（1st AD）和场记，按好莱坞标准制片流程执行场景拆解。

核心原则：
- 完全无视原小说章节划分，按语义切场（Semantic Chunking）
- 切场依据：时间跳跃、空间转换、视角切换、情绪峰谷交替
- 场景最小单位：一个连续时空中的戏剧动作单元
- 每场必须有明确戏剧目的（推情节/揭角色/建氛围/造转折）
- 对话提取保留潜台词层
```

**用户提示词（模板）：**
```
对以下小说全文执行语义切场（Semantic Chunking）。

关键规则：
- 完全无视原文章节划分，纯粹按时间-空间-情绪转换切场
- 每场是一个「连续时空+单一戏剧动作单元」
- 为每场标注：时空标签、在场角色、核心事件、情绪峰值、预计时长

已知角色列表（在characters_present中使用这些一致的名字）：
{character_names}

返回格式（仅返回JSON数组...）
[场景JSON模板...]

小说全文：
---
{text}
---
```

**参数：** `temperature=0.5, max_tokens=12000`

**注意：** `{character_names}` 从 Step 2 获取的角色名用逗号连接传入

### Step 4: 解析场景

```python
scenes = extract_json(raw2)
if isinstance(scenes, dict):
    scenes = scenes.get("scenes", [scenes])
```

## 实现要点

### API 调用方式

```python
# 对于需要流式保活的模型（gpt-5.4, claude-opus-4-6）
# 用 stream_api_call 收集完整文本，避免 Cloudflare 超时
if model_name in {"gpt-5.4", "claude-opus-4-6"}:
    raw, cost = await _call_via_stream(model_name, system, user, temperature, max_tokens)
else:
    raw, cost = await call_api_async(system, user, temperature, max_tokens, model_name)
```

### 重试机制

```python
MAX_RETRIES = 3
RETRY_WAIT_BASE = 10   # 递增：10s, 20s, 30s
RATE_LIMIT_WAIT = 30   # 429 限流等待

# 可重试状态码：500, 502, 503, 504, 524
# 可重试异常：ReadTimeout, RemoteProtocolError
```

## R10 跨模型对比

| 模型 | 指令1耗时 | 指令2耗时 | 总耗时 | 角色数 | 场景数 | Token |
|------|----------|----------|--------|--------|--------|-------|
| ChatGPT | 176s | 100s | 277s | 13 | 27 | 15,638 |
| Claude | 96s | 197s | 293s | 10 | 20 | 10,190 |
| Grok | 90s | 142s | 233s | 8 | 15 | 28,476 |
| Gemini | ❌429 | - | - | - | - | - |

## 优势

- 指令2 能利用指令1 的角色名列表，保证角色名一致性
- 两步可以独立调参（角色提取用较低 max_tokens，场景用较高）
- 如果指令1 失败，不需要重跑全部

## 劣势

- **两次 API 调用 = 两次付费 + 两次延迟**
- 容易触发 429 限流（Gemini 实测中招）
- 总耗时最长（所有模型中 Mode A > Mode B）
- Token 消耗最高（输入文本发送两次）

## 评级：⭐⭐ 不推荐

Mode A 在所有模型上都比 Mode B 慢，Token 消耗更高，且容易触发限流。唯一优势是角色名一致性，但实测中 Mode B 的角色名一致性也完全够用。
