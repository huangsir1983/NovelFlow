# 虚幻造物 (Unreal Make) — 开发指南

> 版本: 6.0 | 日期: 2026-03-06
> 完整PRD: `E:/小说转剧本/软件系统/虚幻造物/PRD.md`
> 开发计划: `E:/小说转剧本/软件系统/虚幻造物/newplan.md`
> 知识库目录: `E:/小说转剧本/软件系统/知识库/`
> 界面设计规范: `E:/小说转剧本/软件系统/界面设计规范/`

---

## 项目概要

AI-Native 全节点可视化影视创作引擎。核心架构：无限节点画布 + Agent Pipeline + Cinema Lab 电影实验室。

**中文名**: 虚幻造物
**英文名**: Unreal Make
**包名**: `@unrealmake/shared`, `@unrealmake/web`

---

## 技术栈

```
前端: React 19 / TypeScript / TailwindCSS v4 + shadcn/ui / Zustand
      TipTap + Yjs / Framer Motion / @xyflow/react v12 (节点画布)
Web:  Next.js 15 / next-intl (i18n, localePrefix: 'as-needed')
桌面: Tauri 2.0 (Phase 5)
后端: Python FastAPI / Anthropic SDK / Celery + Redis
数据: PostgreSQL (Docker Compose, Phase 0 起直接使用)
```

## Monorepo 结构

```
packages/
  shared/   → @unrealmake/shared (95% 共享组件/hooks/types/stores)
  web/      → @unrealmake/web (Next.js)
  desktop/  → Tauri (Phase 5)
backend/    → FastAPI + Agents
```

## 开发规范

- pnpm + Turborepo, `@unrealmake/shared` 引用
- React函数式 + TS strict / Zustand / TailwindCSS + Framer Motion
- `useEdition()` hook 控制版本差异 (Normal/Canvas/Hidden/Ultimate)
- 暗色主题默认, Dark/Light 自动适配
- Git: `main` / `dev` / `feature/Px.x-desc`
- Commit: `feat(module): desc` / `fix(module): desc`
- i18n: next-intl, 中文默认无前缀, 英文 `/en/`

## 关键决策

- MVP先Web, 桌面端Phase 5
- 知识库分层加载 (core/advanced/full)
- 双入口: 小说 + 剧本
- Phase 0 起直接用 PostgreSQL (Docker Compose), 跳过 SQLite
- AIEngine provider 抽象层: anthropic/openai/deepseek 可切换
- 版本门控统一到 middleware 层 (前端 Next.js middleware + 后端 FastAPI Depends)
- 前后端类型安全: OpenAPI → TypeScript codegen (Pydantic → openapi.json → api.generated.ts)
- 资产库 = 跨项目可复用素材系统, 三级scope(公用/自用/项目), 项目引用锁定后成为视觉Prompt强制锚点
- 后期制作(剪辑/调色/音效)交给剪映, 系统输出剪映工程包(Draft)
- AI音乐(Suno/Udio)替代纯标注, 声音叙事→可用音频

## 详细规范

所有详细设计规范(功能模块/节点画布/Agent体系/UI/UX等)请参见:
- **完整PRD**: `E:/小说转剧本/软件系统/虚幻造物/PRD.md`
- **开发计划**: `E:/小说转剧本/软件系统/虚幻造物/newplan.md`
