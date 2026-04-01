# P0 Sprint 拆分

> 阶段: P0
> 时间窗口: 2026-03-25 ~ 2026-04-22

## Sprint 总表

| Sprint | 时间 | 状态 | 目标 |
|--------|------|------|------|
| Sprint 0.1 | 2026-03-25 ~ 2026-04-07 | 已完成 | 三段路由、阶段 Store、后端骨架 API、测试基础设施 |
| Sprint 0.2 | 2026-04-08 ~ 2026-04-22 | 进行中 | 契约门禁、工程收口、阶段对齐文档、P1 迁移准备 |

## Sprint 0.1

### 目标

- 搭起三段产品壳
- 搭起四个阶段 Store
- 搭起四组后端 API skeleton
- 让测试命令真正可跑

### 已完成回填

- `已完成`: 三段路由壳
- `已完成`: `workbenchStore / boardStore / previewStore / pipelineStore`
- `已完成`: `workflow/pipeline / artifacts/writeback / collaboration / preview/export`
- `已完成`: `pytest / vitest / playwright`
- `已完成`: backend、web unit、web e2e 基础验证

### 测试与验证

- backend tests 通过
- web unit 通过
- web e2e 冒烟通过

### 修复重点

- 先修测试环境
- 再修骨架接口和路由问题

## Sprint 0.2

### 目标

- 补契约测试门禁
- 固化阶段执行文档
- 为 P1 迁移和持久化做准备

### 当前状态回填

- `进行中`: 阶段执行文档已建立
- `未开始`: OpenAPI schema snapshot
- `未开始`: 错误码固定与契约回归
- `未开始`: CI 层自动契约门禁

### 测试

- 新增契约测试样板
- 关键错误码用例

### 验证

- 契约快照可生成
- 接口变更能被门禁发现

### 修复重点

- 修文档与实际不一致
- 修接口 schema 漂移
