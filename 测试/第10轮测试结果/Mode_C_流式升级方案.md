# Mode C 流式升级方案 — 完整资产提取管线（v2 重构版）

> 版本: 2.0 | 日期: 2026-03-10
> 基线: `run_test_round10.py` (第10轮测试)
> 目标文件: `测试/run_test_round10.py`
> **重构核心: 区分叙事场景 (Narrative Scene) 与 场景资产卡 (Location Asset Card)**

---

## 零、核心概念澄清

本方案修正 v1 中的概念混淆：**叙事场景**和**场景资产卡**是两个截然不同的东西。

| | 叙事场景 (Narrative Scene) | 场景资产卡 (Location Asset Card) |
|---|---|---|
| **本质** | 有序的故事事件 | 去重的环境视觉描述 |
| **数量** | 可能 20+ 个 | 5-10 个唯一地点 |
| **排序** | 严格按故事时间线排序（`order` 字段） | 无序（资产库条目） |
| **同一地点** | 可出现多次（不同事件） | 只出现一次 |
| **用途** | 故事骨架，后续拆分镜头/VFF 的基础 | 资产库，用于 AI 生成场景图片 |
| **示例** | scene_003: 高家正堂-求亲<br>scene_007: 高家正堂-争执<br>scene_015: 高家正堂-诀别 | loc_高家正堂: 建筑风格/布局/光线/色调 |

**阶段1** 的场景是**流程场景**（叙事场景），需要排序，因为所有故事都发生在场景上。
**阶段2A** 的场景合并是**另一个流程**，目的是产生**资产库里的场景卡**，用来生成图片。

---

## 一、升级目标

当前 Mode C 只渐进导出角色卡，场景在流结束后才解析，道具只是场景里的字符串数组，角色没有变体支持。本次升级将 Mode C 从「角色提取器」升级为「完整资产提取管线」，产出 5 类资产卡：角色主卡、叙事场景、场景资产卡、道具卡、角色变体卡。

**产出物清单：**

| 资产类型 | 文件位置 | 生成方式 |
|----------|----------|----------|
| 角色主卡 | `characters/char_XX_名字.json` | 阶段1 流式渐进导出 |
| 叙事场景 | `narrative_scenes/scene_XXX_地点.json` | 阶段1 流式渐进导出（有序） |
| 时间线索引 | `narrative_scenes/_timeline.json` | 阶段1 结束时汇总 |
| 场景资产卡 | `locations/loc_XXX_地点.json` | 阶段2A 本地分组 + AI生成 |
| 场景索引 | `locations/_index.json` | 阶段2A 结束时汇总 |
| 道具索引 | `props/prop_index.json` | 阶段2B 纯本地计算 |
| 道具卡 | `props/prop_major_名字.json` | 阶段2C AI生成 |
| 角色变体卡 | `variants/variant_角色名_类型.json` | 阶段3 逐角色API调用 |
| 资产清单 | `manifest.json` | 管线结束时汇总 |

---

## 二、总体架构：三阶段管线

```
阶段 1 (流式): 合并提示词 → 渐进导出角色卡 + 叙事场景卡（有序）
阶段 2 (后处理):
  2A: 场景资产卡生成（按地点分组叙事场景 → AI生成视觉描述）
  2B: 道具收集分层（从全部叙事场景收集）
  2C: 道具卡生成（仅 major 道具）
阶段 3 (流式): 逐角色生成变体卡（基于角色主卡 + 叙事场景列表）
```

```
输入: novel_text (小说全文)
  │
  ▼
阶段1: stream_api_call(COMBINED_PROMPT)
  │  ├─ 渐进导出: char_00_高令宁.json ← 15s
  │  ├─ 渐进导出: char_01_沈词.json   ← 25s
  │  ├─ ...characters 闭合...
  │  ├─ 渐进导出: scene_001_高家正堂_求亲.json   ← 叙事场景（有序）
  │  ├─ 渐进导出: scene_002_闺房_待嫁.json
  │  ├─ 渐进导出: scene_003_高家正堂_争执.json   ← 同一地点，不同事件
  │  └─ ...stream 结束...
  │  └─ 生成: _timeline.json（场景时间线索引）
  │
  ▼
阶段2A: 场景资产卡生成
  │  ├─ 本地: 按 location 分组叙事场景
  │  ├─ 本地: 收集每个地点的视觉线索
  │  ├─ AI调用: 生成场景资产卡（批量）
  │  └─ 输出: locations/loc_001_高家正堂.json ...
  │
  ▼
阶段2B: collect_and_tier_props（从全部叙事场景收集）
  │  ├─ major_props (≥3次) → 需要完整卡
  │  └─ minor_props (<3次) → 仅名称+场景
  │
  ▼
阶段2C: smart_call(PROP_CARD_PROMPT)  [仅 major 道具]
  │  └─ 输出: prop_major_木雁.json, prop_major_身契.json, ...
  │
  ▼
阶段3: 对每个主要角色 smart_call(VARIANT_PROMPT)
  │  ├─ variant_高令宁_少女.json
  │  ├─ variant_高令宁_新嫁.json
  │  └─ ...
  │
  ▼
输出: 完整资产包
  ├─ characters/          (角色主卡)
  ├─ narrative_scenes/    (叙事场景 — 有序时间线)
  ├─ locations/           (场景资产卡 — 地点视觉描述)
  ├─ props/               (道具卡 + 道具清单)
  ├─ variants/            (角色变体卡)
  └─ manifest.json        (资产清单索引)
```

---

## 三、阶段 1：多相渐进解析器

### 3.1 改造目标

将 `ProgressiveCharacterParser` 升级为 `ProgressiveAssetParser`，支持依次解析 characters → scenes 两个数组。场景概念明确为**叙事场景 (narrative_scenes)**，必须带 `order` 字段。

### 3.2 解析器状态机

```
流式 chunk 到达
  → buffer 累积
  → Phase 1: 扫描 "characters": [ ... ]
       发现完整角色对象 → 立即导出 characters/char_XX_名字.json
       遇到 ] 闭合 → 标记 characters_closed = True
  → Phase 2: 扫描 "scenes": [ ... ]  (characters 闭合后才激活)
       发现完整场景对象 → 立即导出 narrative_scenes/scene_XXX_地点.json
       遇到 ] 闭合 → 标记 scenes_closed = True
```

### 3.3 ProgressiveAssetParser 完整设计

```python
class ProgressiveAssetParser:
    """多相渐进资产解析器 — 依次扫描 characters → scenes 两个JSON数组。

    继承自原 ProgressiveCharacterParser 的核心逻辑:
    - depth 计数器跟踪大括号嵌套
    - _clean() 清洗 <think> 标签
    - _fix_json_str() 修复裸换行符/断裂数字

    新增:
    - 双数组扫描: characters 闭合后自动切换到 scenes
    - 增量扫描位置 _scan_pos 避免重复扫描已处理区域
    """

    def __init__(self):
        self.buffer = ""
        self.found_chars = []       # 已提取的角色对象
        self.found_scenes = []      # 已提取的叙事场景对象
        self._chars_closed = False  # characters 数组是否已闭合
        self._scenes_closed = False # scenes 数组是否已闭合
        self._scan_pos = 0         # 增量扫描起始位置

        # 当前正在扫描的数组状态
        self._in_array = False      # 是否已进入数组
        self._array_key = None      # 当前数组的 key ("characters" / "scenes")
        self._obj_start = -1        # 当前对象的起始位置
        self._depth = 0             # 大括号嵌套深度

    def feed(self, chunk: str) -> dict:
        """喂入一个流式 chunk，返回本次新发现的资产。

        Returns:
            {"characters": [...new_chars], "scenes": [...new_scenes]}
        """
        self.buffer += chunk
        self.buffer = self._clean(self.buffer)
        result = {"characters": [], "scenes": []}

        if not self._chars_closed:
            new_chars = self._scan_array("characters")
            result["characters"] = new_chars
            self.found_chars.extend(new_chars)

        if self._chars_closed and not self._scenes_closed:
            new_scenes = self._scan_array("scenes")
            result["scenes"] = new_scenes
            self.found_scenes.extend(new_scenes)

        return result

    def _scan_array(self, key: str) -> list[dict]:
        """通用数组扫描 — 从 _scan_pos 开始，寻找完整的 JSON 对象。"""
        found = []
        buf = self.buffer
        pos = self._scan_pos

        while pos < len(buf):
            ch = buf[pos]

            if not self._in_array:
                marker = f'"{key}"'
                idx = buf.find(marker, pos)
                if idx < 0:
                    break
                bracket_pos = buf.find('[', idx + len(marker))
                if bracket_pos < 0:
                    break
                self._in_array = True
                self._array_key = key
                pos = bracket_pos + 1
                continue

            if ch == '{':
                if self._depth == 0:
                    self._obj_start = pos
                self._depth += 1
            elif ch == '}':
                self._depth -= 1
                if self._depth == 0 and self._obj_start >= 0:
                    obj_str = buf[self._obj_start:pos + 1]
                    obj_str = self._fix_json_str(obj_str)
                    try:
                        obj = json.loads(obj_str, strict=False)
                        found.append(obj)
                    except json.JSONDecodeError:
                        pass
                    self._obj_start = -1
            elif ch == ']' and self._depth == 0:
                self._in_array = False
                self._array_key = None
                if key == "characters":
                    self._chars_closed = True
                elif key == "scenes":
                    self._scenes_closed = True
                pos += 1
                break
            pos += 1

        self._scan_pos = pos
        return found

    @staticmethod
    def _clean(text: str) -> str:
        text = re.sub(r'<think>[\s\S]*?</think>', '', text)
        text = re.sub(r'\[Agent \d+\]\[AgentThink\][^\n]*\n?', '', text)
        idx = text.rfind('<think>')
        if idx >= 0 and '</think>' not in text[idx:]:
            text = text[:idx]
        return text

    @staticmethod
    def _fix_json_str(s: str) -> str:
        s = re.sub(r'(?<=": ")(.*?)(?=")',
                   lambda m: m.group(0).replace('\n', '\\n'),
                   s, flags=re.DOTALL)
        return s
```

### 3.4 叙事场景 Schema

每个叙事场景导出为独立文件 `narrative_scenes/scene_001_高家正堂.json`：

```json
{
  "scene_id": "scene_001",
  "order": 0,
  "heading": "INT. 高家正堂 - DAY",
  "location": "高家正堂",
  "time_of_day": "day",
  "characters_present": ["高令宁", "沈词"],
  "core_event": "高家接受沈家求亲，以木雁为聘",
  "key_dialogue": "「沈家六礼已备，求娶高家嫡女令宁」",
  "emotional_peak": "高令宁屏风后偷看聘礼时的期待与忐忑",
  "tension_score": 0.85,
  "estimated_duration_s": 240,
  "key_props": ["木雁", "聘礼箱笼", "大红帖子", "屏风"],
  "dramatic_purpose": "建立两家联姻的叙事起点，暗示门第差距"
}
```

**与 v1 场景 schema 的区别：**
- 新增 `order` 字段（整数，从 0 开始，严格按故事时间线排序）
- 场景是**叙事事件**，同一地点可以有多个场景
- 输出到 `narrative_scenes/` 而非 `scenes/`

### 3.5 提示词调整

在 `COMBINED_SYSTEM` 末尾追加：

```
重要：先输出完整的角色数组，再输出完整的场景数组，合在一个JSON对象中。
场景必须按故事发生的时间顺序排列，每个场景是一个独立的叙事事件。
同一个地点如果发生了不同的事件，应该拆分为多个场景。
场景数组中每个场景的 key_props 要尽量详细列出所有可见道具。
每个场景必须包含 order 字段（从0开始的整数），标记其在时间线上的位置。
```

`COMBINED_USER` 中场景 schema 增加 `order` 字段：

```json
"scenes": [
  {
    "scene_id": "scene_001",
    "order": 0,
    "heading": "INT/EXT. 地点 - 时间",
    "location": "具体地点",
    "time_of_day": "day|night|dawn|dusk",
    "characters_present": ["角色1", "角色2"],
    "core_event": "核心事件",
    "key_dialogue": "最关键台词",
    "emotional_peak": "情绪峰值",
    "tension_score": 0.5,
    "estimated_duration_s": 60,
    "key_props": ["关键道具"],
    "dramatic_purpose": "戏剧功能"
  }
]
```

### 3.6 渐进导出逻辑（test_mode_c 中）

```python
async def test_mode_c(model_key, model_friendly, novel, out_dir, tracker):
    """Mode C 完整资产提取管线。"""
    chars_dir = ensure_dir(out_dir, "characters")
    scenes_dir = ensure_dir(out_dir, "narrative_scenes")

    parser = ProgressiveAssetParser()
    char_count = 0
    scene_count = 0

    # --- 阶段 1: 流式渐进解析 ---
    async for chunk in stream_api_call(...):
        result = parser.feed(chunk)

        for char_obj in result["characters"]:
            name = char_obj.get("name", f"unnamed_{char_count}")
            filename = f"char_{char_count:02d}_{safe_filename(name)}.json"
            save_json(chars_dir, filename, char_obj)
            print(f"    → 导出角色: {name}")
            char_count += 1

        for scene_obj in result["scenes"]:
            loc = scene_obj.get("location", f"unnamed_{scene_count}")
            scene_id = f"scene_{scene_count:03d}"
            scene_obj["scene_id"] = scene_id
            if "order" not in scene_obj:
                scene_obj["order"] = scene_count
            event = scene_obj.get("core_event", "")
            filename = f"{scene_id}_{safe_filename(loc)}.json"
            save_json(scenes_dir, filename, scene_obj)
            print(f"    → 导出叙事场景: [{scene_id}] {loc} — {event[:30]}")
            scene_count += 1

    # 生成时间线索引
    timeline = {
        "total_scenes": scene_count,
        "scenes": [
            {
                "scene_id": s.get("scene_id", f"scene_{i:03d}"),
                "order": s.get("order", i),
                "location": s.get("location", ""),
                "core_event": s.get("core_event", ""),
                "characters_present": s.get("characters_present", []),
            }
            for i, s in enumerate(parser.found_scenes)
        ],
    }
    save_json(scenes_dir, "_timeline.json", timeline)

    print(f"  阶段1完成: {char_count} 角色, {scene_count} 叙事场景")

    # --- 阶段 2: 后处理 ---
    await run_phase2(parser.found_chars, parser.found_scenes,
                     novel, model_key, tracker, out_dir)

    # --- 阶段 3: 变体生成 ---
    await run_phase3(parser.found_chars, parser.found_scenes,
                     model_key, tracker, out_dir)
```

---

## 四、阶段 2：场景资产卡生成 + 道具收集 + 道具卡生成

### 4.1 场景资产卡生成（2A）— 全新流程

**这不是"去重"，而是一个派生/聚合 + AI 生成流程。**

- Step 1（本地计算）：按 `location` 分组所有叙事场景
- Step 2（本地计算）：为每个唯一地点，收集所有关联的视觉线索（时间段、道具、人物、氛围）
- Step 3（AI 调用）：将分组结果 + 小说原文段落发送给 AI，生成每个地点的视觉资产卡

**场景资产卡 Schema：**

```json
{
  "location_id": "loc_001",
  "name": "高家正堂",
  "type": "interior|exterior|mixed",
  "era_style": "明代中晚期官宦府邸",
  "description": "建筑/装饰/家具布局详细描述",
  "visual_reference": "English AI art prompt",
  "atmosphere": "庄重肃穆",
  "color_palette": ["朱红", "檀木色", "金黄"],
  "lighting": "自然光从门窗射入",
  "key_features": ["高悬匾额", "条案香炉", "太师椅"],
  "narrative_scenes": ["scene_001", "scene_007", "scene_015"],
  "scene_count": 3,
  "time_variations": ["day", "night"],
  "emotional_range": "庄重→紧张→悲伤"
}
```

**输出目录：** `locations/`

```python
from collections import defaultdict

def group_scenes_by_location(narrative_scenes: list[dict]) -> dict:
    """按 location 分组叙事场景，收集视觉线索。

    Returns:
        {
            "高家正堂": {
                "scene_ids": ["scene_001", "scene_007"],
                "time_variations": ["day", "night"],
                "all_props": ["木雁", "屏风", ...],
                "all_characters": ["高令宁", "沈词", ...],
                "events": ["求亲", "争执"],
                "emotional_peaks": ["期待", "愤怒"],
            },
            ...
        }
    """
    groups = defaultdict(lambda: {
        "scene_ids": [],
        "time_variations": set(),
        "all_props": set(),
        "all_characters": set(),
        "events": [],
        "emotional_peaks": [],
    })

    for scene in narrative_scenes:
        loc = scene.get("location", "未知地点")
        g = groups[loc]
        g["scene_ids"].append(scene.get("scene_id", ""))
        g["time_variations"].add(scene.get("time_of_day", ""))
        g["all_props"].update(scene.get("key_props", []))
        g["all_characters"].update(scene.get("characters_present", []))
        g["events"].append(scene.get("core_event", ""))
        g["emotional_peaks"].append(scene.get("emotional_peak", ""))

    # Convert sets to sorted lists for JSON serialization
    for g in groups.values():
        g["time_variations"] = sorted(g["time_variations"])
        g["all_props"] = sorted(g["all_props"])
        g["all_characters"] = sorted(g["all_characters"])

    return dict(groups)
```

**新增提示词：**

```python
LOCATION_CARD_SYSTEM = """你是一位影视美术指导，精通场景设计和 AI 视觉档案构建。
你需要为每个拍摄地点生成精确的视觉描述，使其可直接用于 AI 绘图生成一致的场景图。
重点关注：建筑风格、空间布局、装饰细节、光线氛围、色彩基调。
所有输出严格JSON格式，不要输出其他内容。"""

LOCATION_CARD_USER = """为以下拍摄地点生成视觉档案。

每个地点在故事中出现的场景汇总：
{location_groups_json}

小说相关段落（供参考环境描写）：
{relevant_text_snippets}

返回JSON数组，每个地点一个对象：
[
  {{
    "location_id": "loc_001",
    "name": "地点名",
    "type": "interior|exterior|mixed",
    "era_style": "时代风格（年代+建筑类型）",
    "description": "详细环境描述（建筑结构/装饰/家具/摆设/空间感）",
    "visual_reference": "English AI art prompt, detailed, specific architectural style and era",
    "atmosphere": "整体氛围关键词",
    "color_palette": ["主色调1", "主色调2", "主色调3"],
    "lighting": "光线特征描述",
    "key_features": ["标志性视觉元素1", "元素2", "元素3"],
    "narrative_scenes": ["scene_001", "scene_007"],
    "scene_count": 2,
    "time_variations": ["day", "night"],
    "emotional_range": "场景跨度的情绪变化"
  }}
]

规则：
1. description 必须包含空间结构、装饰细节、家具布局等具体视觉信息
2. visual_reference 必须是英文，适合直接喂给 Midjourney/DALL-E
3. era_style 要尽量具体（如"明代中晚期官宦府邸"而非笼统的"古代中国"）
4. color_palette 最少 3 个色调
5. key_features 是该地点最具辨识度的视觉元素
6. emotional_range 描述该地点在不同场景中承载的情绪跨度
"""
```

**调用方式：** `call_api_async()` 单次批量请求（地点数量少，响应快）。

```python
async def generate_location_cards(narrative_scenes, novel, model_key, tracker, out_dir):
    """阶段2A: 场景资产卡生成。"""
    locations_dir = ensure_dir(out_dir, "locations")

    # Step 1: 按 location 分组
    groups = group_scenes_by_location(narrative_scenes)
    print(f"    地点分组: {len(groups)} 个唯一地点")

    if not groups:
        print(f"    无地点信息，跳过场景资产卡生成")
        return []

    # Step 2: 收集相关小说段落
    snippets = []
    for loc_name in groups:
        for m in re.finditer(re.escape(loc_name), novel):
            start = max(0, m.start() - 150)
            end = min(len(novel), m.end() + 150)
            snippets.append(f"[{loc_name}] ...{novel[start:end]}...")
            if len(snippets) >= 30:
                break
        if len(snippets) >= 30:
            break

    # Step 3: AI 生成场景资产卡
    groups_json = json.dumps(
        {k: {**v, "time_variations": list(v["time_variations"]) if isinstance(v["time_variations"], set) else v["time_variations"]}
         for k, v in groups.items()},
        ensure_ascii=False, indent=2
    )

    resp, cost = await smart_call(
        model_key,
        LOCATION_CARD_SYSTEM,
        LOCATION_CARD_USER.format(
            location_groups_json=groups_json,
            relevant_text_snippets="\n".join(snippets[:30]),
        ),
        temperature=0.5,
        max_tokens=8192,
    )
    tracker.add(stage=12, cost_meta=cost)  # stage 12 = 场景资产卡

    location_cards = []
    try:
        cards = extract_json(resp)
        if not isinstance(cards, list):
            cards = [cards]

        for i, card in enumerate(cards):
            loc_id = card.get("location_id", f"loc_{i+1:03d}")
            if not card.get("location_id"):
                card["location_id"] = loc_id
            name = card.get("name", f"unnamed_{i}")
            filename = f"{loc_id}_{safe_filename(name)}.json"
            save_json(locations_dir, filename, card)
            location_cards.append(card)

        # 生成索引
        index = {
            "total_locations": len(location_cards),
            "locations": [
                {
                    "location_id": c.get("location_id"),
                    "name": c.get("name"),
                    "scene_count": c.get("scene_count", 0),
                    "narrative_scenes": c.get("narrative_scenes", []),
                }
                for c in location_cards
            ],
        }
        save_json(locations_dir, "_index.json", index)

        print(f"    场景资产卡: {len(location_cards)} 张")
    except Exception as e:
        print(f"    ⚠ 场景资产卡解析失败: {e}")
        save_text(locations_dir, "_location_card_error.txt", f"{e}\n\n{resp[:2000]}")

    return location_cards
```

### 4.2 道具收集与分层（2B）

**数据源从"去重场景"改为"全部叙事场景"。**

```python
from collections import Counter, defaultdict

def collect_and_tier_props(narrative_scenes: list[dict]) -> dict:
    """从全部叙事场景收集道具，按出现次数分层。

    注意：数据源是 narrative_scenes（叙事场景），不是去重后的场景。
    同一地点的多个叙事场景中的道具都会被计入。

    规则:
    - 出现 ≥3 次 → major (需要完整视觉档案卡)
    - 出现 <3 次 → minor (仅记录名称+关联场景)

    Returns:
        {
            "major": {"木雁": {"count": 5, "scenes": ["scene_001", ...]}},
            "minor": {"茶杯": {"count": 1, "scenes": ["scene_003"]}},
            "total_unique": 15,
            "major_count": 3,
            "minor_count": 12
        }
    """
    prop_counter = Counter()
    prop_scenes = defaultdict(list)

    for scene in narrative_scenes:
        scene_id = scene.get("scene_id", "")
        for prop in scene.get("key_props", []):
            prop = prop.strip()
            if not prop:
                continue
            prop_counter[prop] += 1
            if scene_id not in prop_scenes[prop]:
                prop_scenes[prop].append(scene_id)

    major_props = {
        p: {"count": c, "scenes": prop_scenes[p]}
        for p, c in prop_counter.items() if c >= 3
    }
    minor_props = {
        p: {"count": c, "scenes": prop_scenes[p]}
        for p, c in prop_counter.items() if c < 3
    }

    return {
        "major": major_props,
        "minor": minor_props,
        "total_unique": len(prop_counter),
        "major_count": len(major_props),
        "minor_count": len(minor_props),
    }
```

### 4.3 道具卡生成提示词（2C）

不变，仅对 major 道具调用 AI 生成完整视觉档案卡。

```python
PROP_CARD_SYSTEM = """你是一位影视道具设计师，精通叙事道具设计和 AI 视觉档案构建。
你需要为每个道具生成精确的视觉描述，使其可直接用于 AI 绘图生成一致的道具图。
所有输出严格JSON格式，不要输出其他内容。"""

PROP_CARD_USER = """为以下重要道具生成视觉档案。

道具列表及出场场景：
{prop_list_with_scenes}

小说相关段落（供参考）：
{relevant_text_snippets}

返回JSON数组，每个道具一个对象：
[
  {{
    "name": "道具名",
    "category": "costume|weapon|furniture|document|food|container|symbolic|jewelry|stationery|medical",
    "description": "外观描述（材质、颜色、尺寸、工艺细节）",
    "visual_reference": "English AI art prompt, detailed, specific style and era",
    "narrative_function": "叙事功能（推动情节 / 揭示角色 / 建立象征 / 承载情感）",
    "is_motif": true,
    "scenes_present": ["scene_001", "scene_005"],
    "emotional_association": "与此道具关联的核心情感"
  }}
]

规则：
1. description 必须包含材质、颜色、尺寸、做工等具体视觉信息
2. visual_reference 必须是英文，适合直接喂给 Midjourney/DALL-E
3. narrative_function 要结合小说上下文分析
4. is_motif 只有反复出现且承载象征意义的道具才为 true
"""
```

### 4.4 阶段2 管线函数

```python
async def run_phase2(characters, narrative_scenes, novel, model_key, tracker, out_dir):
    """阶段2: 场景资产卡 + 道具收集 + 道具卡生成。"""
    print(f"\n  阶段2: 后处理...")

    # 2A: 场景资产卡生成（取代原来的场景去重）
    location_cards = await generate_location_cards(
        narrative_scenes, novel, model_key, tracker, out_dir)

    # 2B: 道具收集分层（从全部叙事场景收集）
    props_dir = ensure_dir(out_dir, "props")
    prop_data = collect_and_tier_props(narrative_scenes)
    save_json(props_dir, "prop_index.json", prop_data)
    print(f"    道具: {prop_data['total_unique']} 种 "
          f"(major: {prop_data['major_count']}, minor: {prop_data['minor_count']})")

    # 2C: 道具卡生成（仅 major）
    if prop_data["major"]:
        prop_list_str = json.dumps(prop_data["major"], ensure_ascii=False, indent=2)
        snippets = []
        for prop_name in prop_data["major"]:
            for m in re.finditer(re.escape(prop_name), novel):
                start = max(0, m.start() - 100)
                end = min(len(novel), m.end() + 100)
                snippets.append(f"[{prop_name}] ...{novel[start:end]}...")
                if len(snippets) >= 20:
                    break
            if len(snippets) >= 20:
                break

        resp, cost = await smart_call(
            model_key,
            PROP_CARD_SYSTEM,
            PROP_CARD_USER.format(
                prop_list_with_scenes=prop_list_str,
                relevant_text_snippets="\n".join(snippets[:20]),
            ),
            temperature=0.5,
            max_tokens=8192,
        )
        tracker.add(stage=10, cost_meta=cost)

        try:
            prop_cards = extract_json(resp)
            if not isinstance(prop_cards, list):
                prop_cards = [prop_cards]
            for card in prop_cards:
                name = card.get("name", "unnamed")
                save_json(props_dir, f"prop_major_{safe_filename(name)}.json", card)
            print(f"    道具卡: {len(prop_cards)} 张")
        except Exception as e:
            print(f"    ⚠ 道具卡解析失败: {e}")
            save_text(props_dir, "_prop_card_error.txt", f"{e}\n\n{resp[:2000]}")
    else:
        print(f"    无 major 道具，跳过道具卡生成")

    return location_cards
```

---

## 五、阶段 3：角色变体生成

### 5.1 触发条件

对每个满足以下任一条件的角色触发变体生成：
- `role` 为 `protagonist` 或 `antagonist`
- `role` 为 `supporting` 且出场场景 ≥ 5

**出场统计基于叙事场景 (narrative_scenes)，不是场景资产卡。**

### 5.2 变体提示词

```python
VARIANT_SYSTEM = """你是一位角色概念设计师，基于主设定形象为角色创建不同状态/时期/风格的衍生形象。
每个变体需要标注对应出场场景和与主设定的差异。
所有输出严格JSON格式，不要输出其他内容。"""

VARIANT_USER = """基础角色设定：
{character_card_json}

该角色出场的所有叙事场景：
{character_scenes_json}

分析该角色在不同场景中的状态变化，生成衍生形象。

规则：
1. 只生成有明确文本依据的变体（不要凭空创造）
2. 每个变体标注具体差异和对应场景
3. visual_reference 必须能直接用于 AI 绘图
4. 至少生成 2 个变体，最多 6 个

返回JSON数组：
[
  {{
    "variant_id": "char_name_variant_01",
    "variant_type": "childhood|wedding|pregnant|injured|formal|casual|battle|aged|disguised|emotional_state",
    "variant_name": "高令宁 — 少女时期",
    "tags": ["少女", "未嫁", "活泼"],
    "scene_ids": ["scene_001", "scene_003"],
    "trigger": "出场背景描述（何时何地出现这个状态）",
    "appearance_delta": {{
      "face": "与主设定的面部差异",
      "body": "体型差异",
      "hair": "发型差异",
      "distinguishing_features": "此状态的标志特征"
    }},
    "costume_override": {{
      "outfit": "此状态的具体着装",
      "color_palette": ["色调1", "色调2"]
    }},
    "visual_reference": "English AI art prompt for this specific variant, detailed",
    "emotional_tone": "此变体的核心情绪基调"
  }}
]"""
```

### 5.3 调用策略

```python
async def run_phase3(characters, narrative_scenes, model_key, tracker, out_dir):
    """阶段3: 角色变体生成。基于叙事场景统计出场次数。"""
    print(f"\n  阶段3: 角色变体生成...")

    eligible_chars = []
    for char in characters:
        role = char.get("role", "")
        name = char.get("name", "")

        # 统计出场叙事场景数（不是地点数）
        scene_count = sum(
            1 for s in narrative_scenes
            if name in s.get("characters_present", [])
        )

        if role in ("protagonist", "antagonist"):
            eligible_chars.append((char, scene_count))
        elif role == "supporting" and scene_count >= 5:
            eligible_chars.append((char, scene_count))

    if not eligible_chars:
        print(f"    无符合条件的角色，跳过变体生成")
        return

    print(f"    符合条件: {len(eligible_chars)} 个角色")

    variants_dir = ensure_dir(out_dir, "variants")
    variant_sem = asyncio.Semaphore(2)

    async def gen_variant(char, scene_count):
        name = char.get("name", "unnamed")
        char_scenes = [
            s for s in narrative_scenes
            if name in s.get("characters_present", [])
        ]

        async with variant_sem:
            resp, cost = await smart_call(
                model_key,
                VARIANT_SYSTEM,
                VARIANT_USER.format(
                    character_card_json=json.dumps(char, ensure_ascii=False, indent=2),
                    character_scenes_json=json.dumps(char_scenes, ensure_ascii=False, indent=2),
                ),
                temperature=0.6,
                max_tokens=8192,
            )
            tracker.add(stage=11, cost_meta=cost)

        try:
            variants = extract_json(resp)
            if not isinstance(variants, list):
                variants = [variants]
            for v in variants:
                v_type = v.get("variant_type", "unknown")
                filename = f"variant_{safe_filename(name)}_{safe_filename(v_type)}.json"
                save_json(variants_dir, filename, v)
            print(f"    → {name}: {len(variants)} 个变体")
            return variants
        except Exception as e:
            print(f"    ⚠ {name} 变体解析失败: {e}")
            save_text(variants_dir, f"_error_{safe_filename(name)}.txt",
                      f"{e}\n\n{resp[:2000]}")
            return []

    tasks = [gen_variant(char, sc) for char, sc in eligible_chars]
    all_variants = await asyncio.gather(*tasks, return_exceptions=True)

    total = sum(len(v) for v in all_variants if isinstance(v, list))
    print(f"    变体总计: {total} 个")
```

### 5.4 并发控制

- 角色之间可以并发，但通过 `variant_sem = asyncio.Semaphore(2)` 限制最多 2 个同时请求
- 与模型适配器层的 `_semaphore`（全局 8 并发）形成两级限流

---

## 六、资产清单 manifest.json

管线结束后生成 `manifest.json`，汇总所有产出物：

```python
def build_manifest(out_dir, characters, narrative_scenes, location_cards,
                   prop_data, variants, cost_data):
    """生成资产清单索引。"""
    manifest = {
        "version": "mode_c_v2",
        "generated_at": now_iso(),
        "summary": {
            "characters": len(characters),
            "narrative_scenes": len(narrative_scenes),
            "locations": len(location_cards),
            "props_total": prop_data.get("total_unique", 0),
            "props_major": prop_data.get("major_count", 0),
            "props_minor": prop_data.get("minor_count", 0),
            "variants": len(variants),
        },
        "directories": {
            "characters": "characters/",
            "narrative_scenes": "narrative_scenes/",
            "locations": "locations/",
            "props": "props/",
            "variants": "variants/",
        },
        "files": {
            "timeline": "narrative_scenes/_timeline.json",
            "location_index": "locations/_index.json",
            "props_index": "props/prop_index.json",
            "manifest": "manifest.json",
        },
        "cost": cost_data,
    }
    save_json(out_dir, "manifest.json", manifest)
    return manifest
```

**Schema：**
```json
{
  "version": "mode_c_v2",
  "generated_at": "2026-03-10T15:30:00",
  "summary": {
    "characters": 8,
    "narrative_scenes": 20,
    "locations": 7,
    "props_total": 25,
    "props_major": 4,
    "props_minor": 21,
    "variants": 9
  },
  "directories": {
    "characters": "characters/",
    "narrative_scenes": "narrative_scenes/",
    "locations": "locations/",
    "props": "props/",
    "variants": "variants/"
  }
}
```

---

## 七、输出文件结构

```
第10轮测试结果/{model}/
  ├─ characters/
  │    ├─ char_00_高令宁.json       (角色主卡)
  │    ├─ char_01_沈词.json
  │    └─ ...
  ├─ narrative_scenes/              ← 叙事场景（有序时间线）
  │    ├─ scene_001_高家正堂.json   (叙事事件：求亲)
  │    ├─ scene_002_闺房.json       (叙事事件：待嫁)
  │    ├─ scene_003_高家正堂.json   (叙事事件：争执 — 同一地点!)
  │    └─ _timeline.json            (场景时间线索引)
  ├─ locations/                     ← 场景资产卡（唯一地点视觉描述）
  │    ├─ loc_001_高家正堂.json     (融合了所有在此发生的事件线索)
  │    ├─ loc_002_闺房.json
  │    └─ _index.json               (地点索引)
  ├─ props/
  │    ├─ prop_major_木雁.json      (完整视觉档案)
  │    ├─ prop_major_身契.json
  │    └─ prop_index.json           (全部道具清单 + 分层标记)
  ├─ variants/
  │    ├─ variant_高令宁_childhood.json
  │    ├─ variant_高令宁_wedding.json
  │    └─ ...
  ├─ manifest.json                  (资产清单索引)
  └─ results.json                   (测试指标)
```

---

## 八、需要修改的文件

| 文件 | 改动项 | 详情 |
|------|--------|------|
| `run_test_round10.py` | 解析器重构 | `ProgressiveCharacterParser` → `ProgressiveAssetParser`（多相扫描） |
| | 提示词更新 | `COMBINED_SYSTEM/USER` 增加叙事场景排序要求 + `order` 字段 |
| | 新增提示词 | `LOCATION_CARD_SYSTEM/USER` + `PROP_CARD_SYSTEM/USER` + `VARIANT_SYSTEM/USER` |
| | 新增函数 | `group_scenes_by_location()` — 按地点分组叙事场景 |
| | 新增函数 | `generate_location_cards()` — 场景资产卡生成 |
| | 新增函数 | `collect_and_tier_props()` — 道具收集分层 |
| | 新增管线 | `run_phase2()` — 场景资产卡 + 道具收集 + 道具卡生成 |
| | 新增管线 | `run_phase3()` — 角色变体生成 |
| | 新增函数 | `build_manifest()` — 资产清单索引 |
| | 修改函数 | `test_mode_c()` — 使用新解析器 + 导出到 `narrative_scenes/` + 调用阶段2/3 |
| | 删除函数 | `dedup_scenes()`, `is_same_scene()`, `pick_richest()` — 不再需要 |

---

## 九、验证方法

```bash
# 1. 跑单模型完整管线
py -3.14 run_test_round10.py --only grok --mode C

# 2. 验证叙事场景有序
cat 第10轮测试结果/grok/narrative_scenes/_timeline.json
# scene_001.order < scene_002.order < ...

# 3. 验证场景资产卡 ≠ 叙事场景
ls 第10轮测试结果/grok/narrative_scenes/   # 数量 > locations
ls 第10轮测试结果/grok/locations/          # 唯一地点数

# 4. 验证同一地点多次出现
# 例如 "高家正堂" 在 narrative_scenes 中出现多次
# 但在 locations 中只有一张资产卡

# 5. 验证道具基于叙事场景
cat 第10轮测试结果/grok/props/prop_index.json
# scenes 列表包含 narrative scene IDs

# 6. 验证 manifest.json
cat 第10轮测试结果/grok/manifest.json
# summary 中有 narrative_scenes 和 locations 两个独立计数
```

---

## 十、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 模型不按 chars→scenes 顺序输出 | 解析器Phase2永远不激活 | 提示词强调顺序 + 检测兜底：流结束后 fallback 到完整JSON解析 |
| 模型不输出 order 字段 | 时间线索引无法排序 | 解析时自动填充：`if "order" not in scene: scene["order"] = scene_count` |
| 场景数组过长导致流式超时 | 丢失后半部分场景 | max_tokens 设大（32000）；超时后用已收到的部分 |
| 场景资产卡 AI 调用失败 | 无 locations 产出 | 独立 try/except，不阻断管线；错误信息存入 `_location_card_error.txt` |
| major 道具太少（<3个） | 道具卡阶段无产出 | 降低阈值到 2 次；或强制包含 narrative_function 标记为 symbolic 的道具 |
| 变体请求 429 限流 | 部分角色没有变体 | Semaphore(2) 限流 + 重试机制 + 失败不阻断管线 |
| 地点名不一致（同一地点不同叫法） | 分组遗漏 | 提示词要求地点名一致；后续可增加模糊匹配 |

---

## 十一、与现有 Pipeline 的关系

本方案是 Mode C（流式渐进模式）的**独立升级**，不影响 Mode A/B：

- `--mode C`：运行本方案的三阶段资产提取管线
- `--mode A`：运行分离式双指令管线
- `--mode B`：运行合并式单指令管线

共享基础设施：
- `model_adapters.py` — 模型适配层
- `extract_json()` — JSON 提取工具
- `safe_filename()` / `save_json()` / `ensure_dir()` — 文件工具
- `stream_api_call()` — 流式调用
- `smart_call()` — 智能调用（流式/非流式自动选择）
