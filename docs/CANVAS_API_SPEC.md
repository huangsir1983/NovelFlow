# 画布系统 API 规格说明

> 版本：2.0
> 日期：2026-03-06
> 目标：为中段可执行无限画布提供完整的工作流、运行、工件、回写、协作接口
> 关联文档：`docs/WORKFLOW_SCHEMA.md`、`docs/CANVAS_SYSTEM_DESIGN.md`

---

## 1. 设计原则

- REST 优先
- 长耗时任务异步执行
- 工作流管理与执行分离
- 工件与回写分离
- 协作评论与分享独立建模
- 所有接口考虑版本门控、权限与审计

---

## 2. 资源列表

核心资源如下：

- `Workflow`
- `WorkflowTemplate`
- `WorkflowRun`
- `NodeRun`
- `NodeArtifact`
- `WriteBackAction`
- `WorkflowComment`
- `WorkflowShare`

---

## 3. 工作流管理 API

### 3.1 创建工作流

- `POST /api/projects/{project_id}/workflows`
- 用途：从上下文或模板创建工作流
- 关键字段：`name`、`template_id`、`context_scope`、`workflow_json`

### 3.2 工作流列表

- `GET /api/projects/{project_id}/workflows`
- 支持：`status`、`template_id`、`scene_id`、`keyword`

### 3.3 获取工作流详情

- `GET /api/projects/{project_id}/workflows/{workflow_id}`

### 3.4 更新工作流

- `PUT /api/projects/{project_id}/workflows/{workflow_id}`
- 用途：自动保存、手动保存、元信息编辑

### 3.5 删除工作流

- `DELETE /api/projects/{project_id}/workflows/{workflow_id}`

### 3.6 从模板快速创建

- `POST /api/projects/{project_id}/workflows/from-template`
- 说明：Phase 1 推荐主入口

---

## 4. 模板 API

### 4.1 模板列表

- `GET /api/workflow-templates`
- 支持：`edition`、`category`、`keyword`

### 4.2 模板详情

- `GET /api/workflow-templates/{template_id}`

### 4.3 推荐模板

- `POST /api/workflow-templates/recommend`
- 输入：`source_type`、`scene_count`、`goal`
- 输出：推荐模板与推荐理由

---

## 5. 工作流执行 API

### 5.1 运行整条工作流

- `POST /api/projects/{project_id}/workflows/{workflow_id}/runs`
- 请求：`mode=full`
- 响应：`workflow_run_id`

### 5.2 运行单节点

- `POST /api/projects/{project_id}/workflows/{workflow_id}/nodes/{node_id}/runs`
- 请求：`mode=single_node`

### 5.3 从节点继续运行

- `POST /api/projects/{project_id}/workflows/{workflow_id}/nodes/{node_id}/forward-run`

### 5.4 查询工作流运行记录

- `GET /api/projects/{project_id}/workflows/{workflow_id}/runs`

### 5.5 查询单次运行详情

- `GET /api/projects/{project_id}/workflow-runs/{run_id}`

---

## 6. 节点结果与工件 API

### 6.1 查询节点最近结果

- `GET /api/projects/{project_id}/workflows/{workflow_id}/nodes/{node_id}/artifacts/latest`

### 6.2 查询节点工件列表

- `GET /api/projects/{project_id}/workflows/{workflow_id}/nodes/{node_id}/artifacts`

### 6.3 获取单个工件

- `GET /api/projects/{project_id}/artifacts/{artifact_id}`

### 6.4 比较两个工件

- `POST /api/projects/{project_id}/artifacts/compare`
- 输入：两个 `artifact_id`

---

## 7. 回写 API

### 7.1 创建回写预览

- `POST /api/projects/{project_id}/writebacks/preview`
- 输入：`artifact_id`、`target_type`、`target_id`、`mode`

### 7.2 确认回写

- `POST /api/projects/{project_id}/writebacks/confirm`

### 7.3 拒绝回写

- `POST /api/projects/{project_id}/writebacks/reject`

### 7.4 查询回写记录

- `GET /api/projects/{project_id}/writebacks`

---

## 8. 协作 API

### 8.1 创建评论

- `POST /api/projects/{project_id}/workflows/{workflow_id}/comments`

### 8.2 查询评论

- `GET /api/projects/{project_id}/workflows/{workflow_id}/comments`
- 支持：`anchor_type`、`anchor_id`、`status`

### 8.3 更新评论状态

- `PATCH /api/projects/{project_id}/workflows/{workflow_id}/comments/{comment_id}`

### 8.4 创建分享链接

- `POST /api/projects/{project_id}/workflows/{workflow_id}/shares`

### 8.5 查询分享设置

- `GET /api/projects/{project_id}/workflows/{workflow_id}/shares/{share_id}`

---

## 9. 前后段联动 API

### 9.1 从前半段创建画布工作流

- `POST /api/projects/{project_id}/frontstage/create-workflow`
- 输入：`chapter_ids`、`scene_ids`、`template_id`

### 9.2 送入预演台

- `POST /api/projects/{project_id}/workflows/{workflow_id}/send-to-preview`
- 输出：`preview_bundle_id`

### 9.3 预演回跳节点

- `GET /api/projects/{project_id}/preview/{preview_bundle_id}/source-node`

---

## 10. Phase 1 必须实现的接口

Phase 1 至少落地：

- 工作流 CRUD
- 模板推荐与模板创建
- 工作流整链运行
- 单节点运行
- 工件列表与最近结果
- 回写预览与确认
- 评论创建与列表
- 送入预演台

---

## 11. 错误处理与审计要求

- 所有运行接口返回稳定 `run_id`
- 所有失败必须能返回 `node_id`、`error_code`、`message`
- 所有回写动作必须写审计日志
- 所有分享与评论动作必须受权限控制

---

## 12. 结论

画布 API 的核心价值不只是“保存节点图”，而是支撑从可执行工作流到结果工件再到业务回写的完整闭环。
