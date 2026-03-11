# 小说导入管线重构：章节轴 → 场景轴

> 日期: 2026-03-09
> 状态: 待实施

---

## 一、为什么要重构

当前管线以"章节"为核心轴（分章→章摘要→角色→逐章提场景/节拍→知识库），但章节是文学概念而非影视生产单元。场景才是影视制作的不可约基本单位。当前管线存在三个结构性缺陷：

1. **场景被章节边界截断** — 跨章场景被割裂为两个残缺片段
2. **章节粒度与影视粒度不匹配** — 一章可能5000字含3场景，也可能500字半个场景
3. **管线终点离交付物太远** — 产出Scene+Beat但缺少Shot/ShotGroup/VisualPrompt，还需3步才能驱动AI视频生成

**核心判断（第一性原理）**：当前管线为"理解小说"而设计，新管线为"制作影视"而设计。产品是后者。

---

## 二、新旧管线对比

### 当前管线（5 Phase，章节轴）
```
上传小说 → ①分章节(P01) → ②章节摘要(P01B) → ③角色两轮提取(P03A→P03B)
         → ④逐章Beats+场景(P10+P04) → ⑤知识库(P05V2) → 完成
产出: Chapter, Character, Beat, Scene, Location, KnowledgeBase
缺失: Shot, ShotGroup, VisualPrompt ← 还需3步才能驱动视频生成
```

### 新管线（6 Phase，场景轴）
```
上传小说 → Phase 0: 智能分段(0 AI调用)
         → Phase 1: 场景提取(核心锚点) — 副产角色名+地点
         → Phase 2: 角色档案 + 知识库
         → Phase 3: 分镜拆解 + 节拍生成
         → Phase 4: 镜头合并(VFF格式)
         → Phase 5: 视觉提示词生成
         → 完成
产出: Scene, Character, Beat, Shot, ShotGroup(含VFF+提示词), Location, KnowledgeBase
直出: 可直接驱动AI视频模型的视觉提示词
```

### 关键差异

| 维度 | 当前管线 | 新管线 |
|------|----------|--------|
| **核心轴** | 章节（文学概念） | 场景（影视概念） |
| **AI调用次数** | ~5N+3 (N=章节数) | ~3S+C (S=场景数, C=角色数) |
| **信息损失** | 高（摘要压缩丢失对白/动作） | 低（场景保留原始对白/动作） |
| **最终产出** | Scene + Beat（无提示词） | ShotGroup + VisualPrompt（可直接驱动生成） |
| **场景连续性** | 被章节边界破坏 | 滑动窗口+去重保护 |
| **可恢复性** | 以章节为断点 | 以场景为断点（粒度更细） |
| **并行度** | 低（严格串行5Phase） | 高（角色档案可与分镜并行） |

---

## 三、架构分析（多框架佐证）

### 3.1 第一性原理
- 章节 = 文学分割，影视无对应物 → **不应为管线主轴**
- 场景 = 时空统一的叙事段落 = 导演的基本调度单元 → **应为管线锚点**
- Shot = 摄影的原子单元 → **场景的子结构**
- 章节仅在"大文本切分"时作为提示信号存在，不参与语义处理

### 3.2 逆向思维（Munger反演法）
- 当前失败模式是**结构性的**（跨章场景截断 → 无法修补）
- 新方案失败模式是**工程性的**（上下文窗口溢出 → 可用滑动窗口解决）
- 工程问题可修复，结构问题需重构

### 3.3 JTBD（Jobs To Be Done）
| 用户工作 | 当前管线 | 新管线 |
|----------|----------|--------|
| 识别场景 | 间接（先分章→再从章里提场景） | **直接**（Phase 1输出） |
| 拆分镜头 | ❌ 未实现 | **直接**（Phase 3输出） |
| 控制时长 | ❌ 未实现 | **直接**（Phase 4按时长合并） |
| 生成提示词 | ❌ 部分（仅角色有visual_reference） | **直接**（Phase 5完整输出） |

### 3.4 Wardley价值链
```
用户需要 ←── 提示词(Commodity) ←── 合并镜头(Product) ←── 分镜(Product) ←── 场景(Product) ←── 原文
                ❌当前管线空白          ❌空白               ❌空白            ⚠️间接(章→场景)
                ✅新管线Phase5          ✅Phase4             ✅Phase3          ✅Phase1
```

### 3.5 反馈环分析
- **当前负反馈环**：章节切分不准 → 场景截断 → 角色关系断裂 → 知识库质量降 → 无法修正上游
- **新正反馈环**：场景识别准 → 产出角色+地点 → 分镜角色一致 → 合并叙事连续 → 提示词质量高

---

## 四、复用现有资产（关键 — 不重建）

| 资产 | 文件位置 | 状态 |
|------|----------|------|
| `P04_SCENE_EXTRACT` 场景提取模板 | prompt_templates.py:155 | 增强(加窗口上下文字段) |
| `P06_SCENE_TO_SHOT` 分镜拆解模板 | prompt_templates.py:931 | 直接复用 |
| `P11_VFF_GENERATE` VFF合并模板 | prompt_templates.py:1229 | 直接复用 |
| `P11_VFF_GENERATE_V2` VFF V2模板 | prompt_templates.py:1332 | 直接复用 |
| `P11_VISUAL_PROMPT` 视觉提示词模板 | prompt_templates.py:1167 | 直接复用 |
| `P03A/P03B` 角色两轮提取 | prompt_templates.py | 直接复用 |
| `P05_KNOWLEDGE_BASE_V2` 知识库 | prompt_templates.py | 微调输入描述 |
| 前端 `Shot` 类型定义 | types/project.ts:66-85 | 已存在，无需新建 |
| `AIEngine.call()` 多provider路由 | ai_engine.py | 不变 |
| `_call_with_retry()` 重试机制 | import_pipeline.py | 不变 |
| `ImportProgress` 组件 | ImportProgress.tsx | 仅改步骤标签 |

---

## 五、详细实施步骤

### Step 1: 新建 ORM 模型

**新建 `backend/models/shot.py`**
```python
class Shot(Base, TimestampMixin):
    __tablename__ = "shots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    scene_id = Column(String(36), ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False, index=True)
    shot_number = Column(Integer, nullable=False, default=0)       # 场景内编号
    goal = Column(Text, default="")                                # 叙事目标
    composition = Column(Text, default="")                         # 构图描述
    camera_angle = Column(String(100), default="")                 # 机位角度
    camera_movement = Column(String(100), default="")              # static|pan|tilt|dolly|crane|handheld|steadicam|zoom
    framing = Column(String(20), default="")                       # ECU|CU|MCU|MS|MLS|FS|WS
    duration_estimate = Column(String(20), default="")             # "2-3s"
    characters_in_frame = Column(JSON, default=list)               # ["角色1", "角色2"]
    emotion_target = Column(Text, default="")                      # 情感目标
    dramatic_intensity = Column(Float, default=0.0)                # -1.0 ~ 1.0
    transition_in = Column(String(100), default="")                # cut|dissolve|wipe|match_cut|J-cut|L-cut
    transition_out = Column(String(100), default="")
    description = Column(Text, default="")                         # 镜头描述
    visual_prompt = Column(Text, default="")                       # AI视觉提示词
    order = Column(Integer, nullable=False, default=0)             # 全局顺序
```

**新建 `backend/models/shot_group.py`**
```python
class ShotGroup(Base, TimestampMixin):
    __tablename__ = "shot_groups"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    scene_id = Column(String(36), ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True, index=True)
    shot_ids = Column(JSON, default=list)                          # ["shot_id_1", "shot_id_2"]
    segment_number = Column(Integer, nullable=False, default=0)    # 段落编号
    duration = Column(String(20), default="")                      # 目标时长 "6s"
    transition_type = Column(String(100), default="")              # 转场类型
    emotional_beat = Column(Text, default="")                      # 情感节拍
    continuity = Column(Text, default="")                          # 画面承接描述
    vff_body = Column(Text, default="")                            # VFF格式脚本体
    merge_rationale = Column(Text, default="")                     # 合并理由
    style_metadata = Column(JSON, default=dict)                    # {aspect_ratio, mood, ...}
    visual_prompt_positive = Column(Text, default="")              # 正向提示词(英文)
    visual_prompt_negative = Column(Text, default="")              # 反向提示词
    style_tags = Column(JSON, default=list)                        # 风格标签
    order = Column(Integer, nullable=False, default=0)             # 全局顺序
```

**修改 `backend/models/__init__.py`** — 添加 Shot, ShotGroup 导出

---

### Step 2: 更新现有模型

**`backend/models/import_task.py`**
- phase 值域: `segmenting | scenes | characters | shots | merging | prompts`
- 新增列: `full_text = Column(Text, nullable=True)` — 存储原文供重试使用

**`backend/models/scene.py`** — 添加字段
```python
characters_present = Column(JSON, default=list)    # 在场角色名列表
key_props = Column(JSON, default=list)             # 关键道具
dramatic_purpose = Column(Text, default="")        # 叙事功能
window_index = Column(Integer, nullable=True)      # 来源窗口索引
```

---

### Step 3: 添加解析函数到 `backend/services/novel_parser.py`

**6个新增函数：**

#### 3.1 `smart_segment(text, window_size=20000, overlap=2000) -> list[dict]`
```
纯文本处理，零AI调用。
算法：
1. 检测章节标记（复用 _regex_split 的正则）
2. 按 window_size 步进遍历文本
3. 每个切分点寻找最近的章节标记或段落分界(\n\n)，±500字范围内
4. 窗口间保留 overlap 字节重叠
5. 记录每个窗口内的 chapter_hints
输出: [{window_index, text, start_offset, end_offset, chapter_hints}]
```

#### 3.2 `extract_scenes_windowed(window_text, character_names, previous_scene_summary, window_index, db) -> list[dict]`
```
调用增强版 P04_SCENE_EXTRACT 模板。
- 传入前一窗口最后场景摘要，用于连续性检查和避免重复提取
- 传入已知角色名列表，保证角色名一致性
- 返回场景列表（含 heading, location, time_of_day, action, dialogue, characters_present 等）
```

#### 3.3 `deduplicate_scenes(all_scenes, overlap_chars=50) -> list[dict]`
```
去除窗口重叠区产生的重复场景。
- 相似度键: normalize(heading) + "|" + normalize(action[:50])
- difflib.SequenceMatcher ratio > 0.8 判定为重复
- 保留内容更丰富的版本（action + description 更长者）
- 重新编号 order
```

#### 3.4 `decompose_scene_to_shots(scene_json, character_profiles, style_guide, db) -> list[dict]`
```
调用现有 P06_SCENE_TO_SHOT 模板。
输出: [{shot_number, goal, composition, camera_movement, framing, duration_hint, characters, emotion_target, dramatic_intensity, transition_in, transition_out}]
```

#### 3.5 `merge_shots_to_groups(scene_json, shots_json, char_profiles, style_guide, scene_id, target_duration="6s", target_model="jimeng", db=None) -> list[dict]`
```
调用现有 P11_VFF_GENERATE 模板。
合并边界依据: 角色集合变化、情感弧线转折、时空跳转、时长约束(4-10s)
输出: [{segment_number, shot_ids, target_duration, continuity, vff_body, merge_rationale, style_metadata, ...}]
```

#### 3.6 `generate_visual_prompts(shot_cards, character_profiles, style_guide, db) -> list[dict]`
```
调用现有 P11_VISUAL_PROMPT 模板。
角色外貌从全局档案注入，确保跨镜头视觉一致性。
输出: [{shot_id, prompt_text(英文), style_params, negative_prompt}]
```

---

### Step 4: 增强 Prompt 模板 (`backend/services/prompt_templates.py`)

**修改 `P04_SCENE_EXTRACT`** — user prompt 添加：
```
前一窗口最后场景摘要（连续性检查，避免重复提取同一场景）：
{previous_scene_summary}

窗口编号：{window_index}（用于全局排序参考）
```

**修改 `P05_KNOWLEDGE_BASE_V2`** — system prompt 语义微调：
- `"你的输入是全文摘要（非全文）"` → `"你的输入是从场景中提炼的叙事摘要"`
- 参数名 `{synopsis}` 不变，下游传入场景摘要而非章节摘要

---

### Step 5: 重写管线 `backend/services/import_pipeline.py`（核心变更）

```python
class ImportPipeline:
    PHASES = ["segmenting", "scenes", "characters", "shots", "merging", "prompts"]
```

#### Phase 0 — segmenting（零AI调用）
- 调用 `smart_segment()` → 切分为15-20KB窗口
- 可选：用 `_regex_split` 提取章节作为 Chapter 元数据（降级为辅助信息）
- 存储 `task.full_text = full_text` 用于重试
- SSE: `phase_start` / `phase_done(window_count)`

#### Phase 1 — scenes（核心锚点）
- 逐窗口调用 `extract_scenes_windowed()`
  - 传入前一窗口最后场景摘要（连续性上下文）
  - 累积收集 `character_name_set` 和 `location_dict`（免费副产物）
- 全部窗口处理完后调用 `deduplicate_scenes()` 去重
- 保存 Scene[], Location[] 到 DB
- SSE: `window_progress(index, total, scenes_in_window)`

#### Phase 2 — characters
- 从场景数据构建 synopsis: `"\n\n".join(f"【{heading}】{action[:300]}" for scene in scenes)`
- Round 1: `extract_character_names(synopsis)` → `[{name, brief, role}]` (fast tier)
- Round 2: `extract_character_detail()` per name (max 3 并发) → Character[] (standard tier)
- 知识库: `build_knowledge_base_v2(synopsis, char_names, loc_names)` → KnowledgeBase
- SSE: `item_ready` per character

#### Phase 3 — shots
- 准备全局角色档案 JSON + 风格指南 JSON
- 逐场景:
  - `decompose_scene_to_shots()` → Shot[] (复用 P06 模板)
  - `generate_beats()` → Beat[] (从场景而非章节生成节拍)
  - 保存 Shot, Beat 到 DB
- SSE: `scene_progress(index, total, shots_count)`

#### Phase 4 — merging
- 逐场景获取关联 Shots:
  - `merge_shots_to_groups()` → ShotGroup[] (复用 P11_VFF_GENERATE 模板)
  - 合并逻辑: 角色集合变化 / 情感弧线转折 / 时空跳转 / 时长约束(4-10s)
  - 保存 ShotGroup 到 DB
- SSE: `scene_progress(index, total)`

#### Phase 5 — prompts
- 逐场景的 ShotGroups:
  - `generate_visual_prompts()` → 更新 visual_prompt_positive/negative/style_tags (复用 P11_VISUAL_PROMPT)
  - 角色外貌从全局档案注入 → 跨镜头一致性
- SSE: `phase_done`

#### 完成
- `Project.stage = "storyboard"`
- `ImportTask.status = "completed"`
- SSE: `pipeline_complete(summary)`

---

### Step 6: 更新后端 API (`backend/api/import_novel.py`)

- 创建 ImportTask 时: `current_phase = "segmenting"` (替代 `"splitting"`)
- 存储原文: `task.full_text = full_text`
- 重试逻辑: 从 `task.full_text` 读取原文（不再从章节拼接）
- 新增路由:
  - `GET /api/projects/{id}/shots` — 获取项目所有 Shot
  - `GET /api/projects/{id}/shot-groups` — 获取项目所有 ShotGroup

---

### Step 7: 更新前端类型 (`packages/shared/src/types/project.ts`)

**新增 `ShotGroup` 接口:**
```typescript
export interface ShotGroup {
  id: string;
  project_id: string;
  scene_id?: string;
  shot_ids: string[];
  segment_number: number;
  duration: string;
  transition_type: string;
  emotional_beat: string;
  continuity: string;
  vff_body: string;
  merge_rationale: string;
  style_metadata: Record<string, unknown>;
  visual_prompt_positive: string;
  visual_prompt_negative: string;
  style_tags: string[];
  order: number;
}
```

**扩展 `Scene` 接口:**
```typescript
characters_present?: string[];
key_props?: string[];
dramatic_purpose?: string;
```

**扩展 `ImportSSEEvent`:**
```typescript
| { type: 'window_progress'; phase: string; index: number; total: number; scenes_in_window?: number }
| { type: 'scene_progress'; phase: string; index: number; total: number; shots?: number }
```

---

### Step 8: 更新前端 Store (`packages/shared/src/stores/projectStore.ts`)

```typescript
// 新增 state
shots: Shot[]
shotGroups: ShotGroup[]

// 新增 actions
setShots(shots: Shot[]): void
setShotGroups(groups: ShotGroup[]): void
addShot(shot: Shot): void
addShotGroup(group: ShotGroup): void
```

---

### Step 9: 更新前端项目页 (`packages/web/src/app/[locale]/projects/[id]/page.tsx`)

**PHASE_LABELS:**
```typescript
const PHASE_LABELS: Record<string, string> = {
  segmenting: '智能分段',
  scenes: '场景提取',
  characters: '角色提取与知识库',
  shots: '分镜拆解',
  merging: '镜头合并',
  prompts: '视觉提示词生成',
};
```

**initImportSteps:** 7个步骤 (upload + 6 phases)

**SSE handler:** 增加 `window_progress`, `scene_progress` 事件处理

---

## 六、实施顺序（依赖关系图）

```
并行组A (无相互依赖):          并行组B (依赖A完成):       最终 (依赖B):
├─ Step 1: 新建Shot/ShotGroup  ├─ Step 5: 重写管线核心    Step 6: 更新API路由
├─ Step 2: 更新Scene/ImportTask ├─ Step 9: 更新项目页
├─ Step 3: 新增解析函数
├─ Step 4: 增强Prompt模板
├─ Step 7: 前端类型
├─ Step 8: 前端Store
```

---

## 七、向后兼容

- **Chapter 模型保留不删除**，降级为辅助元数据（可选保存）
- **`create_all()` 自动建表**，新表 `shots`/`shot_groups` 启动时自动创建，不需 migration
- **新增列用 `nullable=True` + `default`**，保护旧数据不报错
- **已导入项目数据不受影响**，新管线仅用于新导入

---

## 八、数据流图

```
全文 (Full Text)
   │
   ▼
Phase 0: smart_segment()
   │ ──→ windows[] (15-20KB each, 2KB overlap)
   │      + chapter_hints (可选保存为 Chapter 元数据)
   │
   ▼
Phase 1: extract_scenes_windowed() × N windows
   │ ──→ raw_scenes[] (含窗口重叠区重复)
   │ ──→ deduplicate_scenes() ──→ Scene[] (保存DB)
   │ ──→ character_names (副产物, set)
   │ ──→ location_data (副产物, dict → Location[] 保存DB)
   │
   ▼
Phase 2: extract_character_names(scene_synopsis) ──→ names[]
   │      extract_character_detail() × N chars ──→ Character[] (保存DB)
   │      build_knowledge_base_v2(scene_synopsis) ──→ KnowledgeBase (保存DB)
   │
   ▼
Phase 3: decompose_scene_to_shots() × M scenes ──→ Shot[] (保存DB, FK→scene_id)
   │      generate_beats() × M scenes ──→ Beat[] (保存DB)
   │
   ▼
Phase 4: merge_shots_to_groups() × M scenes ──→ ShotGroup[] (保存DB, 含VFF脚本)
   │
   ▼
Phase 5: generate_visual_prompts() × M scenes的groups ──→ 更新ShotGroup提示词字段
   │
   ▼
完成: Project.stage = "storyboard", ImportTask.status = "completed"
```

---

## 九、验证方案

1. **单元测试**: `smart_segment()` 对不同格式小说(有章节标记/无章节标记/超长文本)的窗口切分正确性
2. **集成测试**: 上传测试小说(`测试/我和沈词的长子.txt`)，验证6个Phase依次完成:
   - Phase 0: 窗口数合理 (文本长度 / window_size ≈ 预期值)
   - Phase 1: 场景数 > 0，无重复场景（heading不重复）
   - Phase 2: 角色数 > 0，知识库world_building非空
   - Phase 3: 每个场景有 >= 1 个Shot，Shot总数 > Scene总数
   - Phase 4: ShotGroup数 <= Shot数，每组duration在4-10s范围
   - Phase 5: 每个ShotGroup有非空 visual_prompt_positive (英文)
3. **SSE验证**: 前端正确接收所有新事件类型(window_progress, scene_progress)，进度条正常更新
4. **重试验证**: 在任意Phase制造失败(如断网)，调用 `/import/retry` 从该Phase恢复
5. **大文件测试**: 200K字小说，验证窗口切分+去重无遗漏无重复

---

## 十、成本预估

以 200K 字小说（约10个窗口、约30个场景）为例:

| Phase | AI调用数 | Tier | 预计耗时 |
|-------|----------|------|----------|
| Phase 0: 智能分段 | 0 | — | < 1s |
| Phase 1: 场景提取 | 10 | standard | ~30s |
| Phase 2: 角色档案+KB | ~12 | fast+standard | ~35s |
| Phase 3: 分镜拆解 | ~30 | standard | ~90s |
| Phase 4: 镜头合并 | ~30 | fast | ~30s |
| Phase 5: 视觉提示词 | ~30 | standard | ~90s |
| **总计** | **~112** | | **~4.5 min** |

对比当前管线 ~25 calls / ~73s — 调用数增加但产出完整度从40%提升到100%（直出提示词）。

---

## 十一、风险缓解

| 风险 | 缓解策略 |
|------|----------|
| 上下文窗口溢出 | 20KB窗口 << Sonnet 200K上下文，安全余量充足 |
| 场景去重误判 | 0.8阈值保守；heading+action双键比对降低误判率 |
| AI调用成本增加 | Phase 4用fast tier(Haiku)降本；可配置跳过Phase 4/5 |
| 长时间运行 | SSE实时推送进度；每Phase有断点可恢复 |
| 旧数据兼容 | 新列全部nullable+default；旧项目不受影响 |
