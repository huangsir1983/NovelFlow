# NovelFlow 渐进式开发计划

> 生成日期: 2026-03-05 | 基于 CLAUDE.md PRD v5.0
> 最后更新: 2026-03-06

---

## 当前进度总览

| Phase | 名称 | 状态 | 进度 |
|-------|------|------|------|
| **Phase 0** | **基础搭建** | **进行中** | **95%** |
| Phase 1 | 核心管线 | 未开始 | 0% |
| Phase 2 | 分镜 + 画布 | 未开始 | 0% |
| Phase 3 | 知识库引擎 + Agent系统 | 未开始 | 0% |
| Phase 4 | 团队协作 | 未开始 | 0% |
| Phase 5 | 桌面端 | 未开始 | 0% |
| Phase 6 | 视觉生成对接 | 未开始 | 0% |
| Phase 7 | 高级功能 | 未开始 | 0% |

### Phase 0 细项完成情况

| Sprint | 任务 | 状态 |
|--------|------|------|
| 0.1 | pnpm 安装 | ✅ 完成 |
| 0.1 | Git 初始化 | ✅ 完成 |
| 0.1 | 根配置 (package.json / pnpm-workspace / turbo.json) | ✅ 完成 |
| 0.2 | shared 包骨架 | ✅ 完成 |
| 0.2 | 版本门控系统 (Edition / FEATURE_FLAGS / useEdition) | ✅ 完成 |
| 0.2 | 类型定义 (Project/Chapter/Beat/Scene/Shot 等) | ✅ 完成 |
| 0.3 | Next.js 项目初始化 | ✅ 完成 |
| 0.3 | 暗色主题配置 (Tailwind v4 CSS 变量) | ✅ 完成 |
| 0.3 | 基础页面 (首页 + 新建项目 + 项目详情) | ✅ 完成 |
| 0.4 | FastAPI 后端骨架 | ✅ 完成 |
| 0.4 | SQLite 数据库 + Project 模型 | ✅ 完成 |
| 0.4 | 项目 CRUD API | ✅ 完成 |
| 0.5 | 向导式布局 (WizardLayout) | ✅ 完成 |
| 0.5 | 画布工作台布局 (WorkspaceLayout) | ✅ 完成 |
| 0.5 | 版本自动切换 (wizard / workspace) | ✅ 完成 |
| 0.6 | 前后端联调 (创建项目端到端) | ✅ 完成 |
| 0.6 | 启动脚本 (dev-start.bat) | ✅ 完成 |
| 0.6 | Bug 复盘机制 (BUG_REVIEW.md / DECISION_LOG.md) | ✅ 完成 |
| 0.6 | **Git 首次提交** | ❌ 未完成 |
| 0.6 | UI 汉化 + 布局修复验证 | ✅ 完成 |
| 0.7 | next-intl 安装 + i18n 配置 (config/routing/request/middleware) | ✅ 完成 |
| 0.7 | 翻译文件 (zh.json + en.json, ~60 keys) | ✅ 完成 |
| 0.7 | [locale] 路由迁移 (layout/page/projects) | ✅ 完成 |
| 0.7 | 语言切换器 (LanguageSwitcher) + 全页面集成 | ✅ 完成 |
| 0.7 | shared 组件 labels/headerExtra props 改造 | ✅ 完成 |
| 0.7 | 中英文双向切换验证 (zh↔en) | ✅ 完成 |

---

## Phase 0: 基础搭建 (Week 1)

**目标**: Git仓库 + Monorepo骨架 + 前后端能跑 + 版本门控 + 数据库 + 端到端验证

### Sprint 0.1: 环境与Git初始化

- [x] 安装 pnpm
- [x] 创建 .gitignore + .gitattributes
- [x] git init
- [x] 根配置: package.json + pnpm-workspace.yaml + turbo.json
- [x] 安装 turbo

### Sprint 0.2: Shared包 + 版本门控

- [x] packages/shared/ 骨架 (types/lib/hooks/components)
- [x] Edition 枚举 + FEATURE_FLAGS (PRD 4.2)
- [x] featureFlags.ts (setEdition/getEdition/hasFeature/isEditionAtLeast)
- [x] useEdition Zustand store (with persist)
- [x] 类型定义: Project/Chapter/Beat/Scene/Shot/Character/Location

### Sprint 0.3: Web前端

- [x] Next.js 15 + React 19 + Tailwind v4 + App Router
- [x] 暗色主题 CSS 变量 (PRD 7.2 色彩体系)
- [x] 首页 (Logo + 版本切换 + 创建项目)
- [x] 新建项目页 (向导三步)
- [x] 项目详情页

### Sprint 0.4: Python后端

- [x] FastAPI + CORS + health endpoint
- [x] Pydantic Settings 配置
- [x] SQLAlchemy + SQLite
- [x] Project 模型 + CRUD API

### Sprint 0.5: 两套UI布局

- [x] WizardLayout (向导式, Normal版)
- [x] WorkspaceLayout (画布工作台, Canvas+版, react-resizable-panels)
- [x] 版本自动切换

### Sprint 0.6: 端到端验证

- [x] 前端创建项目 -> 后端写入 -> 返回显示
- [x] fetchAPI 封装
- [x] dev-start.bat 启动脚本
- [x] BUG_REVIEW.md + DECISION_LOG.md
- [ ] **Git 首次提交** (待执行)

### Sprint 0.7: 国际化 (i18n)

- [x] 安装 next-intl (packages/web)
- [x] i18n 配置: config.ts + routing.ts + request.ts + middleware.ts
- [x] next.config.ts 集成 createNextIntlPlugin
- [x] 翻译文件: messages/zh.json + messages/en.json (~60 keys)
- [x] 路由迁移: 所有页面移入 `[locale]/` 目录
- [x] locale layout: NextIntlClientProvider + locale 参数
- [x] shared 组件改造: WizardLayout + WorkspaceLayout 加 labels/headerExtra prop
- [x] 各页面硬编码字符串 → `t('key')` + 传 labels 给 shared 组件
- [x] LanguageSwitcher 组件 (使用 createNavigation 实现双向切换)
- [x] 类型声明: next-intl.d.ts 翻译 key 自动补全
- [x] 全页面语言切换器集成 (headerExtra prop)

### Phase 0 验收清单

- [x] `pnpm dev:web` 启动前端，显示暗色主题首页
- [x] 后端 /api/health 返回 JSON
- [x] 前端创建项目 -> 后端写入 -> 前端跳转
- [x] Normal/Canvas 版本切换，布局自动切换
- [x] 中英文切换正常 (默认中文无前缀, 英文 `/en/`)
- [ ] Git 仓库有首次提交

---

## Phase 1: 核心管线 (Week 2-5)

**目标**: 双入口(小说+剧本)导入 -> 知识库 -> Beat Sheet -> 剧本编辑 全流程可走通

### Sprint 1 (Week 2-3): 双入口导入 + 知识库

| ID | 任务 | 关键文件 | 验收 |
|----|------|---------|------|
| 1.1.1 | AI引擎统一层 | `backend/services/ai_engine.py` | streaming调用Claude |
| 1.1.2 | 小说文件上传 | `NovelImport.tsx` + `api/import_novel.py` | 上传TXT/DOCX |
| 1.1.3 | 小说解析(分章) | `services/novel_parser.py` | Prompt P01(Haiku) |
| 1.1.4 | 角色提取 | `services/character_extractor.py` | Prompt P03(Sonnet) |
| 1.1.5 | 知识库初始化 | `models/knowledge_base.py` + `KnowledgePanel.tsx` | 角色/场景CRUD |
| 1.2.1 | 剧本导入解析 | `services/script_parser.py` + `ScriptImport.tsx` | Fountain/FDX解析 |
| 1.2.2 | 剧本适配引擎 | `services/script_adapter.py` | PS02-PS04 |
| 1.2.3 | Beat Sheet编辑器 | `BeatEditor.tsx` | 卡片拖拽+情感曲线 |
| 1.2.4 | 导入选择页 | `projects/new/page.tsx` | 两张Glass Card |

### Sprint 2 (Week 4-5): 剧本工作台

| ID | 任务 | 关键文件 | 验收 |
|----|------|---------|------|
| 1.3.1 | TipTap剧本编辑器 | `ScriptEditor.tsx` | 剧本格式化编辑 |
| 1.3.2 | AI辅助浮动工具栏 | ScriptEditor内 | 改写/扩写/缩写 |
| 1.3.3 | Beat->场景生成 | Prompt P11 | Beat->完整剧本 |
| 1.3.4 | 原文对照面板 | `OriginalTextPanel.tsx` | 左右分屏 |
| 1.3.5 | 版本管理 | `models/version.py` | 自动快照 |

---

## Phase 2: 分镜 + 画布 (Week 6-9)

**目标**: 分镜生成 + 画布工作台 + 导出 → 普通版MVP完成

### Sprint 3 (Week 6-7): 分镜脚本

| ID | 任务 | 验收 |
|----|------|------|
| 2.1.1 | 场景->分镜AI拆解 | 使用director知识库, 生成Shot列表 |
| 2.1.2 | 分镜卡片编辑器 | 16:9缩略图+镜号+景别+时长 |
| 2.1.3 | 时间轴视图 | 底部水平时间轴可拖拽 |
| 2.1.4 | 视觉Prompt生成 | Prompt P26 多平台适配 |
| 2.1.5 | 声音基础标注 | 环境声/音乐/音效文本框 |
| 2.1.6 | 导出系统 | PDF/JSON/CSV |

### Sprint 4 (Week 8-9): 画布工作台

| ID | 任务 | 验收 |
|----|------|------|
| 2.2.1 | 多面板布局完善 | 树形导航+Tab面板, 拖拽折叠 |
| 2.2.2 | 多候选对比 | 3个候选结果 |
| 2.2.3 | 快捷键系统 | Ctrl+S/Z/\ |
| 2.2.4 | 动画体验 | spring动画+Glass+骨架屏 |

---

## Phase 3: 知识库引擎 + Agent系统 (Week 10-14)

**目标**: 31个知识库YAML化 + 9 Agent全部上线 + 全自动管线

### Sprint 5 (Week 10-11): 知识库引擎 + Agent基础

- 知识库YAML加载器 + 版本门控
- Agent基础框架 (BaseAgent/AgentBus/Celery)
- AI引擎升级 (ModelFallback + CircuitBreaker)
- 张力引擎
- PostgreSQL + Redis 安装切换

### Sprint 6 (Week 12-13): 核心Agent

- 小说分析师Agent (含剧本逆向)
- 一致性守护Agent (含视觉母题+张力监控)
- 编剧Agent (原点10专家+4增强)
- 导演Agent (7步+5序列+声音+场面调度+文化)
- Agent监控面板

### Sprint 7 (Week 14): 高级Agent

- 视觉Prompt Agent + 质量审核Agent
- 微短剧编剧Agent (Ultimate)
- 数据优化Agent (Ultimate)
- 协调者 + 全自动管线
- 知识库热加载 + 调试面板

---

## Phase 4: 团队协作 (Week 15-17)

- 用户认证 (NextAuth.js + JWT)
- 团队管理 (Owner/Editor/Commenter/Viewer)
- Yjs实时协作 (Hocuspocus + TipTap)
- 评论系统 + 活动流

---

## Phase 5: 桌面端 (Week 18-20)

- Tauri 2.0 + Rust环境
- 平台抽象层
- 离线模式 (SQLite + Op Log + CRDT)
- Windows MSI + Mac DMG

---

## Phase 6: 视觉生成对接 (Week 21-24)

- AI图像生成 (Kling 3.0 / 即梦 / MJ)
- AI视频生成 (图生视频)
- TTS语音 (旁白+角色配音)
- FFmpeg合成

---

## Phase 7: 高级功能 (持续)

- 关系图谱 / 风格板 / 白标 / API / 数据仪表盘 / i18n

---

## 关键技术决策

| ID | 决策 | 理由 |
|----|------|------|
| DR-001 | Phase 0-2 用 SQLite, Phase 3 切 PG | 一人开发零配置, ORM切换无痛 |
| DR-002 | 开发期默认 Ultimate 版 | 开发需全功能, featureFlags控制 |
| DR-003 | AI功能先 Mock 开发前端 | 节省API费用, 前端稳定后再接真实API |
| DR-004 | Agent逐个开发 | base.py+bus.py先稳, 再逐个加Agent |
| DR-005 | 知识库YAML化优先于Agent | Agent依赖知识库, 先完成转换 |
| DR-006 | i18n 用 next-intl + `localePrefix: 'as-needed'` | 中文默认无前缀, 英文 `/en/`, shared 包不依赖 next-intl |

---

## 已踩的坑

| 问题 | 原因 | 解决 |
|------|------|------|
| Tailwind v4 所有间距/宽度类失效 | `@theme inline` 中定义 `--spacing-xs` 覆盖整个spacing命名空间 | 只定义 `--spacing: 0.25rem` 基础值 |
| react-resizable-panels 导入报错 | v4 API: Group/Panel/Separator (不是 PanelGroup/PanelResizeHandle) | 使用正确导出名 |
| rm -rf 误删项目 | Windows Git Bash 路径处理 | 47个文件全部重建 |
| dev-start.bat 找不到 node/pnpm | Node.js (D:\nodejs) 不在 CMD PATH 中 | bat中手动设置 PATH |
| react-resizable-panels v4 无 `order` prop | v4 API 移除了 Panel 的 order 属性 | 删除所有 order={n} |
| next-intl 语言切换 en→zh 失败 | 手动拼接 pathname 丢失 locale 信息 | 用 `createNavigation` 的 `useRouter` + `router.replace(pathname, { locale })` |
| WizardLayout "上一步" 在 step 0 不可点 | disabled 条件含 `currentStep === 0` + `disabled:invisible` CSS | 移除 step 0 禁用, 在页面层 onPrev 处理导航回首页 |
| TypeScript `value === false` 不可达 | `typeof value === 'boolean'` 后 TS 已缩窄类型 | 移除冗余判断行 |
