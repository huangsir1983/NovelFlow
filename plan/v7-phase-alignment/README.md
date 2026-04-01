# v7 分阶段执行对齐包

> 更新日期: 2026-03-26
> 规划基线: `PRD.md` + `newplan3.md`
> 升级实现蓝图: `claude-plan.md`
> 当前目标: 将 v7 融合升级计划拆成可执行、可测试、可验证、可修复的阶段文档

## 1. 使用说明

这套文档用于后续按阶段对齐开发、测试、验收和修复，不替代 `PRD.md` 与 `newplan3.md`，而是把它们转成工程执行视角。

每个阶段文档都固定使用四段闭环：

1. `计划`: 本阶段要交付什么，边界是什么，依赖是什么
2. `测试`: 本阶段要先写什么测试，覆盖哪些主链路和风险点
3. `验证`: 通过什么命令、场景和验收门槛判断阶段完成
4. `修复闭环`: 缺陷怎么进入、怎么修、怎么回归、何时关闭

## 2. 当前仓库实况

截至 2026-03-26，仓库已经有一批 P0/P1 基础骨架落地，可作为后续对齐起点：

- 已新增三段路由壳：`workbench / board / preview`
- 已新增四个阶段 Store：`workbenchStore / boardStore / previewStore / pipelineStore`
- 已新增后端四组骨架 API：`workflow/pipeline`、`artifacts/writeback`、`collaboration`、`preview/export`
- 已补齐基础测试设施：`pytest`、`vitest`、`playwright`
- 已通过基础验证：backend `7 passed`，web vitest `2 passed`，web playwright `1 passed`

这意味着：

- `P0` 不是从零开始，而是从“底座已起、需要补齐标准和门禁”开始
- `P1` 不是先画图，而是尽快把骨架接上真数据和真流程

## 3. 阶段总览

| Phase | 时间窗口 | 目标 | 里程碑 |
|------|----------|------|--------|
| P0 | 2026-03-25 ~ 2026-04-22 | 基线收口 + TDD底座 + 阶段骨架 | 工程底座可持续迭代 |
| P1 | 2026-04-23 ~ 2026-05-20 | 三段架构整合 + 真数据接线 | 三段骨架完成首轮打通 |
| P2 | 2026-05-21 ~ 2026-07-15 | Normal MVP | 5分钟内导入到可审阅分镜 |
| P3 | 2026-07-16 ~ 2026-10-07 | Canvas MVP | 三段闭环 + 画板自由编排 + 预演导出 |
| P4 | 2026-10-08 ~ 2026-12-30 | Hidden | Cinema Lab + 导演体系 + 6 Agent |
| P5 | 2026-12-31 ~ 2027-03-10 | Ultimate 核心能力 | 9 Agent + 全屏 Pipeline + Debug |
| P6 | 2027-03-11 ~ 2027-05-05 | 协作与生态 | 多人协作 + Marketplace + 桌面端/生成管线完善 |
| P7 | 2027-05-06 ~ 2027-06-16 | 商用稳定版 | SLA/安全/压测/灰度回滚达标 |

## 4. 文档列表

- [P0.md](./P0.md)
- [P1.md](./P1.md)
- [P2.md](./P2.md)
- [P3.md](./P3.md)
- [P4.md](./P4.md)
- [P5.md](./P5.md)
- [P6.md](./P6.md)
- [P7.md](./P7.md)

## 4.1 执行状态总览

| Phase | 当前状态 | 代码进度回填 |
|------|----------|--------------|
| P0 | 进行中 | 三段骨架、四个 Store、四组 API skeleton、pytest/vitest/playwright 已落地 |
| P1 | 未开始 | 前置骨架已具备，但真数据接线、持久化、旧页迁移尚未启动 |
| P2 | 未开始 | Normal MVP 路由壳已存在，业务链路尚未接入 |
| P3 | 未开始 | Board/Preview 壳和导出 skeleton 已存在，生产级能力尚未接入 |
| P4 | 未开始 | Hidden 规划清晰，代码尚未进入专业模块实现 |
| P5 | 未开始 | Ultimate 目标明确，代码尚未进入系统层实现 |
| P6 | 未开始 | 协作与生态能力尚未进入开发主线 |
| P7 | 未开始 | 商用稳定治理能力尚未开始工程落地 |

## 4.2 Sprint 文档

- [sprints/README.md](./sprints/README.md)
- [sprints/P0-SPRINTS.md](./sprints/P0-SPRINTS.md)
- [sprints/P1-SPRINTS.md](./sprints/P1-SPRINTS.md)
- [sprints/P2-SPRINTS.md](./sprints/P2-SPRINTS.md)
- [sprints/P3-SPRINTS.md](./sprints/P3-SPRINTS.md)
- [sprints/P4-SPRINTS.md](./sprints/P4-SPRINTS.md)
- [sprints/P5-SPRINTS.md](./sprints/P5-SPRINTS.md)
- [sprints/P6-SPRINTS.md](./sprints/P6-SPRINTS.md)
- [sprints/P7-SPRINTS.md](./sprints/P7-SPRINTS.md)

## 5. 更新规则

后续阶段推进时，建议只更新三类内容：

1. 阶段状态：`未开始 / 进行中 / 风险中 / 已完成`
2. 验证结果：写清楚通过了哪些命令、哪些场景、哪些门槛
3. 修复记录：把 blocker、回归缺陷和未清项补到对应阶段文件里

这样文档能一直维持“计划和实际在同一个地方对齐”的状态。
