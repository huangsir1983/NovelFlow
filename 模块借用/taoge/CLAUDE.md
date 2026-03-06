# CLAUDE.md - 涛割 (Taoge) 项目上下文

> 此文件为 Claude Code 提供项目上下文，帮助 AI 快速理解项目结构和当前开发状态。

## 项目简介

**涛割 (Taoge)** 是一个基于 PyQt6 的桌面应用，核心功能是 AI 短剧视频生成。采用"先图后视频 (I2V) + 多模型智能路由 + 标准化精品流程"模式。

- **当前版本**: 1.2.1
- **项目状态**: 中后期开发阶段
- **最后更新**: 2026-03-03 (v1.2.1)

## 代码规模

| 指标 | 数值 |
|------|------|
| Python 源文件 (src/) | 85 个 |
| 测试文件 (tests/) | 10 个 |
| 源代码行数 | ~30,800 行 |
| 测试代码行数 | ~2,414 行 |
| 数据库 | SQLite + SQLAlchemy ORM |

## 技术栈

- **前端**: PyQt6 桌面 GUI（深色/浅色主题）
- **后端**: Python 3.x + asyncio + aiohttp
- **数据库**: SQLite + SQLAlchemy 2.0 ORM
- **AI 集成**: DeepSeek LLM（openai SDK）
- **视频生成 API**: Vidu / Kling / Jimeng / ComfyUI
- **测试**: pytest + pytest-asyncio
- **设计模式**: Strategy · Factory · Router · Observer · Singleton

## 五层架构

```
UI Layer (PyQt6, 38个组件)
    ↓ pyqtSignal
Controller Layer (6个控制器)
    ↓
Service Layer (Generation · Scene · TaskQueue · Cost · AIAnalyzer · Export)
    ↓
Data Layer (SQLAlchemy ORM, 8个模型)
    ↓
External Integration Layer (Vidu · Kling · Jimeng · ComfyUI · DeepSeek)
```

## 目录结构

```
taoge/
├── src/
│   ├── main.py                          # 程序入口
│   ├── config/
│   │   ├── settings.py                  # JSON 配置管理
│   │   └── constants.py                 # Prompt 模板、动作库常量（中文）
│   ├── database/
│   │   ├── session.py                   # DatabaseManager 单例 + 会话管理
│   │   └── models/
│   │       ├── base.py                  # SQLAlchemy Base
│   │       ├── project.py              # Project 模型
│   │       ├── scene.py                # Scene 模型（含 AI 标签、首尾帧、generation_params）
│   │       ├── character.py            # Character + SceneCharacter 模型
│   │       ├── prop.py                 # Prop + SceneProp 模型（v1.1）
│   │       ├── task.py                 # Task 异步任务模型
│   │       └── cost.py                 # CostRecord + CostSummary 模型
│   ├── services/
│   │   ├── ai_analyzer.py              # AI 分析服务（画面/视频提示词、角色/道具提取）
│   │   ├── controllers/
│   │   │   ├── project_controller.py   # 项目 CRUD + SRT 导入
│   │   │   ├── generation_controller.py # 图片/视频生成 + I2V + 进度
│   │   │   ├── canvas_controller.py    # 画布属性持久化
│   │   │   ├── material_controller.py  # 角色素材管理
│   │   │   ├── act_controller.py       # 场次 CRUD + 分镜拆分 + 标签持久化
│   │   │   └── prop_controller.py      # 道具 CRUD + 场景关联（v1.1）
│   │   ├── generation/
│   │   │   ├── base_provider.py        # BaseProvider 抽象基类（Strategy）
│   │   │   ├── model_router.py         # 智能路由（6场景×4质量）
│   │   │   ├── image_gen_service.py    # 图像生成服务
│   │   │   ├── closed_source/
│   │   │   │   ├── vidu_provider.py    # Vidu API
│   │   │   │   ├── kling_provider.py   # Kling API（JWT 认证）
│   │   │   │   └── jimeng_provider.py  # 即梦 API
│   │   │   └── open_source/
│   │   │       └── comfyui_provider.py # ComfyUI（WebSocket + 工作流模板）
│   │   ├── scene/
│   │   │   ├── processor.py            # SRT 解析 + 场景分组
│   │   │   ├── prompt_generator.py     # Prompt 生成（6风格×8情绪）
│   │   │   └── image_first_workflow.py # I2V 8阶段工作流
│   │   ├── task_queue/
│   │   │   └── manager.py             # 优先级队列 + 异步执行 + 重试
│   │   ├── cost/
│   │   │   └── cost_tracker.py        # 实时积分 + 预警
│   │   └── export/
│   │       └── jianying_exporter.py   # 剪映项目导出
│   └── ui/
│       ├── main_window.py              # MainWindow（双模式：向导+画布）
│       ├── theme.py                    # 主题系统（深色/浅色）
│       ├── pixmap_cache.py             # 图片缓存
│       ├── resources/
│       │   └── dark_theme.py           # 深色主题 QSS
│       └── components/
│           ├── infinite_canvas_page.py # 四区域全屏入口页
│           ├── top_navigation_bar.py   # 顶部导航栏
│           ├── project_data_hub.py     # 数据中心（信号枢纽，6个控制器实例）
│           ├── base_canvas_view.py     # 无限画布基类（点阵网格/右键平移/滚轮平移/Ctrl缩放/网格吸附）
│           ├── canvas_mode.py          # CanvasView（卡片管理/框选打组/组工具栏/曲线连线/帧预览/底部控制栏）
│           ├── canvas_connections.py   # 曲线连线模块（CurvedConnectionLine/AnimatedDot/贝塞尔曲线）
│           ├── canvas_context_menu.py  # 右键菜单
│           ├── canvas_sidebar.py       # 画布左侧边栏（角色区+道具区）
│           ├── canvas_property_panel.py # 画布属性面板
│           ├── scene_work_canvas.py    # 场景工作画布（双击卡片进入，贝塞尔曲线连线+箭头）
│           ├── scene_detail_canvas.py  # 场景精编面板
│           ├── scene_editor_page.py    # 场景编辑器
│           ├── scene_card.py           # 场景卡片
│           ├── scene_adjustment_widget.py # 场景调整控件
│           ├── shot_property_panel.py  # 镜头属性面板
│           ├── video_preview_panel.py  # 视频预览
│           ├── first_last_frame.py     # 首尾帧控制
│           ├── character_extraction_widget.py # 角色提取
│           ├── script_structure_panel.py # 脚本结构面板
│           ├── projects_page.py        # 项目管理页
│           ├── materials_page.py       # 素材库页
│           ├── tasks_page.py           # 任务管理页
│           ├── settings_page.py        # 设置页面
│           ├── srt_import_dialog.py    # SRT 导入对话框
│           ├── storyboard_analysis_dialog.py # 分镜分析对话框
│           └── zones/
│               ├── script_zone.py      # 剧本区（QStackedWidget: 模式选择/剧情模式/解说模式）
│               ├── mode_select_panel.py # 模式选择面板（剧情模式/解说模式两张卡片）
│               ├── story_mode_panel.py  # 剧情模式面板（承载 UnifiedStoryCanvasView）
│               ├── unified_story_canvas.py # 统一无限画布（4个 ZoneFrame + SceneConnectionManager，垂直布局从下到上）
│               ├── zone_delegates.py    # 区域交互委托（ActSequenceZoneDelegate / ShotRhythmZoneDelegate / CharacterPropZoneDelegate）
│               ├── mindmap_branch_node.py # 思维导图分支节点（MindMapBranchNode + SceneConnectionManager）
│               ├── execution_node.py    # 剧本执行区纯绘制节点（ShotExecutionNode + EditableTextField）
│               ├── act_sequence_panel.py # 大场景序列区卡片类（SentenceCard/ActSummaryCard/ActGroupBackground）
│               ├── shot_rhythm_panel.py # 分镜节奏区卡片类（ShotCanvasCard / ActSectionHeader）
│               ├── shot_card_actions.py # 分镜卡操作组件（ShotCardPlusButton / ShotDragActionMenu / ImagePreviewNode / ShotImageConnection）
│               ├── shot_image_console.py # 图片生成控制台（ShotImageConsole / PopupSelector / ToolbarButton）
│               ├── asset_requirement_cards.py # 资产需求卡片系统（AssetRequirementCard / MultiAnglePreviewGroup / AssetConnectionManager）
│               ├── shot_execution_panel.py # 剧本执行区旧 QWidget 表单（已被 execution_node.py 替代）
│               ├── character_prop_zone.py # 角色道具区
│               ├── director_zone.py    # 导演画布区（QStackedWidget 双页面）
│               ├── smart_ps_window.py  # 智能PS独立窗口（QDialog 最大化）
│               ├── smart_ps_node_canvas.py # 智能PS ComfyUI节点画布（BaseCanvasView + 自动布局 + 连线）
│               ├── smart_ps_nodes.py   # 智能PS节点（InputAsset/PSCanvas/Snapshot/Dissolve/HDOutput）
│               ├── smart_ps_pipeline.py # 智能PS管线节点（ViewAngle/Expression/HDUpscale/AIMatting）
│               ├── smart_ps_agent_node.py # 智能PS嵌入式画布（EmbeddedCanvasWidget + LayerPanel）
│               ├── smart_ps_connections.py # 智能PS连线管理（PSConnection + DragConnectionLine）
│               └── pre_edit_zone.py    # 预编辑区
├── tests/                              # 10 个测试文件
├── data/                               # SQLite 数据库存储
├── generated/                          # 生成输出目录
├── materials/                          # 素材库
├── requirements.txt                    # 依赖清单
├── pytest.ini                          # pytest 配置
├── taoge_settings.json                 # 运行时配置
├── 开发进度报告.md                      # 详细开发进度报告
└── 开发路线图.md                        # 完整开发路线图
```

## 模块完成度

| 模块 | 完成度 | 状态 |
|------|--------|------|
| 数据库层 (database/) | 100% | 已完成 — 8个ORM模型，完整关系映射 |
| 生成服务 (generation/) | 95% | 已完成 — 5个Provider + 智能路由，待真实API测试 |
| 场景处理 (scene/) | 100% | 已完成 — SRT解析、Prompt生成、I2V工作流 |
| 任务队列 (task_queue/) | 100% | 已完成 — 优先级队列、异步执行、重试 |
| 成本追踪 (cost/) | 100% | 已完成 — 实时计费、预警机制 |
| 导出服务 (export/) | 100% | 已完成 — 剪映项目导出 |
| AI分析 (ai_analyzer) | 100% | 已完成 — 画面/视频提示词、角色/道具提取 |
| 控制器 (controllers/) | 100% | 已完成 — 6个控制器（Project/Generation/Canvas/Material/Prop/Act） |
| 配置 (config/) | 100% | 已完成 — JSON配置 + 中文Prompt模板 |
| 测试 (tests/) | 85% | 已完成 — 10个测试文件，核心链路覆盖 |
| UI层 (ui/) | 93% | **进行中** — 38个组件，四区域画布架构 |

## 已完成功能概要

| 时间 | 功能模块 | 主要文件 |
|------|----------|----------|
| 03-03 | 智能PS管线状态持久化 + 额外资产恢复 + 画布交互修复 + AnimatedDot安全保护 | `smart_ps_pipeline.py`, `smart_ps_node_canvas.py`, `smart_ps_window.py`, `smart_ps_agent_node.py`, `canvas_connections.py` |
| 03-02 | 智能PS节点拓扑重构：每资产独立管线链 + 拖拽快照 + 重置按钮 | `smart_ps_nodes.py`, `smart_ps_node_canvas.py` |
| 03-01 | 智能PS ComfyUI节点画布窗口 + 资产编辑器全屏 + Agent适配器 | `smart_ps_window.py`, `smart_ps_node_canvas.py`, `smart_ps_nodes.py`, `asset_editors/`, `workflow_adapter.py` |
| 02-26 | 多视角图片展开连线系统（缩略图网格 + 懒加载） | `asset_requirement_cards.py`, `zone_delegates.py` |
| 02-21 | 提示词框内联缩略图 + @资产弹窗 + 风格提示词更新 | `shot_image_console.py`, `unified_story_canvas.py` |
| 02-20 | 图片卡交互优化（鼠标定位 + 位置持久化 + 空闲自毁） | `shot_card_actions.py`, `unified_story_canvas.py` |
| 02-19 | 分镜卡+号拖拽交互 + 图片生成控制台 + 底部控制栏单按钮 | `shot_card_actions.py`, `shot_image_console.py`, `bottom_console_bar.py` |
| 02-15 | Zone布局从左到右→从下到上 + 思维导图分支节点 + 分组算法重写 | `unified_story_canvas.py`, `zone_delegates.py`, `mindmap_branch_node.py` |
| 02-14 | 标签持久化 + 全场景分镜 + 角色道具区集成画布 | `zone_delegates.py`, `act_controller.py`, `unified_story_canvas.py` |
| 02-13 | 剧情模式三栏→统一无限画布 + 手动打组/拆分/排序/剔除 | `unified_story_canvas.py`, `zone_delegates.py`, `execution_node.py` |
| 02-12 | 场景拆分/分析分离 + 句子-场次坐标匹配修复 + 项目名同步 | `act_sequence_panel.py`, `shot_rhythm_panel.py`, `story_mode_panel.py` |
| 02-11 | 画布交互重构（右键平移/框选打组/分组拖拽/底部控制栏） | `base_canvas_view.py`, `canvas_mode.py` |
| 02-10 | 画布曲线连线系统 + 场景工作画布 | `canvas_connections.py`, `scene_work_canvas.py` |
| 02-08 | AI提示词中文化 + 画布角色道具区 | `constants.py`, `canvas_sidebar.py` |

> 详细变更记录见 `开发进度报告.md`

## 待开发事项

### 阶段 1: 稳定化与联调 [当前]
- [ ] 全链路联调：SRT导入 → AI分析 → 图片生成 → 视频生成 → 剪映导出
- [ ] Vidu / Kling / Jimeng API 真实凭证对接测试
- [ ] ComfyUI 本地服务器连接稳定性测试
- [ ] 场景工作画布交互打磨
- [ ] 数据持久化完整性测试
- [ ] 错误处理与恢复机制完善

### 阶段 2: 核心体验提升
- [ ] 视频播放预览节点
- [ ] 历史版本对比
- [ ] 批量生成进度面板
- [ ] 画布性能优化（100+场景）
- [ ] 角色一致性跨场景预览

### 阶段 3: 高级功能
- [ ] 多场景连续视频生成（首尾帧衔接）
- [ ] 自定义 ComfyUI 工作流模板编辑器
- [ ] 视频转场效果 / 背景音乐轨道
- [ ] 项目模板

### 阶段 4-5: 优化与发布
- [ ] 性能优化（数据库查询、缓存、内存）
- [ ] Undo/Redo 系统
- [ ] PyInstaller / Nuitka 打包
- [ ] Windows 安装包

## API 对接状态

| Provider | 图片 | 视频 | I2V | 角色一致性 | 状态 |
|----------|------|------|-----|-----------|------|
| Vidu | ✅ | ✅ | ✅ | ✅ | 待真实测试 |
| Kling | ✅ | ✅ | ✅ | ✅ | 待真实测试 |
| Jimeng | ✅ | ✅ | ✅ | ❌ | 待完善 |
| ComfyUI | ✅ | ✅ | ✅ | ✅ | 待本地测试 |
| DeepSeek | ✅ | - | - | - | 已对接 |

## 开发约定

### 防崩溃规则（必须遵守）

- **QGraphicsScene 生命周期**: `scene.clear()` 会销毁所有子项及其包裹的 QWidget，需要保留的 QGraphicsProxyWidget 必须在 `clear()` 前用 `removeItem()` 摘除，且保持 Python 引用防止 GC
- **信号处理中禁止销毁发送者**: 在 `clicked` 等信号 slot 中**不得**直接销毁发出信号的对象（段错误）。同理 `QGraphicsItem` 回调中不得 `clear_all()` 销毁自身。正确做法：`setVisible(False)` + `QTimer.singleShot(0, ...)` 延迟销毁
- **QGraphicsProxyWidget 弹窗限制**: 禁止从 proxy widget 弹模态对话框（QColorDialog/QFileDialog），会中断画布事件链；用 `QFrame(Popup)` 或 `QMenu`
- **QGraphicsProxyWidget 事件分发**: `mousePressEvent` 中必须用 `_is_interactive_proxy()` 检测点击目标是否为 proxy widget，是则交给 `super()` 处理，否则按钮点击被框选拦截
- **AnimatedDot C++ 安全检查**: `_dot_alive()` 通过 `try/except RuntimeError` 检测存活，`_tick` 中已销毁则 `_timer.stop()`。`CurvedConnectionLine` 的 `update_position()/remove()` 同样需 `try/except` 保护
- **DatabaseManager 会话 API**: 使用 `db.session_scope()` 上下文管理器（自动 commit/rollback/close），**不是** `db.session()`。JSON 字段变更必须 `flag_modified(obj, 'field_name')`

### 画布架构

- **画布交互模型**: 右键拖动=平移，左键拖空白=框选，滚轮=垂直平移（反向），Shift+滚轮=水平平移，Ctrl+滚轮=缩放；DragMode 始终 NoDrag
- **画布缩放**: `BaseCanvasView` 使用 `NoAnchor`，缩放时手动 `mapToScene` 计算偏移并 `translate` 补偿
- **剧情模式统一画布**: `UnifiedStoryCanvasView` 一个 QGraphicsScene + 四个 `ZoneFrame`（大场景序列 | 分镜节奏 | 剧本执行 | 角色道具），垂直堆叠从下到上。`ZoneDelegate` 委托处理各区域交互
- **跨区域连线**: `SceneConnectionManager` 管理场景卡→分支节点→分镜卡的持久贝塞尔连线，分组/分镜加载后自动 `rebuild_all_connections()`
- **分支节点延迟重排**: toggle/solo 回调必须 `QTimer.singleShot(0, _deferred_relayout_and_rebuild)` 延迟，避免回调链中 `clear_all()` 销毁自身。重排流程：① relayout → ② _do_layout → ③ rebuild_connections → ④ update_all

### 智能PS架构

- **节点拓扑**: `InputAsset₁→ViewAngle₁→Expression₁→HDUpscale₁→AIMatting₁ → PSCanvasNode`，PS拖拽创建 `SnapshotNode → DissolveNode → HDOutputNode`
- **初始化时序**: `_build_graph()`（同步，含 `_restore_extra_assets`）→ `_preload_all_chains`（500ms）→ `_restore_pipeline_state`（800ms）→ `fit_all_in_view`（1000ms）
- **管线状态持久化**: `get_state()/restore_state()` 存取节点状态，只要有 `_output_pixmap` 就保存（不门控 `_is_confirmed`）。子类覆盖以保存额外参数（ViewAngle: 角度, Expression: 提示词），延迟 200ms 恢复嵌入控件。所有路径用 `os.path.join(os.getcwd(), ...)` 绝对路径
- **管线状态匹配**: `_restore_pipeline_state()` 优先按 `asset_name` 匹配链，回退到索引。数据存于 `generation_params['pipeline_state']['chains']`
- **额外资产持久化**: 粘贴/继承尾帧创建的链通过 `_save_extra_asset()` 保存到 `generation_params['extra_pipeline_assets']`，`_restore_extra_assets()` 在 `_build_graph()` 前恢复
- **内外层画布事件分发**: 右键通过 `_is_inside_ps_node()` 检测目标是否在 PSCanvasNode 内部，是则 `QGraphicsView.mousePressEvent` 透传给内层，否则走外层逻辑。显示右键菜单前先重置 `_is_panning=False`

### 剧情模式数据流

- **拆分流程**: 导入文本 → 句子卡片 → 场景拆分（仅分组）→ 场景分析（出摘要卡片+标签）→ AI 分镜拆分（批量逐组）
- **句子分组**: `_build_groups_from_acts()` 用双指针边界法按原文坐标分组，`_fill_uncovered_text()` 自动检测序幕/尾声
- **标签格式**: `Act.tags` JSON 支持 dict `{labels, emotion, emotion_detail, ...}` 和 list 两种格式，读取用 `_tags_has_content()` / `_extract_tags_labels()` 兼容
- **multi_angle_images 格式**: 数据库存 `[{"angle": "视角1", "path": "xx"}, ...]`（dict 列表），UI 层必须 `isinstance(img, dict)` 判断后取 `img.get('path', '')`

### 通用约定

- **ProjectDataHub**: 6个控制器（project/generation/canvas/material/prop/act），`pyqtSignal` 驱动 UI 更新
- **新建项目流程**: 所有入口 → `_create_blank_project()` → 编辑器 → ScriptZone 检测空 `source_type` → ModeSelectPanel
- **生成输出路径**: `generated/pipeline/`（管线输出）, `generated/paste/`（粘贴图片）, `generated/end_frames/`（尾帧）, `generated/view_angle/`（视角转换）
- **语言**: 所有 AI Prompt 模板和用户界面使用中文
- **异步**: 生成任务基于 asyncio + aiohttp，UI 层使用 QThread
- **配置文件**: `taoge_settings.json`（运行时）、`src/config/settings.py`（代码层）
- **测试**: `pytest` 运行，配置见 `pytest.ini`

## 运行方式

```bash
pip install -r requirements.txt
python src/main.py
```

## 参考文档

- `开发进度报告.md` — 详细的模块级开发进度和文件变更记录
- `开发路线图.md` — 完整的功能清单和路线图规划
