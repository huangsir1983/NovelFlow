# 虚幻造物 — 端到端最佳实践流程（终极融合版）

> 版本: 2.0 | 日期: 2026-03-10
> 基于: Mode C 流式升级方案 v2 + 三方案决策融合 + 音频后处理重构
> 状态: **FINAL PLAN — 可执行蓝图**

---

## 零、决策方法论

本文档通过以下方法论，将三个 AI 方案融合为一份可落地的终极流程：

### 0.1 评估维度与权重

| 维度 | 权重 | 含义 |
|------|------|------|
| **可落地性 (Feasibility)** | 30% | 基于现有 Mode C 代码和技术栈，能否直接实现 |
| **用户心流 (Flow)** | 20% | 用户从导入到看到第一个可预览成果的体感速度 |
| **质量可控性 (Quality)** | 20% | 对 AI 生成物的质量控制、一致性保障能力 |
| **架构一致性 (Alignment)** | 15% | 与 PRD/newplan3 三段式架构、版本门控体系的契合度 |
| **成本效率 (Cost)** | 15% | Token 消耗、API 调用次数、并发效率 |

### 0.2 三方案评分矩阵

| 维度 | 方案一 (结构化五阶段) | 方案二 (终极最佳实践) | 方案三 (融合版 v8) | 权重 |
|------|---------------------|---------------------|-------------------|------|
| **可落地性** | ★★★★☆ (4) | ★★★☆☆ (3) | ★★★★★ (5) | 30% |
| **用户心流** | ★★★☆☆ (3) | ★★★★★ (5) | ★★★★★ (5) | 20% |
| **质量可控性** | ★★★☆☆ (3) | ★★★★★ (5) | ★★★★☆ (4) | 20% |
| **架构一致性** | ★★★☆☆ (3) | ★★★★☆ (4) | ★★★★★ (5) | 15% |
| **成本效率** | ★★★★☆ (4) | ★★★☆☆ (3) | ★★★★☆ (4) | 15% |
| **加权总分** | **3.45** | **4.00** | **4.70** | — |

### 0.3 融合策略

```
方案三 (融合版) = 主体骨架 (70%)
  + 方案二的"定妆拦截"、"单机位铁律"、"局部重绘" (20%)
  + 方案一的"智能合并推荐"、"质量评分"概念 (5%)
  + v2.0 新增: "音色后处理"替代"Audio First 直出" (5%)
```

**关键决策：**

| 决策点 | 方案一 | 方案二 | 方案三 | **最终采纳 (v2.0)** | 理由 |
|--------|--------|--------|--------|---------------------|------|
| 切场策略 | 语义切场 | 语义切场 | 语义切场 | ✅ 全部一致 | — |
| 剧本形态 | 轻量版剧本 | 轻量级 Scene Beats | 轻量版剧本 | **Scene Beats** | 比完整剧本轻 3-5×，足够驱动分镜 |
| 分镜合并 | 智能合并 | **绝不合并** | 智能合并建议 | **建议分组，不强制合并** | 方案二的"不合并"太绝对，但合并确实有风险；用"分组框"替代 |
| 时长锚定 | 无 | Audio First (TTS 锁定时长) | 无 | **TTS 估时锚定** | TTS 仍用于测量台词精确时长以锁定视频 duration，但不作为最终音频 |
| 最终配音 | — | TTS 直出 | — | **ComfyUI 音色替换** | I2V/T2V 生成的视频自带默认配音，时间位置不统一；后处理统一替换音色更可控 |
| 角色声音资产 | 无 | 无 | 无 | **✅ 新增 voice_description** | 为音色替换提供目标锚点，保证跨镜头声音一致性 |
| 视频生成策略 | 直出 | 先图后视频 (T2I → I2V) | 先图后视频 | **✅ T2I → I2V** | 废片率从 ~40% 降到 ~10% |
| 修复策略 | 重跑 | 局部重绘 Inpainting | Object Replacement | **局部重绘 + Object Replacement** | 方案二三互补 |
| 定妆时机 | 阶段一之后 | 阶段一与二之间 | 阶段一之后 | **阶段一结束后立即拦截** | 方案二的"定妆间掩盖算力"是天才设计 |
| 并发策略 | 阶段二并发 | 定妆期间暗中并发 | Haiku 8-16 并发 | **定妆期间暗中启动并发** | 用户体感 0 等待 |

### 0.4 v2.0 音频流程重构原因

v1.0 采纳的 "Audio First" 策略假设 TTS 生成的音频即为最终配音。但实际工程中存在核心矛盾：

```
问题:
  1. I2V (图生视频) 和 T2V (文生视频) 模型会生成自带配音的视频
  2. 不同模型/不同 Shot 生成的配音时间位置不一致
  3. 同一角色在不同 Shot 中的音色可能完全不同
  4. TTS 直出的声音无法与视频中角色的口型/动态精确匹配

解决:
  Video First + 音色后处理
  ├─ TTS 仅用于"测量台词时长" → 锁定视频 duration（保留 v1.0 的时长锚定优势）
  ├─ 视频生成后 → 声音分离（提取原始音轨）
  ├─ ComfyUI → 以角色 voice_description 为目标，音色替换
  └─ 替换后音轨 → 与视频重新合并
```

**核心优势**: 无论 I2V/T2V 生成了什么样的默认配音，最终都经过统一的音色替换管线，保证同一角色声音一致。

---

## 一、总体流程概览（9 步）

```
┌─────────────────────────────────────────────────────────────────┐
│                    Stage 1: 创作工坊 (Front Half)                │
│                                                                  │
│  步骤1: 全局解析与切场 ──→ 步骤2: 角色定妆拦截 ──→             │
│  步骤3: 并发剧本与分镜（定妆期间暗中执行）                       │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                    Stage 2: 执行画板 (Middle Stage)               │
│                                                                  │
│  步骤4: 智能分组与画板铺设 ──→ 步骤5: 关键帧打样与视频生成 ──→  │
│  步骤6: 连续性修复                                                │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                    Stage 3: 预演交付 (Back Half)                  │
│                                                                  │
│  步骤7: 音频后处理 ──→ 步骤8: 预演审片 ──→ 步骤9: 导出与迭代    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 音频数据流（贯穿全流程）

```
步骤1: 角色资产含 voice_description（声音锚点）
  │
步骤2: 用户可微调角色声音描述 / 上传参考音频
  │
步骤3: TTS 生成台词音频 → 仅用于测量精确时长 → 锁定 Shot duration
  │
步骤5: I2V 生成视频（自带默认配音，音色不可控）
  │
步骤7: ★ 音频后处理 ★
  │  ├─ 声音分离: 从生成视频中提取音轨
  │  ├─ 音色替换: ComfyUI 以 voice_description 为目标替换音色
  │  └─ 音视频合并: 替换后音轨 + 原始视频画面
  │
步骤8: 导演审片（画面+声音 完整预览）
```

### 耗时目标（1.3 万字小说，前 3 章）

| 步骤 | 耗时目标 | 核心输出 | 用户介入 | 关键技术 |
|------|---------|---------|---------|---------|
| 1. 全局解析与切场 | 15-30s | 角色库(含声音描述) + 叙事场景时间线 + 场景资产卡 | 低（等待） | Claude Opus + Prompt Cache + 流式渐进 |
| 2. 角色定妆拦截 | 用户主导 1-3min | 锁定角色视觉+声音锚点 (Reference Node) | **高** | 定妆面板 + AI 候选图 + 声音预览 |
| 3. 并发剧本与分镜 | 20-40s (暗中) | Shot Card + VFF V2 + TTS 时长锚点 | 低（定妆期间并行） | Haiku/Flash 8-16 并发 + TTS 估时 |
| 4. 智能分组与画板 | 5-10s | Clip Unit 分组 + 画板布局 | 中（确认/调整） | Grouping Node + TapNow 画板 |
| 5. 关键帧打样与生成 | 30-120s/Clip | 静态关键帧 → 视频片段(含默认音频) | 中（选图确认） | T2I → AI 质检 → I2V |
| 6. 连续性修复 | 10-30s | 修复后视频片段 | 低（自动/手动） | Object Replacement + Inpainting |
| 7. 音频后处理 | 15-45s | 音色统一的音轨 + 合并后视频 | 低（自动/可调） | ComfyUI 声音分离 + 音色替换 |
| 8. 预演审片 | 用户主导 3-8min | 完整时间线 + 批注 | **高** | 导演审片回路 |
| 9. 导出与迭代 | 30s | 最终视频 + CapCut 工程包 | 低 | 自动打包 |

**总首次可预览时间**: ≈ **60-120 秒**（用户定妆完毕即可看到第一批 Shot Card）

---

## 二、步骤 1：全局解析与切场（15-30s）

### 2.1 与 Mode C 的关系

本步骤直接继承 Mode C 流式升级方案 v2 的阶段 1-2，但扩展了输出范围：

```
Mode C 阶段1 (流式渐进)
  → 角色主卡 (characters/) — v2.0 新增 voice_description
  → 叙事场景 (narrative_scenes/ — 有序时间线)

Mode C 阶段2A (场景资产卡)
  → 场景资产卡 (locations/)

Mode C 阶段2B/2C (道具)
  → 道具索引 + 道具卡 (props/)

[新增] 全局元数据
  → 世界观摘要 (worldview_summary)
  → 时代/风格标签 (era_style_tags)
```

### 2.2 技术实现

```python
# 与 Mode C run_test_round10.py 的映射
async def step1_global_analysis(novel_text, model_key):
    """步骤1: 全局解析 — 直接复用 Mode C 阶段1+2"""

    # === Mode C 阶段1: 流式渐进导出 ===
    characters, narrative_scenes, s1_meta = await _mode_c_stage1_streaming(
        model_key, novel_text, out_dir)
    # 产出: characters/ (含 voice_description), narrative_scenes/_timeline.json

    # === Mode C 阶段2A: 场景资产卡 ===
    location_cards, loc_cost = await generate_location_cards(
        narrative_scenes, novel_text, model_key, out_dir)
    # 产出: locations/_index.json

    # === Mode C 阶段2B: 道具收集 ===
    prop_data = collect_and_tier_props(narrative_scenes)
    # 产出: props/prop_index.json

    # === 新增: 世界观摘要（从角色+场景推导，无需额外 API 调用）===
    worldview = derive_worldview(characters, narrative_scenes, location_cards)

    return characters, narrative_scenes, location_cards, prop_data, worldview
```

### 2.3 角色声音描述（v2.0 新增）

角色主卡中新增 `voice_description` 字段，作为后续音色替换的目标锚点：

```json
{
  "name": "高令宁",
  "role": "protagonist",
  "gender": "female",
  "age_range": "16-18",
  "appearance": { "...": "原有外貌描述" },

  "voice_description": {
    "voice_type": "青年女声",
    "timbre": "清冷、略带沙哑",
    "pitch_range": "中高音",
    "speaking_pace": "语速偏慢，措辞考究",
    "accent": "官话正音，偶带吴侬软语",
    "emotional_markers": {
      "neutral": "平稳清冷，字句分明",
      "angry": "声音压低但字字带刺，气息加重",
      "sad": "尾音微颤，气息不稳，偶有哽咽",
      "happy": "难得上扬但仍克制，透出一丝暖意",
      "contempt": "语调拖长，尾音下压，带冷笑气息"
    },
    "reference_description_en": "Young woman, cool and slightly husky mezzo-soprano, measured aristocratic speech pattern with subtle Wu dialect inflections"
  }
}
```

**为什么需要声音描述**:
- **TTS 选声**: 根据 voice_type + timbre 选择最匹配的 TTS 声音
- **ComfyUI 音色替换**: reference_description_en 作为音色替换目标锚点
- **跨 Shot 一致性**: 无论视频模型生成了什么样的默认配音，音色替换统一到同一个目标
- **情绪分层**: emotional_markers 指导不同场景下的声音微调

### 2.4 叙事场景 vs 场景资产卡（核心概念，继承 Mode C v2）

| | 叙事场景 (Narrative Scene) | 场景资产卡 (Location Asset Card) |
|---|---|---|
| **数量** | 20-30 个 | 5-10 个唯一地点 |
| **排序** | 严格时间线（`order` 字段） | 无序（资产库条目） |
| **同一地点** | 多次出现 | 只出现一次 |
| **用途** | 故事骨架 → 步骤3拆分镜 | 视觉锚点 → 步骤5生成图片 |

### 2.5 输出数据结构

```
step1_output/
  ├─ characters/              (角色主卡 — 流式渐进，含 voice_description)
  │    ├─ char_00_高令宁.json
  │    └─ ...
  ├─ narrative_scenes/        (叙事场景 — 有序)
  │    ├─ scene_001_*.json
  │    └─ _timeline.json
  ├─ locations/               (场景资产卡 — 唯一地点)
  │    ├─ loc_001_*.json
  │    └─ _index.json
  ├─ props/                   (道具)
  │    ├─ prop_index.json
  │    └─ prop_major_*.json
  └─ worldview.json           (世界观摘要)
```

---

## 三、步骤 2：角色定妆拦截（用户主导 1-3min）

### 3.1 设计理念（采纳方案二）

> **"用高仪式感的交互掩盖后台算力时间，锁定视觉+声音资产。"**

这是方案二最精妙的设计：在用户饶有兴致地定妆时，后台已经在暗中并发执行步骤 3。

### 3.2 用户操作

```
┌─────────────────────────────────────────────────┐
│           角色定妆面板 (v2.0: 视觉+声音)          │
│                                                  │
│  AI 已为您识别出 8 位角色：                       │
│                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│  │  高令宁    │ │  沈词     │ │  陆姝仪   │        │
│  │  主角      │ │  男主     │ │  对手     │         │
│  │  [选脸]    │ │  [选脸]   │ │  [选脸]   │         │
│  │  [听声]    │ │  [听声]   │ │  [听声]   │         │
│  └──────────┘ └──────────┘ └──────────┘         │
│                                                  │
│  视觉风格: [古风水墨 v] [赛博朋克] [写实]         │
│  声音风格: [古典温婉 v] [现代干练] [AI自动]        │
│                                                  │
│  优先处理: [v 前3场] [ 高潮场] [ 全部]             │
│                                                  │
│             [ 开始制作 ]                          │
└─────────────────────────────────────────────────┘
```

### 3.3 系统行为

1. **前台**: 展示角色卡 + AI 生成的 3-5 张候选脸 + 声音预览（基于 voice_description 的 TTS 样本）
2. **后台（暗中）**: 用户开始定妆的瞬间，立即启动步骤 3 的并发管线
3. **锁定产出**:
   - 角色面孔 → 创建全局 **Visual Reference Node**（后续所有视觉生成的锚点）
   - 角色声音 → 锁定 **Voice Reference Node**（后续音色替换的目标锚点）

### 3.4 版本门控

| 版本 | 定妆能力 |
|------|---------|
| Normal | AI 自动选脸选声，用户一键确认 |
| Canvas | 选脸 + 选声 + 风格 + 优先场次 |
| Hidden | + 上传真人照/参考音频 + 自定义 LoRA + 声音克隆 |
| Ultimate | + 批量参考图管理 + 资产库导入 + 声音微调面板 |

---

## 四、步骤 3：并发剧本与分镜（20-40s，定妆期间暗中执行）

### 4.1 核心策略

```
叙事场景 (来自步骤1)
  │
  ├─ 每场独立指令 (并发 8-16 线程)
  │    ├─ 原文段落 + 角色库(含声音描述) + 场景资产卡
  │    ├─ → Scene Beats (轻量级剧本)
  │    └─ → Shot Card x N (单机位、单动作)
  │
  ├─ TTS 时长测量 (Duration Anchor)
  │    └─ 每个 Shot 的台词 → TTS 生成 → 测量精确时长 → 锁定 duration
  │         (注: 此 TTS 音频仅用于测时，不作为最终配音)
  │
  └─ 输出: Shot Card JSON + VFF V2 + 时长锚点
```

### 4.2 模型分层策略

| 任务 | 模型 | 理由 |
|------|------|------|
| 步骤1 全局解析 | Claude Opus / GPT-5.4 | 需要全文理解力 |
| 步骤3 剧本拆分 | Claude Haiku / Gemini Flash | 速度快、成本低、可大规模并发 |
| 步骤3 TTS 估时 | ElevenLabs / Azure TTS | 极速 <2s/句，仅用于测时 |
| 步骤5 T2I | Midjourney / FLUX / SD3 | 高质量静态图 |
| 步骤5 I2V | Kling 3.0 / Sora / Runway | 按镜头类型路由 |
| 步骤7 音色替换 | ComfyUI + RVC/SoVITS | 高质量音色转换 |

### 4.3 Shot Card Schema（VFF V2 扩展）

```json
{
  "shot_id": "shot_003_002",
  "scene_id": "scene_003",
  "order_in_scene": 1,
  "shot_type": "CLOSE-UP",
  "camera_movement": "STATIC",
  "duration_s": 4.2,
  "duration_locked": true,
  "duration_source": "tts_measurement",
  "characters": ["高令宁"],
  "action": "高令宁抬起头，眼中含泪但嘴角带着冷笑",
  "dialogue": "「我说了，木雁不够。」",
  "emotion": "冷傲中带悲伤",
  "visual_prompt_en": "Close-up of a young Chinese noblewoman in Ming dynasty silk robes, tears in eyes but cold smirk on lips, warm candlelight, cinematic lighting, 8K",
  "tts_duration_ref": "tts_ref/shot_003_002.wav",
  "reference_nodes": ["ref_高令宁_face_v1"],
  "voice_nodes": ["voice_高令宁_v1"],
  "location_id": "loc_001",
  "props": ["木雁"],
  "tension_score": 0.85,
  "quality_scores": null,
  "audio_status": "pending_post_process"
}
```

**与 v1.0 的区别**:
- `duration_source`: 从 `"tts_audio"` 改为 `"tts_measurement"`（强调 TTS 仅测时）
- `tts_duration_ref`: 替代 `audio_file`，明确这是测时参考而非最终音频
- `voice_nodes`: 新增，指向角色的 Voice Reference Node
- `audio_status`: 新增，追踪音频后处理状态 (`pending_post_process` → `separated` → `timbre_replaced` → `merged`)

### 4.4 TTS 时长锚定（v2.0 重构）

```
Shot Card 生成完毕
  → TTS 生成台词音频（用于测时，非最终配音）
  → 测量精确时长 (例: 3.8s)
  → 锁定 Shot duration 为 4s
  → 后续 I2V 生成严格遵守此时长
  → TTS 音频保存为 tts_ref/（供后续音色替换参考对比）
```

**与 v1.0 的关键区别**: v1.0 的 Audio First 将 TTS 音频直接作为最终配音。v2.0 认识到 I2V/T2V 生成的视频会自带配音（时间位置不统一、音色不可控），因此 TTS 仅用于精确测量台词时长，最终配音由步骤 7 的 ComfyUI 音色替换管线统一处理。

### 4.5 单机位铁律（采纳方案二，软化版）

> **每个 Shot Card = 一个独立镜头 = 单一机位 + 单一核心动作**

方案二提出"绝不合并分镜"，这在工程上是正确的（避免物体变异/粘连），但在用户体验上过于僵化。我们的折中：

- **生成阶段**: 严格单机位，不合并
- **展示阶段**: 用 Grouping Node 建议分组（步骤4），视觉上有聚合感但底层仍是独立 Shot
- **视频输出**: 通过剪辑切镜实现连贯感，不走长视频合并

---

## 五、步骤 4：智能分组与画板铺设（5-10s）

### 5.1 Grouping Node 逻辑

```python
def group_shots_into_clips(shots: list[dict]) -> list[dict]:
    """智能分组建议 — 不强制合并，只建议分组框。

    规则:
    1. 同一场景内的连续 Shot 归入同一 Clip Unit
    2. Clip Unit 总时长 <= 模型上限 (Kling 120s / Sora 60s)
    3. 跨场景必须拆分（时空跳转 = 新 Clip）
    4. 情绪峰值点前后建议拆分（用于剪辑节奏控制）
    """
```

### 5.2 画板布局（对接 Stage 2 TapNow 画板）

```
┌─────────────────────────────────────────────────────┐
│  Clip Unit 1: 高府正堂 — 求亲                         │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐        │
│  │ Shot 1  │ │ Shot 2  │ │ Shot 3  │ │ Shot 4  │     │
│  │ 全景    │ │ 中景    │ │ 特写    │ │ 反打    │      │
│  │ 4.0s   │ │ 3.2s   │ │ 4.2s   │ │ 2.8s   │       │
│  │ [预览]  │ │ [预览]  │ │ [预览]  │ │ [预览]  │      │
│  └────────┘ └────────┘ └────────┘ └────────┘        │
│  总时长: 14.2s | 模型: Kling 3.0 | 可直接生成         │
├─────────────────────────────────────────────────────┤
│  Clip Unit 2: 高令宁闺房 — 父女争执                   │
│  ┌────────┐ ┌────────┐ ┌────────┐                   │
│  │ Shot 5  │ │ Shot 6  │ │ Shot 7  │                 │
│  │ 中景    │ │ 过肩    │ │ 特写    │                  │
│  │ 5.1s   │ │ 3.5s   │ │ 4.8s   │                   │
│  └────────┘ └────────┘ └────────┘                   │
│  总时长: 13.4s | 模型: Sora | 可直接生成               │
└─────────────────────────────────────────────────────┘
```

---

## 六、步骤 5：关键帧打样与视频生成（30-120s/Clip）

### 6.1 T2I → 质检 → I2V 三段流（采纳方案二+三）

```
Shot Card
  │
  v
[T2I] 生成 4 张候选静态图
  │  ├─ 输入: visual_prompt_en + Visual Reference Node (角色脸模)
  │  └─ 输出: 4 张高质量关键帧
  │
  v
[AI 质检] 六维打分
  │  ├─ 角色一致性 / 构图 / 情绪 / 光照 / 道具准确 / 手部质量
  │  ├─ 废片折叠隐藏（变形、多指）
  │  └─ 推荐最优一张，标记 "助理推荐"
  │
  v
[用户确认] 选择关键帧
  │  ├─ Normal: 自动选推荐图
  │  ├─ Canvas+: 可对比 4 张，手动选择
  │  └─ Hidden+: 可唤出 Cinema Lab 微调（3D 相机、ARRI 镜头、姿势控制）
  │
  v
[I2V] 以选中图为首帧，生成固定时长视频
  │  ├─ 时长: 由 TTS 时长锚点锁定
  │  ├─ 模型: Model Router 自动选择
  │  │    ├─ 对话重 → Kling 3.0 (有原生唇同步)
  │  │    ├─ 动作重 → Sora / Luma
  │  │    └─ 长镜头 → Kling 3.0
  │  ├─ Visual Reference Node 注入角色一致性
  │  └─ 输出视频自带默认音频（音色不可控，将在步骤7统一处理）
  │
  v
生成完毕: 单个 Shot 视频片段 (含待处理音轨)
```

### 6.2 为什么先图后视频（决策依据）

| 策略 | 废片率 | 一致性 | 用户控制力 | 成本 |
|------|--------|--------|-----------|------|
| 直接 T2V | ~40% | 低 | 无（盲盒） | 高（重跑） |
| **T2I → I2V** | **~10%** | **高** | **强（选图确认）** | **低（局部重跑）** |

### 6.3 视频生成中的音频标注

每个生成的视频片段标记 `audio_status: "pending_post_process"`，表示其音轨尚未经过音色替换。步骤 7 将统一处理。

---

## 七、步骤 6：连续性修复（10-30s）

### 7.1 双重修复机制

**自动修复 (AI Agent)**:
- 一致性 Agent 自动检测跳轴、角色外观偏移、光照不连续
- 标记问题区域，建议重新生成

**手动修复 (用户触发)**:
- **Object Replacement**: 框选问题物体 → 保持其他元素不变 → 单独重生成
- **局部重绘 (Inpainting)**: 画笔涂抹问题区域 → 输入修复指令 → 只修该区域
- **Point-to-Edit**: 暂停播放 → 点击问题帧 → 跳回对应 Shot Card → 微调 → 重跑单个 Shot

注意：重新生成的视频同样标记 `audio_status: "pending_post_process"`，等待步骤 7 处理。

### 7.2 版本门控

| 版本 | 修复能力 |
|------|---------|
| Normal | AI 自动修复 + 简易重跑 |
| Canvas | + Object Replacement |
| Hidden | + Inpainting 画笔 + Point-to-Edit |
| Ultimate | + 批量修复 + 修复策略调试 |

---

## 八、步骤 7：音频后处理（15-45s）— v2.0 新增

### 8.1 设计理念

> **"视频生成管线只负责画面质量，声音一致性由独立的音频后处理管线统一保证。"**

I2V/T2V 模型生成的视频往往自带配音，但存在以下不可控因素：
- 不同模型（Kling/Sora/Luma）生成的配音风格各异
- 同一角色在不同 Shot 中的声音可能完全不一致
- 配音的时间位置（起止点）因模型而异
- 无法预先指定音色

音频后处理管线一次性解决以上所有问题。

### 8.2 三段式音频管线（ComfyUI）

```
步骤6 完成的视频片段（含不可控默认音轨）
  │
  v
[Stage A] 声音分离 (Audio Separation)
  │  ├─ 工具: UVR5 / Demucs / HTDemucs
  │  ├─ 输入: 视频片段
  │  ├─ 输出:
  │  │    ├─ vocal_track.wav    (人声轨)
  │  │    ├─ bgm_track.wav      (背景音乐轨)
  │  │    └─ sfx_track.wav      (音效轨)
  │  └─ 纯画面视频 video_silent.mp4
  │
  v
[Stage B] 音色替换 (Voice Timbre Replacement)
  │  ├─ 工具: RVC v2 / GPT-SoVITS / ComfyUI-Audio 节点
  │  ├─ 输入:
  │  │    ├─ vocal_track.wav (分离出的人声)
  │  │    ├─ voice_description (角色声音锚点)
  │  │    └─ voice_reference.wav (可选：用户上传的参考音频)
  │  ├─ 处理:
  │  │    ├─ 识别 vocal_track 中每段话的说话人
  │  │    ├─ 匹配 Shot Card 中的 characters 列表
  │  │    ├─ 对每个角色的语音段，按 voice_description 替换音色
  │  │    └─ 保持原始语速、情绪、音调起伏不变
  │  └─ 输出: vocal_replaced.wav (音色统一的人声轨)
  │
  v
[Stage C] 音视频合并 (Audio-Video Merge)
  │  ├─ 输入:
  │  │    ├─ video_silent.mp4   (纯画面)
  │  │    ├─ vocal_replaced.wav (替换后人声)
  │  │    ├─ sfx_track.wav      (原始音效，可保留/丢弃)
  │  │    └─ bgm: 步骤8自动铺设（不在此步处理）
  │  ├─ 合并策略:
  │  │    ├─ 人声轨: 使用 vocal_replaced
  │  │    ├─ 音效轨: 保留原始 sfx（如脚步声、环境音）
  │  │    └─ BGM: 留空，步骤8时间线拼装时统一铺设
  │  └─ 输出: shot_xxx_final.mp4 (audio_status: "merged")
  │
  v
所有 Shot 音频处理完毕 → 进入步骤8 预演审片
```

### 8.3 角色声音一致性保障

```
角色 voice_description (步骤1 提取)
  │
  ├─ 定妆阶段 (步骤2): 用户确认/微调 → 锁定 Voice Reference Node
  │
  ├─ 音色替换时: Voice Reference Node 作为目标
  │    ├─ 所有 Shot 中该角色的配音 → 统一替换为同一音色
  │    ├─ 即使原始视频中的默认配音完全不同
  │    └─ 也能输出一致的角色声音
  │
  └─ 跨 Clip Unit 验证: 一致性 Agent 抽检同一角色的声音相似度
```

### 8.4 ComfyUI 工作流示意

```
ComfyUI Workflow: audio_post_process.json
  │
  ├─ [输入节点]
  │    ├─ LoadVideo → 加载 Shot 视频
  │    ├─ LoadAudioRef → 加载 Voice Reference (角色声音锚点)
  │    └─ LoadShotCard → 读取 Shot Card JSON (角色列表、情绪)
  │
  ├─ [分离节点]
  │    └─ AudioSeparation (UVR5) → vocal / bgm / sfx
  │
  ├─ [替换节点]
  │    ├─ SpeakerDiarization → 说话人识别 (哪段话是谁说的)
  │    ├─ VoiceConversion (RVC/SoVITS) → 按角色替换音色
  │    │    ├─ 输入: vocal_segment + voice_reference
  │    │    ├─ 参数: pitch_shift, timbre_strength
  │    │    └─ 输出: converted_segment
  │    └─ EmotionPreserve → 保持原始情绪/语速/重音
  │
  ├─ [合并节点]
  │    ├─ AudioMerge → vocal_replaced + sfx → final_audio
  │    └─ VideoAudioMerge → silent_video + final_audio → output.mp4
  │
  └─ [输出节点]
       └─ SaveVideo → shot_xxx_final.mp4
```

### 8.5 批处理与并发

```python
async def step7_audio_post_process(all_shots: list[dict], voice_refs: dict):
    """步骤7: 音频后处理 — 批量并发处理所有 Shot"""

    sem = asyncio.Semaphore(4)  # ComfyUI 并发上限

    async def process_one_shot(shot):
        async with sem:
            # Stage A: 声音分离
            vocal, bgm, sfx, silent_video = await comfyui_separate(shot["video_path"])

            # Stage B: 音色替换
            for char_name in shot["characters"]:
                voice_ref = voice_refs[char_name]
                vocal = await comfyui_voice_convert(
                    vocal, voice_ref,
                    emotion=shot["emotion"]
                )

            # Stage C: 合并
            final_video = await comfyui_merge(silent_video, vocal, sfx)
            shot["video_path"] = final_video
            shot["audio_status"] = "merged"
            return shot

    results = await asyncio.gather(*[process_one_shot(s) for s in all_shots])
    return results
```

### 8.6 版本门控

| 版本 | 音频后处理能力 |
|------|--------------|
| Normal | AI 自动音色替换，无用户干预 |
| Canvas | + 角色声音预览 + 手动微调音色参数 |
| Hidden | + 上传参考音频 + 声音克隆 + 情绪微调 |
| Ultimate | + 多语种音色替换 + 自定义 ComfyUI 工作流 + 旁白独立控制 |

### 8.7 降级策略

| 情况 | 处理 |
|------|------|
| 视频无人声（纯动作/风景镜头） | 跳过 Stage B，仅保留 sfx |
| 分离质量差（人声/BGM 混叠） | 降级为 TTS 重新合成配音，用 TTS 时长参考对齐 |
| ComfyUI 不可用 | 降级为保留原始音频 + 提示用户手动处理 |
| 多角色同框对话 | SpeakerDiarization 按时间段切分，分别替换后拼接 |

---

## 九、步骤 8：预演审片（Stage 3）

### 9.1 时间线自动拼装

```
Clip Unit 1 (14.2s)  →  Clip Unit 2 (13.4s)  →  Clip Unit 3 (18.7s)  → ...
    │                       │                       │
    ├─ 人声轨（已音色替换）──┤                       │
    ├─ 音效轨 ──────────────┤                       │
    └─ BGM 自动铺设 ────────┴─ 音量自动调节 ────────┴─ 情绪匹配
```

### 9.2 导演审片回路（核心工作流）

```
看片 → 发现问题 → 结构化批注（节奏/表演/连续性/声音）
  │
  ├─ 一键跳回 Stage 2 对应 Shot Card
  ├─ 局部重跑画面（不影响其他 Shot）→ 自动触发步骤7音频后处理
  ├─ 局部重跑声音（仅重做音色替换，不重新生成视频）
  ├─ 新旧版本并排对比（画面+声音）
  └─ 七维评分差异高亮
```

### 9.3 质量评分系统（v2.0: 7 维）

| 维度 | 评分项 | 权重 |
|------|--------|------|
| 角色视觉一致性 | 脸部/服装/体型 跨镜头一致 | 20% |
| **角色声音一致性** | **同一角色跨 Shot 音色/语速/风格一致** | **15%** |
| 叙事连贯性 | 情节逻辑、时间线无跳跃 | 15% |
| 视觉质量 | 构图、光照、色彩和谐 | 15% |
| 情感表达 | 情绪峰值与音乐/节奏匹配 | 15% |
| 技术质量 | 无变形、无多指、无粘连 | 10% |
| 音画同步 | 口型、动作与音频对齐 | 10% |

**v2.0 变化**: 从六维升级为七维，新增"角色声音一致性"维度，原"音画同步"权重从 10% 不变但评判标准更严格（因为音色替换后需要重新验证同步性）。

---

## 十、步骤 9：导出与迭代

### 10.1 导出格式

| 格式 | 内容 | 适用版本 |
|------|------|---------|
| MP4 4K | 完整视频 + 内嵌字幕 + 统一音色配音 | Normal+ |
| CapCut 工程包 | Draft + 分轨素材（画面/人声/音效/BGM 独立轨道）+ 字幕轨 | Canvas+ |
| 宣发物料包 | 海报 + 预告片 + 角色卡 + 角色声音样本 | Hidden+ |
| 完整项目包 | 所有资产 + 流程模板 + ComfyUI 音频工作流 + 参数 | Ultimate |

**v2.0 分轨导出**: CapCut 工程包中，人声/音效/BGM 作为独立轨道导出，用户可在剪映中继续精调。

### 10.2 模板发布（TapTV 模式）

用户可将整套流程（角色库 + 声音描述 + Shot Card 布局 + Cinema Lab 参数 + ComfyUI 音频工作流）发布为模板，其他用户一键 Clone。

---

## 十一、与现有代码的对接关系

### 11.1 Mode C → 终极流程的映射

| Mode C 阶段 | 终极流程步骤 | 状态 |
|-------------|------------|------|
| 阶段1: 流式渐进导出 | 步骤1: 全局解析 (角色+叙事场景) | ✅ **已实现** (run_test_round10.py) |
| 阶段2A: 场景资产卡 | 步骤1: 全局解析 (locations) | ✅ **已实现** |
| 阶段2B/C: 道具 | 步骤1: 全局解析 (props) | ✅ **已实现** |
| 阶段3: 角色变体 | 步骤2: 定妆 (变体作为候选外观) | ✅ **已实现** |
| — | 步骤1: 角色 voice_description | 🔲 **待实现**（扩展角色提示词） |
| — | 步骤3: 并发剧本与分镜 | 🔲 **待实现** |
| — | 步骤4: 智能分组 | 🔲 **待实现** |
| — | 步骤5: T2I → I2V | 🔲 **待实现** |
| — | 步骤6: 连续性修复 | 🔲 **待实现** |
| — | 步骤7: 音频后处理 (ComfyUI) | 🔲 **待实现** |
| — | 步骤8-9: 审片/导出 | 🔲 **待实现** |

### 11.2 现有代码资产

```
已实现（可直接复用）:
  ├─ ProgressiveAssetParser      — 流式双相解析器
  ├─ stream_api_call()           — 流式 API 调用
  ├─ smart_call()                — 智能调用（流式/非流式）
  ├─ generate_location_cards()   — 场景资产卡生成
  ├─ collect_and_tier_props()    — 道具收集分层
  ├─ run_phase2()                — 阶段2管线编排
  ├─ run_phase3()                — 角色变体生成
  ├─ build_manifest()            — 资产清单
  └─ model_adapters.py           — 四模型适配层（ChatGPT/Claude/Gemini/Grok）

待实现:
  ├─ voice_description_prompt()  — 角色声音描述提示词（扩展阶段1提示词）
  ├─ scene_to_beats()            — 叙事场景 → Scene Beats
  ├─ beats_to_shots()            — Scene Beats → Shot Cards
  ├─ tts_measure_duration()      — TTS 台词时长测量（仅测时，非最终配音）
  ├─ group_shots()               — 智能分组
  ├─ t2i_candidates()            — 关键帧候选生成
  ├─ quality_scorer()            — 七维质量评分（含声音一致性）
  ├─ i2v_generate()              — 图生视频
  ├─ model_router()              — 视频模型路由
  ├─ consistency_checker()       — 连续性检测（视觉+声音）
  ├─ comfyui_audio_separate()    — ComfyUI 声音分离
  ├─ comfyui_voice_convert()     — ComfyUI 音色替换
  ├─ comfyui_audio_merge()       — ComfyUI 音视频合并
  ├─ speaker_diarization()       — 说话人识别
  └─ timeline_assembler()        — 时间线拼装（含分轨音频）
```

---

## 十二、R10 测试数据验证

### 12.1 步骤1 已通过四模型验证（2026-03-10）

| 模型 | 角色 | 叙事场景 | 场景资产卡 | 道具 | 变体 | 阶段1耗时 | 管线总耗时 |
|------|------|---------|-----------|------|------|----------|-----------|
| ChatGPT | 13 | 30 | 27 | 216 | 31 | 361s | 1005s |
| Claude | 10 | 14 | 9 | 49 | 15 | 102s | 241s |
| Gemini | 9 | 19 | 19 | 65 | 14 | 449s | 1297s |
| Grok | 8 | 14 | 14 | 14 | 13 | 102s | 266s |

### 12.2 生产环境推荐模型组合

| 步骤 | 推荐模型 | 备选 | 理由 |
|------|---------|------|------|
| 步骤1 全局解析 | Claude Opus | ChatGPT | Claude 最快(102s)且质量好 |
| 步骤1 声音描述 | Claude Opus | ChatGPT | 与角色提取合并，无额外调用 |
| 步骤3 并发分镜 | Claude Haiku x 16 | Gemini Flash | 成本最低、速度最快 |
| 步骤5 T2I | FLUX Pro | Midjourney | 角色一致性 + Reference Node 支持 |
| 步骤5 I2V | Kling 3.0 | Sora | 唇同步 + 长镜头支持 |
| 步骤7 音频分离 | UVR5 / Demucs | HTDemucs | 本地运行，无 API 成本 |
| 步骤7 音色替换 | RVC v2 | GPT-SoVITS | 高质量、低延迟、支持情绪保持 |

---

## 十三、边缘情况处理

| 情况 | 处理策略 |
|------|---------|
| 超长小说 (>30万字) | 先 semantic chunk 成 50-100 场，用户分批优先处理高潮部分，后台异步补全 |
| 用户中途修改小说 | 仅重跑受影响的场次（Prompt Cache 复用未变部分） |
| 预算敏感 (Normal) | 默认 Gemini Flash + 少候选；Canvas+ 才开 Kling/Sora 高质量 |
| TTS 语种不支持 | 降级为按字数估算时长（中文 3 字/秒） |
| 模型 429 限流 | Semaphore 限流 + 指数退避重试 + 失败不阻断管线 |
| 场景资产卡 AI 调用失败 | 独立 try/except，使用叙事场景的 location 字段降级 |
| **视频无人声（纯画面镜头）** | 步骤7 跳过 Stage B 音色替换，仅保留原始音效轨 |
| **音频分离质量差** | 降级为 TTS 重新合成 + 音色替换，用 tts_duration_ref 对齐时长 |
| **ComfyUI 服务不可用** | 降级为保留原始音频 + 在导出时标注"音频未处理" |
| **多角色同框对话** | SpeakerDiarization 按时间段切分，逐角色替换后拼接 |
| **旁白/画外音** | 单独标记为 narrator，使用独立的旁白 Voice Reference |

---

## 十四、实施优先级（Phased Delivery）

### Phase 1: 资产提取管线（✅ 已完成）
- Mode C 三阶段管线
- 四模型验证通过
- 输出: 角色/叙事场景/场景资产卡/道具/变体

### Phase 1.5: 角色声音描述（新增，低成本）
- 扩展阶段1提示词，在角色主卡中增加 voice_description
- 无额外 API 调用（合并在现有角色提取提示词中）
- 验证四模型均能输出合格的声音描述

### Phase 2: 分镜生成管线（下一步）
- 叙事场景 → Scene Beats → Shot Cards
- 并发处理
- VFF V2 数据结构（含 voice_nodes + audio_status 字段）

### Phase 3: TTS 时长锚定 + 定妆拦截
- TTS 台词时长测量（仅测时）
- 角色定妆 UI（视觉 + 声音预览）
- Visual Reference Node + Voice Reference Node 系统

### Phase 4: T2I → I2V 管线
- 关键帧候选生成
- 七维质量评分（含声音一致性）
- Model Router
- Image-to-Video 生成

### Phase 5: 音频后处理管线（ComfyUI）
- ComfyUI 工作流搭建（audio_post_process.json）
- 声音分离（UVR5/Demucs）
- 音色替换（RVC v2 / GPT-SoVITS）
- 音视频合并
- 说话人识别（多角色场景）
- 降级策略实现

### Phase 6: Stage 3 预演
- 时间线拼装（含分轨音频）
- 导演审片回路（视觉 + 声音双重审查）
- 分轨导出（CapCut 工程包）
- 导出与迭代

---

## 十五、总结：为什么这是最佳实践

| 优势 | 来源 | 实现方式 |
|------|------|---------|
| **速度最快** | 方案二 "定妆间" + 方案三 "Haiku 并发" | 用户体感 0 等待，后台并发榨干算力 |
| **废片率最低** | 方案二 "先图后视频" + "单机位铁律" | T2I→质检→I2V 三段流，废片从 40% 降到 10% |
| **视觉一致性** | 方案二 "Reference Node" + Mode C "角色变体" | Visual Reference Node 贯穿全流程 |
| **声音一致性** | v2.0 "voice_description + ComfyUI 音色替换" | 同一角色声音在所有 Shot 中保持统一 |
| **控制感最佳** | 方案二 "局部重绘" + 方案三 "导演审片回路" | 从"重跑全片"降维到"涂抹修复" |
| **架构最清晰** | Mode C v2 概念分离 + newplan3 三段式 | 视觉管线与音频管线解耦，各自可独立迭代 |
| **可落地** | Mode C 已实现 + 渐进式扩展 | Phase 1 已验证，逐步叠加后续阶段 |

### v2.0 核心设计哲学

```
视觉管线: T2I → 质检 → I2V → 连续性修复
           (只管画面质量，不管声音)

音频管线: TTS 估时 → 视频生成(含默认音频) → 声音分离 → 音色替换 → 合并
           (统一后处理，保证声音一致性)

两条管线通过 Shot Card 的 audio_status 字段衔接:
  pending_post_process → separated → timbre_replaced → merged
```

---

> **下一步行动**: Phase 1.5 — 在 `run_test_round10.py` 的角色提取提示词中增加 voice_description 字段，验证四模型均能输出合格的声音描述。随后进入 Phase 2（叙事场景 → Scene Beats → Shot Cards）。
