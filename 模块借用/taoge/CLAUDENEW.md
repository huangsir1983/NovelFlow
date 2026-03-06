# CLAUDE.md - 涛割 (Taoge) 项目上下文（融合版）

> 此文件为 Claude Code 提供项目上下文，帮助 AI 快速理解项目结构和当前开发状态。本版已融合外部参考软件（以下简称“参考软件”）的核心功能和设计理念，包括其总控中心、画布交互、分镜/故事板生成、角色/风格库、快捷功能等。融合目标：增强从分镜脚本到视频生成的闭环工作流，实现高效、标准化AI短剧视频生产。参考软件的网页式交互（如工具栏、快捷键）被适配到PyQt6桌面GUI中，确保无缝集成。

## 项目简介

**涛割 (Taoge)** 是一个基于 PyQt6 的桌面应用，核心功能是 AI 短剧视频生成。采用"先图后视频 (I2V) + 多模型智能路由 + 标准化精品流程"模式。融合参考软件后，工作流更注重闭环设计：从脚本输入、分镜脚本生成、故事板/分镜创建、图片/视频生成，到最终导出。强调角色一致性、风格自定义、快捷优化，以及电商/慢剧扩展。

- **当前版本**: 1.1.7 (融合预备版)
- **项目状态**: 中后期开发阶段，融合参考软件功能进入迭代期
- **最后更新**: 2026-02-17 (融合设计需求文档)
- **融合亮点**: 引入参考软件的画布式交互（拖拽排序、废片删除）、故事板（100张分镜生成）、快捷功能（提示增强），并与现有五层架构对接。实现从脚本到视频的自然闭环：输入脚本 → AI分析生成分镜/故事板 → 图片生成（I2V） → 视频合成 → 导出/成本统计。

## 代码规模

| 指标 | 数值（预融合） | 融合后预期变化 |
|------|---------------|---------------|
| Python 源文件 (src/) | 83 个 | +10-15 个（新增画布组件、故事板服务、快捷模块） |
| 测试文件 (tests/) | 10 个 | +5 个（覆盖融合功能如分镜排序、角色库测试） |
| 源代码行数 | ~29,489 行 | +5,000-8,000 行（交互逻辑、AI路由扩展） |
| 测试代码行数 | ~2,414 行 | +1,000 行（异步生成、错误处理测试） |
| 数据库 | SQLite + SQLAlchemy ORM | 新增字段（如故事板JSON、风格库表） |

## 技术栈

- **前端**: PyQt6 桌面 GUI（深色/浅色主题），融合参考软件的画布交互（QGraphicsView扩展，支持拖拽、缩放、双击编辑）
- **后端**: Python 3.x + asyncio + aiohttp
- **数据库**: SQLite + SQLAlchemy 2.0 ORM（扩展模型支持故事板、风格库）
- **AI 集成**: DeepSeek LLM（openai SDK），融合参考软件模型（如BananaPro、Mejourney、Vivo、Kling）；新增逆向代理（如云雾）支持低成本生成
- **视频生成 API**: Vidu / Kling / Jimeng / ComfyUI，融合参考软件的多参视频（纹生/图生视频）
- **测试**: pytest + pytest-asyncio
- **设计模式**: Strategy · Factory · Router · Observer · Singleton，新增Command模式（快捷功能）、Composite模式（故事板树状结构）
- **融合技术**: QKeyEvent（快捷键如空格拖动、/触发菜单）、QGraphicsItem（分镜卡片自适应）、asyncio.Queue（任务闭环管理）

## 五层架构（融合后）

融合参考软件后，架构扩展为支持闭环工作流：脚本输入 → 分镜/故事板 → 生成 → 导出。新增跨层信号（如故事板生成信号触发画布刷新）。

```
UI Layer (PyQt6, 38+组件)  # 新增: 总控输入框、工具栏（左侧:角色/风格库；右侧:下载/排序）、画布（QGraphicsScene扩展）
    ↓ pyqtSignal (融合: 分镜排序信号、快捷菜单信号)
Controller Layer (6+控制器)  # 新增: StoryboardController (故事板管理)、QuickFuncController (快捷功能)
    ↓
Service Layer (Generation · Scene · TaskQueue · Cost · AIAnalyzer · Export)  # 扩展: GenerationService (融合I2V路由、故事板生成)；新增: StyleService (风格库)、MergeService (Stack合并)
    ↓
Data Layer (SQLAlchemy ORM, 8+模型)  # 扩展: Scene (新增storyboard_json字段)；新增: Style (风格库模型)、QuickTemplate (快捷模板)
    ↓
External Integration Layer (Vidu · Kling · Jimeng · ComfyUI · DeepSeek)  # 融合: BananaPro/Mejourney (图片)、Vivo/Kling (视频)；新增云雾代理 (逆向低成本)
```

## 目录结构（融合后预期）

```
taoge/
├── src/
│   ├── main.py                          # 程序入口（初始化融合控制器）
│   ├── config/
│   │   ├── settings.py                  # JSON 配置管理（新增融合模型API密钥、风格模板）
│   │   └── constants.py                 # Prompt 模板、动作库常量（中文）；新增参考软件常量（如比例:16:9、21:9）
│   ├── database/
│   │   ├── session.py                   # DatabaseManager 单例 + 会话管理
│   │   └── models/
│   │       ├── base.py                  # SQLAlchemy Base
│   │       ├── project.py              # Project 模型（新增storyboard_path字段）
│   │       ├── scene.py                # Scene 模型（含 AI 标签、首尾帧、generation_params；新增storyboard_json）
│   │       ├── character.py            # Character + SceneCharacter 模型（融合角色库一致性）
│   │       ├── prop.py                 # Prop + SceneProp 模型（v1.1）
│   │       ├── task.py                 # Task 异步任务模型（扩展支持故事板任务）
│   │       ├── cost.py                 # CostRecord + CostSummary 模型
│   │       ├── style.py                # 新增: Style 模型（风格库）
│   │       └── quick_template.py       # 新增: QuickTemplate 模型（快捷功能模板）
│   ├── services/
│   │   ├── generation_service.py       # GenerationService（融合I2V、故事板生成、多模型路由）
│   │   ├── scene_service.py            # SceneService
│   │   ├── task_queue.py               # TaskQueue（异步生成队列，融合失败重试）
│   │   ├── cost_service.py             # CostService
│   │   ├── ai_analyzer.py              # AIAnalyzer（融合提示增强）
│   │   ├── export_service.py           # ExportService（融合批量下载/素材包）
│   │   ├── style_service.py            # 新增: StyleService（风格库管理）
│   │   └── merge_service.py            # 新增: MergeService（Stack合并、废片删除）
│   ├── controllers/
│   │   ├── project_controller.py       # ProjectController
│   │   ├── generation_controller.py    # GenerationController（融合分镜/视频生成）
│   │   ├── canvas_controller.py        # CanvasController（融合画布交互）
│   │   ├── material_controller.py      # MaterialController（角色管理，融合角色库）
│   │   ├── prop_controller.py          # PropController（道具管理）
│   │   ├── act_controller.py           # ActController（分镜节奏）
│   │   ├── storyboard_controller.py    # 新增: StoryboardController（故事板管理）
│   │   └── quick_func_controller.py    # 新增: QuickFuncController（快捷功能）
│   ├── ui/
│   │   ├── main_window.py              # MainWindow（融合总控中心、工具栏）
│   │   ├── canvas_panel.py             # CanvasPanel（融合画布：拖拽、缩放、双击编辑）
│   │   ├── zone_1_script_zone.py       # Zone1ScriptZone（脚本区，融合句子卡片原文坐标）
│   │   ├── zone_2_shot_rhythm.py       # Zone2ShotRhythmZone（分镜区，融合卡片排序/删除）
│   │   ├── zone_3_script_exec.py       # Zone3ScriptExec（剧本执行，融合镜头分析）
│   │   ├── zone_4_role_prop.py         # Zone4RoleProp（角色道具，融合角色/风格库）
│   │   ├── storyboard_widget.py        # 新增: StoryboardWidget（故事板网格显示）
│   │   └── quick_menu.py               # 新增: QuickMenu（斜杠触发快捷功能）
│   ├── utils/
│   │   ├── logger.py                   # Logger
│   │   ├── ai_utils.py                 # AI 工具函数（融合提示优化）
│   │   ├── graphics_utils.py           # 图形工具（融合贝塞尔线、浮动按钮）
│   │   └── async_utils.py              # 异步工具（融合生成失败处理）
│   └── tests/                          # 测试目录（新增融合功能测试）
└── docs/                               # 文档（新增融合工作流图）
    ├── 开发进度报告.md
    ├── 开发路线图.md
    └── 融合工作流.md                   # 新增: 闭环工作流描述
```

## 关键功能与融合设计（闭环工作流）

融合参考软件后，工作流形成完整闭环：脚本输入 → AI分镜/故事板 → 图片生成 → 视频合成 → 导出/优化。所有操作通过总控中心（融合参考软件的核心）驱动，确保自然流畅。以下按阶段描述设计需求。

### 1. 分镜脚本阶段（输入与分析）
- **输入脚本**: 用户在Zone1ScriptZone导入/编辑脚本（原文）。融合参考软件的笔记功能：支持@角色（e.g., "@大壮和@王丽娟滑雪"），自动关联Character模型。
- **AI分析与分组**: AIAnalyzer使用DeepSeek LLM分析脚本，生成act组（_build_groups_from_acts()）。融合参考软件的故事板：新增StoryboardService，生成20-100张分镜（e.g., "生成故事版@Lisa穿着白色羽绒服"），存储为Scene.storyboard_json。自动填充序幕/尾声（_fill_uncovered_text()），确保原文全覆盖。
- **句子卡片管理**: SentenceCard记录original_start/end偏移。融合快捷功能：斜杠(/)触发QuickMenu（e.g., 提示增强、服装增强），优化脚本提示词。
- **闭环点**: 分析结果信号触发Zone2刷新分镜卡片，确保脚本变更实时同步DataHub。

### 2. 分镜/故事板生成阶段（可视化与编辑）
- **分镜区布局**: Zone2ShotRhythmZone按场景横向列排列分镜卡（ShotCanvasCard，200x280竖卡布局：序号+时长 → 标签 → 文本 → 资产 → 状态条）。融合参考软件的分镜：支持1-25张序列帧生成（GenerationService路由模型如BananaPro），参数（比例:16:9/21:9、分辨率:1K/2K/4K、数量）。
- **故事板集成**: 新增StoryboardWidget（网格显示100张分镜），点击放大特定分镜（e.g., "放大第13号分镜"）。融合风格库：StyleService预设/自定义风格（e.g., "电影风格"、"皮克斯3D"），自动风格化提示词。
- **交互编辑**: 融合画布：CanvasPanel支持拖拽排序（QGraphicsScene）、删除废片（点击X）、添加空图、合并Stack（MergeService，e.g., 4张合成九宫格）。双击进入编辑模式（画圈添加元素，如"生成钻戒"），保存为MA格式。高清放大（720P→2K/4K）。
- **折叠与连线**: 折叠组使用CollapsedShotCard（200x200），贝塞尔线连接分支节点。_compute_act_x_positions()对齐Zone1场景卡。
- **闭环点**: 编辑后信号触发GenerationController重新生成图片，确保分镜变更闭环到视频阶段。

### 3. 图片生成阶段（I2V准备）
- **总控中心**: MainWindow中央输入框（融合参考软件总控），负责所有图片生成。选择模型（BananaPro不支持2K/4K）、参数。融合角色库：MaterialController保存角色一致性（不超过3个，避免崩溃）。
- **生成逻辑**: GenerationService路由API（DeepSeek + 云雾逆向），支持纹生图/图生图。融合Mejourney（V7，英文提示，固定16:9）。进度条显示，失败重试（云雾不稳定、网络、违规）。
- **快捷扩展**: QuickFuncController支持提示增强（优化简单提示）、服装/表情/动作增强。电商扩展：生成买家秀/产品详情页。
- **闭环点**: 生成图片自动关联Scene模型（首尾帧），信号触发视频合成队列。

### 4. 视频生成阶段（合成与优化）
- **视频合成**: GenerationController调用Vidu/Kling/Jimeng/ComfyUI，支持图生视频（序列帧输入）、纹生视频（文字直接生成）。融合多参视频：保存角色交互（e.g., "老王和小兰吵架"），参数（镜头:上移/跟随、背景音乐、音频）。
- **镜头控制**: 融合参考软件的镜头分析：生成中间帧（首尾针衔接）、参考帧。ActController管理时长/节奏。
- **异步任务**: TaskQueue处理生成（asyncio + QThread），融合不可能三角优化（优先价格低，失败不扣费）。
- **成本统计**: CostService实时记录（e.g., Kling 2-4元/视频），融合参考软件扣费逻辑（钱包显示）。
- **闭环点**: 合成后视频存储为Task结果，信号触发ExportService导出。

### 5. 导出与优化阶段（闭环结束）
- **导出**: ExportService一键下载多张图片/视频/素材包（包括提示词）。融合批量操作：入库/截取/回收站。
- **优化循环**: 融合错误处理（显示原因，如"音频生成失败"）；用户反馈信号触发重生成。CostSummary汇总，确保经济性。
- **闭环点**: 导出后返回脚本阶段，支持迭代（e.g., 重新分析未覆盖文本），形成完整生产循环。

## 开发规范（融合后）

- **画布规范**: QGraphicsView固定，Zone 2（分镜节奏）在 Zone 1 上方自适应（y = Zone 1 顶部 - ZONE_GAP - Zone 2 高度），Zone 3（剧本执行）在 Zone 2 上方，Zone 4（角色道具）在 Zone 1 右侧；初始视口滚动到 Zone 1。融合快捷键：空格拖动、Command+滚轮缩放、/触发快捷。
- **分镜区按场景列排列**: ShotRhythmZoneDelegate.load_all_acts_shots() 按场景分列横向排列，每列内分镜卡纵向排列；_compute_act_x_positions() 与 Zone 1 中对应场景卡 x 坐标对齐；add_act_shot_cards() 支持逐组增量添加；relayout_after_toggle() 重排可见卡片（折叠组跳过，隐藏其 header）。
- **分镜卡竖卡布局**: ShotCanvasCard 尺寸 200×280（竖卡），纵向布局：顶行（序号+时长）→ 标签行 → 分隔线 → 文本区（TextWordWrap）→ 资产标签 → 底部状态条。
- **ProjectDataHub 控制器**: 8个控制器实例（原有6个 + storyboard_controller / quick_func_controller），角色操作用 material_controller，道具操作用 prop_controller。
- **句子卡片原文坐标**: SentenceCard.original_start/end 记录句子在原文中的真实字符偏移，_build_groups_from_acts() 用边界法（双指针）按原文顺序将句子连续分配到各 act 组，保证分组连续且原文顺序不可改变。分组后 _sync_group_ranges_to_data_hub() 将实际范围同步回 data_hub.acts_data。
- **序幕/尾声自动填充**: _fill_uncovered_text() 在 _save_acts() 保存前检测原文中 AI 未覆盖的首尾文本（间隙 > 10 字符），自动插入「序幕」/「尾声」act 到数据库，确保全文都有对应 act 记录并能生成分镜。
- **折叠卡片连线**: 分镜组折叠后，CollapsedShotCard（200×200 竖卡）底部中点到分支节点顶部有贝塞尔扇形线连接，update_all() 中实时更新路径。
- **QGraphicsRectItem 高度自适应**: 使用 QFontMetrics.boundingRect(0, 0, width, 0, TextWordWrap, text) 在构造时精确测量文本渲染高度，setRect 设置卡片尺寸，paint 中使用同一套高度数据绘制，确保测量与渲染一致。
- **浮动按钮模式**: 画布面板上的操作按钮使用浮动 QWidget + resizeEvent + _position_floats() + raise_() 确保在画布上方。
- **语言**: 所有 AI Prompt 模板和用户界面使用中文。
- **数据库**: SQLAlchemy ORM，JSON 字段变更需使用 flag_modified。
- **信号机制**: PyQt6 pyqtSignal 驱动 UI 更新，ProjectDataHub 作为信号枢纽（融合故事板信号）。
- **异步**: 生成任务基于 asyncio + aiohttp，UI 层使用 QThread（融合重试机制）。
- **配置文件**: taoge_settings.json（运行时）、src/config/settings.py（代码层）；新增融合模型配置。
- **测试**: pytest 运行，配置见 pytest.ini；新增融合测试（e.g., test_storyboard_generation、test_quick_enhance）。
- **融合优先级**: 先实现故事板/分镜（Service/Controller扩展），后加视频路由（GenerationService），最后优化UI交互（CanvasPanel）。

## 运行方式

```bash
pip install -r requirements.txt
python src/main.py
```

## 参考文档

- `开发进度报告.md` — 详细的模块级开发进度和文件变更记录（包含融合变更）
- `开发路线图.md` — 完整的功能清单和路线图规划（新增融合里程碑）
- `融合工作流.md` — 闭环工作流图（脚本 → 分镜 → 图片 → 视频 → 导出）