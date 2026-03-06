# 虚幻造物：现状 vs PRD / newplan 差距清单与开发任务表

> 分析日期：2026-03-06  
> 对照文档：`PRD.md`、`newplan3.md`  
> 当前代码基线：以 `backend/main.py` 为后端入口，结合 `backend/`、`packages/web/`、`packages/shared/` 现状评估

---

## 1. 当前项目所处阶段

当前仓库已经具备：

- Monorepo 基础结构
- Next.js 前端壳
- FastAPI 后端壳
- 项目 `Project` 的最小 CRUD
- edition 的前端配置化切换

但距离 `PRD.md` 和 `newplan3.md` 中定义的当前目标形态，仍有明显差距。

当前状态更接近：

> **Phase 0：产品骨架 + 数据骨架 + 交互原型期**

而不是：

> **Phase 1+：具备导入、解析、知识库、Beat、剧本、分镜、视觉生成、资产库、剪映工程包、Animatic 的业务系统**

---

## 2. 现状总览

### 2.1 已实现部分

- 后端应用入口已存在：`backend/main.py`
- 数据库初始化已存在：`backend/database.py`
- 配置系统已存在：`backend/config.py`
- 项目模型已存在：`backend/models/project.py`
- 项目 CRUD API 已存在：`backend/api/projects.py`
- 前端新建项目流程已存在：`packages/web/src/app/[locale]/projects/new/page.tsx`
- 前端项目页/工作区壳已存在：`packages/web/src/app/[locale]/projects/[id]/page.tsx`
- edition 特性开关已存在：`packages/shared/src/types/edition.ts`
- 前端共享类型已先行定义：`packages/shared/src/types/project.ts`

### 2.2 未形成业务闭环的部分

- 没有小说文件上传与解析
- 没有剧本导入与适配引擎
- 没有知识库构建流程
- 没有 Beat Sheet 实体与编辑流
- 没有剧本编辑实体与版本流
- 没有分镜/镜头数据落库与执行流
- 没有 AI Engine、Provider 抽象层
- 没有 Agent 执行框架接入主流程
- 没有节点执行引擎
- 没有资产库系统
- 没有 CapCut Draft 导出
- 没有 Animatic 预览链路
- 没有宣发物料模块
- 没有后端统一 edition 门控
- 没有 OpenAPI -> TS codegen 流水线
- 没有 PostgreSQL / Redis / Celery / Docker Compose 开发基建

---

## 3. 差距清单（现状 vs PRD / newplan）

下面按模块列出“目标、现状、差距、影响、优先级”。

---

### G1. 后端基础架构

| 项目 | PRD / newplan目标 | 当前现状 | 差距 | 影响 | 优先级 |
|------|-------------------|----------|------|------|--------|
| 应用架构 | FastAPI + AIEngine + Agent + 节点执行 | 只有 FastAPI + projects CRUD | 缺核心执行中枢 | 后续业务会反复返工 | P0 |
| 数据库 | Phase 0 直接 PostgreSQL | 仍为 SQLite | 与目标架构不一致 | 迁移成本增加 | P0 |
| 异步任务 | Redis + Celery | 未落地 | 无法承载长耗时 AI 任务 | 生成链路无法稳定 | P0 |
| Docker开发环境 | Compose 一键起服务 | 未落地 | 本地环境不可复制 | 团队协作困难 | P0 |
| OpenAPI codegen | 后端模型驱动前端类型 | 仅手写共享类型 | 双端类型可能漂移 | 联调成本高 | P1 |

**现状判断**：当前后端只够支撑“项目管理 demo”，不够支撑“AI 工作流产品”。

---

### G2. 版本门控与权限体系

| 项目 | PRD / newplan目标 | 当前现状 | 差距 | 影响 | 优先级 |
|------|-------------------|----------|------|------|--------|
| 前端版本门控 | middleware + 节点过滤 | 主要在前端 Zustand 配置中 | 缺统一路由级门控 | 容易绕过限制 | P0 |
| 后端版本门控 | FastAPI Depends 统一拦截 | 未实现 | 业务层没有权限保护 | edition 失真 | P0 |
| 特性授权 | 后端按 edition 验证可用能力 | 前端直接传 `edition` | 没有可信授权来源 | 安全与计费风险 | P0 |

**现状判断**：edition 目前是“UI 开关”，还不是“真正的产品分层机制”。

---

### G3. 核心领域模型

| 项目 | PRD / newplan目标 | 当前现状 | 差距 | 影响 | 优先级 |
|------|-------------------|----------|------|------|--------|
| Project | 已有 | 已有 | 基本可用 | 低 | - |
| Chapter | 需要 | 仅前端类型存在 | 未建表/API | 无法导入小说 | P0 |
| Character | 需要 | 仅前端类型存在 | 未建表/API | 无法形成知识库 | P0 |
| Location | 需要 | 仅前端类型存在 | 未建表/API | 无法形成世界观/场景档案 | P0 |
| Beat | 需要 | 仅前端类型存在 | 未建表/API | 无法进入编剧流 | P0 |
| Scene | 需要 | 仅前端类型存在 | 未建表/API | 无法分镜 | P0 |
| Shot | 需要 | 仅前端类型存在 | 未建表/API | 无法导演/视觉/导出 | P0 |
| KnowledgeBase | 需要 | 仅前端类型存在 | 未建模 | 无法做一致性守护 | P0 |
| Asset相关模型 | v6.0 新增核心 | 无 | 未建模 | 无法做资产库 | P1 |
| Marketing相关模型 | v6.0 新增核心 | 无 | 未建模 | 无法做宣发输出 | P2 |
| Draft/Animatic相关模型 | v6.0 新增核心 | 无 | 未建模 | 无法做交付预览 | P2 |

**现状判断**：共享 types 已经在“描述未来系统”，但数据库和 API 仍停留在单表阶段。

---

### G4. 双入口导入系统

| 项目 | PRD / newplan目标 | 当前现状 | 差距 | 影响 | 优先级 |
|------|-------------------|----------|------|------|--------|
| 小说导入 | TXT/DOCX/EPUB/PDF/MD | 没有真正上传与解析 | 仅创建项目记录 | 无法开始主流程 | P0 |
| 剧本导入 | Fountain/FDX/TXT/DOCX | 无 | 无格式解析与标准化 | 剧本入口缺失 | P0 |
| 从零创建 | Ultimate 可用 | 前端可选 `blank` | 后端无对应流程 | 只有占位能力 | P1 |
| 文件存储 | 上传文件、源文件管理 | 无 | 无存储策略 | 无法追溯输入源 | P0 |

**现状判断**：入口层目前只有“选项”，没有“真正导入能力”。

---

### G5. 分析层与知识库层

| 项目 | PRD / newplan目标 | 当前现状 | 差距 | 影响 | 优先级 |
|------|-------------------|----------|------|------|--------|
| 章节分割 | P01 | 无 | 无 agent / 无任务流 | 小说无法拆解 | P0 |
| 角色提取 | P03 | 无 | 无 AI 任务 | 知识库无法初始化 | P0 |
| 场景提取 | 小说/剧本分析后进入知识库 | 无 | 无实体与任务 | 创作链路断裂 | P0 |
| Story Bible | 角色/场景/世界观统一档案 | 无 | 无结构化汇总层 | 无一致性基础 | P0 |
| 一致性守护 | 全局枢纽 | 无 | 无规则/无校验 | 后续生成漂移 | P1 |
| 知识库热加载 | `knowledge/loader.py` | 目录存在但未接入 | 无实际装载流程 | 文档与代码脱节 | P1 |

**现状判断**：知识库目录是占位，知识库引擎尚未形成。 

---

### G6. AI Engine / Agent / 节点执行

| 项目 | PRD / newplan目标 | 当前现状 | 差距 | 影响 | 优先级 |
|------|-------------------|----------|------|------|--------|
| AIEngine | anthropic/openai/deepseek 抽象 | 无 | 无统一模型调用层 | 后续 prompt/模型耦合 | P0 |
| Prompt模板体系 | Prompt ID 驱动 | 无 | 无模板注册/版本管理 | Prompt工程无法积累 | P0 |
| Agent基类 | `base.py` 架构 | `agents/` 仅占位 | 无可执行 agent | 主流程无法自动化 | P0 |
| 节点执行映射 | `node_execution.py` | 无 | 无 Node -> Task 映射 | 画布只能做静态 UI | P0 |
| 流式输出 | AI 长文本/分步输出 | 前端有 stream helper | 后端无对应接口 | 体验断裂 | P1 |

**现状判断**：当前没有 AI 产品最关键的“执行层”。

---

### G7. 编剧主链路

| 项目 | PRD / newplan目标 | 当前现状 | 差距 | 影响 | 优先级 |
|------|-------------------|----------|------|------|--------|
| Beat Sheet | AI生成 + 编辑 | 无 | 无实体/无页面/无 API | 无法推进叙事设计 | P0 |
| 剧本生成 | Beat -> Scene -> Script | 无 | 无脚本工作台 | 主产品价值缺失 | P0 |
| 原点10+4专家 | Agent 化接入 | 无 | 无专家编剧能力 | PRD 核心能力缺失 | P1 |
| 微短剧模式 | Ultimate 特性 | 无 | 无链路 | 高阶卖点缺失 | P2 |
| 张力引擎 | 情绪/节奏驱动 | 无 | 无计算逻辑与可视化 | 叙事优势未体现 | P1 |

**现状判断**：编剧层还没有真正开始开发。

---

### G8. 导演层 / 分镜层 / Cinema Lab

| 项目 | PRD / newplan目标 | 当前现状 | 差距 | 影响 | 优先级 |
|------|-------------------|----------|------|------|--------|
| Scene -> Shot | 场景到镜头设计 | 无 | 无 Shot 生成链路 | 无法进入视觉层 | P1 |
| 导演分镜 7步+5序列 | 专业导演能力 | 无 | 无数据模型与流程 | 关键差异化缺失 | P1 |
| 声音叙事 | Hidden+ | 无 | 无结构与输出 | 导演能力不完整 | P2 |
| 场面调度 | Hidden+ | 无 | 无结构与输出 | 导演能力不完整 | P2 |
| 文化视觉适配 | Hidden+ | 无 | 无策略层 | 本土化差异不明显 | P2 |
| Cinema Lab | 全屏实验室 | 无真实实现 | 仅工作区壳 | 高价值模块未落地 | P2 |

**现状判断**：导演层仍为文档阶段。

---

### G9. 视觉生成层

| 项目 | PRD / newplan目标 | 当前现状 | 差距 | 影响 | 优先级 |
|------|-------------------|----------|------|------|--------|
| 视觉 Prompt 工程 | 9模块 + 20检 | 无 | 无 prompt 产出体系 | 无法接图像/视频生成 | P1 |
| 视觉母题追踪 | 终检模块 | 无 | 无视觉一致性引擎 | 高级能力缺失 | P2 |
| 图像/视频生成接口 | 统一生成层 | 无 | 无 provider / 无任务 | 产品链路断 | P1 |
| 候选管理 | 多方案生成与选择 | 无 | 无结果管理 | 无法形成专业工作流 | P2 |

**现状判断**：视觉层目前没有后端实现，也没有真正的前端操作面板。

---

### G10. 资产库系统（v6.0新增）

| 项目 | PRD / newplan目标 | 当前现状 | 差距 | 影响 | 优先级 |
|------|-------------------|----------|------|------|--------|
| Asset Library | 公用/自用/项目内三级 | 无 | 无模型/API/UI | v6.0 关键升级未启动 | P1 |
| 角色视觉资产 | 生成/锁定/复用 | 无 | 无视觉资产流 | 一致性无法落实 | P1 |
| 场景概念资产 | 生成/引用 | 无 | 无概念图体系 | 美术前置缺失 | P2 |
| Mood Board / 色彩剧本 | 资产化输出 | 无 | 无生产设计模块 | 导演-视觉桥梁缺失 | P2 |
| 资产引用到下游 | 强制锚点 | 无 | 无绑定关系 | 视觉一致性无法闭环 | P1 |

**现状判断**：这是 v6.0 的核心新增卖点，但代码还未进入实现期。

---

### G11. 输出层：CapCut Draft / 宣发物料 / Animatic（v6.0新增）

| 项目 | PRD / newplan目标 | 当前现状 | 差距 | 影响 | 优先级 |
|------|-------------------|----------|------|------|--------|
| CapCut Draft 导出 | 时间线 + 视频 + 音频 + 字幕 + 标记 | 无 | 无 builder / 无下载接口 | 后期交接点缺失 | P2 |
| Animatic | 低成本节奏预览 | 无 | 无本地合成链路 | 无法快速验证节奏 | P2 |
| 宣发物料 | 封面/海报/预告草稿 | 无 | 无营销资产流程 | 发行环节空缺 | P3 |
| AI音乐 | 输出到后期 | 无 | 无声音资产模块 | 声音叙事断层 | P3 |

**现状判断**：输出层完全未进入开发。

---

### G12. 前端交互与画布工作台

| 项目 | PRD / newplan目标 | 当前现状 | 差距 | 影响 | 优先级 |
|------|-------------------|----------|------|------|--------|
| 无限节点画布 | 节点可连线可执行 | 无 | 当前只是 workspace 占位 | Canvas 核心卖点未实现 | P1 |
| 节点状态 | 实时运行状态和输出预览 | 无 | 无任务状态体系 | 无法形成 AI-native 体验 | P1 |
| 工作区布局 | 已有基础壳 | 已有 | 需连接真实业务模块 | 中 | P1 |
| AI 助手侧栏 | 有占位 | 无真实能力 | 无会话/上下文/操作绑定 | 中 | P2 |

**现状判断**：前端壳比后端略领先，但离“画布产品”还差执行层、节点层、状态层。

---

## 4. 总体优先级判断

### 4.1 必须先做的 P0

这些是后续所有功能的地基，不先做会持续返工：

1. PostgreSQL + Alembic + Docker Compose
2. 后端 edition / 权限门控
3. AIEngine + Prompt 注册 + Agent 基类
4. 节点执行映射框架
5. 核心领域模型落库：Chapter / Character / Location / Beat / Scene / Shot / KnowledgeBase
6. 双入口导入最小闭环：小说导入、剧本导入
7. 分析层最小闭环：章节分割、角色提取、知识库初始化
8. 编剧主链路最小闭环：Beat Sheet -> Scene

### 4.2 适合第二阶段做的 P1

1. 节点画布可执行化
2. 剧本工作台
3. 分镜生成与导演基础链路
4. 视觉 Prompt 工程基础版
5. 资产库第一版
6. OpenAPI -> TS codegen

### 4.3 适合第三阶段做的 P2 / P3

1. Cinema Lab MVP
2. 资产库高级能力
3. Animatic
4. CapCut Draft
5. 宣发物料
6. AI音乐
7. 微短剧增强链路
8. 数据闭环优化

---

## 5. 按开发顺序拆分的可执行任务表

下面的任务表按“先地基、再主链路、后增强模块”的顺序排列。

---

## Phase 0：基础设施与领域建模

### T0-1. 数据库迁移到 PostgreSQL

**目标**

- 将 `backend/config.py` 的数据库默认配置切换到 PostgreSQL
- 引入迁移工具，替代 `create_all`
- 保留本地开发可运行性

**具体任务**

- [ ] 新增 PostgreSQL 连接配置与 `.env.example` 说明
- [ ] 引入 Alembic 迁移
- [ ] 替换 `init_db()` 的生产职责，避免仅靠 `create_all`
- [ ] 增加 Docker Compose：PostgreSQL / Redis / backend
- [ ] 验证本地启动链路

**交付物**

- `backend/alembic/`
- `docker-compose.yml`
- 更新后的 `backend/config.py`
- 首个 migration

**优先级**

- P0

---

### T0-2. 建立后端可信的 edition / 权限门控

**目标**

- edition 不再只由前端决定
- 后端接口按版本控制功能开放范围

**具体任务**

- [ ] 新增 `Edition` 枚举与后端共享常量
- [ ] 新增 FastAPI Depends：`require_edition()`
- [ ] 对未来 AI、导出、资产、Cinema Lab 接口挂载版本限制
- [ ] 规范项目创建时 edition 的来源与校验

**交付物**

- `backend/core/edition.py`
- `backend/deps/edition.py`
- CRUD 接口与后续接口的统一门控策略

**优先级**

- P0

---

### T0-3. 建立 AIEngine 抽象层

**目标**

- 统一大模型调用入口
- 隔离 provider 差异

**具体任务**

- [ ] 新增 `ai_engine.py`
- [ ] 抽象 provider：anthropic / openai / deepseek
- [ ] 统一请求参数：model / temperature / system / messages / streaming
- [ ] 提供同步、异步、流式三类能力
- [ ] 增加 provider 配置与容错机制

**交付物**

- `backend/services/ai_engine.py`
- `backend/services/providers/`

**优先级**

- P0

---

### T0-4. 建立 Prompt 注册与 Agent 基类

**目标**

- 让 Prompt 和 Agent 从“文档描述”变成“可执行能力”

**具体任务**

- [ ] 设计 Prompt registry：按 `P01 / P03 / PS01...` 注册
- [ ] 设计 Agent base class
- [ ] 增加 AnalystAgent / ConsistencyAgent 第一版骨架
- [ ] 定义 agent 输入输出 schema

**交付物**

- `backend/agents/base.py`
- `backend/prompts/registry.py`
- `backend/agents/analyst.py`
- `backend/agents/consistency.py`

**优先级**

- P0

---

### T0-5. 建立节点执行引擎

**目标**

- 为未来画布执行流提供统一入口

**具体任务**

- [ ] 新增 `node_execution.py`
- [ ] 定义节点类型到任务类型的映射
- [ ] 支持最小执行链：import -> analysis -> knowledge -> beat
- [ ] 增加任务状态：pending / running / success / failed
- [ ] 为前端预留轮询或流式状态接口

**交付物**

- `backend/services/node_execution.py`
- `backend/models/node_run.py` 或等价任务表
- `backend/api/executions.py`

**优先级**

- P0

---

### T0-6. 补齐核心领域模型

**目标**

- 让共享类型对应真实数据库与 API

**具体任务**

- [ ] 新建 `Chapter` 模型与 CRUD/API
- [ ] 新建 `Character` 模型与 CRUD/API
- [ ] 新建 `Location` 模型与 CRUD/API
- [ ] 新建 `Beat` 模型与 CRUD/API
- [ ] 新建 `Scene` 模型与 CRUD/API
- [ ] 新建 `Shot` 模型与 CRUD/API
- [ ] 新建 `KnowledgeBase` / `StoryBible` 汇总模型
- [ ] 明确表关系与级联策略

**交付物**

- `backend/models/*.py`
- `backend/api/*.py`
- migrations

**优先级**

- P0

---

## Phase 1：双入口导入与分析最小闭环

### T1-1. 小说导入最小闭环

**目标**

- 从上传文本到生成章节记录

**具体任务**

- [ ] 新增文件上传接口
- [ ] 支持 TXT / MD 第一版
- [ ] 保存源文件元数据
- [ ] 触发章节分割任务
- [ ] 落库 `Chapter`

**交付物**

- `backend/api/imports.py`
- `backend/services/importers/novel_importer.py`

**优先级**

- P0

---

### T1-2. 剧本导入最小闭环

**目标**

- 从脚本文件到结构化场景/角色基础数据

**具体任务**

- [ ] 支持 TXT / Fountain 第一版
- [ ] 实现格式识别与标准化
- [ ] 输出内部 JSON
- [ ] 触发结构分析与知识库初始化

**交付物**

- `backend/services/importers/script_importer.py`
- `backend/services/parsers/fountain_parser.py`

**优先级**

- P0

---

### T1-3. 分析层最小闭环

**目标**

- 从输入内容中生成最基础的知识库

**具体任务**

- [ ] P01 章节分割任务
- [ ] P03 角色提取任务
- [ ] 场景提取任务
- [ ] Character / Location / StoryBible 初始化
- [ ] 项目 `stage` 自动推进：`import -> knowledge`

**交付物**

- `backend/agents/analyst.py`
- `backend/services/pipelines/analysis_pipeline.py`

**优先级**

- P0

---

## Phase 2：编剧主链路 MVP

### T2-1. Beat Sheet MVP

**目标**

- 从分析结果生成可编辑 Beat 列表

**具体任务**

- [ ] 实现 `P10` 小说 -> Beat
- [ ] 剧本逆向 Beat 的第一版
- [ ] Beat CRUD API
- [ ] Beat 排序与手动编辑
- [ ] 项目 `stage` 推进到 `beat_sheet`

**交付物**

- `backend/api/beats.py`
- `packages/web/.../beats` 对应页面或面板

**优先级**

- P0

---

### T2-2. Scene / 剧本工作台 MVP

**目标**

- 从 Beat 生成 Scene，并提供基础编辑能力

**具体任务**

- [ ] 实现 `P11` Beat -> Scene
- [ ] Scene CRUD
- [ ] 剧本文本导出第一版
- [ ] 项目 `stage` 推进到 `script`

**交付物**

- `backend/api/scenes.py`
- 剧本工作台基础页面

**优先级**

- P0

---

### T2-3. 一致性守护 MVP

**目标**

- 在角色、场景、剧情术语上给出最基本的一致性检查

**具体任务**

- [ ] 检查角色命名冲突
- [ ] 检查场景信息缺失
- [ ] 检查时间/地点自相矛盾
- [ ] 输出 review 结果到项目面板

**交付物**

- `backend/agents/consistency.py`
- `backend/api/reviews.py`

**优先级**

- P1

---

## Phase 3：画布执行化与导演基础链路

### T3-1. 节点画布 MVP

**目标**

- 让 Canvas 版不再只是壳，而是真正可执行

**具体任务**

- [ ] 引入 React Flow 或等价方案
- [ ] 建立节点类型：Import / Analysis / Knowledge / Beat / Script
- [ ] 节点执行状态展示
- [ ] 节点输出预览卡片
- [ ] 与 `node_execution.py` 对接

**交付物**

- 画布页面
- 节点组件库
- 执行状态 UI

**优先级**

- P1

---

### T3-2. Scene -> Shot 分镜 MVP

**目标**

- 从 Scene 生成结构化 Shot 列表

**具体任务**

- [ ] 设计 Shot 生成 schema
- [ ] 实现分镜生成任务
- [ ] Shot CRUD / 重排序
- [ ] 项目 `stage` 推进到 `storyboard`

**交付物**

- `backend/api/shots.py`
- 分镜面板/分镜页

**优先级**

- P1

---

### T3-3. 导演链路基础版

**目标**

- 在 Shot 上补足基础导演参数

**具体任务**

- [ ] 镜头景别
- [ ] 机位角度
- [ ] 运镜方式
- [ ] 时长建议
- [ ] 基础导演说明

**交付物**

- Shot 扩展字段与表单
- 导演基础任务接口

**优先级**

- P1

---

## Phase 4：视觉生成主链路

### T4-1. 视觉 Prompt 工程 MVP

**目标**

- 从 Shot 生成可用于图像/视频模型的视觉描述

**具体任务**

- [ ] 建立 `visual_prompt` schema
- [ ] 按镜头生成 prompt
- [ ] 支持多候选生成
- [ ] 项目 `stage` 推进到 `visual_prompt`

**交付物**

- `backend/api/visual_prompts.py`
- prompt 预览面板

**优先级**

- P1

---

### T4-2. 图像 / 视频生成第一版

**目标**

- 让系统第一次具备“从文本到素材”的生成能力

**具体任务**

- [ ] 对接至少一个图像 provider
- [ ] 保存生成结果元数据
- [ ] 结果回填到 Shot
- [ ] 生成任务状态追踪

**交付物**

- `backend/api/generation.py`
- 生成结果表

**优先级**

- P1

---

## Phase 5：v6.0 资产库第一版

### T5-1. Asset Library 数据模型与 API

**目标**

- 落地 v6.0 的核心新增模块

**具体任务**

- [ ] 设计 `Asset`, `AssetContent`, `ProjectAssetRef`
- [ ] 设计 scope：public / personal / project
- [ ] 设计 type：character / prop / location / lighting / motion / style
- [ ] 新增资产 CRUD API
- [ ] 新增项目引用资产 API

**交付物**

- `backend/models/asset*.py`
- `backend/api/assets.py`

**优先级**

- P1

---

### T5-2. 角色视觉资产 MVP

**目标**

- 先打通角色视觉一致性闭环

**具体任务**

- [ ] 角色视觉卡生成
- [ ] 角色参考图生成接口
- [ ] 锁定角色视觉资产
- [ ] 在视觉 prompt 中强制注入锁定资产信息

**交付物**

- 角色视觉资产 API
- 锁定机制
- 与 visual prompt 的绑定逻辑

**优先级**

- P1

---

## Phase 6：CapCut Draft / Animatic / Cinema Lab

### T6-1. CapCut Draft MVP

**目标**

- 打通后期交接点

**具体任务**

- [ ] 设计 Draft builder
- [ ] 支持基础时间线导出
- [ ] 支持字幕与标记导出
- [ ] 提供下载接口

**交付物**

- `backend/services/capcut_draft_builder.py`
- `backend/api/capcut.py`

**优先级**

- P2

---

### T6-2. Animatic MVP

**目标**

- 提供低成本节奏预览能力

**具体任务**

- [ ] 静帧串联
- [ ] TTS 配音占位
- [ ] 基础转场
- [ ] 生成预览视频

**交付物**

- `backend/services/animatic_builder.py`
- `backend/api/animatic.py`

**优先级**

- P2

---

### T6-3. Cinema Lab MVP

**目标**

- 提供高阶镜头实验场

**具体任务**

- [ ] Shot 参数高级编辑
- [ ] 镜头实验参数面板
- [ ] 输出回写主项目镜头

**交付物**

- Cinema Lab 页面
- Shot 高级编辑数据结构

**优先级**

- P2

---

## Phase 7：宣发物料与高级能力

### T7-1. 宣发物料生成

**目标**

- 补齐发行链路

**具体任务**

- [ ] 封面选帧
- [ ] 海报 prompt
- [ ] 预告草稿
- [ ] 结果入资产库

**优先级**

- P3

---

### T7-2. 高阶能力补齐

**目标**

- 向 Hidden / Ultimate 版本能力靠拢

**具体任务**

- [ ] 声音叙事
- [ ] 场面调度
- [ ] 文化视觉适配
- [ ] 微短剧增强链路
- [ ] 数据反馈闭环

**优先级**

- P3

---

## 6. 建议的近期开发顺序（最务实版本）

如果目标是尽快从“原型壳”走到“可用 MVP”，建议严格按下面顺序推进：

1. `T0-1` PostgreSQL + migration + Docker Compose
2. `T0-2` edition / 权限门控
3. `T0-3` AIEngine 抽象层
4. `T0-4` Prompt / Agent 基类
5. `T0-5` 节点执行引擎
6. `T0-6` 核心领域模型落库
7. `T1-1` 小说导入最小闭环
8. `T1-2` 剧本导入最小闭环
9. `T1-3` 分析层最小闭环
10. `T2-1` Beat Sheet MVP
11. `T2-2` Scene / 剧本工作台 MVP
12. `T3-1` 节点画布 MVP
13. `T3-2` 分镜 MVP
14. `T4-1` 视觉 Prompt MVP
15. `T4-2` 图像/视频生成第一版
16. `T5-1` 资产库第一版
17. `T5-2` 角色视觉资产 MVP
18. `T6-1` CapCut Draft MVP
19. `T6-2` Animatic MVP
20. `T6-3` Cinema Lab MVP
21. `T7-1` 宣发物料
22. `T7-2` 高阶能力补齐

---

## 7. 一句话结论

当前软件已经有了 **产品骨架**，但离 `PRD.md` 与 `newplan3.md` 中定义的当前目标形态，还差三层：

1. **底层执行层**：AIEngine、Agent、Node Execution、异步任务、数据库基建
2. **中间业务层**：导入、分析、知识库、Beat、Scene、Shot、视觉生成
3. **高阶产品层**：资产库、CapCut Draft、Animatic、Cinema Lab、宣发物料

建议先把 **P0 主链路地基** 打稳，再进入 v6.0 的新增模块开发。

---

## 8. 技术实现版

这一部分将上面的任务，进一步细化成“按代码目录、数据结构、接口、前端页面、测试与验收”的技术实现清单。

---

### 8.1 总体技术分层建议

建议把后端按下面结构逐步收敛，避免后期功能膨胀后难以维护：

```text
backend/
  api/                # HTTP 路由层
  core/               # 配置、枚举、权限、异常、日志
  deps/               # FastAPI Depends
  models/             # SQLAlchemy 模型
  schemas/            # Pydantic 请求/响应模型
  services/           # 纯业务服务
  agents/             # Agent 执行单元
  prompts/            # Prompt 注册与模板
  workers/            # Celery 任务
  repositories/       # 数据访问封装（可选）
```

前端建议按下面结构演进：

```text
packages/web/src/
  app/                # Next.js 路由
  components/         # 页面组件
  features/           # 按业务域组织：project/import/beat/script/shot/assets
  stores/             # Zustand stores
  hooks/              # 页面 hooks
  lib/                # fetch、路由适配、格式化

packages/shared/src/
  types/              # 双端共享类型（短期）
  schemas/            # 未来可迁到 codegen
  components/         # 通用组件
```

---

### 8.2 Phase 0 技术实现细化

#### T0-1 技术实现：PostgreSQL + Alembic + Docker Compose

**涉及目录**

- `backend/config.py`
- `backend/database.py`
- `backend/models/`
- `backend/requirements.txt`
- `backend/alembic.ini`
- `backend/alembic/`
- `docker-compose.yml`
- `backend/.env.example`

**具体实现点**

- 将 `database_url` 改为优先读取 `DATABASE_URL`
- 开发环境默认值切换为 PostgreSQL，例如：
  - `postgresql+psycopg://postgres:postgres@localhost:5432/unrealmake`
- 引入 Alembic，迁移模型而非使用 `create_all` 作为长期方案
- `docker-compose.yml` 至少包含：
  - `postgres`
  - `redis`
  - `backend`
- 本地开发统一通过 `.env` 注入：
  - `DATABASE_URL`
  - `REDIS_URL`
  - `APP_ENV`

**接口/行为变化**

- `main.py` 启动时不再承担“自动建所有表”的长期职责
- 改为：
  - 开发期允许 fallback 初始化
  - 正式开发流统一使用 migration

**验收标准**

- `docker compose up` 可启动 PostgreSQL、Redis、backend
- 迁移可执行
- `projects` CRUD 在 PostgreSQL 下正常运行

---

#### T0-2 技术实现：edition / 权限门控

**涉及目录**

- `backend/core/edition.py`
- `backend/deps/edition.py`
- `backend/schemas/auth.py` 或等价模块
- `backend/api/*.py`
- `packages/shared/src/types/edition.ts`

**具体实现点**

- 后端定义统一 edition 枚举：
  - `normal`
  - `canvas`
  - `hidden`
  - `ultimate`
- 定义版本比较工具：
  - `is_edition_at_least(current, required)`
- 定义 Depends：
  - `require_edition(min_edition)`
- 所有未来高阶接口显式挂载版本限制，例如：
  - `/assets` >= `canvas`
  - `/cinema-lab` >= `hidden`
  - `/debug` == `ultimate`

**关键设计建议**

- 不要继续信任前端传入的 `edition`
- 项目的 `edition` 只能由：
  - 当前用户订阅/授权
  - 管理员设置
  - 开发测试配置
  来决定

**验收标准**

- 低版本请求高版本接口返回 403
- 业务代码内部不出现大量 `if edition == ...`
- edition 判断统一集中在 Depends 与配置层

---

#### T0-3 技术实现：AIEngine

**涉及目录**

- `backend/services/ai_engine.py`
- `backend/services/providers/base.py`
- `backend/services/providers/anthropic.py`
- `backend/services/providers/openai.py`
- `backend/services/providers/deepseek.py`
- `backend/schemas/ai.py`

**建议接口设计**

```python
class AIRequest(BaseModel):
    provider: str | None = None
    model: str
    temperature: float = 0.4
    system: str | None = None
    messages: list[dict]
    stream: bool = False
    metadata: dict | None = None
```

```python
class AIEngine:
    async def generate(self, request: AIRequest) -> AIResponse: ...
    async def stream(self, request: AIRequest): ...
```

**实现策略**

- 统一 provider 注册表
- 将模型名、超参、限流、重试策略放在 provider 层
- Agent 层不要直接访问第三方 SDK

**验收标准**

- 同一 Agent 可切换 provider 而无需改业务代码
- 支持普通响应与流式响应
- 失败时有清晰错误分类：超时、鉴权失败、限流、格式错误

---

#### T0-4 技术实现：Prompt Registry + Agent Base

**涉及目录**

- `backend/prompts/registry.py`
- `backend/prompts/templates/`
- `backend/agents/base.py`
- `backend/agents/analyst.py`
- `backend/agents/consistency.py`
- `backend/schemas/agent.py`

**建议数据结构**

```python
class PromptSpec(BaseModel):
    id: str
    name: str
    model: str
    temperature: float
    system_template: str
    user_template: str
    output_schema: dict | None = None
```

```python
class AgentResult(BaseModel):
    success: bool
    data: dict | list | str | None
    usage: dict | None = None
    warnings: list[str] = []
```

**Agent 基类能力建议**

- 输入校验
- Prompt 渲染
- AIEngine 调用
- 输出解析
- 错误封装
- tracing / logging hooks

**验收标准**

- `AnalystAgent` 可跑通至少一个任务
- Prompt 使用 ID 管理，不散落在业务代码中

---

#### T0-5 技术实现：节点执行引擎

**涉及目录**

- `backend/services/node_execution.py`
- `backend/models/node_run.py`
- `backend/schemas/execution.py`
- `backend/api/executions.py`
- `packages/web/src/features/executions/`

**建议最小数据结构**

```python
class NodeRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"

class NodeRun(Base):
    id
    project_id
    node_type
    input_payload
    output_payload
    status
    error_message
    started_at
    finished_at
```

**最小节点集合**

- `import_novel`
- `import_script`
- `analyze_content`
- `build_knowledge`
- `generate_beats`

**API 设计建议**

- `POST /api/projects/{id}/executions`
- `GET /api/projects/{id}/executions`
- `GET /api/executions/{execution_id}`

**验收标准**

- 可触发一个节点执行
- 前端能看到运行状态变化
- 错误可追踪

---

#### T0-6 技术实现：核心领域模型

**涉及目录**

- `backend/models/chapter.py`
- `backend/models/character.py`
- `backend/models/location.py`
- `backend/models/beat.py`
- `backend/models/scene.py`
- `backend/models/shot.py`
- `backend/models/knowledge_base.py`
- `backend/schemas/*.py`
- `backend/api/*.py`

**建模建议**

- `Project 1:N Chapter`
- `Project 1:N Character`
- `Project 1:N Location`
- `Project 1:N Beat`
- `Project 1:N Scene`
- `Scene 1:N Shot`
- `Project 1:1 KnowledgeBaseSummary` 或 `Project 1:N KnowledgeSnapshots`

**字段约束建议**

- 所有核心实体加 `project_id`
- 所有顺序实体加 `order_index`
- 复杂结构优先使用 JSON 字段承载可变信息

**验收标准**

- 前端 `packages/shared/src/types/project.ts` 中核心类型至少 70% 有后端对应实体
- 可通过 API 完成核心链路数据读写

---

### 8.3 Phase 1 技术实现细化

#### T1-1 技术实现：小说导入 MVP

**涉及目录**

- `backend/api/imports.py`
- `backend/services/importers/novel_importer.py`
- `backend/services/file_storage.py`
- `backend/workers/import_tasks.py`
- `packages/web/src/features/imports/`

**建议能力边界**

- 第一版只做：`txt`、`md`
- 第二版再扩：`docx`、`epub`、`pdf`

**最小 API**

- `POST /api/projects/{id}/import/novel`
- 上传文件或原始文本
- 返回 `execution_id`

**处理流程**

1. 保存源文本
2. 预处理（去 BOM、标准化换行）
3. 章节切分
4. 写入 `chapters`
5. 推进项目状态

**验收标准**

- 用户上传 `txt` 后可看到章节列表

---

#### T1-2 技术实现：剧本导入 MVP

**涉及目录**

- `backend/services/importers/script_importer.py`
- `backend/services/parsers/fountain_parser.py`
- `backend/services/parsers/text_script_parser.py`

**建议能力边界**

- 第一版只做：`txt`、`fountain`
- `fdx` 放第二阶段

**处理流程**

1. 识别脚本格式
2. 标准化为内部 JSON
3. 提取场景标题、角色名、对白段落
4. 初始化 `Scene` / `Character`

**验收标准**

- 导入 Fountain 后能得到结构化场景列表

---

#### T1-3 技术实现：分析层 MVP

**涉及目录**

- `backend/services/pipelines/analysis_pipeline.py`
- `backend/agents/analyst.py`
- `backend/api/analysis.py`

**最小输出**

- 角色列表
- 场景列表
- 世界观摘要
- 项目知识摘要

**验收标准**

- 从导入内容可生成基础知识卡

---

### 8.4 Phase 2 技术实现细化

#### T2-1 技术实现：Beat Sheet MVP

**涉及目录**

- `backend/api/beats.py`
- `backend/services/pipelines/beat_pipeline.py`
- `packages/web/src/features/beats/`

**建议 API**

- `POST /api/projects/{id}/beats/generate`
- `GET /api/projects/{id}/beats`
- `PUT /api/beats/{beat_id}`
- `POST /api/projects/{id}/beats/reorder`

**前端能力**

- Beat 列表
- 排序
- 编辑标题/描述
- 标注情绪值

**验收标准**

- 用户可在 UI 中编辑 AI 生成 Beat

---

#### T2-2 技术实现：Scene / Script MVP

**涉及目录**

- `backend/api/scenes.py`
- `backend/services/pipelines/script_pipeline.py`
- `packages/web/src/features/script/`

**建议能力边界**

- 第一版先保证结构化 Script 数据，不急于上复杂富文本编辑器
- 可先用“场景卡 + 对白块”的方式交付 MVP

**验收标准**

- 用户可从 Beat 生成 Scene，并进行基础编辑

---

### 8.5 Phase 3 技术实现细化

#### T3-1 技术实现：节点画布 MVP

**涉及目录**

- `packages/web/src/features/canvas/`
- `packages/shared/src/components/workspace/`
- `packages/shared/src/types/canvas.ts`

**建议最小节点类型**

- ImportNode
- AnalysisNode
- KnowledgeNode
- BeatNode
- ScriptNode

**前端状态模型**

- `idle`
- `ready`
- `running`
- `success`
- `failed`

**验收标准**

- 用户能在 Canvas 上触发节点执行并看到结果预览

---

#### T3-2 技术实现：Shot / Storyboard MVP

**涉及目录**

- `backend/api/shots.py`
- `backend/services/pipelines/storyboard_pipeline.py`
- `packages/web/src/features/storyboard/`

**最小输出字段**

- `shot_number`
- `shot_size`
- `camera_angle`
- `camera_movement`
- `duration`
- `description`

**验收标准**

- 每个 Scene 可生成 1 组可编辑 Shot 列表

---

### 8.6 Phase 4 技术实现细化

#### T4-1 技术实现：视觉 Prompt MVP

**涉及目录**

- `backend/api/visual_prompts.py`
- `backend/services/pipelines/visual_prompt_pipeline.py`
- `packages/web/src/features/visual-prompts/`

**数据设计建议**

- `Shot.visual_prompt` 保存最终文本
- 候选方案单独建表：`shot_prompt_candidates`

**验收标准**

- 每个 Shot 至少可生成 1 条视觉 prompt

---

#### T4-2 技术实现：生成层 MVP

**涉及目录**

- `backend/api/generation.py`
- `backend/models/generated_asset.py`
- `backend/services/generators/`
- `packages/web/src/features/generation/`

**建议输出模型**

- `GeneratedAsset`
  - `id`
  - `project_id`
  - `shot_id`
  - `type`
  - `provider`
  - `prompt`
  - `url`
  - `thumbnail_url`
  - `metadata`

**验收标准**

- 视觉 prompt 可驱动至少一个外部生成接口，返回结果可在 UI 查看

---

### 8.7 Phase 5 技术实现细化

#### T5-1 技术实现：Asset Library MVP

**涉及目录**

- `backend/models/asset.py`
- `backend/models/project_asset_ref.py`
- `backend/api/assets.py`
- `backend/services/assets/`
- `packages/web/src/features/assets/`

**建议核心表**

- `assets`
- `asset_contents`
- `project_asset_refs`

**建议最小字段**

- `scope`
- `type`
- `name`
- `description`
- `owner_id`
- `project_id`（仅项目级资产）
- `is_locked`

**验收标准**

- 项目可绑定角色资产并在下游读取

---

#### T5-2 技术实现：角色视觉一致性 MVP

**涉及目录**

- `backend/services/assets/character_visual_service.py`
- `backend/api/assets.py`
- `packages/web/src/features/assets/characters/`

**最小链路**

1. Character -> 视觉卡
2. 视觉卡 -> 参考图 prompt
3. 参考图生成
4. 资产锁定
5. Prompt 注入下游镜头

**验收标准**

- 锁定某角色后，后续镜头 prompt 能引用对应角色资产

---

### 8.8 Phase 6 技术实现细化

#### T6-1 技术实现：CapCut Draft MVP

**涉及目录**

- `backend/services/capcut/capcut_draft_builder.py`
- `backend/api/capcut.py`
- `packages/web/src/features/export/capcut/`

**建议拆分**

- `timeline_mapper.py`
- `subtitle_builder.py`
- `marker_builder.py`
- `archive_builder.py`

**验收标准**

- 能导出一个最小 Draft 包，包含基础时间线和字幕

---

#### T6-2 技术实现：Animatic MVP

**涉及目录**

- `backend/services/animatic/animatic_builder.py`
- `backend/services/tts/`
- `backend/api/animatic.py`
- `packages/web/src/features/animatic/`

**第一版建议**

- 静帧图 + 时长 + TTS 占位音轨
- 不要一开始就做完整 Ken Burns

**验收标准**

- 能生成一个可播放预览文件

---

### 8.9 测试与验收建议

#### 后端建议测试层级

- 单元测试：
  - provider 适配
  - prompt 渲染
  - parser
  - pipeline 纯函数
- 集成测试：
  - projects CRUD
  - import -> analysis -> beats
  - assets 绑定
- 合约测试：
  - OpenAPI schema
- 端到端测试：
  - 创建项目
  - 导入文本
  - 生成 Beat

#### 前端建议测试层级

- 组件测试：
  - WizardLayout
  - WorkspaceLayout
  - Canvas Nodes
- 页面流程测试：
  - 新建项目
  - Beat 编辑
  - 节点执行展示

---

## 9. Jira / Tapd 可直接导入的任务清单版

下面提供两种格式：

1. **表格版**：方便你直接复制到 Jira / Tapd 批量建单页面
2. **CSV 模板版**：方便后续导出为 `.csv`

字段尽量采用通用管理工具都能映射的形式：

- `Epic`
- `Issue Type`
- `Summary`
- `Description`
- `Priority`
- `Labels`
- `Component`
- `Sprint`
- `Depends On`
- `Acceptance Criteria`

---

### 9.1 导入字段建议

| 字段 | 建议值说明 |
|------|------------|
| Epic | `Phase 0 基建` / `Phase 1 导入分析` / `Phase 2 编剧链路` 等 |
| Issue Type | `Epic` / `Story` / `Task` |
| Summary | 简短任务名，建议带模块前缀 |
| Description | 任务背景 + 目标 + 范围 |
| Priority | `Highest` / `High` / `Medium` / `Low` |
| Labels | 例如 `backend,ai,phase0,p0` |
| Component | `backend` / `web` / `shared` / `infra` |
| Sprint | `Sprint 0` / `Sprint 1` / `Sprint 2` |
| Depends On | 依赖任务编号 |
| Acceptance Criteria | 用 2-4 条 bullet 描述 |

---

### 9.2 任务表（可直接复制）

| Epic | Issue Type | Summary | Description | Priority | Labels | Component | Sprint | Depends On | Acceptance Criteria |
|------|------------|---------|-------------|----------|--------|-----------|--------|------------|---------------------|
| Phase 0 基建 | Story | INFRA-001 搭建 PostgreSQL 与 Alembic | 将后端从 SQLite 迁移到 PostgreSQL，引入 migration 机制，作为后续模型扩展地基。 | Highest | backend,infra,phase0,p0 | infra | Sprint 0 | - | 1. PostgreSQL 可启动；2. Alembic 可迁移；3. projects CRUD 正常 |
| Phase 0 基建 | Story | INFRA-002 增加 Docker Compose 开发环境 | 提供 PostgreSQL、Redis、backend 的一键开发环境，降低协作成本。 | Highest | infra,docker,phase0,p0 | infra | Sprint 0 | INFRA-001 | 1. `docker compose up` 成功；2. backend 可连接 DB/Redis |
| Phase 0 基建 | Story | AUTH-001 建立 edition 枚举与后端门控 | 在后端建立可信 edition 体系，并提供统一 Depends 进行版本控制。 | Highest | backend,auth,edition,phase0,p0 | backend | Sprint 0 | INFRA-001 | 1. 存在统一枚举；2. 低版本访问受限接口返回 403 |
| Phase 0 基建 | Story | AI-001 建立 AIEngine 抽象层 | 统一接入 Anthropic/OpenAI/DeepSeek，隔离 provider 差异。 | Highest | backend,ai,phase0,p0 | backend | Sprint 0 | INFRA-001 | 1. AIEngine 可调用 provider；2. 支持普通/流式响应 |
| Phase 0 基建 | Story | AI-002 建立 Prompt Registry 与 Agent Base | 建立 Prompt ID 注册机制、Agent 基类与最小可执行 Agent。 | Highest | backend,ai,agent,phase0,p0 | backend | Sprint 0 | AI-001 | 1. Prompt 可按 ID 管理；2. AnalystAgent 可跑通最小任务 |
| Phase 0 基建 | Story | EXEC-001 建立节点执行引擎 | 建立 Node -> Task 的执行映射、状态追踪与执行结果结构。 | Highest | backend,execution,phase0,p0 | backend | Sprint 0 | AI-002 | 1. 可触发执行；2. 有状态跟踪；3. 可查询结果 |
| Phase 0 基建 | Story | MODEL-001 补齐核心领域模型 | 新增 Chapter、Character、Location、Beat、Scene、Shot、KnowledgeBase 模型及迁移。 | Highest | backend,models,phase0,p0 | backend | Sprint 0 | INFRA-001 | 1. 表结构可迁移；2. 实体关系明确；3. 可通过 API 读写 |
| Phase 1 导入分析 | Story | IMPORT-001 实现小说导入 MVP | 支持 txt/md 上传、文本预处理、章节切分、Chapter 落库。 | Highest | backend,import,novel,phase1,p0 | backend | Sprint 1 | MODEL-001,EXEC-001 | 1. 可上传 txt/md；2. 能生成章节列表 |
| Phase 1 导入分析 | Story | IMPORT-002 实现剧本导入 MVP | 支持 txt/fountain 导入、格式识别、内部 JSON 标准化、结构提取。 | Highest | backend,import,script,phase1,p0 | backend | Sprint 1 | MODEL-001,EXEC-001 | 1. 可导入 fountain；2. 得到结构化 Scene/Character |
| Phase 1 导入分析 | Story | ANALYSIS-001 实现分析层 MVP | 从导入内容生成角色、场景、世界观摘要，并初始化知识库。 | Highest | backend,analysis,knowledge,phase1,p0 | backend | Sprint 1 | IMPORT-001,IMPORT-002,AI-002 | 1. 可生成角色/场景；2. 项目 stage 推进到 knowledge |
| Phase 2 编剧链路 | Story | BEAT-001 实现 Beat Sheet MVP | 从内容生成 Beat 列表，支持查看、编辑、排序。 | Highest | backend,web,beat,phase2,p0 | backend,web | Sprint 2 | ANALYSIS-001 | 1. 可生成 Beat；2. 前端可编辑；3. stage 推进到 beat_sheet |
| Phase 2 编剧链路 | Story | SCRIPT-001 实现 Scene/Script MVP | 从 Beat 生成 Scene，提供基础剧本编辑能力。 | Highest | backend,web,script,phase2,p0 | backend,web | Sprint 2 | BEAT-001 | 1. 可生成 Scene；2. 前端可编辑；3. stage 推进到 script |
| Phase 2 编剧链路 | Story | REVIEW-001 实现一致性守护 MVP | 检查角色命名、场景缺失、基础逻辑冲突，并输出 review 结果。 | High | backend,review,consistency,phase2,p1 | backend | Sprint 2 | SCRIPT-001 | 1. 可输出 review；2. UI 可查看结果 |
| Phase 3 画布导演 | Story | CANVAS-001 实现节点画布 MVP | 引入可执行节点画布，展示节点状态与结果预览。 | High | web,canvas,phase3,p1 | web | Sprint 3 | EXEC-001,BEAT-001 | 1. 画布可展示节点；2. 可触发执行；3. 可展示状态 |
| Phase 3 画布导演 | Story | SHOT-001 实现 Shot/Storyboard MVP | 从 Scene 生成 Shot 列表，支持编辑基础镜头参数。 | High | backend,web,storyboard,phase3,p1 | backend,web | Sprint 3 | SCRIPT-001 | 1. 可生成 Shot；2. 可编辑镜头字段 |
| Phase 3 画布导演 | Story | DIRECTOR-001 实现导演基础链路 | 在 Shot 上补充景别、角度、运镜、时长建议、导演说明。 | High | backend,director,phase3,p1 | backend | Sprint 3 | SHOT-001 | 1. Shot 含基础导演字段；2. 可生成导演说明 |
| Phase 4 视觉生成 | Story | VP-001 实现视觉 Prompt MVP | 从 Shot 生成可用于图像/视频生成的视觉 prompt。 | High | backend,web,visual-prompt,phase4,p1 | backend,web | Sprint 4 | SHOT-001 | 1. 每个 Shot 可生成 prompt；2. UI 可预览 |
| Phase 4 视觉生成 | Story | GEN-001 实现图像生成第一版 | 接入至少一个图像生成 provider，保存结果并回填镜头。 | High | backend,ai,generation,phase4,p1 | backend | Sprint 4 | VP-001,AI-001 | 1. 可发起图像生成；2. 结果可查看 |
| Phase 5 资产库 | Story | ASSET-001 实现 Asset Library MVP | 建立资产模型、CRUD、项目引用机制。 | High | backend,web,assets,phase5,p1 | backend,web | Sprint 5 | MODEL-001 | 1. 可创建资产；2. 项目可引用资产 |
| Phase 5 资产库 | Story | ASSET-002 实现角色视觉一致性 MVP | 角色视觉卡生成、参考图生成、锁定与下游 prompt 注入。 | High | backend,web,assets,character,phase5,p1 | backend,web | Sprint 5 | ASSET-001,VP-001 | 1. 可锁定角色资产；2. 下游 prompt 能使用锁定资产 |
| Phase 6 输出层 | Story | EXPORT-001 实现 CapCut Draft MVP | 生成最小 Draft 包，包含基础时间线、字幕、标记与下载接口。 | Medium | backend,export,capcut,phase6,p2 | backend | Sprint 6 | SHOT-001,GEN-001 | 1. 可导出 Draft；2. 包含时间线和字幕 |
| Phase 6 输出层 | Story | ANIMATIC-001 实现 Animatic MVP | 用静帧、时长和 TTS 占位音轨生成预览视频。 | Medium | backend,web,animatic,phase6,p2 | backend,web | Sprint 6 | SHOT-001,GEN-001 | 1. 可生成可播放预览；2. 前端可查看 |
| Phase 6 输出层 | Story | CINEMA-001 实现 Cinema Lab MVP | 建立镜头高级实验面板与主项目回写能力。 | Medium | web,cinema-lab,phase6,p2 | web | Sprint 6 | SHOT-001 | 1. 可编辑高级镜头参数；2. 可回写主镜头 |
| Phase 7 高级能力 | Story | MKT-001 实现宣发物料生成 | 生成封面、海报、预告草稿，并纳入资产系统。 | Low | backend,marketing,phase7,p3 | backend | Sprint 7 | ASSET-001,GEN-001 | 1. 可输出至少一种宣发物料 |
| Phase 7 高级能力 | Story | ADV-001 实现高阶导演/声音/微短剧能力 | 补齐声音叙事、场面调度、文化适配、微短剧增强与数据反馈。 | Low | backend,advanced,phase7,p3 | backend | Sprint 7 | DIRECTOR-001,REVIEW-001 | 1. 至少实现一个高阶子能力闭环 |

---

### 9.3 CSV 模板版（Jira / Tapd 导入参考）

> 使用方式：复制下面内容到 `tasks.csv`，再按 Jira/Tapd 的字段映射导入。  
> 如果你的管理工具字段名不同，可将第一行表头替换成对应中文字段名。

```csv
Epic,Issue Type,Summary,Description,Priority,Labels,Component,Sprint,Depends On,Acceptance Criteria
Phase 0 基建,Story,INFRA-001 搭建 PostgreSQL 与 Alembic,"将后端从 SQLite 迁移到 PostgreSQL，引入 migration 机制，作为后续模型扩展地基。",Highest,"backend,infra,phase0,p0",infra,Sprint 0,-,"PostgreSQL 可启动；Alembic 可迁移；projects CRUD 正常"
Phase 0 基建,Story,INFRA-002 增加 Docker Compose 开发环境,"提供 PostgreSQL、Redis、backend 的一键开发环境，降低协作成本。",Highest,"infra,docker,phase0,p0",infra,Sprint 0,INFRA-001,"docker compose up 成功；backend 可连接 DB/Redis"
Phase 0 基建,Story,AUTH-001 建立 edition 枚举与后端门控,"在后端建立可信 edition 体系，并提供统一 Depends 进行版本控制。",Highest,"backend,auth,edition,phase0,p0",backend,Sprint 0,INFRA-001,"存在统一枚举；低版本访问受限接口返回 403"
Phase 0 基建,Story,AI-001 建立 AIEngine 抽象层,"统一接入 Anthropic/OpenAI/DeepSeek，隔离 provider 差异。",Highest,"backend,ai,phase0,p0",backend,Sprint 0,INFRA-001,"AIEngine 可调用 provider；支持普通/流式响应"
Phase 0 基建,Story,AI-002 建立 Prompt Registry 与 Agent Base,"建立 Prompt ID 注册机制、Agent 基类与最小可执行 Agent。",Highest,"backend,ai,agent,phase0,p0",backend,Sprint 0,AI-001,"Prompt 可按 ID 管理；AnalystAgent 可跑通最小任务"
Phase 0 基建,Story,EXEC-001 建立节点执行引擎,"建立 Node -> Task 的执行映射、状态追踪与执行结果结构。",Highest,"backend,execution,phase0,p0",backend,Sprint 0,AI-002,"可触发执行；有状态跟踪；可查询结果"
Phase 0 基建,Story,MODEL-001 补齐核心领域模型,"新增 Chapter、Character、Location、Beat、Scene、Shot、KnowledgeBase 模型及迁移。",Highest,"backend,models,phase0,p0",backend,Sprint 0,INFRA-001,"表结构可迁移；实体关系明确；可通过 API 读写"
Phase 1 导入分析,Story,IMPORT-001 实现小说导入 MVP,"支持 txt/md 上传、文本预处理、章节切分、Chapter 落库。",Highest,"backend,import,novel,phase1,p0",backend,Sprint 1,"MODEL-001|EXEC-001","可上传 txt/md；能生成章节列表"
Phase 1 导入分析,Story,IMPORT-002 实现剧本导入 MVP,"支持 txt/fountain 导入、格式识别、内部 JSON 标准化、结构提取。",Highest,"backend,import,script,phase1,p0",backend,Sprint 1,"MODEL-001|EXEC-001","可导入 fountain；得到结构化 Scene/Character"
Phase 1 导入分析,Story,ANALYSIS-001 实现分析层 MVP,"从导入内容生成角色、场景、世界观摘要，并初始化知识库。",Highest,"backend,analysis,knowledge,phase1,p0",backend,Sprint 1,"IMPORT-001|IMPORT-002|AI-002","可生成角色/场景；项目 stage 推进到 knowledge"
Phase 2 编剧链路,Story,BEAT-001 实现 Beat Sheet MVP,"从内容生成 Beat 列表，支持查看、编辑、排序。",Highest,"backend,web,beat,phase2,p0","backend,web",Sprint 2,ANALYSIS-001,"可生成 Beat；前端可编辑；stage 推进到 beat_sheet"
Phase 2 编剧链路,Story,SCRIPT-001 实现 Scene/Script MVP,"从 Beat 生成 Scene，提供基础剧本编辑能力。",Highest,"backend,web,script,phase2,p0","backend,web",Sprint 2,BEAT-001,"可生成 Scene；前端可编辑；stage 推进到 script"
Phase 2 编剧链路,Story,REVIEW-001 实现一致性守护 MVP,"检查角色命名、场景缺失、基础逻辑冲突，并输出 review 结果。",High,"backend,review,consistency,phase2,p1",backend,Sprint 2,SCRIPT-001,"可输出 review；UI 可查看结果"
Phase 3 画布导演,Story,CANVAS-001 实现节点画布 MVP,"引入可执行节点画布，展示节点状态与结果预览。",High,"web,canvas,phase3,p1",web,Sprint 3,"EXEC-001|BEAT-001","画布可展示节点；可触发执行；可展示状态"
Phase 3 画布导演,Story,SHOT-001 实现 Shot/Storyboard MVP,"从 Scene 生成 Shot 列表，支持编辑基础镜头参数。",High,"backend,web,storyboard,phase3,p1","backend,web",Sprint 3,SCRIPT-001,"可生成 Shot；可编辑镜头字段"
Phase 3 画布导演,Story,DIRECTOR-001 实现导演基础链路,"在 Shot 上补充景别、角度、运镜、时长建议、导演说明。",High,"backend,director,phase3,p1",backend,Sprint 3,SHOT-001,"Shot 含基础导演字段；可生成导演说明"
Phase 4 视觉生成,Story,VP-001 实现视觉 Prompt MVP,"从 Shot 生成可用于图像/视频生成的视觉 prompt。",High,"backend,web,visual-prompt,phase4,p1","backend,web",Sprint 4,SHOT-001,"每个 Shot 可生成 prompt；UI 可预览"
Phase 4 视觉生成,Story,GEN-001 实现图像生成第一版,"接入至少一个图像生成 provider，保存结果并回填镜头。",High,"backend,ai,generation,phase4,p1",backend,Sprint 4,"VP-001|AI-001","可发起图像生成；结果可查看"
Phase 5 资产库,Story,ASSET-001 实现 Asset Library MVP,"建立资产模型、CRUD、项目引用机制。",High,"backend,web,assets,phase5,p1","backend,web",Sprint 5,MODEL-001,"可创建资产；项目可引用资产"
Phase 5 资产库,Story,ASSET-002 实现角色视觉一致性 MVP,"角色视觉卡生成、参考图生成、锁定与下游 prompt 注入。",High,"backend,web,assets,character,phase5,p1","backend,web",Sprint 5,"ASSET-001|VP-001","可锁定角色资产；下游 prompt 能使用锁定资产"
Phase 6 输出层,Story,EXPORT-001 实现 CapCut Draft MVP,"生成最小 Draft 包，包含基础时间线、字幕、标记与下载接口。",Medium,"backend,export,capcut,phase6,p2",backend,Sprint 6,"SHOT-001|GEN-001","可导出 Draft；包含时间线和字幕"
Phase 6 输出层,Story,ANIMATIC-001 实现 Animatic MVP,"用静帧、时长和 TTS 占位音轨生成预览视频。",Medium,"backend,web,animatic,phase6,p2","backend,web",Sprint 6,"SHOT-001|GEN-001","可生成可播放预览；前端可查看"
Phase 6 输出层,Story,CINEMA-001 实现 Cinema Lab MVP,"建立镜头高级实验面板与主项目回写能力。",Medium,"web,cinema-lab,phase6,p2",web,Sprint 6,SHOT-001,"可编辑高级镜头参数；可回写主镜头"
Phase 7 高级能力,Story,MKT-001 实现宣发物料生成,"生成封面、海报、预告草稿，并纳入资产系统。",Low,"backend,marketing,phase7,p3",backend,Sprint 7,"ASSET-001|GEN-001","可输出至少一种宣发物料"
Phase 7 高级能力,Story,ADV-001 实现高阶导演/声音/微短剧能力,"补齐声音叙事、场面调度、文化适配、微短剧增强与数据反馈。",Low,"backend,advanced,phase7,p3",backend,Sprint 7,"DIRECTOR-001|REVIEW-001","至少实现一个高阶子能力闭环"
```

---

### 9.4 Jira / Tapd 建单建议

- 如果你们按“需求 -> 故事 -> 子任务”管理：
  - `Phase 0 基建`、`Phase 1 导入分析` 等建成 Epic
  - `INFRA-001`、`AI-001` 这类建成 Story
  - 每个 Story 再拆后端、前端、测试子任务
- 如果你们按 Tapd 普通任务流管理：
  - 直接把 `Story` 当作“开发任务”导入
  - 用 `Labels` 区分模块
  - 用 `Sprint` 区分阶段
- 如果准备做排期：
  - `Sprint 0` 只做 P0 基建
  - `Sprint 1-2` 做导入、分析、Beat、Script 主链路
  - `Sprint 3+` 再进入画布与 v6.0 增强
