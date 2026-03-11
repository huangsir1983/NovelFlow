# TapNow 画布系统 — 软件设计需求文档

> 基于 TapNow (app.tapnow.ai) 的完整功能分析
> 文档版本: 1.0 | 日期: 2026-03-11
> 目标: 将 TapNow 的所有操作转换为可实施的软件设计需求

---

## 目录

1. [系统总览](#1-系统总览)
2. [画布核心系统](#2-画布核心系统)
3. [节点系统](#3-节点系统)
4. [连线系统](#4-连线系统)
5. [分组系统](#5-分组系统)
6. [AI 生成引擎](#6-ai-生成引擎)
7. [脚本与故事系统](#7-脚本与故事系统)
8. [电影级视觉控制](#8-电影级视觉控制)
9. [视频生成与编辑](#9-视频生成与编辑)
10. [音频系统](#10-音频系统)
11. [工作流模板系统](#11-工作流模板系统)
12. [社区与协作系统 (TapTV)](#12-社区与协作系统-taptv)
13. [积分与计费系统](#13-积分与计费系统)
14. [项目管理系统](#14-项目管理系统)
15. [导出与交付系统](#15-导出与交付系统)
16. [UI 布局与交互规范](#16-ui-布局与交互规范)
17. [键盘快捷键与手势](#17-键盘快捷键与手势)
18. [与虚幻造物的映射关系](#18-与虚幻造物的映射关系)

---

## 1. 系统总览

### 1.1 核心理念 (TapNow Manifesto)

TapNow 定义了一套创作语言体系：

| 概念 | 比喻 | 定义 | 系统映射 |
|------|------|------|----------|
| **Node (节点)** | Vocabulary (词汇) | 创意的原子单位 | 画布上每个可执行的功能块 |
| **Wire (连线)** | Logic (逻辑) | 思维的流动方向 | 节点间的数据/控制连接 |
| **Group (分组)** | Phrase (短语) | 将知识结晶为可复用章节 | 节点组合封装为可复用模板 |
| **Canvas (画布)** | Universe (宇宙) | 无限空间，自由编排 | 无限缩放平移的工作区 |

### 1.2 产品定位

- **不是**自由绘图白板 (不是 Figma/Miro)
- **是**可执行创作画布 — 每个节点代表一个可运行的 AI 操作
- **核心价值**: 将脚本/创意 → 视觉内容的全流程自动化

### 1.3 技术栈要求

```
前端画布: @xyflow/react v12 (React Flow)
状态管理: Zustand
UI 框架: React 19 + TailwindCSS + shadcn/ui
动画: Framer Motion
后端: FastAPI + Celery (异步任务)
AI: 多模型集成 (Anthropic / OpenAI / Midjourney / Runway / Kling 等)
```

---

## 2. 画布核心系统

### 2.1 无限画布 (Infinite Canvas)

#### REQ-CANVAS-001: 无限平移与缩放
- **描述**: 画布支持无限方向的平移和自由缩放
- **缩放范围**: 10% ~ 400%
- **平移方式**:
  - 鼠标中键拖拽
  - 触控板双指滑动
  - Space + 左键拖拽
- **缩放方式**:
  - Ctrl + 滚轮
  - 触控板双指捏合
  - 工具栏缩放按钮
  - 快捷键 Ctrl+0 重置为 100%
- **性能要求**: 500+ 节点时保持 60fps

#### REQ-CANVAS-002: 视口管理
- **Fit to View**: 自动缩放以展示所有节点
- **Fit to Selection**: 聚焦到选中节点
- **记忆视口**: 保存并恢复用户上次的视口位置和缩放级别
- **视口状态**: `{ x, y, zoom }` 持久化到 workflow JSON

#### REQ-CANVAS-003: 小地图 (MiniMap)
- **位置**: 右下角
- **功能**:
  - 展示全局节点分布缩略图
  - 可点击跳转到指定区域
  - 显示当前视口框
  - 支持折叠/展开
- **节点颜色**: 按节点类型/状态着色

#### REQ-CANVAS-004: 画布背景
- **网格**: 点阵/线格两种模式可选
- **暗色主题**: 默认深色背景 (符合影视创作氛围)
- **亮色主题**: 可切换
- **网格吸附**: 可选 — 节点位置可吸附到网格

#### REQ-CANVAS-005: 多选操作
- **框选**: 鼠标左键拖拽画布空白区域创建选框
- **加选**: Shift + 点击
- **全选**: Ctrl + A
- **反选**: 操作支持
- **批量移动**: 拖拽选中的任一节点，其余跟随
- **批量删除**: Delete 键
- **批量复制**: Ctrl + C / Ctrl + V

---

### 2.2 画布交互

#### REQ-CANVAS-006: 撤销/重做
- **Undo**: Ctrl + Z
- **Redo**: Ctrl + Shift + Z / Ctrl + Y
- **历史步数**: 至少 50 步
- **覆盖操作**: 节点增删、移动、连线变化、属性修改

#### REQ-CANVAS-007: 复制/粘贴
- **节点复制**: Ctrl + C 复制选中节点及其内部状态
- **粘贴**: Ctrl + V 在鼠标位置粘贴，自动偏移避免重叠
- **跨画布**: 支持在不同工作流画布间复制粘贴
- **快捷复制**: Ctrl + D 原地复制并偏移

#### REQ-CANVAS-008: 右键上下文菜单
- **画布空白处右键**:
  - 添加节点 (按类别展开子菜单)
  - 粘贴节点
  - 适应视图 (Fit View)
  - 排列节点 (Auto Layout)
  - 显示/隐藏网格
  - 显示/隐藏小地图
- **节点上右键**:
  - 运行此节点
  - 从此节点向前运行 (Forward Run)
  - 复制节点
  - 删除节点
  - 锁定/解锁
  - 折叠/展开
  - 添加评论
  - 查看运行日志
  - 查看结果历史
- **连线上右键**:
  - 删除连线
  - 添加中间节点
  - 查看数据流

#### REQ-CANVAS-009: 拖放添加节点
- **从节点库拖拽**: 从左侧面板拖入节点到画布
- **快速搜索添加**: 双击画布空白处 → 弹出搜索框 → 输入节点名称 → 回车添加
- **从连线拖出**: 从节点端口拖出连线到空白处 → 弹出兼容节点列表

#### REQ-CANVAS-010: 自动布局
- **水平流布局**: 从左到右自动排列
- **垂直流布局**: 从上到下自动排列
- **力导向布局**: 基于连接关系自动分布
- **局部重排**: 只对选中节点重新排列
- **动画过渡**: 布局变化使用 Framer Motion 平滑过渡

---

## 3. 节点系统

### 3.1 节点基础结构

#### REQ-NODE-001: 节点通用结构
每个节点包含：

```typescript
interface CanvasNode {
  id: string;
  type: NodeType;                    // 节点类型
  title: string;                     // 节点标题
  group: NodeGroup;                  // 所属分组
  position: { x: number; y: number }; // 画布位置

  // 端口
  ports: {
    inputs: Port[];                  // 输入端口
    outputs: Port[];                 // 输出端口
  };

  // 配置
  config: Record<string, unknown>;   // 节点参数配置

  // 状态
  status: 'idle' | 'queued' | 'running' | 'success' | 'error' | 'warning';
  progress?: number;                 // 0-100 执行进度

  // 结果
  latestResult?: NodeResult;         // 最新执行结果
  resultHistory?: NodeResult[];      // 历史结果列表

  // UI 状态
  collapsed: boolean;                // 是否折叠
  selected: boolean;                 // 是否选中
  locked: boolean;                   // 是否锁定
  displayMode: 'summary' | 'result' | 'config' | 'compare';
}
```

#### REQ-NODE-002: 节点端口 (Ports)

```typescript
interface Port {
  id: string;
  name: string;
  direction: 'input' | 'output';
  dataType: PortDataType;            // 数据类型
  required: boolean;
  connected: boolean;
  multiple: boolean;                 // 是否允许多条连线
}

type PortDataType =
  | 'text'       // 文本/脚本
  | 'image'      // 图片
  | 'video'      // 视频
  | 'audio'      // 音频
  | 'prompt'     // AI Prompt
  | 'config'     // 配置对象
  | 'any';       // 通用类型
```

#### REQ-NODE-003: 节点视觉状态
- **Idle (空闲)**: 灰色边框
- **Queued (排队中)**: 黄色脉冲
- **Running (运行中)**: 蓝色呼吸动画 + 进度条
- **Success (成功)**: 绿色边框 + 结果缩略图
- **Error (失败)**: 红色边框 + 错误提示
- **Warning (警告)**: 橙色边框

#### REQ-NODE-004: 节点折叠与展开
- **折叠态**: 仅显示标题、类型图标、状态指示器、缩略结果
- **展开态**: 显示完整配置面板和结果预览
- **双击切换**: 双击节点标题切换折叠/展开
- **全部折叠/展开**: 工具栏按钮

---

### 3.2 节点类型清单

#### 3.2.1 输入节点 (Input Group)

| 节点类型 | 功能 | 输入 | 输出 |
|----------|------|------|------|
| **REQ-NODE-INPUT-001: 文本输入** | 手动输入文本/脚本 | 无 | text |
| **REQ-NODE-INPUT-002: 脚本导入** | 导入剧本文件 | file | text, scenes[] |
| **REQ-NODE-INPUT-003: 小说导入** | 导入小说文件并解析 | file | text, chapters[] |
| **REQ-NODE-INPUT-004: 图片上传** | 上传参考图片 | file(s) | image(s) |
| **REQ-NODE-INPUT-005: 视频上传** | 上传参考视频 | file | video |
| **REQ-NODE-INPUT-006: 草图输入 (Draw-to-Video)** | 手绘草图 + 动作标注 | sketch + text | image + annotations |
| **REQ-NODE-INPUT-007: 角色包输入** | 导入角色资料 | character_data | character_profile |
| **REQ-NODE-INPUT-008: 风格包输入** | 导入视觉风格参考 | style_data | style_config |

#### 3.2.2 分析节点 (Analysis Group)

| 节点类型 | 功能 | 输入 | 输出 |
|----------|------|------|------|
| **REQ-NODE-ANALYSIS-001: 节拍提取** | 从文本中提取故事节拍 | text | beats[] |
| **REQ-NODE-ANALYSIS-002: 场景拆解** | 将文本拆分为场景 | text | scenes[] |
| **REQ-NODE-ANALYSIS-003: 角色分析** | 分析文本中的角色 | text | characters[] |
| **REQ-NODE-ANALYSIS-004: 冲突分析** | 分析戏剧冲突 | text | conflicts[] |
| **REQ-NODE-ANALYSIS-005: 情绪曲线** | 分析情绪变化 | text / beats | emotion_curve |
| **REQ-NODE-ANALYSIS-006: 动机分析** | 分析角色动机 | text + characters | motivations[] |
| **REQ-NODE-ANALYSIS-007: 亮点提取** | 提取叙事亮点 | text | highlights[] |

#### 3.2.3 创意节点 (Creative Group)

| 节点类型 | 功能 | 输入 | 输出 |
|----------|------|------|------|
| **REQ-NODE-CREATIVE-001: 节拍板** | 组织和编排故事节拍 | beats[] | beat_sheet |
| **REQ-NODE-CREATIVE-002: 剧本工作台** | AI 辅助剧本创作 | text + beats | screenplay |
| **REQ-NODE-CREATIVE-003: 张力引擎** | 调节叙事张力 | beats + emotion | tension_map |
| **REQ-NODE-CREATIVE-004: 情绪曲线编辑** | 可视化编辑情绪弧 | emotion_curve | refined_curve |

#### 3.2.4 导演节点 (Director Group)

| 节点类型 | 功能 | 输入 | 输出 |
|----------|------|------|------|
| **REQ-NODE-DIRECTOR-001: 场景分镜** | 生成分镜脚本 | scene + style | storyboard |
| **REQ-NODE-DIRECTOR-002: 镜头语言** | 设计镜头运动 | storyboard | shot_list |
| **REQ-NODE-DIRECTOR-003: 调度设计 (Blocking)** | 设计角色走位和舞台调度 | scene | blocking_map |
| **REQ-NODE-DIRECTOR-004: 声音叙事** | 设计声音/音乐叙事 | scene + emotion | sound_narrative |
| **REQ-NODE-DIRECTOR-005: 节奏设计** | 镜头节奏和剪辑节奏 | shots + emotion | rhythm_plan |
| **REQ-NODE-DIRECTOR-006: 文化视觉适配** | 不同文化背景的视觉调整 | scene + culture | adapted_visuals |

#### 3.2.5 视觉节点 (Visual Group)

| 节点类型 | 功能 | 输入 | 输出 |
|----------|------|------|------|
| **REQ-NODE-VISUAL-001: 角色锚定** | 角色视觉一致性锚点 | character + style | character_anchor |
| **REQ-NODE-VISUAL-002: 场景锚定** | 场景视觉一致性锚点 | scene_desc + style | scene_anchor |
| **REQ-NODE-VISUAL-003: 风格板** | 定义整体视觉风格 | references + config | style_board |
| **REQ-NODE-VISUAL-004: Prompt 组装** | 组装完整的 AI 生成 Prompt | anchors + shot + style | final_prompt |
| **REQ-NODE-VISUAL-005: 视觉主题追踪** | 追踪视觉主题贯穿一致性 | prompts[] | motif_report |

#### 3.2.6 生成节点 (Generation Group)

| 节点类型 | 功能 | 输入 | 输出 |
|----------|------|------|------|
| **REQ-NODE-GEN-001: AI 图片生成** | 根据 Prompt 生成图片 | prompt + config | image(s) |
| **REQ-NODE-GEN-002: AI 视频生成** | 根据图片/Prompt 生成视频 | image/prompt + config | video |
| **REQ-NODE-GEN-003: AI 语音合成 (TTS)** | 文本转语音 | text + voice_config | audio |
| **REQ-NODE-GEN-004: AI 音乐生成** | 生成配乐/音效 | music_prompt + config | audio |
| **REQ-NODE-GEN-005: 字幕生成** | 自动生成字幕 | audio/text | subtitle_srt |
| **REQ-NODE-GEN-006: 封面/海报生成** | 生成宣传物料 | prompt + style | image |
| **REQ-NODE-GEN-007: 素材批量生成** | 批量出图/出视频 | prompts[] + config | assets[] |
| **REQ-NODE-GEN-008: 高清放大 (Upscale)** | 图片 4K 放大 | image | hd_image |
| **REQ-NODE-GEN-009: 局部重绘 (Inpaint)** | 对图片指定区域重绘 | image + mask + prompt | edited_image |

#### 3.2.7 质量节点 (Quality Group)

| 节点类型 | 功能 | 输入 | 输出 |
|----------|------|------|------|
| **REQ-NODE-QA-001: 一致性检查** | 检查角色/场景视觉一致性 | images[] + anchors | consistency_report |
| **REQ-NODE-QA-002: 节奏检查** | 检查镜头节奏合理性 | timeline + shots | rhythm_report |
| **REQ-NODE-QA-003: 连续性检查** | 检查画面连续性 | shots[] | continuity_report |
| **REQ-NODE-QA-004: 风险警告** | 检测潜在问题 | workflow_state | risk_alerts[] |

#### 3.2.8 输出节点 (Output Group)

| 节点类型 | 功能 | 输入 | 输出 |
|----------|------|------|------|
| **REQ-NODE-OUT-001: 预演动画 (Animatic)** | 组合成预演视频 | shots + audio | animatic_video |
| **REQ-NODE-OUT-002: 剪映工程包导出** | 输出完整剪映项目 | all_assets | draft_package |
| **REQ-NODE-OUT-003: 分享包** | 生成可分享的项目包 | workflow + results | share_package |
| **REQ-NODE-OUT-004: 审阅包** | 生成审阅/评审包 | workflow + results | review_package |

---

### 3.3 节点交互操作清单

#### REQ-NODE-INTERACT-001: 节点选中
- 单击选中
- 选中态: 蓝色外框 + 轻微放大

#### REQ-NODE-INTERACT-002: 节点移动
- 按住节点标题拖动
- 支持网格吸附
- 支持对齐辅助线 (靠近其他节点时显示)

#### REQ-NODE-INTERACT-003: 节点调整大小
- 拖拽节点右下角调整宽度
- 最小宽度 200px，最大宽度 600px

#### REQ-NODE-INTERACT-004: 节点运行
- **单节点运行**: 点击节点上的运行按钮
- **从此节点向前运行 (Forward Run)**: 从当前节点开始，执行所有下游节点
- **选择性运行**: 选中多个节点后批量运行
- **全链运行**: 运行整个工作流

#### REQ-NODE-INTERACT-005: 节点结果查看
- 节点执行后，直接在节点卡片上显示结果缩略图
- 点击缩略图在右侧 Inspector 面板查看完整结果
- 支持结果历史回溯和版本对比

#### REQ-NODE-INTERACT-006: 节点配置
- 选中节点后，右侧 Inspector 显示完整配置面板
- 配置变化实时反映在节点上
- 支持配置的保存/加载/重置默认

---

## 4. 连线系统

### REQ-WIRE-001: 连线创建
- 从输出端口拖拽到输入端口
- 端口高亮提示兼容性 (类型匹配 = 绿色, 不匹配 = 红色)
- 释放在空白处时弹出兼容节点搜索菜单

### REQ-WIRE-002: 连线类型

```typescript
type WireKind =
  | 'data'      // 数据流: 传递生成结果
  | 'control'   // 控制流: 定义执行顺序 (Hidden/Ultimate 版本)
  | 'reference'; // 引用流: 读取但不消费数据
```

- **数据线**: 实线，随数据类型着色
- **控制线**: 虚线，灰色
- **引用线**: 点线，蓝色

### REQ-WIRE-003: 连线视觉
- **曲线类型**: 贝塞尔曲线 (Bezier)
- **动画**: 数据流动时显示流动粒子动画
- **选中态**: 加粗 + 高亮
- **悬停态**: 显示数据类型 tooltip

### REQ-WIRE-004: 连线管理
- 点击选中连线
- Delete 键删除选中连线
- 右键菜单: 删除 / 在中间插入节点 / 查看传输数据
- 不允许循环连接 (DAG 约束)

### REQ-WIRE-005: 自动连线推荐
- 新节点拖入画布时，高亮推荐可连接的端口
- 从模板生成的工作流自动预连线

---

## 5. 分组系统

### REQ-GROUP-001: 帧分组 (Frame)
- 创建可视化区域框 (类似 Figma 的 Frame)
- 标题 + 背景色 + 可折叠
- 节点拖入帧中自动归属
- 帧移动时内部节点一起移动

### REQ-GROUP-002: 场景帧
- 按场景 (Scene) 自动或手动分组
- 帧标题显示场景编号和名称
- 帧颜色按场景类型区分

### REQ-GROUP-003: 章节帧
- 按章节 (Chapter) 自动分组
- 嵌套: 章节帧 > 场景帧 > 节点

### REQ-GROUP-004: 组封装与复用
- 选中多个节点 → 「创建分组」
- 分组可保存为可复用模板
- 分组可导入到其他工作流
- 分组显示: 折叠态为单个大节点，展开态显示内部详情

---

## 6. AI 生成引擎

### REQ-AI-001: 多模型引擎集成

| 能力 | 支持的模型/引擎 | 用途 |
|------|-----------------|------|
| 文本/脚本 | Claude / GPT / DeepSeek | 剧本创作、分析、Prompt 优化 |
| 图片生成 | Midjourney / Imagen / DALL-E / Kling / Dreamina | 分镜图、角色图、场景图 |
| 视频生成 | Runway / Kling / Dreamina / Pika | 镜头视频、TVC、动画 |
| 语音合成 | TTS 引擎 | 角色配音、旁白 |
| 音乐生成 | Suno / Udio | 配乐、音效 |
| 图片增强 | TopazLabs / Real-ESRGAN | 高清放大、降噪 |

### REQ-AI-002: 模型选择器
- 每个生成节点可独立选择 AI 模型
- 显示模型信息: 名称、擅长领域、速度、价格/积分消耗
- 支持模型对比 (同一 Prompt 用不同模型生成结果并排比较)

### REQ-AI-003: 并发控制
- 根据用户版本限制并发生成数
  - Normal/免费: 1-2 并发
  - Canvas: 4 并发
  - Hidden: 8 并发
  - Ultimate: 无限制
- 排队机制: 超出并发数时进入队列

### REQ-AI-004: 生成参数控制

#### 图片生成参数:
- 尺寸: 预设比例 (1:1, 16:9, 9:16, 4:3, 2.35:1 等)
- 风格: 写实 / 动漫 / 水彩 / 油画 / 3D 渲染等
- 质量: 标准 / 高质量 / 超高质量
- 种子值 (Seed): 可锁定/随机
- 引导强度 (CFG Scale)
- 采样步数
- 负面提示词 (Negative Prompt)

#### 视频生成参数:
- 时长: 3s / 5s / 6s / 10s
- 帧率: 24fps / 30fps
- 运镜: 推/拉/摇/移/跟/升降
- 运动强度: 低/中/高
- 起始帧/结束帧 (Image-to-Video)

---

## 7. 脚本与故事系统

### REQ-SCRIPT-001: 脚本编辑器节点
- 内置富文本编辑器 (TipTap)
- 支持剧本格式: 场景标题、角色名、对白、动作描写、转场
- 自动格式化剧本排版
- AI 辅助续写 / 改写 / 润色

### REQ-SCRIPT-002: Script-to-Visual (脚本转视觉)
- 输入脚本文本或场景描述
- AI 自动生成对应的视觉分镜图
- 逐场景 / 逐段落生成
- 支持指定角色外观一致性约束

### REQ-SCRIPT-003: 场景描述解析
- AI 从脚本中提取:
  - 场景环境 (室内/室外、时间、天气、地点)
  - 角色 (在场人物、服装、表情、动作)
  - 道具 (关键物品)
  - 氛围 (情绪、光线、色调)
  - 镜头建议 (景别、角度)

### REQ-SCRIPT-004: 分镜脚本板 (Storyboard)
- 将场景描述转化为分镜卡片
- 每张卡片: 缩略图 + 场景号 + 镜头描述 + 对白
- 拖拽重新排序
- 支持画面说明标注

---

## 8. 电影级视觉控制

### REQ-CINEMA-001: 电影摄影机模拟
- **摄影机型号模拟**:
  - ARRI ALEXA 35
  - Sony VENICE 2
  - RED V-RAPTOR
  - Canon C70
  - Blackmagic URSA
- **效果**: 不同机型产生不同的色彩科学、动态范围、噪点特性
- **镜头模拟**: 焦距 (14mm ~ 200mm)、光圈 (f/1.2 ~ f/22)、景深效果

### REQ-CINEMA-002: 多角度重渲染
- 对已生成图片调整:
  - 旋转 (Rotation): 0° ~ 360°
  - 倾斜 (Tilt): 上下倾斜角度
  - 缩放 (Scale): 近景/远景调整
  - 广角变形 (Wide-angle): 透视畸变
- 重新生成保持角色/物体一致

### REQ-CINEMA-003: 影棚灯光控制
在画布上直接调节:
- **亮度 (Brightness)**: 整体明暗
- **色温 (Color Temperature)**: 暖色 (2700K) ↔ 冷色 (6500K)
- **主灯位置 (Key Light Position)**: 左/中/右 × 高/中/低
- **轮廓光 (Rim Light)**: 强度、颜色、方向
- **补光 (Fill Light)**: 阴影填充比例
- **环境光**: 颜色和强度

### REQ-CINEMA-004: 姿态控制
- 输入动作指令 (如"攀岩"、"挥手告别")
- AI 根据动作调整角色姿态
- 支持参考姿态图片上传

---

## 9. 视频生成与编辑

### REQ-VIDEO-001: Image-to-Video (图生视频)
- 输入: 静态图片 + 运动描述 Prompt
- 输出: 3~10 秒视频
- 控制: 运镜方向、运动强度、镜头速度

### REQ-VIDEO-002: Text-to-Video (文生视频)
- 输入: 文本描述
- 输出: 视频
- 先文字→图片→视频的两步流程

### REQ-VIDEO-003: Draw-to-Video (画生视频)
- 画布上提供画笔/草图工具
- 用户在已有图片上绘制运动路径和方向标注
- 添加动作文字描述
- AI 将草图 + 标注 → 生成平滑视频

### REQ-VIDEO-004: 视频对象替换
- 在视频中替换:
  - 人物: 换人 / 换脸
  - 服装: 替换衣着
  - 物体: 替换场景中的道具
- **约束**: 保持光线、运动、场景连续性

### REQ-VIDEO-005: 视频预览
- 画布节点内嵌视频播放器
- 支持循环播放
- 支持帧级检视
- 支持并排对比多个版本

---

## 10. 音频系统

### REQ-AUDIO-001: TTS 语音合成
- 多角色配音
- 音色选择/定制
- 语速、语调、情感控制
- 实时预听

### REQ-AUDIO-002: AI 音乐生成
- 风格描述生成音乐 (Suno / Udio 集成)
- 指定情绪、节奏、乐器
- 支持生成器乐 / 带歌词音乐
- 时长控制

### REQ-AUDIO-003: 音效生成
- 场景音效 (风声、雨声、脚步声等)
- 动作音效
- 环境氛围音

---

## 11. 工作流模板系统

### REQ-TEMPLATE-001: 模板库
- **预设模板类别**:
  - 电商广告 (产品图 → 广告视频)
  - 短剧创作 (小说 → 分镜 → 视频)
  - TVC 制作 (脚本 → 故事板 → 成片)
  - 社交媒体内容 (创意 → 图文/短视频)
  - 动画制作 (角色 → 场景 → 动画)
  - 音乐 MV (歌曲 → 视觉 → MV)
- 每个模板包含: 预设节点 + 预设连线 + 推荐参数

### REQ-TEMPLATE-002: 模板选择与应用
- 新建项目/工作流时显示模板选择器
- 模板缩略图预览
- 一键应用: 自动创建所有节点和连线
- 应用后可自由修改

### REQ-TEMPLATE-003: 模板推荐
- 根据用户输入 (小说/剧本) 的内容类型推荐匹配模板
- 基于使用历史推荐

### REQ-TEMPLATE-004: 自定义模板保存
- 将当前工作流保存为自定义模板
- 支持命名、描述、标签
- 支持分享到社区 (TapTV)

---

## 12. 社区与协作系统 (TapTV)

### REQ-COMMUNITY-001: 作品发布
- 将完成的项目/工作流发布到社区
- 支持设置: 公开 / 仅链接可见
- 展示: 最终成品 + 完整创作过程

### REQ-COMMUNITY-002: 作品探索
- 社区画廊: 瀑布流展示优秀作品
- 筛选: 类别 / 风格 / 热度 / 最新
- 搜索: 关键词 / 标签 / 作者

### REQ-COMMUNITY-003: 工作流 Fork/Clone
- **查看全过程**: 公开画布可查看完整节点和参数
- **克隆 (Clone)**: 一键复制整个工作流到自己的项目
- **Fork (分叉)**: 基于他人工作流创建自己的变体
- **Remix (混搭)**: 提取部分节点/组合到自己的工作流

### REQ-COMMUNITY-004: 社交功能
- 点赞 / 收藏
- 评论 / 讨论
- 关注创作者
- 创作者主页

### REQ-COMMUNITY-005: 工作流协作
- **实时协作**:
  - 多光标显示 (Presence Layer)
  - 可看到其他协作者正在操作的节点
- **评论锚定**:
  - 在画布的特定节点/区域添加评论
  - 评论线程
- **分享模式**:
  - 查看者: 只读浏览
  - 评论者: 可添加评论
  - 编辑者: 可修改工作流
  - 审批者: 可批准/拒绝修改
- **帧区域 (Frame)**:
  - 标注重点区域
  - 会议演示模式 (Presentation Mode)

---

## 13. 积分与计费系统

### REQ-BILLING-001: 积分系统 (Tapies)
- 所有 AI 生成操作消耗积分
- 不同操作消耗不同积分:

| 操作类型 | 大约积分消耗 |
|----------|--------------|
| 图片生成 (标准) | ~2 Tapies |
| 图片生成 (高质量) | ~4 Tapies |
| 视频生成 (5s) | ~10 Tapies |
| 视频生成 (10s) | ~20 Tapies |
| TTS 语音 | ~1 Tapie |
| AI 音乐 | ~1 Tapie |
| 图片高清放大 | ~2 Tapies |

### REQ-BILLING-002: 版本等级

| 版本 | 积分 | 并发数 | 视频上限 | 图片上限 | 音频上限 |
|------|------|--------|----------|----------|----------|
| 免费 | 200 (注册赠送) | 1-2 | 限额 | 限额 | 限额 |
| Starter | 1,500/年 | 4 | ~150 | ~670 | ~1,000 |
| Pro | 6,000/年 | 8 | ~600 | ~2,700 | ~4,000 |
| Enterprise | 36,000/年 | 无限 | ~3,000 | ~13,500 | ~20,000 |

### REQ-BILLING-003: 积分管理 UI
- 积分余额显示 (Header)
- 操作前预估消耗提示
- 积分不足警告
- 充值/升级入口
- 消耗历史记录

---

## 14. 项目管理系统

### REQ-PROJECT-001: 项目列表
- 项目卡片展示: 缩略图 + 名称 + 更新时间 + 状态
- 排序: 最近 / 创建时间 / 名称
- 筛选: 状态 / 类型
- 新建项目按钮

### REQ-PROJECT-002: 项目内结构
```
Project
├── Story Bible (故事圣经)
├── Characters (角色列表)
├── Scenes (场景列表)
├── Workflows (工作流列表)
│   ├── Workflow 1 (Canvas 画布)
│   ├── Workflow 2
│   └── ...
├── Assets (素材库)
│   ├── Generated Images
│   ├── Generated Videos
│   ├── Audio
│   └── References
└── Exports (导出记录)
```

### REQ-PROJECT-003: 项目设置
- 项目名称、描述
- 默认 AI 模型配置
- 默认视觉风格
- 协作者管理
- 版本历史

---

## 15. 导出与交付系统

### REQ-EXPORT-001: 素材导出
- 单个素材下载 (图片/视频/音频)
- 批量打包下载
- 格式选择: PNG/JPG/WEBP (图片), MP4/MOV (视频), WAV/MP3 (音频)

### REQ-EXPORT-002: 剪映工程包导出
- 输出完整剪映 Draft 包:
  - 视频片段 (按时间线顺序)
  - TTS 语音文件
  - AI 音乐文件
  - SRT 字幕文件
  - 时间线草稿
  - 导演标记 (剪辑建议点)
- 用户在剪映中完成精剪、调色、后期

### REQ-EXPORT-003: 分镜稿导出
- PDF 格式分镜脚本
- 每页: 画面 + 场景号 + 镜头描述 + 对白 + 音效标注

### REQ-EXPORT-004: 宣传物料导出
- 封面图
- 海报
- 预告片
- 社交媒体格式裁切

### REQ-EXPORT-005: 工作流导出
- 导出工作流 JSON (不含生成结果)
- 导出工作流完整包 (含所有结果文件)
- 导入工作流

---

## 16. UI 布局与交互规范

### REQ-UI-001: 整体布局

```
┌──────────────────────────────────────────────────────────────┐
│  Header: Logo | 项目名 | 保存状态 | 运行状态 | 积分 | 用户   │
├──────┬──────────────────────────────────────────┬────────────┤
│      │                                          │            │
│  左  │                                          │   右侧     │
│  侧  │           中心画布区域                    │   面板     │
│  面  │      (Infinite Canvas + Nodes)           │            │
│  板  │                                          │  Inspector │
│      │                                          │  Result    │
│      │                                          │  History   │
│      │                                          │            │
├──────┴──────────────────────────────────────────┴────────────┤
│  底部栏: 运行控制台 | 事件流 | 警告摘要 | 缩放控制 | 小地图   │
└──────────────────────────────────────────────────────────────┘
```

### REQ-UI-002: Header 栏
- Logo + 首页链接
- 面包屑: 项目 > 工作流
- 保存状态指示器 (已保存 / 保存中 / 未保存)
- 全局运行状态 (空闲 / 运行中 / 完成 / 错误)
- 积分余额显示
- 协作者头像
- 分享按钮
- 用户菜单

### REQ-UI-003: 左侧面板 (可折叠, 默认宽度 280px)
分为多个标签页:
- **模板库 (Templates)**: 工作流模板列表, 搜索, 分类
- **节点库 (Nodes)**: 所有可用节点类型, 按 Group 分类, 搜索, 拖拽到画布
- **素材树 (Assets)**: 项目素材层级树, 图片/视频/音频缩略图
- **场景导航 (Scenes)**: 场景列表, 点击跳转到对应帧

### REQ-UI-004: 右侧面板 (可折叠, 默认宽度 360px)
根据选中内容动态切换:
- **Node Inspector (节点检查器)**:
  - 节点标题编辑
  - 配置参数面板
  - 输入绑定设置
  - 输出设置
  - 运行设置
- **Result Panel (结果面板)**:
  - 最新生成结果 (全尺寸预览)
  - 多版本切换
  - 结果对比 (A/B Split View)
  - 下载/导出按钮
- **Writeback Panel (回写面板)**:
  - 将结果写回项目数据 (Scene / Shot / Character 等)
  - 预览写回效果
  - 确认/取消
- **History (历史)**:
  - 运行历史列表
  - 每次运行的参数和结果
  - 恢复历史版本

### REQ-UI-005: 底部栏
- **运行控制台 (Run Console)**: 实时显示节点执行日志
- **事件流 (Event Stream)**: 系统消息 (连接成功/失败、排队等)
- **警告摘要**: 一致性/质量问题汇总
- **缩放控制**: - / 百分比 / + / Fit View
- **小地图切换**: 显示/隐藏

### REQ-UI-006: 工具栏 (Canvas 上方浮动)
- 选择工具 (指针)
- 平移工具 (手)
- 框选工具
- 添加评论
- 运行全部
- 停止运行
- 自动布局
- 保存

---

## 17. 键盘快捷键与手势

### REQ-KB-001: 快捷键列表

| 操作 | 快捷键 |
|------|--------|
| 撤销 | Ctrl + Z |
| 重做 | Ctrl + Shift + Z |
| 复制 | Ctrl + C |
| 粘贴 | Ctrl + V |
| 快速复制 | Ctrl + D |
| 全选 | Ctrl + A |
| 删除 | Delete / Backspace |
| 保存 | Ctrl + S |
| 运行工作流 | Ctrl + Enter |
| 运行选中节点 | Shift + Enter |
| 适应视图 | Ctrl + 0 |
| 放大 | Ctrl + = |
| 缩小 | Ctrl + - |
| 搜索节点 | Ctrl + K |
| 快速添加节点 | 双击画布空白处 |
| 折叠/展开节点 | 双击节点标题 |
| 锁定节点 | Ctrl + L |
| 分组选中节点 | Ctrl + G |
| 打开/关闭左面板 | Ctrl + [ |
| 打开/关闭右面板 | Ctrl + ] |
| 打开/关闭底部面板 | Ctrl + \ |

### REQ-KB-002: 触控板手势
- 双指平移: 移动画布
- 双指捏合: 缩放画布
- 三指左右滑: 撤销/重做

---

## 18. 与虚幻造物的映射关系

### 18.1 概念映射

| TapNow 概念 | 虚幻造物对应概念 | 差异说明 |
|-------------|-----------------|----------|
| Canvas | 中段可执行画布 | 定位一致，但虚幻造物更强调影视叙事深度 |
| Node | WorkflowNode | 虚幻造物增加版本门控 + 回写机制 |
| Wire | WorkflowEdge | 虚幻造物增加 control/reference 类型 |
| Group | WorkflowGroup / Frame | 虚幻造物绑定场景/章节语义 |
| TapTV | 社区系统 (待建) | 虚幻造物可简化为工作流分享 |
| Tapies | 积分系统 | 虚幻造物按版本付费 + 积分混合模式 |
| Template | WorkflowTemplate | 完全对应 |
| Draw-to-Video | 草图节点 + 视频生成节点 | 可分解为两个节点 |
| Script-to-Visual | 前段工作台 → 中段画布 | 虚幻造物分为三段实现 |

### 18.2 虚幻造物独有优势 (超越 TapNow)

1. **三段式创作系统**: 前段(创作) → 中段(画布) → 后段(预演) — TapNow 仅有画布
2. **故事深度**: 节拍分析、张力引擎、情绪曲线 — TapNow 偏通用
3. **版本门控**: Normal/Canvas/Hidden/Ultimate 四层 — TapNow 仅按积分
4. **显式回写**: 结果经审批后写回项目数据 — TapNow 为直接覆盖
5. **资产库系统**: 跨项目可复用资产 + 视觉锚定 — TapNow 无
6. **剪映/CapCut 无缝交付**: Draft 工程包导出 — TapNow 仅素材导出
7. **影视级知识库**: 导演分镜、镜头设计知识体系 — TapNow 无

### 18.3 实施优先级建议

#### P0 — 画布核心 (必须首先实现)
- [ ] 无限画布 (平移/缩放/背景)
- [ ] 节点系统 (创建/移动/删除/选中)
- [ ] 连线系统 (创建/删除/类型检查)
- [ ] 节点执行 (单节点运行/全链运行)
- [ ] 右侧 Inspector 面板
- [ ] 左侧节点库面板
- [ ] 撤销/重做

#### P1 — 核心生成能力
- [ ] 文本输入节点
- [ ] AI 图片生成节点
- [ ] AI 视频生成节点 (Image-to-Video)
- [ ] Prompt 组装节点
- [ ] 结果预览与历史
- [ ] 工作流保存/加载

#### P2 — 叙事深度 (虚幻造物差异化)
- [ ] 脚本导入/解析节点
- [ ] 小说导入/解析节点
- [ ] 场景分镜节点
- [ ] 角色/场景锚定节点
- [ ] 节拍提取节点
- [ ] 张力/情绪引擎节点

#### P3 — 高级画布功能
- [ ] 分组/帧系统
- [ ] 工作流模板系统
- [ ] 自动布局
- [ ] 批量生成
- [ ] 版本对比
- [ ] 协作功能 (多光标、评论)

#### P4 — 社区与交付
- [ ] 工作流分享/克隆
- [ ] 社区画廊
- [ ] 剪映工程包导出
- [ ] 宣传物料生成

---

## 附录 A: 技术实现参考

### React Flow (@xyflow/react v12) 核心 API

```typescript
// 画布容器
<ReactFlow
  nodes={nodes}
  edges={edges}
  onNodesChange={onNodesChange}
  onEdgesChange={onEdgesChange}
  onConnect={onConnect}
  nodeTypes={customNodeTypes}
  edgeTypes={customEdgeTypes}
  fitView
  snapToGrid
  snapGrid={[16, 16]}
  minZoom={0.1}
  maxZoom={4}
>
  <Background variant="dots" gap={16} />
  <Controls />
  <MiniMap nodeColor={nodeColor} />
  <Panel position="top-left">
    {/* 工具栏 */}
  </Panel>
</ReactFlow>
```

### 自定义节点注册

```typescript
const nodeTypes = {
  // Input Group
  textInput: TextInputNode,
  scriptImport: ScriptImportNode,
  novelImport: NovelImportNode,
  imageUpload: ImageUploadNode,
  sketchInput: SketchInputNode,

  // Analysis Group
  beatExtraction: BeatExtractionNode,
  sceneBreakdown: SceneBreakdownNode,
  characterAnalysis: CharacterAnalysisNode,

  // Creative Group
  beatBoard: BeatBoardNode,
  screenplayWorkbench: ScreenplayWorkbenchNode,

  // Director Group
  storyboard: StoryboardNode,
  shotLanguage: ShotLanguageNode,
  blocking: BlockingNode,

  // Visual Group
  characterAnchor: CharacterAnchorNode,
  sceneAnchor: SceneAnchorNode,
  styleBoard: StyleBoardNode,
  promptAssembly: PromptAssemblyNode,

  // Generation Group
  imageGeneration: ImageGenerationNode,
  videoGeneration: VideoGenerationNode,
  ttsGeneration: TTSGenerationNode,
  musicGeneration: MusicGenerationNode,

  // Quality Group
  consistencyCheck: ConsistencyCheckNode,
  rhythmCheck: RhythmCheckNode,

  // Output Group
  animaticOutput: AnimaticOutputNode,
  draftExport: DraftExportNode,
};
```

### Zustand Store 结构

```typescript
interface CanvasStore {
  // Workflow state
  nodes: Node[];
  edges: Edge[];

  // Selection
  selectedNodes: string[];
  selectedEdges: string[];

  // Execution
  runningNodes: Set<string>;
  nodeResults: Map<string, NodeResult[]>;

  // UI State
  leftPanelOpen: boolean;
  leftPanelTab: 'templates' | 'nodes' | 'assets' | 'scenes';
  rightPanelOpen: boolean;
  rightPanelTab: 'inspector' | 'result' | 'writeback' | 'history';
  bottomPanelOpen: boolean;

  // History (undo/redo)
  history: CanvasSnapshot[];
  historyIndex: number;

  // Actions
  addNode: (type: string, position: Position) => void;
  removeNode: (id: string) => void;
  updateNodeConfig: (id: string, config: Record<string, unknown>) => void;
  addEdge: (edge: Edge) => void;
  removeEdge: (id: string) => void;
  runNode: (id: string) => Promise<void>;
  runWorkflow: () => Promise<void>;
  undo: () => void;
  redo: () => void;
}
```

---

## 附录 B: API 端点总览

| 类别 | 方法 | 端点 | 说明 |
|------|------|------|------|
| 工作流 | POST | `/api/projects/{id}/workflows` | 创建工作流 |
| 工作流 | GET | `/api/projects/{id}/workflows` | 获取工作流列表 |
| 工作流 | PUT | `/api/workflows/{id}` | 更新工作流 (节点/连线) |
| 工作流 | DELETE | `/api/workflows/{id}` | 删除工作流 |
| 模板 | GET | `/api/workflow-templates` | 获取模板列表 |
| 模板 | POST | `/api/workflow-templates` | 保存为模板 |
| 模板 | GET | `/api/workflow-templates/recommend` | 推荐模板 |
| 执行 | POST | `/api/workflows/{id}/runs` | 执行整个工作流 |
| 执行 | POST | `/api/workflows/{id}/nodes/{nodeId}/runs` | 执行单个节点 |
| 执行 | POST | `/api/workflows/{id}/nodes/{nodeId}/forward-run` | 从节点向前执行 |
| 执行 | GET | `/api/workflows/{id}/runs/{runId}` | 获取执行状态 |
| 执行 | POST | `/api/workflows/{id}/runs/{runId}/cancel` | 取消执行 |
| 结果 | GET | `/api/workflows/{id}/nodes/{nodeId}/artifacts` | 获取节点结果 |
| 结果 | GET | `/api/workflows/{id}/nodes/{nodeId}/artifacts/latest` | 最新结果 |
| 结果 | POST | `/api/artifacts/compare` | 对比两个结果 |
| 回写 | POST | `/api/projects/{id}/writebacks/preview` | 预览回写 |
| 回写 | POST | `/api/projects/{id}/writebacks/confirm` | 确认回写 |
| AI | POST | `/api/ai/generate/image` | 图片生成 |
| AI | POST | `/api/ai/generate/video` | 视频生成 |
| AI | POST | `/api/ai/generate/audio/tts` | TTS 生成 |
| AI | POST | `/api/ai/generate/audio/music` | 音乐生成 |
| AI | POST | `/api/ai/analyze/text` | 文本分析 |
| AI | GET | `/api/ai/models` | 获取可用模型列表 |
| 积分 | GET | `/api/billing/balance` | 查询积分余额 |
| 积分 | GET | `/api/billing/history` | 消耗记录 |
| 社区 | POST | `/api/community/publish` | 发布到社区 |
| 社区 | GET | `/api/community/gallery` | 社区画廊 |
| 社区 | POST | `/api/community/clone/{id}` | 克隆工作流 |
| 导出 | POST | `/api/exports/draft-package` | 剪映工程包 |
| 导出 | POST | `/api/exports/storyboard-pdf` | 分镜 PDF |

---

## 附录 C: 数据模型总览

```typescript
// 工作流
interface Workflow {
  id: string;
  projectId: string;
  name: string;
  templateId?: string;
  status: 'draft' | 'active' | 'archived';
  editionScope: 'normal' | 'canvas' | 'hidden' | 'ultimate';
  workflowJson: {
    nodes: WorkflowNode[];
    edges: WorkflowEdge[];
    groups: WorkflowGroup[];
    viewport: { x: number; y: number; zoom: number };
  };
  createdAt: string;
  updatedAt: string;
}

// 节点结果
interface NodeArtifact {
  id: string;
  nodeId: string;
  runId: string;
  type: 'text' | 'image' | 'video' | 'audio' | 'prompt' | 'report';
  url?: string;
  content?: string;
  metadata: Record<string, unknown>;
  version: number;
  createdAt: string;
}

// 执行记录
interface WorkflowRun {
  id: string;
  workflowId: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  startedAt: string;
  completedAt?: string;
  nodeRuns: NodeRun[];
  creditsUsed: number;
}

interface NodeRun {
  id: string;
  nodeId: string;
  runId: string;
  status: 'pending' | 'running' | 'success' | 'error' | 'skipped';
  startedAt: string;
  completedAt?: string;
  inputData: Record<string, unknown>;
  outputArtifacts: string[];  // artifact IDs
  error?: { code: string; message: string };
  creditsUsed: number;
}
```

---

> **参考资料**:
> - [TapNow 官网](https://www.tapnow.ai/)
> - [TapNow 文档](https://docs.tapnow.ai/en/docs)
> - [TapNow Manifesto](https://www.tapnow.ai/manifesto)
> - [TapNow 定价](https://www.tapnow.ai/pricing)
> - [TapNow 社区创作者计划](https://www.tapnow.ai/creator-program)
> - [React Flow (@xyflow/react)](https://reactflow.dev)
> - 项目内部文档: `CANVAS_SYSTEM_DESIGN.md`, `CANVAS_API_SPEC.md`, `WORKFLOW_SCHEMA.md`, `TRI_STAGE_CREATIVE_UX.md`, `newplan3.md`
