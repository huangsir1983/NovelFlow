# 无限画布系统融合实施计划

> 版本: 1.0
> 日期: 2026-04-01
> 目标: 将画布模式借鉴文件夹中的无限画布系统融合到现有"小说到视频生成"框架中

---

## 一、项目背景

### 1.1 现有系统概况

**虚幻造物 (Unreal Make)** 是一个 AI-Native 影视创作引擎，已完成：

- ✅ 小说/剧本导入与分析
- ✅ 章节、Beat、Scene 结构化拆解
- ✅ Shot 分镜生成
- ✅ 角色/场景/道具资产库
- ✅ 知识库与一致性守护
- ✅ 三段式产品架构（前半段创作工作台 + 中段画布 + 后半段预演交付）

**当前缺失**：中段可执行无限画布工作台

### 1.2 画布借鉴系统概况

`画布模式借鉴` 文件夹提供了一个完整的无限画布实现：

- ✅ 基于 Zustand 的画布状态管理
- ✅ 虚拟化节点渲染（性能优化）
- ✅ 5 类工作流模块（对话/动作/悬疑/环境/情感）
- ✅ Claude Agent 智能分析与分配
- ✅ 分镜→图片→视频完整链路
- ✅ 节点执行引擎与工作流编排

### 1.3 融合目标

将画布系统作为**中段工作台**融入现有架构，实现：

1. **数据打通**：前段输出（Scene/Shot）→ 画布节点
2. **执行能力**：画布中可运行 AI 分析、图片合成、视频生成
3. **结果回写**：画布产出回写到项目真相层
4. **协作增强**：多人画布、评论、评审模式
5. **版本分层**：Normal/Canvas/Hidden/Ultimate 渐进开放能力

---

## 二、系统架构对比与映射

### 2.1 数据模型映射

| 现有系统 | 画布系统 | 映射关系 |
|---------|---------|---------|
| `Project` | `projectId` | 1:1 项目 ID |
| `Chapter` | `Chapter` | 直接复用 |
| `Scene` | `Scene` | 直接复用 |
| `Shot` | `StoryboardContent` | Shot → 分镜节点 |
| `Character` | `ProjectAsset (character)` | 角色资产 |
| `Location` | `ProjectAsset (scene)` | 场景资产 |
| `Prop` | `ProjectAsset (prop)` | 道具资产 |
| - | `ImageContent` | 新增：图片合成节点 |
| - | `VideoContent` | 新增：视频生成节点 |

### 2.2 技术栈对比

| 层级 | 现有系统 | 画布系统 | 融合方案 |
|-----|---------|---------|---------|
| 状态管理 | Zustand | Zustand | ✅ 统一使用 Zustand |
| UI 组件 | shadcn/ui | 自定义组件 | 保留画布自定义组件 |
| 画布引擎 | - | 自研虚拟化渲染 | ✅ 采用画布系统 |
| AI 调用 | 后端统一 | Claude SDK 前端直调 | ⚠️ 需改造为后端调用 |
| 路由 | Next.js App Router | - | 新增 `/projects/[id]/canvas` |

### 2.3 API 接口设计

#### 新增后端接口

```python
# backend/api/canvas.py

# 1. 画布 CRUD
POST   /api/projects/{project_id}/canvas          # 创建画布
GET    /api/projects/{project_id}/canvas          # 获取画布
PUT    /api/projects/{project_id}/canvas          # 保存画布
DELETE /api/projects/{project_id}/canvas          # 删除画布

# 2. 节点执行
POST   /api/canvas/nodes/{node_id}/execute        # 执行单节点
POST   /api/canvas/batch-execute                  # 批量执行
GET    /api/canvas/nodes/{node_id}/status         # 查询节点状态

# 3. Agent 服务
POST   /api/canvas/agent/analyze-storyboard       # 分镜分析
POST   /api/canvas/agent/assign-modules           # 模块分配
POST   /api/canvas/agent/optimize-prompt          # 提示词优化
POST   /api/canvas/agent/review-composition       # 构图审查

# 4. 工作流引擎
POST   /api/canvas/workflow/image                 # 图片合成工作流
POST   /api/canvas/workflow/video                 # 视频生成工作流
GET    /api/canvas/workflow/{job_id}/status       # 工作流状态查询

# 5. 数据同步
POST   /api/canvas/sync/from-project              # 从项目加载到画布
POST   /api/canvas/sync/to-project                # 画布结果回写项目
```

---

## 三、实施路线图

### Phase 1: 基础集成（2 周）

**目标**：画布页面可访问，能展示从 Scene/Shot 转换的节点

#### 任务清单

1. **前端路由与页面**
   - [ ] 创建 `/projects/[id]/canvas` 路由
   - [ ] 集成 `InfiniteCanvas.tsx` 主组件
   - [ ] 适配现有 UI 主题与样式变量

2. **状态管理集成**
   - [ ] 将 `canvasStore.ts` 集成到 `packages/shared/src/stores/`
   - [ ] 将 `projectStore.ts`（画布版）与现有 `projectStore.ts` 合并
   - [ ] 添加 `agentStore.ts` 到共享 stores

3. **数据适配器**
   - [ ] 实现 `integrationAdapter.ts` 中的 `loadFromExistingSystem()`
   - [ ] 编写 Scene/Shot → Canvas Node 转换逻辑
   - [ ] 实现资产库数据映射

4. **后端基础接口**
   - [ ] 创建 `backend/api/canvas.py`
   - [ ] 实现画布 CRUD 接口
   - [ ] 添加 Canvas 数据模型到数据库

**交付物**：
- 用户可进入画布页面
- 画布中显示项目的 Scene/Shot 节点
- 节点可拖拽、选择、缩放

---

### Phase 2: Agent 智能能力（2 周）

**目标**：Claude Agent 可分析分镜、生成提示词、分配模块

#### 任务清单

1. **后端 Agent 服务**
   - [ ] 创建 `backend/services/canvas_agent.py`
   - [ ] 实现分镜分析（生成 imagePrompt/videoPrompt）
   - [ ] 实现模块自动分配（5 类工作流识别）
   - [ ] 实现提示词优化
   - [ ] 实现图片构图审查

2. **前端 Agent 集成**
   - [ ] 移除 `claudeAgent.ts` 中的前端直调 Anthropic SDK
   - [ ] 改为调用后端 Agent API
   - [ ] 实现 Agent 任务队列 UI
   - [ ] 添加 Agent 执行进度显示

3. **模块系统**
   - [ ] 集成 5 类工作流模块（对话/动作/悬疑/环境/情感）
   - [ ] 实现模块区域可视化（ModuleBlock）
   - [ ] 实现节点自动归入模块
   - [ ] 添加模块折叠/展开功能

4. **知识库对接**
   - [ ] 将现有知识库（导演分镜、编剧系统）暴露给 Agent
   - [ ] Agent 调用时注入项目上下文（角色外貌、场景描述）

**交付物**：
- 点击"Agent 自动分配"可智能识别场景类型
- 点击分镜节点"执行"可生成提示词
- 节点按模块类型自动分组

---

### Phase 3: 工作流执行引擎（3 周）

**目标**：画布中可执行图片合成、视频生成完整链路

#### 任务清单

1. **图片合成工作流**
   - [ ] 后端实现 `backend/services/image_workflow.py`
   - [ ] 对接图片生成 API（Kling/即梦/MJ）
   - [ ] 实现背景生成、角色生成、镂空、合成等步骤
   - [ ] 前端显示工作流步骤进度

2. **视频生成工作流**
   - [ ] 后端实现 `backend/services/video_workflow.py`
   - [ ] 对接视频生成 API（Kling/即梦）
   - [ ] 实现任务提交、轮询、结果获取
   - [ ] 前端显示视频生成进度

3. **节点执行引擎**
   - [ ] 实现 `workflowEngine.ts` 后端版本
   - [ ] 支持单节点执行
   - [ ] 支持批量执行（拓扑排序 + 并行）
   - [ ] 支持执行中断与重试

4. **结果管理**
   - [ ] 节点结果存储（图片/视频 URL）
   - [ ] 中间产物管理
   - [ ] 候选版本管理（支持生成多个候选）

**交付物**：
- 分镜节点执行后生成提示词
- 图片节点执行后生成合成图
- 视频节点执行后生成视频
- 支持批量执行整条链路

---

### Phase 4: Tapnow 式交互增强（2 周）

**目标**：吸收 Tapnow/TapFlow 的可执行画布特性

#### Tapnow 核心特性借鉴

1. **模板驱动工作流**
   - [ ] 预设工作流模板（小说转视频标准版、微短剧全链路等）
   - [ ] 用户从模板创建画布
   - [ ] 模板包含预配置节点和连线

2. **结果优先展示**
   - [ ] 节点卡默认展示结果摘要（而非参数）
   - [ ] 结果卡支持预览、比较、回写
   - [ ] 高级参数折叠到右侧检查器

3. **局部重跑机制**
   - [ ] 单节点重跑
   - [ ] 从当前节点向后重跑
   - [ ] 分支候选比较（生成多个版本对比）

4. **显式回写系统**
   - [ ] 回写动作需明确目标（回写到哪个 Shot/Scene）
   - [ ] 回写前预览差异
   - [ ] 回写后可撤回

5. **执行状态可观察**
   - [ ] 节点状态实时更新（idle/ready/processing/done/error）
   - [ ] 连线根据上游状态变色
   - [ ] 底部控制台显示执行日志

**交付物**：
- 用户可从模板快速创建工作流
- 节点执行结果清晰可见
- 支持局部重跑和结果对比
- 画布产出可回写到项目

---

### Phase 5: 协作与评审（2 周）

**目标**：吸收 Figma/Miro 的协作能力

#### 任务清单

1. **多人协作**
   - [ ] 实时 Presence（显示其他用户光标）
   - [ ] 基于 Yjs 的画布状态同步
   - [ ] 冲突检测与合并

2. **评论系统**
   - [ ] 评论可挂载到节点、Frame、工件
   - [ ] 评论状态（open/resolved）
   - [ ] @提及与通知

3. **评审模式**
   - [ ] 编辑模式 vs 评审模式切换
   - [ ] 评审模式下只读、可评论
   - [ ] 审批流（待审批/已批准/需修改）

4. **Frame 与分组**
   - [ ] Frame 区域（类似 Figma）
   - [ ] 按章节/场景/评审区域分组
   - [ ] Frame 可折叠、命名、着色

**交付物**：
- 多人可同时编辑画布
- 可对节点和结果添加评论
- 支持评审模式与审批流

---

### Phase 6: 版本分层与权限（1 周）

**目标**：按 Normal/Canvas/Hidden/Ultimate 渐进开放能力

#### 版本能力矩阵

| 能力 | Normal | Canvas | Hidden | Ultimate |
|-----|--------|--------|--------|----------|
| 画布访问 | 向导式锁定 | 自由画布 | 自由画布 | 自由画布 |
| 节点类型 | 7 种基础 | 20 种 | 全部 | 全部+实验 |
| 自由连线 | ❌ | 受限 | ✅ | ✅ |
| Agent 调用 | 后台自动 | 手动触发 | 手动+批量 | 手动+批量+调试 |
| 模块分配 | 自动 | 自动+手动 | 完全手动 | 完全手动 |
| 候选数量 | 1 | 3 | 5 | 不限 |
| 调试视图 | ❌ | ❌ | 部分 | 完整 |
| 节点嵌套 | ❌ | ❌ | 部分 | ✅ |

#### 实施任务

1. **版本门控**
   - [ ] 前端：根据用户版本过滤节点库
   - [ ] 前端：根据版本禁用高级功能
   - [ ] 后端：API 层版本校验

2. **Normal 版向导式体验**
   - [ ] 预设固定工作流，不可修改连线
   - [ ] 自动执行，无需手动触发
   - [ ] 只展示最终结果

3. **Ultimate 版调试能力**
   - [ ] 显示 Prompt 原文
   - [ ] 显示 Token 消耗
   - [ ] 显示模型选择与温度
   - [ ] 显示执行耗时

**交付物**：
- 不同版本用户看到不同画布能力
- Normal 用户体验简化向导式流程
- Ultimate 用户可访问完整调试信息

---

## 四、关键技术决策

### 4.1 AI 调用架构

**决策**：所有 AI 调用统一走后端，不在前端直调 Anthropic SDK

**理由**：
- 安全性：API Key 不暴露到前端
- 统一管理：复用现有 provider 系统和 rate limiter
- 成本控制：后端统一记录 token 消耗
- 降级策略：后端可实现多 provider fallback

**改造方案**：
```typescript
// 画布系统原方案（前端直调）
const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
const response = await client.messages.create({...});

// 改造后方案（调用后端）
const response = await fetch('/api/canvas/agent/analyze-storyboard', {
  method: 'POST',
  body: JSON.stringify({ nodeId, content })
});
```

### 4.2 状态管理架构

**决策**：画布状态独立管理，与项目状态松耦合

**理由**：
- 画布是临时工作空间，不是项目真相层
- 画布可以有多个版本（草稿/正式）
- 画布状态变更频繁，不应污染项目状态

**数据流**：
```
项目真相层 (Scene/Shot/Asset)
    ↓ 加载
画布状态层 (Canvas Nodes/Edges)
    ↓ 执行
画布结果层 (Generated Images/Videos)
    ↓ 回写
项目真相层 (Shot.visual_prompt / Shot.candidates)
```

### 4.3 节点执行模式

**决策**：采用事件驱动 + 轮询混合模式

**短任务（< 30s）**：事件驱动
- 分镜分析、提示词生成
- 后端同步返回结果
- 前端直接更新节点状态

**长任务（> 30s）**：轮询模式
- 图片合成、视频生成
- 后端返回 jobId
- 前端轮询 `/status` 接口
- 支持 SSE 推送进度（可选）

### 4.4 数据持久化策略

**画布数据存储**：
```sql
-- 新增表
CREATE TABLE canvas_workflows (
  id UUID PRIMARY KEY,
  project_id UUID REFERENCES projects(id),
  name VARCHAR(255),
  workflow_json JSONB,  -- 完整画布状态
  status VARCHAR(20),   -- draft/active/archived
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE canvas_node_executions (
  id UUID PRIMARY KEY,
  workflow_id UUID REFERENCES canvas_workflows(id),
  node_id VARCHAR(100),
  status VARCHAR(20),
  input_snapshot JSONB,
  output_snapshot JSONB,
  started_at TIMESTAMP,
  completed_at TIMESTAMP
);
```

**自动保存策略**：
- 用户操作后 3 秒防抖保存
- 节点执行完成后立即保存
- 离开页面前强制保存

---

## 五、核心代码结构

### 5.1 前端目录结构

```
packages/shared/src/
├── stores/
│   ├── canvasStore.ts           # 画布状态（节点/连线/视图）
│   ├── canvasAgentStore.ts      # Agent 任务队列
│   └── projectStore.ts          # 扩展：添加画布相关字段
├── components/
│   └── canvas/
│       ├── InfiniteCanvas.tsx   # 主画布容器
│       ├── CanvasRenderer.tsx   # 虚拟化渲染器
│       ├── nodes/
│       │   ├── BaseNode.tsx
│       │   ├── StoryboardNode.tsx
│       │   ├── ImageNode.tsx
│       │   └── VideoNode.tsx
│       ├── modules/
│       │   ├── ModuleBlock.tsx
│       │   └── ModuleTemplates.ts
│       ├── panels/
│       │   ├── NodeInspector.tsx
│       │   ├── ChainProgressPanel.tsx
│       │   └── AssetPanel.tsx
│       └── toolbar/
│           ├── Toolbar.tsx
│           ├── MiniMap.tsx
│           └── ConnectionLayer.tsx
├── hooks/
│   ├── useCanvas.ts
│   ├── useWorkflow.ts
│   └── useCanvasSync.ts
└── services/
    └── canvasApi.ts             # 画布 API 调用封装

packages/web/src/app/[locale]/projects/[id]/
└── canvas/
    └── page.tsx                 # 画布页面入口
```

### 5.2 后端目录结构

```
backend/
├── api/
│   └── canvas.py                # 画布 API 路由
├── services/
│   ├── canvas_agent.py          # Agent 服务
│   ├── canvas_workflow.py       # 工作流执行引擎
│   ├── image_workflow.py        # 图片合成工作流
│   └── video_workflow.py        # 视频生成工作流
├── models/
│   ├── canvas_workflow.py       # 画布数据模型
│   └── canvas_node_execution.py # 节点执行记录
└── knowledge/
    └── modules/
        └── canvas_modules.yaml  # 5 类工作流模块知识库
```

---

## 六、数据迁移与兼容

### 6.1 现有项目迁移

**场景**：已有项目（已完成 Scene/Shot 拆解）如何使用画布？

**方案**：
1. 用户首次进入画布页面
2. 系统检测到该项目无画布数据
3. 自动调用 `loadFromExistingSystem(projectId)`
4. 将 Scene/Shot 转换为画布节点
5. 自动布局并保存

**转换规则**：
```typescript
// 每个 Shot 生成 3 个节点
Shot → StoryboardNode (分镜文本)
     → ImageNode (图片合成，初始 idle)
     → VideoNode (视频生成，初始 idle)

// 节点位置自动布局
按 Scene 分组，横向排列
每个 Shot 链路纵向排列
```

### 6.2 向后兼容

**原则**：画布是增强功能，不影响现有流程

- 不使用画布的用户：现有流程不变
- 使用画布的用户：画布产出可回写到 Shot
- Shot 数据结构扩展：
  ```python
  # Shot 模型新增字段
  canvas_node_id = Column(String(100), nullable=True)
  canvas_generated_image = Column(Text, nullable=True)
  canvas_generated_video = Column(Text, nullable=True)
  ```

---

## 七、性能优化策略

### 7.1 前端性能

**虚拟化渲染**：
- 只渲染视口内节点（+ 200px 缓冲区）
- 节点数 > 100 时启用虚拟化
- 使用 `getVisibleNodes()` 过滤

**连线优化**：
- SVG 连线层独立渲染
- 连线数 > 200 时降级为简化样式
- 使用 `useMemo` 缓存连线计算

**状态更新优化**：
- 使用 Zustand 的 `immer` 中间件
- 避免全量 nodes Map 替换
- 使用 `subscribeWithSelector` 精确订阅

### 7.2 后端性能

**Agent 调用优化**：
- 批量分析时使用单次 API 调用
- 实现请求合并（debounce 500ms）
- 使用流式输出减少等待时间

**工作流执行优化**：
- 并行执行无依赖节点
- 使用 Celery 异步任务队列
- 实现任务优先级（用户手动触发 > 批量执行）

**数据库优化**：
- `workflow_json` 使用 JSONB 索引
- 节点执行记录定期归档
- 使用 Redis 缓存画布状态

---

## 八、测试策略

### 8.1 单元测试

**前端**：
- [ ] canvasStore 状态管理测试
- [ ] 节点转换逻辑测试
- [ ] 工作流执行计划生成测试

**后端**：
- [ ] Agent 服务单元测试
- [ ] 工作流引擎单元测试
- [ ] 数据转换逻辑测试

### 8.2 集成测试

- [ ] 项目 → 画布数据加载
- [ ] 画布节点执行完整链路
- [ ] 画布结果回写项目
- [ ] 多人协作冲突处理

### 8.3 性能测试

- [ ] 1000 节点画布渲染性能
- [ ] 100 节点并发执行
- [ ] 多用户同时编辑画布

---

## 九、风险与应对

### 9.1 技术风险

| 风险 | 影响 | 概率 | 应对措施 |
|-----|------|------|---------|
| AI API 限流 | 批量执行失败 | 高 | 实现队列 + 重试 + 降级 |
| 画布状态冲突 | 多人协作数据丢失 | 中 | 使用 Yjs CRDT + 冲突检测 |
| 大画布性能 | 节点 > 500 时卡顿 | 中 | 虚拟化 + 分页加载 |
| 数据迁移失败 | 老项目无法使用画布 | 低 | 提供手动修复工具 |

### 9.2 产品风险

| 风险 | 影响 | 概率 | 应对措施 |
|-----|------|------|---------|
| 用户学习成本高 | 用户不使用画布 | 中 | 提供模板 + 引导教程 |
| 画布与现有流程割裂 | 用户困惑 | 中 | 强化数据打通 + 回写机制 |
| 版本能力差异大 | Normal 用户感觉受限 | 低 | 优化 Normal 版向导体验 |

---

## 十、里程碑与交付

### 时间线（总计 12 周）

```
Week 1-2:  Phase 1 基础集成
Week 3-4:  Phase 2 Agent 智能能力
Week 5-7:  Phase 3 工作流执行引擎
Week 8-9:  Phase 4 Tapnow 式交互增强
Week 10-11: Phase 5 协作与评审
Week 12:   Phase 6 版本分层与权限
```

### 关键里程碑

- **M1 (Week 2)**：画布页面可访问，显示节点
- **M2 (Week 4)**：Agent 可分析分镜并分配模块
- **M3 (Week 7)**：完整链路可执行（分镜→图→视频）
- **M4 (Week 9)**：支持模板工作流和结果回写
- **M5 (Week 11)**：支持多人协作和评审
- **M6 (Week 12)**：版本分层完成，全功能上线

---

## 十一、总结

本计划将画布借鉴系统作为**中段可执行工作台**融入现有架构，实现：

✅ **数据打通**：Scene/Shot → Canvas Nodes → 执行结果 → 回写项目
✅ **智能增强**：Claude Agent 自动分析、分配、优化
✅ **执行能力**：完整的图片合成 + 视频生成工作流
✅ **协作增强**：多人画布、评论、评审模式
✅ **渐进开放**：Normal → Canvas → Hidden → Ultimate 分层能力

**核心原则**：
- 画布是增强功能，不破坏现有流程
- 采用 Tapnow 式可执行画布，而非自由白板
- 结果优先于参数，模板优先于空白
- 显式回写，可观察执行，支持局部重跑

**下一步行动**：
1. 评审本计划，确认技术方案
2. 启动 Phase 1 基础集成开发
3. 建立每周进度同步机制

