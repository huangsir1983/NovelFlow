# NovelFlow — 小说/剧本到视频全链路AI创作平台 PRD

> 版本: 5.0 | 日期: 2026-03-05
> PRD原始文档: `E:/小说转剧本/小说视频化-小说到分镜脚本.md`
> 知识库目录: `E:/小说转剧本/软件系统/知识库/`
> 界面设计规范: `E:/小说转剧本/软件系统/界面设计规范/`

---

## 一、产品概述

### 1.1 产品定位

从小说/剧本文本到完整视频的端到端AI辅助创作系统。
Web + 桌面(Win/Mac)双端，多版本产品体系，核心模块Agent化，支持团队协同。
内置专业级导演分镜知识体系 + 编剧知识体系，面向奥斯卡级电影品质与国内顶级AI微短剧。

### 1.2 目标用户

| 版本 | 用户画像 | 核心需求 |
|------|---------|---------|
| 普通版 Normal | 个人创作者/小白 | 零门槛完成小说→分镜全流程 |
| 画布版 Canvas | 团队/影视公司 | 多人协作 + 专业编剧工具 |
| 隐藏版 Hidden | 合作方(邀请制) | 全模块 + 可定制知识库 |
| 自用版 Ultimate | 内部使用 | 全功能 + 调试 + 数据闭环 |

---

## 二、核心流程

### 2.1 双入口架构

```
                    +---------------------------+
                    |      入口A: 小说导入        |
                    |  TXT/DOCX/EPUB/PDF/MD     |
                    +-------------+-------------+
                                  |
                    +-------------v-------------+
                    |   智能解析 + 知识库构建      |
                    |  分章->角色->场景->结构分析   |
                    +-------------+-------------+
                                  |
                    +-------------v-------------+
                    |    Beat Sheet 生成/编辑     |
                    +-------------+-------------+
                                  |
                    +-------------v-------------+
                    |      剧本生成/编辑          |
                    +-------------+-------------+
                                  |
  +-------------------------------+
  |                               |
  |  +-----------------------+    |
  |  |   入口B: 剧本导入      |    |
  |  | Fountain/FDX/TXT      |    |
  |  | /DOCX/PDF             |    |
  |  +----------+------------+    |
  |             |                 |
  |  +----------v------------+    |
  |  |  剧本适配优化引擎      |    |
  |  |  (详见2.2)            |    |
  |  +----------+------------+    |
  |             |                 |
  +-------------+-----------------+
                |
   +------------v------------------+
   |    统一剧本工作台 (已适配)      |
   +------------+------------------+
                |
   +------------v--------------+
   |   声音叙事设计 (与分镜并行)  |
   +------------+--------------+
                |
   +------------v--------------+
   |   导演分镜 + 场面调度       |
   |   (7步流程 + 序列设计器)    |
   +------------+--------------+
                |
   +------------v--------------+
   |   视觉母题终检             |
   +------------+--------------+
                |
   +------------v--------------+
   |   视觉Prompt工程           |
   |   (多平台适配)             |
   +------------+--------------+
                |
   +------------v--------------+
   |   图像/视频生成 -> 成品     |
   +---------------------------+
```

### 2.2 剧本导入适配引擎 (入口B)

用户直接导入已有剧本时，经过四步适配对接下游分镜流程：

```
剧本文件上传
    |
    v
+------------------------------------------------+
|  Step 1: 格式识别与标准化                        |
|  - 自动识别格式 (Fountain/FDX/自由格式TXT)       |
|  - 解析剧本元素 (场景标题/动作/角色/对话/转场)    |
|  - 转换为内部标准JSON Schema                     |
|  - 格式问题标注 + 用户确认/手动修正               |
+------------------------------------------------+
|  Step 2: 结构分析                               |
|  - 自动识别Act结构 (三幕/五幕/分集)              |
|  - 逆向提取Beat Sheet                           |
|  - 情感曲线分析 + 节奏密度分析                    |
|  - 结构健康度评分                                |
+------------------------------------------------+
|  Step 3: 知识库逆向构建                          |
|  - 从对话/动作提取角色档案                        |
|  - 从场景标题提取场景档案                         |
|  - 推断角色关系 (对话互动+场景共现)               |
|  - 推断世界观设定                                |
|  - 生成Story Bible初稿 -> 用户审核               |
+------------------------------------------------+
|  Step 4: 质量评估与适配优化                      |
|  - 分镜可执行性评估 (场景/动作/环境描述充分度)    |
|  - 标注需补充的信息                              |
|  - AI优化建议 (可选执行): 补充动作/氛围/光线描述  |
|  - 用户选择: 直接进入分镜 / 先在工作台优化        |
+------------------------------------------------+
```

**适配引擎Prompt:**

| ID | 名称 | 模型 | 温度 | 说明 |
|----|------|------|------|------|
| PS01 | 剧本格式识别与解析 | Haiku | 0.2 | 识别格式类型，解析为标准JSON |
| PS02 | 剧本逆向Beat提取 | Sonnet | 0.4 | 从完整剧本逆向推导Beat Sheet |
| PS03 | 剧本知识库逆向构建 | Sonnet | 0.4 | 从剧本内容提取角色/场景/世界观 |
| PS04 | 剧本分镜可执行性评估 | Sonnet | 0.3 | 评估每个场景的视觉化充分度 |
| PS05 | 剧本适配优化 | Sonnet | 0.6 | 补充视觉描述/动作细节/氛围描写 |

---

## 三、功能模块

### 3.1 核心模块 (所有版本)

**小说解析管线**: 上传 -> 分章 -> 角色提取 -> 场景提取 -> 知识库初始化
**Beat Sheet编辑器**: AI生成 + 手动调整 + 情感曲线可视化
**剧本编辑器**: TipTap富文本 + AI辅助(改写/扩写/缩写/对话优化)
**分镜脚本生成器**: 场景->镜头拆解 + 分镜卡片 + 时间轴视图
**视觉Prompt引擎**: 分镜->AI绘图Prompt (多平台适配)
**导出系统**: PDF / JSON / Fountain / FDX / CSV / DOCX

### 3.2 编剧系统 — "原点"编剧体系 (Canvas+)

10位子专家协作模式:

```
基础子专家 (Canvas+):
  @StructureGenius    — 结构设计
  @SceneCrafter       — 场景构建
  @WorldBuilder       — 世界观
  @ActionChoreographer — 动作编排
  @DialogueDoctor     — 对白设计
  @EmotionResonance   — 情感共鸣
  @SubtextExpert      — 潜台词
  @RhythmController   — 节奏控制
  @VisualHammer       — 视觉锤
  @CharPsychologist   — 角色心理

增强子专家 (Hidden+):
  @ThemeArchaeologist — 主题三层挖掘 + 多义性 + 隐喻系统
  @TimelineArchitect  — 非线性叙事 + 多时间线管理 + 信息不对称设计
  @DialogueDoctor v2  — 对白节奏韵律 + 意象运用 + 大师风格参考
  @CharPsychologist v2 — 矛盾性设计 + 灰色地带 + 无意识驱动
```

**Intent Anchor管理器** + **Sandbox模式** + **创作风格记忆**

### 3.3 微短剧编剧系统 (Ultimate)

11节点流水线 + 爽点引擎(3层) + 付费卡点优化 + 性别向调优 + 小说改编专用模块

### 3.4 导演分镜系统 (Hidden+)

```
核心: 7步执行流 + 8列输出 + 14种转场 + 16点质检
高级: 6大模块(角色深度/镜头语言/动作拆解/对白精修/高级转场/终极戒律)
序列设计器(5种): 动作/对白/情感/蒙太奇/悬疑 (按场景类型自动选择)
```

### 3.5 高级功能模块

#### 3.5.1 声音叙事系统 (Hidden+)

导演Agent子模块，为每个镜头生成完整 `sound_narrative` 对象。

```
1. 三层环境声设计:
   - Layer 1: 底噪层 (空间声特征: 空旷/密闭/户外/水边)
   - Layer 2: 环境活动层 (背景人声/动物/机械/自然)
   - Layer 3: 焦点音效层 (与叙事直接相关的特定声音)
2. 音乐情感映射引擎:
   - 12条场景情感->音乐调性映射
   - 音乐动机追踪 (角色主题/场景主题/关系主题)
   - 音乐入出点标注 (精确到镜头级)
3. 静默运用规则:
   - 高冲击静默 (情感高潮前2-3秒)
   - 过渡静默 / 叙事静默
4. 声音转场设计:
   - J-cut / L-cut / 声音桥 / 音量渐变转场
5. 音画关系标注:
   - 音画同步 / 音画对位 / 音画分离
```

#### 3.5.2 视觉母题追踪系统 (Hidden+)

一致性守护Agent子模块，分镜完成后自动扫描全片生成《视觉叙事报告》。

```
1. 视觉符号提取与登记:
   - 从Theme/Motif自动提取视觉隐喻候选
   - 人工确认核心视觉符号 (3-5个)
2. 色彩叙事弧规划:
   - 全片色温变化曲线 / 角色专属色彩 / 情感色彩映射
   - 关键转折点的色彩突变设计
3. 构图回响检测:
   - 开头/结尾构图呼应 / 重要场景构图变奏
4. 母题密度控制:
   - 理想分布: 开头暗示->中段强化->高潮爆发->尾声回响
5. 跨镜头视觉连贯性:
   - 色彩连续性 / 道具追踪 / 光影连续性
```

#### 3.5.3 场面调度系统 (Hidden+)

导演Agent子模块，适用于重要对话、群戏、长镜头、复杂动作场景。
输出: `mise_en_scene` 对象 (位置图JSON + 走位序列)。

```
1. 演员位置标注: 场景俯视图 + 角色初始/终止位置 + 关键时间点快照
2. 走位路线设计: 移动轨迹 + 移动动机 + 与台词时序关系
3. 空间叙事层次: 前景层/中景层/背景层 + 景深叙事含义
4. 群戏编排: 注意力引导 + 空间主次关系 + 进出场时序
5. 长镜头设计: 走位+机位时序图 + 焦点转移计划
```

#### 3.5.4 情感张力量化引擎 (Canvas+)

编剧Agent + 导演Agent共享模块。
输出: 全片/分幕/分场景张力图表 + 节奏优化建议。

```
1. 多维张力模型:
   - 叙事张力 (信息落差) / 情感张力 (困境深度x共情强度)
   - 时间张力 (截止期限x紧迫度) / 道德张力 (伦理困境两难强度)
   - 综合张力 = f(叙事,情感,时间,道德) -> 0-100分
2. 张力曲线规划:
   - 全片弧线模板 (经典三幕/W型/阶梯型/下沉-爆发型)
   - 峰谷最优分布 (基于观众注意力模型)
3. 节奏密度分析:
   - 场景时长 vs 对话密度 vs 动作密度
   - "呼吸点"检测 + 连续同节奏场景预警
4. 观众疲劳预测:
   - 认知负荷衰减模型 / "刺激过载"与"刺激不足"区间标注
```

#### 3.5.5 跨文化视觉语言适配 (Hidden+)

导演Agent子模块，基于项目genre + 目标受众自动推荐视觉语言预设。

```
文化镜头语言预设:
  中国武侠: 写意远景/飘逸运镜/静->动突转/诗意空镜
  中国古装: 对称构图/色彩象征/仪式感镜头/庭院空间
  韩式情感: 柔光特写/慢速推进/OST标注/雨景运用
  好莱坞商业: 三分法/快节奏剪辑/大特效全景/英雄低角度
  欧洲艺术: 长镜头/自然光/固定机位/留白
  日式动画: 极端透视/速度线/表情夸张/定格

支持混合预设 + 文化冲突检测
```

#### 3.5.6 爽点视觉联动 (Ultimate)

微短剧编剧Agent标注爽点 -> 导演Agent自动选择视觉增强 -> 视觉Agent嵌入增强参数。

```
爽点类型 -> 视觉增强方案:
  反转 -> 镜头突变(固定->手持/匀速->急推) + 音乐突变
  打脸 -> 表情特写序列(ECU) + 正反打加速 + 定格
  逆袭 -> 低角度英雄镜头 + 背光剪影 + 升格慢动作
  甜蜜 -> 柔光滤镜 + 浅景深 + 暖色调 + 慢推
  释放 -> 远景->近景快切 + 动态构图 + 强音乐
```

#### 3.5.7 数据反馈闭环 (Ultimate)

数据优化Agent管理，沉淀到知识库供后续数据分析及系统升级优化。

```
1. 数据采集: 对接抖音/快手/微信视频号API
   收集完播率/互动率/分享率/付费率/弹幕热词 (按集/按时间段)
2. 内容-数据关联分析:
   将指标映射到内容结构特征 -> 归纳高效/失效模式
3. 知识库沉淀:
   - project-level + platform-level两级知识库
   - 高效模式入库 / 失效模式入库
4. 反哺创作:
   新项目自动检索历史数据模式 -> 创作参考 + 预测性评分
```

#### 3.5.8 IP延展规划 (Canvas+)

编剧Agent/微短剧Agent子模块，项目完成后自动生成IP评估报告。

```
- 系列化潜力评估 / 续集钩子设计
- 衍生内容方向 (番外/前传/角色独立剧/互动剧)
- 粉丝运营素材 / IP核心资产清单
```

---

## 四、产品版本矩阵

### 4.1 版本定义

```
+----------+----------+----------+----------+-------------------------+
|          |  普通版   |  画布版   |  隐藏版   |  自用版                 |
|          | Normal   | Canvas   | Hidden   | Ultimate               |
+----------+----------+----------+----------+-------------------------+
| 获取方式 | 公开注册  | 订阅付费  | 邀请制    | 不公开                  |
+----------+----------+----------+----------+-------------------------+
| 入口     | 小说导入  | 小说+剧本 | 小说+剧本 | 小说+剧本+从零创建      |
| UI模式   | 向导式    | 画布工作台| 可定制    | 全功能+调试面板          |
| 协作     | 单人      | 多人实时  | 多人+API | 不限                    |
| 平台     | Web      | Web+桌面 | Web+桌面  | Web+桌面                |
| Agent    | 无        | 3个核心  | 6个Agent | 9个Agent+编排器          |
| 知识库   | 内置不可见| 可查看    | 可自定义  | 完全可编辑+热加载        |
| AI候选   | 1个结果   | 3个候选  | 5个候选   | 不限+模型可选            |
| 编剧模式 | 基础      | 原点系统 | 原点+增强 | 原点+微短剧双系统        |
| 分镜质量 | Core     | Core+Adv | 全部      | 全部                    |
| 声音叙事 | 基础标注  | 基础标注  | 完整系统  | 完整系统                |
| 张力引擎 | 简化      | 标准     | 完整     | 完整+数据反馈            |
| 数据反馈 | 无        | 无       | 基础报告  | 完整闭环+知识库沉淀      |
+----------+----------+----------+----------+-------------------------+
```

### 4.2 版本控制实现

```typescript
enum Edition {
  NORMAL = 'normal',
  CANVAS = 'canvas',
  HIDDEN = 'hidden',
  ULTIMATE = 'ultimate',
}

const FEATURE_FLAGS: Record<Edition, FeatureConfig> = {
  normal: {
    ui_mode: 'wizard',
    import_sources: ['novel'],
    max_projects: 5,
    collaboration: false,
    agents: [],
    knowledge_level: 'core',
    screenwriter_mode: 'basic',
    director_capabilities: ['core'],
    visual_capabilities: ['core'],
    sound_narrative: false,
    mise_en_scene: false,
    visual_motif_tracking: false,
    tension_engine: 'simplified',
    cultural_presets: ['auto'],
    data_feedback: false,
    candidates_per_generation: 1,
    export_formats: ['pdf', 'json'],
    model_selection: false,
    default_model: 'haiku',
    custom_prompts: false,
    custom_knowledge: false,
    desktop_app: false,
    api_access: false,
    debug_panel: false,
  },
  canvas: {
    ui_mode: 'workspace',
    import_sources: ['novel', 'script'],
    max_projects: -1,
    collaboration: true,
    agents: ['analyst', 'consistency', 'screenwriter'],
    knowledge_level: 'advanced',
    screenwriter_mode: 'origin',
    director_capabilities: ['core', 'advanced'],
    visual_capabilities: ['core', 'advanced'],
    sound_narrative: false,
    mise_en_scene: false,
    visual_motif_tracking: false,
    tension_engine: 'standard',
    cultural_presets: ['auto', 'manual'],
    data_feedback: false,
    candidates_per_generation: 3,
    export_formats: ['pdf', 'json', 'fountain', 'fdx', 'csv', 'docx'],
    model_selection: false,
    default_model: 'sonnet',
    custom_prompts: 'tune',
    custom_knowledge: 'view',
    desktop_app: true,
    api_access: false,
    debug_panel: false,
  },
  hidden: {
    ui_mode: 'workspace',
    import_sources: ['novel', 'script'],
    max_projects: -1,
    collaboration: true,
    agents: ['analyst', 'consistency', 'screenwriter', 'director', 'visual', 'reviewer'],
    knowledge_level: 'full',
    screenwriter_mode: 'origin_enhanced',
    director_capabilities: ['core', 'advanced', 'sequences', 'sound', 'mise_en_scene', 'cultural'],
    visual_capabilities: ['core', 'advanced', 'platform_adapt', 'edge_cases'],
    sound_narrative: true,
    mise_en_scene: true,
    visual_motif_tracking: true,
    tension_engine: 'full',
    cultural_presets: 'all',
    data_feedback: 'basic',
    ip_extension: true,
    candidates_per_generation: 5,
    export_formats: 'all',
    model_selection: true,
    default_model: 'sonnet',
    custom_prompts: 'full',
    custom_knowledge: 'edit',
    desktop_app: true,
    api_access: true,
    white_label: true,
    debug_panel: false,
  },
  ultimate: {
    ui_mode: 'workspace',
    import_sources: ['novel', 'script', 'blank'],
    max_projects: -1,
    collaboration: true,
    agents: ['analyst', 'consistency', 'screenwriter', 'micro_drama_writer',
             'director', 'visual', 'reviewer', 'data_optimizer', 'coordinator'],
    knowledge_level: 'full',
    screenwriter_mode: 'origin+micro_drama',
    director_capabilities: 'all',
    visual_capabilities: 'all',
    sound_narrative: true,
    mise_en_scene: true,
    visual_motif_tracking: true,
    tension_engine: 'full',
    cultural_presets: 'all',
    data_feedback: 'full_loop',
    ip_extension: true,
    thrill_visual_linkage: true,
    candidates_per_generation: -1,
    export_formats: 'all',
    model_selection: true,
    default_model: 'opus',
    custom_prompts: 'full',
    custom_knowledge: 'full',
    desktop_app: true,
    api_access: true,
    debug_panel: true,
    auto_pipeline: true,
    experimental: true,
  },
};
```

---

## 五、智能Agent体系 (9 Agents)

### 5.1 架构总览

```
+-----------------------------------------------------------------------+
|                        NovelFlow Agent 架构                             |
|                                                                         |
|  +---------------------------------------------------------------+     |
|  |              Agent Coordinator (Ultimate)                       |     |
|  +-----------------------------+---------------------------------+     |
|                                 |                                       |
|   +--------+--------+----------+--------+--------+--------+            |
|   v        v        v          v        v        v        v            |
| +------+ +------+ +---------+ +------+ +------+ +------+ +--------+  |
| |分析师 | |编剧  | |微短剧   | |导演  | |视觉  | |审核官| |数据    |  |
| |Agent | |Agent | |编剧Agent| |Agent | |Agent | |Agent | |优化Agent|  |
| |      | |10专家| |11节点   | |7步+5器| |9模块 | |      | |Ultimate|  |
| |      | |+增强 | |Ultimate | |+声音  | |+20检 | |      | |        |  |
| +--+---+ +--+---+ +----+----+ +--+---+ +--+---+ +--+---+ +----+---+  |
|    +--------+----------+--------+--------+--------+---------+          |
|                                 |                                       |
|                   +-------------v-------------+                        |
|                   |   一致性守护 Agent          |                        |
|                   |   + 视觉母题追踪           |                        |
|                   |   + 张力曲线监控           |                        |
|                   +---------------------------+                        |
+-----------------------------------------------------------------------+
```

### 5.2 Agent定义

#### Agent 1: 小说分析师 (Novel Analyst)
**版本**: Canvas+ | **触发**: 文件上传时自动启动

| 特性 | 行为 |
|------|------|
| 自主性 | 分章->角色提取->场景提取->结构分析->知识库初始化 |
| 反应性 | 用户修改章节边界后自动重新分析 |
| 主动性 | 完成后推送报告并标注矛盾点 |
| 社交性 | 知识库->一致性Agent，结构->编剧Agent |
| 剧本导入 | 执行逆向构建: 从剧本提取知识库 + 分镜可执行性评估 |

#### Agent 2: 一致性守护者 (Consistency Guardian)
**版本**: Canvas+ | **子模块**: 视觉母题追踪(Hidden+) + 张力曲线监控

| 特性 | 行为 |
|------|------|
| 自主性 | 事件驱动 + 定时全扫描 |
| 反应性 | 内容变更时即时校验 |
| 主动性 | 视觉母题追踪 + 色彩叙事弧检查 + 张力曲线偏离预警 |
| 社交性 | 向所有Agent发出约束; 管理一致性知识图谱 |

#### Agent 3: 编剧 (Screenwriter)
**版本**: Canvas+ | **子系统**: 原点系统10子专家 + 增强专家(Hidden+)

详见 3.2 编剧系统。

#### Agent 4: 微短剧编剧 (Micro-Drama Screenwriter)
**版本**: Ultimate独占

详见 3.3 微短剧编剧系统。

#### Agent 5: 导演 (Director)
**版本**: Hidden+

详见 3.4 导演分镜系统 + 3.5.1 声音叙事 + 3.5.3 场面调度 + 3.5.5 文化适配 + 3.5.6 爽点联动。

#### Agent 6: 视觉提示词工程师 (Visual Prompt Engineer)
**版本**: Hidden+ | 镜头画面设计9模块 + 20点质检

多平台适配: Kling 3.0 / 即梦 Seedance 2.0 / MJ / SD-Flux
边缘案例处理: 手部/多人/特效/文字叠加

#### Agent 7: 质量审核官 (Quality Reviewer)
**版本**: Hidden+

评审维度: 声音叙事完整度 + 场面调度合理性 + 张力曲线达标 + 视觉母题覆盖率

#### Agent 8: 数据优化Agent (Data Optimizer)
**版本**: Ultimate独占

完播率预测 + 付费转化评估 + 社交传播性 + A/B版本 + 数据沉淀到知识库

#### Agent 9: 项目协调者 (Project Coordinator)
**版本**: Ultimate独占

全自动管线:
```
1. 分析师Agent -> 知识库 (小说导入 or 剧本逆向构建)
2. 用户确认知识库 (可跳过)
3. [小说] 编剧Agent -> 全量剧本 / [剧本导入] 适配优化
4. [微短剧] 微短剧编剧Agent -> 分集剧本
5. 一致性Agent + 审核Agent + 张力引擎 -> 自动修正 (最多3轮)
6. [微短剧] 数据优化Agent -> 内容优化
7. 导演Agent -> 全量分镜 (含声音叙事+场面调度)
8. 视觉Agent -> 全量Prompt (适配目标平台)
9. 一致性Agent -> 视觉母题终检 + 色彩叙事弧检查
10. [Phase6] -> 图像/视频/音频生成
11. 输出成品 + 数据追踪初始化
```

### 5.3 Agent与版本映射

| Agent | Normal | Canvas | Hidden | Ultimate |
|-------|--------|--------|--------|----------|
| 小说分析师 | - | 自动 | 自动(+逆向构建) | 自动 |
| 一致性守护 | - | 自动 | +母题+张力 | +母题+张力 |
| 编剧(原点) | - | 10专家 | +4增强专家 | +4增强专家 |
| 微短剧编剧 | - | - | - | 自动 |
| 导演 | - | - | 全能力 | 全能力 |
| 视觉工程师 | - | - | 全能力 | 全能力 |
| 质量审核 | - | - | 增强评审 | +微短剧专项 |
| 数据优化 | - | - | - | 自动+沉淀 |
| 协调者 | - | - | - | 自动 |

### 5.4 Agent运行时架构

Agent不是常驻进程，而是**事件驱动的Celery Worker**。通过钩子(Hook)系统触发，按需唤醒执行，完成后回到空闲。

#### 5.4.1 生命周期状态机

```
                    +------------+
                    |  DORMANT   |  (版本不支持 / 未启用)
                    +-----+------+
                          | edition_check_pass
                          v
                    +------------+
         +--------->|   IDLE     |<---------+
         |          +-----+------+          |
         |                | event/hook      |
         |                v                 |
         |          +------------+          |
         |          | RUNNING    |----------+  (task_complete)
         |          +-----+------+
         |                |
         |          error | need_input
         |                v
         |          +------------+
         +----------| WAITING    |  (等待用户确认 / 等待其他Agent / 等待重试)
                    +------------+

状态持久化: Redis Hash  agent:{agent_id}:status
前端同步:   WebSocket 推送状态变化 -> AgentMonitor面板实时刷新
```

#### 5.4.2 钩子(Hook)触发体系

Agent靠三类钩子被唤醒，不需要轮询或常驻：

```
=== 1. 管线钩子 (Pipeline Hooks) — 阶段推进时触发 ===

  触发时机              -> 唤醒的Agent              -> 执行内容
  ─────────────────────────────────────────────────────────────
  文件上传完成           -> 分析师Agent              -> 解析+知识库构建
  知识库确认             -> 编剧Agent                -> Beat->场景生成
  剧本定稿               -> 导演Agent                -> 分镜拆解
  剧本定稿(并行)         -> 声音叙事模块             -> 声音设计
  分镜完成               -> 视觉Agent                -> Prompt生成
  分镜完成               -> 一致性Agent(母题终检)     -> 视觉叙事报告
  Prompt完成             -> [Phase6] 生成管线         -> 图像/视频

  实现: 后端在每个阶段完成的API endpoint末尾发布事件
  代码位置: backend/api/*.py 每个状态更新接口

  # 示例: 剧本定稿后触发
  @router.post("/projects/{id}/script/finalize")
  async def finalize_script(id: UUID):
      project = await update_project_stage(id, "script_finalized")
      # 管线钩子: 发布事件，唤醒下游Agent
      await event_bus.publish(Event(
          type="pipeline.script_finalized",
          project_id=id,
          payload={"scene_count": len(scenes)},
      ))
      return project

=== 2. 内容钩子 (Content Hooks) — 用户编辑时触发 ===

  触发时机              -> 唤醒的Agent              -> 执行内容
  ─────────────────────────────────────────────────────────────
  剧本文字变更(防抖2s)   -> 一致性Agent              -> 增量校验
  角色档案修改           -> 一致性Agent              -> 关联内容检查
  分镜参数修改           -> 视觉Agent                -> 重新生成Prompt
  张力值手动调整         -> 一致性Agent(张力模块)     -> 曲线重算

  实现: 前端编辑器通过WebSocket发送变更事件
  防抖: 用户停止编辑2秒后才触发(避免每次按键都唤醒)
  增量: 只传递变更的delta，不重新处理全文

  # 前端防抖发送
  const debouncedNotify = useDebouncedCallback((delta) => {
    ws.send({ type: "content.changed", scope: "script", delta });
  }, 2000);

=== 3. 定时钩子 (Schedule Hooks) — 周期性触发 ===

  频率                  -> 唤醒的Agent              -> 执行内容
  ─────────────────────────────────────────────────────────────
  每30分钟(活跃项目)     -> 一致性Agent              -> 全局一致性扫描
  每小时                -> 一致性Agent(张力模块)     -> 张力曲线偏离检测
  每天(有发布的项目)     -> 数据优化Agent            -> 拉取平台数据+分析

  实现: Celery Beat定时调度
  条件: 仅对"活跃项目"(最近24h有编辑)执行，避免空跑

=== 4. Agent间钩子 (Inter-Agent Hooks) — Agent互相触发 ===

  源Agent               -> 目标Agent               -> 场景
  ─────────────────────────────────────────────────────────────
  编剧Agent(场景完成)    -> 一致性Agent              -> 校验新场景
  一致性Agent(发现冲突)  -> 编剧Agent                -> 请求修正
  导演Agent(分镜完成)    -> 视觉Agent                -> 生成Prompt
  审核Agent(质量不达标)  -> 编剧/导演Agent           -> 返回修正(最多3轮)
  微短剧Agent(爽点标注)  -> 导演Agent                -> 爽点视觉增强
  协调者Agent            -> 任意Agent                -> 管线调度指令

  实现: AgentBus (Redis Pub/Sub) + 直接消息
```

#### 5.4.3 事件总线设计 (AgentBus)

```python
class Event:
    id: UUID
    type: str                    # "pipeline.script_finalized" / "content.changed" / ...
    project_id: UUID
    source: str                  # "api" / "user" / "agent:director" / "scheduler"
    payload: dict
    timestamp: datetime
    trace_id: UUID               # 链路追踪 (同一管线流程共享)

class AgentBus:
    """基于Redis Pub/Sub + Stream的事件总线"""

    # 频道设计
    CHANNELS = {
        "pipeline.*":     "管线阶段事件 (所有Agent可订阅)",
        "content.*":      "内容变更事件 (一致性Agent订阅)",
        "agent.{name}.*": "Agent私有频道 (定向消息)",
        "system.*":       "系统事件 (健康检查/配置变更)",
    }

    async def publish(self, event: Event):
        """发布事件到匹配的频道"""
        # 1. 写入Redis Stream (持久化, 防丢失)
        await redis.xadd(f"stream:{event.type}", event.to_dict())
        # 2. Pub/Sub广播 (实时通知)
        await redis.publish(event.type, event.to_json())
        # 3. 记录到事件日志 (调试面板用)
        await self._log_event(event)

    async def subscribe(self, pattern: str, handler: Callable):
        """Agent订阅事件模式"""
        # 消费者组: 同类Agent多实例时只有一个处理
        # 如: 3个一致性Agent worker, 一条消息只被其中一个消费

# Agent注册订阅 (在Agent初始化时声明)
AGENT_SUBSCRIPTIONS = {
    "analyst":     ["pipeline.file_uploaded", "pipeline.script_uploaded"],
    "consistency": ["pipeline.*", "content.*", "agent.consistency.*"],
    "screenwriter":["pipeline.knowledge_confirmed", "agent.screenwriter.*"],
    "director":    ["pipeline.script_finalized", "agent.director.*"],
    "visual":      ["pipeline.storyboard_complete", "agent.visual.*"],
    "reviewer":    ["pipeline.storyboard_complete", "pipeline.prompt_complete"],
    "micro_drama": ["pipeline.knowledge_confirmed", "agent.micro_drama.*"],
    "data_optimizer": ["pipeline.published", "scheduler.daily"],
    "coordinator": ["pipeline.*", "agent.*"],  # 监听一切
}
```

#### 5.4.4 任务队列与执行

```python
class AgentTaskQueue:
    """Celery任务调度"""

    # 优先级队列 (数字越小越优先)
    QUEUES = {
        "critical":  0,   # 用户正在等待的实时操作
        "pipeline":  1,   # 管线推进任务
        "background": 2,  # 定时扫描/数据拉取
    }

    # 重试策略
    RETRY_POLICY = {
        "max_retries": 3,
        "retry_backoff": True,           # 指数退避: 10s -> 30s -> 90s
        "retry_backoff_max": 300,        # 最大5分钟
        "retry_on": [APITimeoutError, RateLimitError],
        "no_retry_on": [ValidationError, EditionNotAllowed],
    }

    # 超时
    TIMEOUTS = {
        "analyst":      300,   # 5分钟 (长文小说解析)
        "screenwriter": 180,   # 3分钟 (单场景生成)
        "director":     120,   # 2分钟 (单场景分镜)
        "visual":       60,    # 1分钟 (单镜头Prompt)
        "consistency":  60,    # 1分钟 (增量校验)
    }

    # 降级策略: AI API不可用时
    FALLBACK = {
        "opus_unavailable":  "降级到sonnet",
        "sonnet_unavailable": "降级到haiku + 标记需人工审核",
        "all_unavailable":   "任务挂起 + 通知用户",
    }

# Celery Worker配置
# 每种Agent类型独立worker进程, 互不阻塞
celery_app.conf.task_routes = {
    "agents.analyst.*":      {"queue": "agent-analyst"},
    "agents.screenwriter.*": {"queue": "agent-screenwriter"},
    "agents.director.*":     {"queue": "agent-director"},
    "agents.visual.*":       {"queue": "agent-visual"},
    "agents.consistency.*":  {"queue": "agent-consistency"},
    "agents.coordinator.*":  {"queue": "agent-coordinator"},
}
```

#### 5.4.5 LLM调用层与心跳隔离

**核心原则: LLM是"嘴"，不是"心脏"。**

LLM不管理时间、不发心跳、不感知自己是否超时。所有时间敏感操作由Python基础设施层处理。
LLM只负责一件事：接收Prompt，返回文本。

```
系统三层分离:

  +------------------------------------------------------+
  |  Layer 1: 基础设施层 (Python/Celery/Redis)             |
  |  职责: 心跳、计时、重试、降级、状态管理                  |
  |  特点: 精确的系统时钟, 不依赖任何LLM                    |
  +------------------------------------------------------+
  |  Layer 2: Agent逻辑层 (Python业务代码)                  |
  |  职责: 组装Prompt、解析LLM输出、校验结果、写入DB         |
  |  特点: 调用LLM但不被LLM阻塞心跳                        |
  +------------------------------------------------------+
  |  Layer 3: LLM调用层 (HTTP API调用)                      |
  |  职责: 发送请求、接收streaming响应                       |
  |  特点: 纯I/O操作, 可能耗时30s~5min, 可中断可替换       |
  +------------------------------------------------------+

关键: Layer 1的心跳在独立线程/协程运行, 不被Layer 3的I/O阻塞。
即使LLM调用卡了3分钟, Worker心跳依然每30秒正常上报。
```

**LLM调用不阻塞心跳的实现:**

```python
class AIEngine:
    """统一的LLM调用层 — Agent通过此层调用LLM, 不直接调API"""

    async def call(
        self,
        prompt: str,
        model: str = "sonnet",
        task_id: UUID = None,
        timeout: int = 120,
        stream: bool = True,
    ) -> AIResponse:
        """
        所有LLM调用的唯一入口。
        心跳由Celery Worker主循环维持, 此处是普通的async I/O。
        Worker进程是多协程的: 心跳协程 + 任务协程并行, 互不阻塞。
        """
        start_time = time.monotonic()  # 系统单调时钟, 不是LLM感知的时间
        model_config = self._resolve_model(model)

        try:
            if stream:
                response = await self._stream_call(prompt, model_config, timeout)
            else:
                response = await self._batch_call(prompt, model_config, timeout)

            # 记录实际耗时 (系统时钟, 精确可靠)
            elapsed = time.monotonic() - start_time
            await self._log_call(task_id, model, elapsed, response.usage)
            return response

        except (httpx.TimeoutException, anthropic.APITimeoutError):
            elapsed = time.monotonic() - start_time
            await self._log_timeout(task_id, model, elapsed)
            raise AITimeoutError(model=model, elapsed=elapsed)

        except anthropic.RateLimitError:
            raise AIRateLimitError(model=model)

    def _resolve_model(self, requested: str) -> ModelConfig:
        """模型解析 + 可用性检查 (不涉及LLM, 纯本地逻辑)"""
        model_map = {
            "opus":   "claude-opus-4-6",
            "sonnet": "claude-sonnet-4-6",
            "haiku":  "claude-haiku-4-5-20251001",
        }
        return ModelConfig(
            model_id=model_map[requested],
            max_tokens=self._get_max_tokens(requested),
        )
```

**模型切换时的上下文接续:**

```python
class ModelFallbackManager:
    """
    模型降级时保证上下文连续性。
    LLM没有"记忆" — 每次调用都是独立的HTTP请求。
    上下文由Python代码管理, 不依赖LLM维持。
    """

    FALLBACK_CHAIN = ["opus", "sonnet", "haiku"]

    async def call_with_fallback(
        self,
        prompt: str,
        preferred_model: str,
        task_context: TaskContext,
    ) -> AIResponse:

        for model in self._chain_from(preferred_model):
            try:
                # 每次调用都传入完整上下文 — 模型切换对Prompt透明
                adjusted_prompt = self._adapt_prompt_for_model(prompt, model)
                response = await ai_engine.call(adjusted_prompt, model=model)

                # 记录实际使用的模型 (供调试面板和质量审计)
                task_context.actual_model = model
                if model != preferred_model:
                    task_context.degraded = True
                    task_context.degradation_reason = f"{preferred_model}_unavailable"

                return response

            except (AITimeoutError, AIRateLimitError) as e:
                # 当前模型不可用, 尝试下一个
                await self._log_fallback(task_context.task_id, model, str(e))
                continue

        # 所有模型都不可用
        raise AllModelsUnavailableError()

    def _adapt_prompt_for_model(self, prompt: str, model: str) -> str:
        """
        不同模型能力不同, Prompt可能需要微调:
        - opus: 完整Prompt, 最高复杂度
        - sonnet: 完整Prompt (能力足够)
        - haiku: 简化Prompt, 减少复杂推理要求, 增加结构化输出指令
        """
        if model == "haiku":
            return self._simplify_for_haiku(prompt)
        return prompt

    def _chain_from(self, start: str) -> list[str]:
        """从指定模型开始的降级链"""
        idx = self.FALLBACK_CHAIN.index(start)
        return self.FALLBACK_CHAIN[idx:]
```

**为什么LLM的"时间幻觉"不影响系统:**

```
LLM不参与任何时间敏感决策, 具体来说:

  时间相关操作          负责方              LLM参与?
  ──────────────────────────────────────────────────
  心跳上报              Celery Worker线程    否 (独立线程, 不受LLM调用阻塞)
  任务超时判定          Celery time_limit    否 (系统时钟 time.monotonic())
  重试间隔计算          Python退避算法       否 (10s * 2^n, 纯数学)
  定时钩子触发          Celery Beat          否 (cron调度器, 系统时钟)
  事件时间戳            Python datetime.now  否 (写入Event前由Python生成)
  管线阶段耗时统计      Python计时器         否 (start/end用monotonic clock)
  断路器半开等待30s     Python asyncio.sleep 否 (系统定时器)
  数据反馈采集周期      Celery Beat          否 (cron调度)

  LLM唯一的工作: 接收文本 -> 生成文本
  LLM不需要知道"现在几点""过了多久""下次什么时候执行"
  所有时序逻辑都在Python层用系统时钟完成

  即使LLM在Prompt里输出了错误的时间 (如"本次分析耗时2秒"但实际耗时30秒),
  系统也不会采信 — 耗时由Python的time.monotonic()记录。
```

**长时间LLM调用期间的状态同步:**

```python
class AgentTaskRunner:
    """任务执行器: 处理LLM长调用期间的状态更新"""

    async def execute_with_progress(self, agent: BaseAgent, task: AgentTask):
        """
        Celery Worker进程内部:
        - 心跳: Worker主循环自动维护 (Celery内置, 独立于任务)
        - 进度: 通过Redis推送给前端
        - LLM调用: async I/O, 不阻塞Worker事件循环
        """

        # 1. 更新状态: RUNNING
        await self._set_status(task, "running", progress=0)

        # 2. 分步执行 (以导演Agent 7步流程为例)
        steps = agent.get_execution_steps(task)
        for i, step in enumerate(steps):
            # 每步开始前更新进度 (前端实时显示)
            await self._set_status(task, "running",
                progress=i / len(steps),
                current_step=step.name,
            )

            if step.requires_llm:
                # LLM调用 — async等待, Worker心跳不受影响
                result = await ai_engine.call_with_fallback(
                    prompt=step.build_prompt(task.context),
                    preferred_model=agent.default_model,
                    task_context=task.context,
                )
                step.process_result(result, task.context)
            else:
                # 纯本地计算 (如张力值计算、格式转换)
                step.execute_local(task.context)

        # 3. 完成
        await self._set_status(task, "completed", progress=1)

    async def _set_status(self, task, status, **kwargs):
        """状态写入Redis + WebSocket推送前端"""
        data = {"status": status, "updated_at": datetime.utcnow().isoformat(), **kwargs}
        await redis.hset(f"task:{task.id}", mapping=data)
        await ws_manager.broadcast(task.project_id, {
            "type": "agent.progress",
            "task_id": str(task.id),
            **data,
        })
```

#### 5.4.6 健康保活与监控

```
=== 心跳机制 ===
  Celery Worker内置心跳 (与任务执行在不同线程):
    - Worker主进程每30秒上报心跳到Redis
    - key: worker:{worker_id}:heartbeat -> timestamp
    - LLM调用在任务协程中, 不阻塞心跳线程
    - 超过90秒无心跳 -> 标记UNHEALTHY -> Supervisor自动重启Worker

  重要: 心跳完全不经过LLM, 不受模型切换/超时/幻觉影响

=== 任务级超时 (双保险) ===
  soft_time_limit: 到时发SoftTimeLimitExceeded异常, Agent可优雅收尾
  hard_time_limit: 到时强制kill任务 (soft_limit + 30秒)

  示例: 导演Agent 7步流程
    soft_time_limit = 120s -> 超时后保存已完成的步骤, 标记"部分完成"
    hard_time_limit = 150s -> 强制终止

  超时由系统时钟判定, LLM无法"欺骗"系统觉得自己没超时

=== 任务卡死检测 ===
  terminated任务自动进入重试队列 (如果剩余重试次数 > 0)
  超过max_retries -> 标记FAILED -> 通知用户 + 记录到调试面板

=== 管线断路器 (Circuit Breaker) ===
  连续3次同类型失败 -> 断路器打开 -> 暂停该Agent新任务
  30秒后半开: 允许1个试探性任务
  成功 -> 关闭断路器, 恢复正常
  失败 -> 继续打开, 等待下次半开

  断路器计时: Python asyncio定时器, 非LLM

=== 模型健康度追踪 ===
  每个模型独立统计:
    - 最近100次调用的成功率/平均延迟/P99延迟
    - 连续失败次数
    - 最后成功调用时间
  当某模型健康度下降 -> 自动增大该模型的超时容忍 或 提前触发降级

=== 监控指标 (调试面板展示) ===
  每个Agent:
    - 当前状态 / 正在执行的任务 / 队列深度
    - 最近10次执行: 耗时 / token消耗 / 成功/失败 / 实际使用模型
    - 断路器状态: CLOSED / OPEN / HALF_OPEN
    - 降级次数和原因
  全局:
    - 管线进度: 当前阶段 + 已完成步骤 / 总步骤
    - 各模型: 成功率 / 延迟 / token消耗 / 费用
    - 事件总线: 未消费消息数 / 消费延迟
```

#### 5.4.6 协调者管线编排 (Ultimate)

```python
class PipelineOrchestrator:
    """协调者Agent的核心: 管线状态机"""

    PIPELINE_STAGES = [
        Stage("import",       agents=["analyst"]),
        Stage("knowledge",    agents=["analyst"],       wait_user=True),
        Stage("beat_sheet",   agents=["screenwriter"]),
        Stage("script",       agents=["screenwriter", "micro_drama"]),
        Stage("review",       agents=["consistency", "reviewer"],  max_rounds=3),
        Stage("data_optimize",agents=["data_optimizer"],           condition="is_micro_drama"),
        Stage("storyboard",   agents=["director"],                 parallel=["sound_narrative"]),
        Stage("visual_prompt",agents=["visual"]),
        Stage("final_check",  agents=["consistency"],              sub_task="motif_review"),
        Stage("generate",     agents=[],                           condition="phase6_ready"),
    ]

    async def advance(self, project_id: UUID):
        """推进管线到下一阶段"""
        current = await self.get_current_stage(project_id)
        # 检查当前阶段所有任务是否完成
        if not await self.all_tasks_complete(project_id, current):
            return  # 还没完成，等待

        next_stage = self.PIPELINE_STAGES[current.index + 1]

        # 条件检查 (如: data_optimize仅微短剧)
        if next_stage.condition and not await self.check_condition(project_id, next_stage.condition):
            next_stage = self.PIPELINE_STAGES[current.index + 2]  # 跳过

        # 需要用户确认的阶段
        if next_stage.wait_user:
            await self.notify_user_and_pause(project_id, next_stage)
            return

        # 派发任务给目标Agent
        for agent_name in next_stage.agents:
            await event_bus.publish(Event(
                type=f"pipeline.{next_stage.name}_started",
                project_id=project_id,
                source="agent:coordinator",
            ))

        # 并行任务
        if next_stage.parallel:
            for parallel_task in next_stage.parallel:
                await event_bus.publish(Event(
                    type=f"pipeline.{parallel_task}_started",
                    project_id=project_id,
                ))

    async def on_review_loop(self, project_id: UUID, round_num: int):
        """审核不通过时的循环修正"""
        if round_num >= 3:
            # 超过3轮，停止自动修正，交给用户
            await self.notify_user(project_id, "auto_review_exhausted")
            return
        # 将审核意见发回编剧/导演Agent
        await event_bus.publish(Event(
            type="agent.screenwriter.revision_requested",
            payload={"round": round_num, "issues": issues},
        ))
```

#### 5.4.7 基础类定义

```python
class BaseAgent:
    name: str
    required_edition: Edition
    status: AgentStatus           # DORMANT/IDLE/RUNNING/WAITING
    event_subscriptions: list[str]
    knowledge_modules: list[str]
    circuit_breaker: CircuitBreaker

    async def run(self, task: AgentTask) -> AgentResult:
        """执行具体任务 (子类实现)"""
        ...

    async def on_event(self, event: Event):
        """事件钩子入口: 收到订阅的事件后调用"""
        if not self._edition_allowed():
            return
        task = self._event_to_task(event)
        if self.circuit_breaker.is_open:
            await self._queue_for_retry(task)
            return
        self.status = AgentStatus.RUNNING
        try:
            result = await self.run(task)
            self.circuit_breaker.record_success()
            await self._publish_completion(result)
        except Exception as e:
            self.circuit_breaker.record_failure()
            await self._handle_error(task, e)
        finally:
            self.status = AgentStatus.IDLE

    async def communicate(self, target: str, message: AgentMessage):
        """Agent间直接通信"""
        await event_bus.publish(Event(
            type=f"agent.{target}.message",
            source=f"agent:{self.name}",
            payload=message.to_dict(),
        ))

    def load_knowledge(self, module: str) -> KnowledgeModule:
        """按版本权限加载知识库模块"""
        ...

class KnowledgeModule:
    name: str
    version: str
    prompts: list[PromptTemplate]
    rules: list[Rule]
    checklists: list[Checklist]
```

---

## 六、系统架构

### 6.1 双平台架构 (Web + 桌面)

```
+-------------------------------------------------------------+
|  Shared Core (95% 代码共享)                                    |
|  React + TypeScript + Zustand + TipTap + Yjs                 |
+---------------------------+-----------------------------------+
|  Web (Next.js + Vercel)   |  Desktop (Tauri 2.0 + Rust)      |
|  WebSocket协作             |  本地文件 + SQLite + 离线模式     |
+---------------------------+-----------------------------------+
|  Platform Abstraction Layer                                    |
|  storage / notification / file / network                       |
+-------------------------------------------------------------+
```

Tauri ~10MB vs Electron ~150MB, 内存减少50%+, Rust内存安全
离线同步: 本地SQLite + Op Log -> 联网后CRDT(Yjs)合并

### 6.2 技术栈

```
前端: React 18+ / TypeScript / TailwindCSS + shadcn/ui / Zustand
      TipTap + Yjs / dnd-kit / Framer Motion / React Flow / Recharts
Web:  Next.js 14+ / Hocuspocus / Vercel or Docker
桌面: Tauri 2.0 / Rust / SQLite
后端: Python FastAPI / Anthropic SDK / Celery + Redis / Hocuspocus
数据: PostgreSQL / SQLite(桌面) / Redis / S3-MinIO
知识库引擎: YAML/MD -> KnowledgeModule加载器 + 热加载(Ultimate)
```

### 6.3 团队协同

```
实时同步: Yjs (CRDT) + Hocuspocus WebSocket + TipTap协作
权限角色: Owner / Editor / Commenter / Viewer
协作功能: 多人光标 / 行内评论 / 任务指派 / 审批流 / 活动流
```

### 6.4 项目目录结构

```
novelflow/
+-- packages/
|   +-- shared/                      # 共享核心 95%
|   |   +-- components/
|   |   |   +-- ui/                  # shadcn
|   |   |   +-- editors/             # ScriptEditor, BeatEditor, ShotCard, Timeline
|   |   |   +-- panels/              # AIAssistant, AgentMonitor, CollabPresence, Comments
|   |   |   |                        # TensionCurve, SoundNarrative, MotifTracker
|   |   |   +-- workspace/           # Canvas, PanelLayout, Minimap
|   |   |   +-- wizard/              # StepNav, WizardLayout
|   |   |   +-- import/              # NovelImport, ScriptImport, AdaptationReport
|   |   |   +-- cards/
|   |   +-- stores/                  # project, editor, agent, collab, edition
|   |   +-- hooks/                   # useAgent, useCollaboration, useEdition, useKnowledge
|   |   +-- lib/                     # api, featureFlags, platform
|   |   +-- types/
|   +-- web/                         # Next.js
|   +-- desktop/                     # Tauri
|
+-- backend/
|   +-- main.py
|   +-- api/                         # REST routes
|   |   +-- projects.py
|   |   +-- import_novel.py
|   |   +-- import_script.py         # 剧本导入API
|   |   +-- script_adaptation.py     # 剧本适配API
|   |   +-- knowledge.py
|   |   +-- beats.py, script.py, storyboard.py
|   |   +-- ai_operations.py
|   |   +-- collaboration.py, teams.py
|   |   +-- data_feedback.py         # 数据反馈API
|   |   +-- export.py
|   +-- agents/
|   |   +-- base.py                  # BaseAgent + KnowledgeModule
|   |   +-- bus.py                   # AgentBus (Redis Pub/Sub)
|   |   +-- coordinator.py
|   |   +-- analyst.py
|   |   +-- consistency.py
|   |   +-- screenwriter.py
|   |   +-- micro_drama_writer.py
|   |   +-- director.py
|   |   +-- visual_prompt.py
|   |   +-- reviewer.py
|   |   +-- data_optimizer.py
|   |   +-- registry.py
|   +-- knowledge/
|   |   +-- loader.py                # YAML/MD -> KnowledgeModule
|   |   +-- modules/
|   |   |   +-- director_core.yaml
|   |   |   +-- director_advanced.yaml
|   |   |   +-- visual_design.yaml
|   |   |   +-- sequence_designers/  # 5个
|   |   |   +-- origin_screenwriter/ # 原点10专家
|   |   |   +-- micro_drama/         # 11节点
|   |   |   +-- sound_narrative.yaml
|   |   |   +-- mise_en_scene.yaml
|   |   |   +-- visual_motif.yaml
|   |   |   +-- tension_dynamics.yaml
|   |   |   +-- cultural_visual.yaml
|   |   |   +-- nonlinear_narrative.yaml
|   |   |   +-- theme_archaeology.yaml
|   |   |   +-- script_adaptation.yaml
|   |   |   +-- thrill_visual_linkage.yaml
|   |   |   +-- ip_extension.yaml
|   |   |   +-- data_patterns/       # 数据沉淀
|   |   +-- hot_reload.py
|   +-- services/
|   |   +-- ai_engine.py
|   |   +-- novel_parser.py
|   |   +-- script_parser.py         # 剧本格式解析器
|   |   +-- script_adapter.py        # 剧本适配引擎
|   |   +-- tension_engine.py        # 张力引擎
|   |   +-- collab_service.py
|   |   +-- export_service.py
|   +-- prompts/                     # YAML模板
|   +-- models/
|   +-- config.py
|
+-- knowledge-base/                  # 原始知识库Markdown
+-- infra/
+-- docs/
+-- turbo.json
+-- pnpm-workspace.yaml
```

### 6.5 数据模型

```
=== 核心业务 ===
Project (import_source: novel/script/blank)
  -> [小说入口] Chapter -> Beat -> Scene -> Shot -> VisualPrompt
  -> [剧本入口] ScriptAdaptationReport -> Scene -> Shot -> VisualPrompt
  -> KnowledgeBase -> Character/Location/WorldBuilding/StyleGuide

Shot 扩展字段:
  + sound_narrative JSONB      (声音叙事)
  + mise_en_scene JSONB        (场面调度)
  + tension_score DECIMAL      (张力值)
  + visual_motifs JSONB        (命中的视觉母题)
  + cultural_preset VARCHAR    (文化视觉预设)
  + thrill_type VARCHAR        (爽点类型标注, 微短剧)
  + thrill_visual_strategy JSONB  (爽点视觉增强策略)

=== 协作 ===
Team, Comment, Activity

=== Agent ===
AgentTask, AgentMemory, KnowledgeModuleVersion

=== 数据反馈 ===
PerformanceData (project_id, episode, platform, metrics_json, collected_at)
ContentPattern (pattern_type, description, evidence, confidence, source_projects[])
PlatformInsight (platform, genre, insight, data_points_count, updated_at)

=== 剧本适配 ===
ScriptAdaptationReport (project_id, scene_id, visual_readiness_score,
                        missing_elements, suggestions, user_action)
```

---

## 七、UI/UX 设计体系

**设计规范来源:**
- Apple Human Interface Guidelines (HIG 2025+)
- 参考界面: `界面设计规范/Snipaste_2026-03-05_18-19-00.png`
- 详细规范: `界面设计规范/苹果界面设计规范.txt`

### 7.1 设计原则 (Apple HIG适配)

```
+-------------------------------------------------------------------------+
|                   NovelFlow 设计原则 (HIG-Aligned)                       |
+-------------------------------------------------------------------------+
|                                                                         |
|  Principle 1: Hierarchy (层级感)                                        |
|  - 内容至上: 小说文本/剧本/分镜画面始终是视觉焦点                        |
|  - 控件和导航使用半透明/模糊材质，"浮于"内容之上但不抢焦点               |
|  - 层级: 内容层(不透明) -> 功能层(半透明) -> 浮动层(弹窗/面板)          |
|  - 卡片/面板使用微妙阴影和发光边框建立Z轴层次                           |
|                                                                         |
|  Principle 2: Harmony (和谐统一)                                        |
|  - Web端与桌面端视觉完全一致 (Shared Core组件库)                        |
|  - 圆角、间距、字重与系统原生控件对齐                                   |
|  - 所有动画使用spring物理缓动                                           |
|                                                                         |
|  Principle 3: Consistency (一致性)                                       |
|  - 所有版本共用同一套组件库                                              |
|  - 相同操作在不同阶段使用相同交互模式                                    |
|  - 快捷键全局统一，遵循系统惯例                                          |
|  - Light/Dark自动适配，Dark为默认                                        |
|                                                                         |
|  Principle 4: Content-Driven (内容驱动)                                  |
|  - 创作内容占据 >=60% 屏幕面积                                          |
|  - 所有面板可折叠/隐藏                                                   |
|  - AI结果直接嵌入内容区                                                  |
|                                                                         |
+-------------------------------------------------------------------------+
```

### 7.2 视觉规范

```
=== 色彩体系 ===

  主题模式: Dark (默认) / Light (可切换)
  自动跟随系统设置 (prefers-color-scheme)

  Dark Mode (默认):
    背景层级:
      Level 0 (最底层): #0a0a1a
      Level 1 (卡片/面板): #12122a
      Level 2 (弹出/浮动): #1a1a36
      Level 3 (工具提示): #242450

    Glass Effect (仿Liquid Glass):
      - backdrop-filter: blur(20px) saturate(180%)
      - 背景色: rgba(255,255,255,0.05) ~ 0.08
      - 边框: 1px solid rgba(255,255,255,0.08)
      - 上方高光线: 1px solid rgba(255,255,255,0.12)
      - 仅用于: 导航栏/工具栏/面板头部/浮动按钮/Agent面板
      - 主编辑区域不使用Glass

    强调色:
      主色: #6366f1 (Indigo)
      暖金: #e2b714 (进度/高亮/CTA)
      渐变: linear-gradient(135deg, #6366f1, #8b5cf6)

    语义色:
      成功: #22c55e | 警告: #f59e0b | 错误: #ef4444 | 信息: #3b82f6

    Agent状态色:
      运行中: #3b82f6 + pulse动画
      已完成: #22c55e | 等待中: #6b7280 | 错误: #ef4444
      不可用(版本限制): #374151 + lock icon

  Light Mode:
    背景: #fafafa -> #ffffff -> #f5f5f5
    Glass Effect: backdrop-filter: blur(20px), bg rgba(255,255,255,0.7)
    文字: #1a1a2e
    强调色/语义色不变

=== 字体体系 ===

  中文正文: "Noto Sans SC", system-ui, sans-serif
  英文正文: "Inter", system-ui, sans-serif
  剧本/代码: "JetBrains Mono", "SF Mono", monospace

  字号体系:
    xs: 11px    (辅助标签, 时间戳)
    sm: 13px    (次要信息, 按钮小字)
    base: 15px  (正文默认)
    lg: 17px    (卡片标题)
    xl: 20px    (面板标题)
    2xl: 24px   (页面标题)
    3xl: 30px   (大标题, 项目名)

  行高: 1.5 (正文) / 1.3 (标题) / 1.8 (剧本文本)
  中文: letter-spacing: 0.02em

=== 间距与圆角 ===

  间距 (4px基准):
    xs: 4px  sm: 8px  md: 12px  lg: 16px  xl: 24px  2xl: 32px  3xl: 48px

  圆角:
    sm: 6px (小按钮/标签) | md: 8px (按钮/输入框)
    lg: 12px (卡片/面板) | xl: 16px (模态框/Sheet) | full: 9999px

=== 阴影与边框 ===

  Dark Mode (发光边框替代阴影):
    卡片: border 1px rgba(255,255,255,0.06)
    浮动面板: border 1px rgba(255,255,255,0.1) + box-shadow 0 8px 32px rgba(0,0,0,0.5)
    弹窗: border 1px rgba(255,255,255,0.12) + box-shadow 0 16px 48px rgba(0,0,0,0.6)
    聚焦: ring 2px #6366f1

  Light Mode:
    卡片: shadow-sm | 浮动: shadow-lg

=== 动画规范 ===

  核心: Framer Motion

  过渡时长:
    微交互 (hover/press): 100-150ms
    面板展开/折叠: 200-300ms
    页面切换: 300-400ms
    Agent状态变化: 500ms

  缓动函数:
    默认: spring({ stiffness: 300, damping: 30 })
    退出: ease-out 200ms
    强调: spring({ stiffness: 400, damping: 25 })

  必须支持:
    prefers-reduced-motion: 禁用所有spring和弹性动画，改为简单fade

  Agent脉冲: @keyframes agentPulse { 0%,100% opacity:0.6; 50% opacity:1 } 2s infinite
  加载: 骨架屏 / AI流式文字渐现 / 长任务进度条
```

### 7.3 组件规范

```
=== 按钮 ===

  主按钮 (Primary):
    高度: 36px (md) / 44px (lg, HIG最小44pt触控目标)
    圆角: 8px | 背景: 品牌渐变 或 Glass + 强调色tint
    hover: 亮度+10%, 上移1px | active: 亮度-5%, scale(0.98)
    disabled: opacity 0.5

  次按钮 (Secondary): Glass背景 + 主色文字
  幽灵按钮 (Ghost): 无背景, hover浅背景
  图标按钮: 最小44x44px, 图标20px居中
  危险按钮: #ef4444 + 二次确认弹窗

=== 卡片 ===

  基础: Level 1背景, 1px rgba(255,255,255,0.06)边框, 12px圆角, 16px内边距
  hover: 边框变亮, 上移2px
  选中: 品牌色边框 + 2px强调线
  拖拽: scale(1.02), 阴影加深

  分镜卡片 (参考截图):
    缩略图: 16:9, 圆角8px
    信息: 镜号 + 景别标签 + 时长
    网格: 2/3/4列自适应 (<1200px:2列, 1200-1600:3列, >1600:4列)
    高清放大: 点击缩略图弹出大图预览

=== 导航 ===

  顶部导航栏: 48px高, Glass背景
    左: Logo + 项目名 | 中: 阶段Tab (胶囊切换器) | 右: 团队状态 + 设置

  左侧边栏 (macOS侧边栏惯例): 240px可拖拽, 可折叠(Cmd+\)
    分组: 章节/角色/场景/风格/声音/母题, 树形结构

  右侧面板: 320px可拖拽, Tab切换(AI/Agent/张力/声音/母题/一致性/评论)

=== 编辑器 (TipTap) ===

  等宽字体15px, 行间距1.8
  场景标题: 大写加粗+分隔线 | 角色名: 居中大写品牌色
  对话: 左右缩进25% | 括号注释: 左缩进30%斜体

  AI浮动工具栏: Glass背景, [改写][扩写][缩写][对话优化][AI聊天]

=== Sheet / Modal ===

  HIG Sheet规范: 底部/中央弹出, 16px圆角
  关闭: X + ESC + 背景点击 + 下滑手势

=== Toast ===

  右上角, Glass背景
  自动消失: 3s(成功) / 5s(警告) / 手动(错误)
```

### 7.4 页面布局

#### 7.4.1 普通版向导式
```
+--------------------------------------------------------------+
|  [Glass Nav] NovelFlow                        [设置][头像]     |
+--------------------------------------------------------------+
|                                                                |
|                    创建新项目                                  |
|                                                                |
|   +---------------------+    +---------------------+          |
|   |  [Glass Card]        |    |  [Glass Card]        |          |
|   |    从小说开始        |    |    从剧本开始        |          |
|   |  上传小说文件        |    |  上传剧本文件        |          |
|   |  AI自动分析         |    |  自动格式适配        |          |
|   |  生成知识库         |    |  逆向构建知识库      |          |
|   |  改编为剧本         |    |  评估优化建议        |          |
|   |  生成分镜           |    |  直接进入分镜        |          |
|   |  [品牌渐变按钮]      |    |  [品牌渐变按钮]      |          |
|   +---------------------+    +---------------------+          |
|                                                                |
|   -- 步骤进度条 (胶囊式, 当前高亮) --                          |
|   [导入] -> [知识库] -> [节拍] -> [剧本] -> [分镜]             |
|                                                                |
|         [<- 上一步]                    [下一步 ->]             |
+--------------------------------------------------------------+
```

#### 7.4.2 画布版工作台
```
+----------------------------------------------------------------------+
| [Glass Nav] NovelFlow | 项目名 | (导入)(知识库)(节拍)(剧本)(分镜)| 3在线|
+----------+-------------------------------------------+-------------------+
| [Glass]  |                                           |  [Glass Panel]    |
| 左侧边栏  |          主编辑区 (内容层, 不透明)          |  右侧面板          |
|          |                                           |                   |
| 章节      |  +-----------------+-----------------+    |  Tab: [AI][Agent] |
| +Ch.1    |  |  编辑器/卡片     |  预览/对照       |    |  [张力][声音]     |
| +Ch.2    |  |  (剧本/Beat     |  (原文/分镜     |    |  [母题][一致性]   |
| ------   |  |   /分镜网格)    |   /时间轴)      |    |  [评论]           |
| 角色      |  +-----------------+-----------------+    |                   |
| +张三    |                                           |  +--Agent Monitor-+|
| +李四    |  +-----------------------------------+    |  | 分析师: 运行    ||
| ------   |  | [Glass] 张力: ########_ 72          |    |  | 编剧:   空闲    ||
| 场景      |  | 色彩弧线: 暖->冷 [正常]              |    |  | 一致性: 监听    ||
|          |  +-----------------------------------+    |  +-----------------+|
|          |                                           |                   |
|          |  [Glass Toolbar]                          |  在线协作者:       |
|          |  [改写][扩写][缩写][AI对话][生成分镜]      |  [A] [B]          |
+----------+-------------------------------------------+-------------------+
| [Glass Status] 自动保存 v3.2 | AI: 1200tok | [导出] | 4人在线            |
+----------------------------------------------------------------------+

面板系统:
  - 所有面板可拖拽调整宽度
  - 主编辑区保持 >=50% 宽度
  - 支持水平/垂直分屏
```

#### 7.4.3 分镜网格视图
```
+----------------------------------------------------------------------+
| [Glass Nav] 分镜编辑器                          场景: INT.书房-夜      |
+----------+-------------------------------------------+-------------------+
| 场景导航  |  分镜网格                                  |  属性面板         |
|          |                                           |                   |
| Sc.1     |  +----------+ +----------+ +----------+   |  镜头 #003        |
| Sc.2 *   |  | [缩略图]  | | [缩略图]  | | [缩略图]  |   |  景别: [中景]     |
| Sc.3     |  | Shot 001  | | Shot 002  | | Shot 003  |   |  角度: [平角]     |
|          |  | 全景 3s   | | 中景 2s   | | 近景 2.5s |   |  运动: [推]       |
| 进度:     |  | [高清放大] | | [高清放大] | | [选中]    |   |  时长: [2.5s]    |
| 24/36    |  +----------+ +----------+ +----------+   |                   |
|          |                                           |  画面描述:        |
| 总时长:   |  +----------+ +----------+ +----------+   |  [张三缓缓站起   |
| 2:30     |  | Shot 004  | | Shot 005  | | Shot 006  |   |   面露震惊之色]  |
| /3:00    |  | 特写 1.5s | | 过肩 2s   | | 全景 4s   |   |                   |
|          |  | [高清放大] | | [高清放大] | | [高清放大] |   |  声音叙事:        |
|          |  +----------+ +----------+ +----------+   |  [环境声: 夜虫]   |
|          |                                           |  [音乐: 紧张弦乐] |
|          |  -- 时间轴 (底部) --                       |                   |
|          |  |001|002|003|004|005|  006  |             |  视觉Prompt:      |
|          |                                           |  [A young man...] |
|          |  -- 对应剧本 (可折叠) --                   |                   |
|          |  "张三猛地站起身来..."                      |                   |
+----------+-------------------------------------------+-------------------+
| [Glass] [+插入] [拆分] [合并] [调时长] [批量Prompt] [预览] [导出]        |
+----------------------------------------------------------------------+
```

#### 7.4.4 自用版调试面板
```
画布版基础 + 底部可展开调试面板 (Cmd+`):

+--------------------------------------------------------------+
| [Glass] Debug Panel                              [折叠]       |
+----------------+--------------------+----------------------------+
| Agent日志       | Prompt日志          | 知识库 + 数据反馈         |
|                |                    |                            |
| [导演]          | 声音叙事模块        | sound_narrative: loaded   |
| Step 4/7       | Input: 2800 tok    | tension_engine: 72/100    |
| 序列: 对白      | Output: 1200 tok   | visual_motif: 3/5 命中    |
| 子技能: OTS    | Latency: 2.1s      | 数据沉淀: 3条新模式       |
|                | [查看完整Prompt]    | 模型: opus-4-6 (切换)    |
+----------------+--------------------+----------------------------+

特性: 可拖拽高度 / 实时流式更新 / 虚拟滚动 / 按Agent/severity过滤
```

### 7.5 无障碍规范 (HIG强制)

```
1. 键盘导航: 所有功能可通过键盘完成, Tab顺序合理
2. 焦点环: 所有可交互元素 2px品牌色 Focus Ring
3. 颜色对比: 文字/背景 >= 4.5:1 (AA), 重要信息 >= 7:1 (AAA)
4. 不依赖颜色: Agent状态除颜色外有文字标签/图标
5. Reduced Motion: prefers-reduced-motion 禁用弹性/脉冲动画
6. 字体缩放: rem单位, 支持浏览器字号调整
7. 屏幕阅读器: aria-label / alt / role
8. 高对比模式: prefers-contrast: more -> 边框加粗, 背景纯色化

测试:
  - [ ] 纯键盘完成全流程
  - [ ] VoiceOver遍历无死角
  - [ ] 200%字体缩放不崩溃
  - [ ] Reduced Motion全降级
  - [ ] Dark/Light对比度达标
```

### 7.6 响应式与多窗口

```
断点: sm:640px | md:768px | lg:1024px | xl:1280px | 2xl:1536px

macOS桌面端:
  - 支持全屏/分屏 (Stage Manager)
  - 窗口缩小时自动折叠次要面板
  - 最小窗口: 800x600
  - 记忆窗口大小和面板布局

面板记忆: 宽度/折叠状态持久化, 不同阶段可有不同布局预设
```

---

## 八、开发计划

### Phase 0: 基础搭建 (1周)
- [ ] Monorepo (pnpm + Turborepo) + shared/web/backend初始化
- [ ] 版本门控系统 + 两套UI布局 + 主题
- [ ] DB Schema + Claude API + Docker Compose

### Phase 1: 核心管线 (4周)

#### Sprint 1 (Week 1-2): 双入口导入 + 知识库
- [ ] P1.1-P1.10 小说导入流程
- [ ] P1.11 剧本导入: 格式识别+解析器 (Fountain/FDX/自由格式)
- [ ] P1.12 剧本适配: 逆向Beat提取 + 知识库逆向构建
- [ ] P1.13 剧本适配: 分镜可执行性评估 + 优化建议
- [ ] P1.14 剧本适配报告UI
- [ ] P1.15 向导式UI: 导入选择页

**交付**: 双入口可用 — 小说或剧本都能进入知识库审核

#### Sprint 2 (Week 3-4): 剧本工作台
- [ ] Beat Sheet / 剧本编辑器 / AI辅助 / 原文对照 / 版本管理
- [ ] 张力引擎(简化版): 情感曲线可视化 + 基础张力评分
- [ ] 向导式UI: Step 3-4

### Phase 2: 分镜 + 画布 (4周)

#### Sprint 3 (Week 5-6): 分镜脚本
- [ ] 场景->分镜拆解 + 分镜卡片编辑器
- [ ] AI视觉Prompt生成 + 时间轴视图
- [ ] 声音设计基础标注
- [ ] 导出 + 向导端到端串通

#### Sprint 4 (Week 7-8): 画布版工作台
- [ ] 多面板布局 + 面板系统 + 多候选对比
- [ ] 版本历史 + 快捷键 + 体验打磨

### Phase 3: 知识库引擎 + Agent系统 (5周)

#### Sprint 5 (Week 9-10): 知识库引擎 + Agent基础
- [ ] YAML/MD -> KnowledgeModule加载器 + 版本门控
- [ ] Agent框架 (BaseAgent/Bus/TaskQueue) + Celery/Redis
- [ ] 知识库模块YAML化:
  sound_narrative / mise_en_scene / visual_motif / tension_dynamics
  cultural_visual / nonlinear_narrative / theme_archaeology
  script_adaptation / thrill_visual_linkage / ip_extension

#### Sprint 6 (Week 11-12): 核心Agent
- [ ] 小说分析师Agent (含剧本逆向构建)
- [ ] 一致性守护Agent (含视觉母题追踪 + 张力监控)
- [ ] 编剧Agent (原点10专家 + 4增强专家)
- [ ] 导演Agent (7步 + 5序列 + 声音叙事 + 场面调度 + 文化适配)

#### Sprint 7 (Week 13): 高级Agent + 全自动管线
- [ ] 视觉Prompt Agent / 质量审核Agent
- [ ] 微短剧编剧Agent / 数据优化Agent
- [ ] 协调者Agent + 知识库热加载 + 调试面板

### Phase 4: 团队协作 (3周)
Week 14-16: 认证/团队/Yjs+Hocuspocus/评论/任务/审批

### Phase 5: 桌面端 (3周)
Week 17-19: Tauri/离线/同步/Win+Mac安装包

### Phase 6: 视觉生成对接 (4周)
Week 20-23: AI图像(Kling/即梦/SD/MJ) / 视频 / TTS / FFmpeg / PS Agent

### Phase 7: 高级功能 (持续)
关系图谱 / 风格板 / 白标 / API / 数据仪表盘 / i18n / 知识库社区

---

## 九、验收标准

### 普通版 (Phase 1-2)
- [ ] 双入口: 小说导入 + 剧本导入均可完整走通
- [ ] 剧本导入: 格式识别->标准化->逆向知识库->适配评估->优化->分镜
- [ ] 小白用户无引导完成全流程
- [ ] AI streaming + 可撤销

### 画布版 (Phase 2-4)
- [ ] 3 Agent后台运行
- [ ] 编剧Agent原点10子专家正常
- [ ] 张力引擎可视化
- [ ] 5人同时编辑无冲突

### 隐藏版 (Phase 3)
- [ ] 6 Agent + 4增强子专家
- [ ] 声音叙事系统输出完整
- [ ] 场面调度标注重要场景
- [ ] 视觉母题追踪报告
- [ ] 跨文化视觉预设生效
- [ ] 多平台Prompt适配

### 自用版 (Phase 3)
- [ ] 9 Agent全部可用
- [ ] 双入口全自动管线
- [ ] 微短剧11节点 + 爽点视觉联动
- [ ] 数据反馈闭环 + 知识库沉淀
- [ ] 知识库热加载
- [ ] 调试面板: Agent/Prompt/知识库/数据/张力

### 桌面端 (Phase 5)
- [ ] Windows/Mac + 离线 + 同步 + 50万字流畅

---

## 十、开发规范

### 10.1 Monorepo
- pnpm + Turborepo, `@novelflow/shared` 引用

### 10.2 前端
- React函数式 + TS strict / Zustand + React Query / TailwindCSS + Framer Motion
- `useEdition()` hook控制版本差异

### 10.3 后端
- FastAPI / AI统一走 `ai_engine.py` / Agent基于 `base.py`
- 知识库通过 `knowledge/loader.py` + 热加载

### 10.4 知识库规范
- 模块定义: YAML(结构) + MD(Prompt内容)
- 声明: name, version, edition_required, prompts[], rules[], checklists[]
- 热加载: Ultimate版运行时修改

### 10.5 Git
- `main` / `dev` / `feature/Px.x-desc`
- `feat(module): desc` / `fix(module): desc`

---

## 十一、Prompt优先级

### MVP (Phase 1-2)

| 优先级 | ID | 名称 | 模型 | 说明 |
|--------|----|------|------|------|
| P0 | P01 | 章节分割 | Haiku | 小说入口 |
| P0 | P03 | 角色提取 | Sonnet | 小说入口 |
| P0 | P10 | 小说->Beat | Sonnet | 小说入口 |
| P0 | P11 | Beat->场景 | Sonnet | 共用 |
| P0 | PS01 | 剧本格式解析 | Haiku | 剧本入口 |
| P0 | PS02 | 剧本逆向Beat | Sonnet | 剧本入口 |
| P0 | PS03 | 剧本知识库构建 | Sonnet | 剧本入口 |
| P1 | PS04 | 分镜可执行性评估 | Sonnet | 剧本入口 |
| P1 | PS05 | 剧本适配优化 | Sonnet | 剧本入口 |
| P1 | P04 | 角色档案深化 | Sonnet | |
| P1 | P12 | 文本改写 | Sonnet | |
| P1 | P22 | 场景->分镜 | Sonnet | |
| P1 | P26 | 视觉Prompt | Sonnet | |

### Agent阶段 (Phase 3)

| 类别 | Prompt来源 |
|------|-----------|
| 编剧子专家 | 原点10专家 + @ThemeArchaeologist + @TimelineArchitect |
| 导演 | 7步流程 + 5序列 + 声音叙事 + 场面调度 + 文化适配 |
| 张力引擎 | tension_dynamics模块 |
| 视觉母题 | visual_motif模块 |
| 视觉Prompt | 9模块 + 爽点视觉联动 |
| 微短剧 | 11节点 + 数据模式参照 |

---

## 十二、里程碑

```
Phase 0 (1周)   ====                           基础搭建
Phase 1 (4周)   ================               双入口+核心管线
Phase 2 (4周)   ================               分镜+画布
Phase 3 (5周)   ====================           知识库+Agent
Phase 4 (3周)   ============                   团队协作
Phase 5 (3周)   ============                   桌面端
Phase 6 (4周)   ================               视觉生成
Phase 7 (持续)  ====================...        高级功能

关键节点:
  Week 5:  普通版MVP (双入口->分镜全流程)
  Week 9:  画布版可用 + 张力引擎
  Week 10: 知识库引擎 + 10个模块
  Week 13: 核心Agent全部上线
  Week 14: 全部Agent + 全自动管线
  Week 16: 团队协作
  Week 19: 桌面端
  Week 23: 视频生成链路打通
```

---

## 附录A: 已有资产

### 知识库文件
```
知识库/CC Skills — 导演分镜/ (core.md + advanced.md)
知识库/CC Skills — 镜头画面设计/ (advanced.md + README.md)
知识库/CC Skills — 镜头序列设计/ (5个.SKILL.md + README.md)
知识库/"原点"编剧系统/ (V2.0.md + 3模块.md + 8个@专家.md)
知识库/微短剧AI辅助编剧系统/ (00-11节点.txt + 改编方法论.txt)
```

### 外部资产
- PS Agent: `E:/小说转剧本/软件系统/ps_agent/` (Phase 6集成)
- 参考项目: `Toonflow-app-master/`, `novel-to-script/`

### 关键决策记录
- 暗色主题默认
- MVP先Web, 桌面端Phase 5
- 知识库分层加载 (core/advanced/full)
- 双入口: 小说 + 剧本
- 剧本导入需适配优化后才能高质量对接分镜
- Claude API Key: Ultimate设置页, 其他后端统一
- 初期数据库: Docker PG + 桌面SQLite
- 桌面端: Win + Mac双平台 (Tauri 2.0)
