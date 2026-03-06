# CLAUDE.md

This file provides working guidance for agents operating in this repository.

## Project Overview

虚幻造物（Unreal Make）是一个面向“小说/剧本到影视级短剧”的 AI-Native 创作平台。
当前产品主战略已经确定为：

- 前半段：`Sudowrite` 式创作工作台
- 中段：`Tapnow/TapFlow` 式可执行无限画布工作台，并吸收 `Figma/Miro` 协作优势
- 后半段：`Premiere/CapCut` 式预演与交付工作台

四层用户版本体系：`Normal` → `Canvas` → `Hidden` → `Ultimate`
其中当前规划主版本为 `newplan3.md`，它以 `newplan1.md` 的完整细节为主体，融合 `newplan2.md` 的高层判断。

## Current Canonical Docs

Priority order for product and planning context:

1. `PRD.md`
2. `newplan3.md`
3. `FINAL_ROADMAP.md`
4. `docs/TRI_STAGE_CREATIVE_UX.md`
5. `docs/MIDDLE_STAGE_WORKBENCH_DECISION_REPORT.md`
6. `docs/CANVAS_SYSTEM_DESIGN.md`
7. `docs/WORKFLOW_SCHEMA.md`
8. `docs/CANVAS_API_SPEC.md`

Document roles:

- `newplan3.md`：current integrated master planning document
- `newplan1.md`：detailed historical baseline with full module depth
- `newplan2.md`：high-level transition document that introduced three-stage framing and version-system calibration

## Repository Structure

- `packages/shared/`：共享类型、hooks、组件、store
- `packages/web/`：Next.js Web 应用
- `backend/`：FastAPI 后端
- `docs/`：产品、架构、接口与设计文档
- `知识库/`：提示词、导演分镜、镜头设计相关知识资产

## Commands

```bash
pnpm install
pnpm dev
pnpm dev:web
pnpm dev:backend
pnpm build
pnpm lint
```

Backend local run:

```bash
cd backend
uvicorn main:app --reload --port 8000
```

## Architecture Notes

### Product Form

- The product is not a single workspace.
- It is a three-stage creative system with shared project truth and stage-specific workbenches.
- The middle stage is an executable canvas, not a freeform whiteboard.
- All planning references should now align to `newplan3.md` as the planning baseline.

### Edition System

- `Normal`：entry layer
- `Canvas`：production layer
- `Hidden`：solution layer
- `Ultimate`：internal operating system layer

Edition gating should remain centralized and avoid scattering business checks throughout the codebase.

### Canvas Direction

For any canvas-related implementation, follow these rules:

- template-first
- result-first
- explicit writeback
- progressive unlock
- collaboration enhancement, not whiteboard-first freedom

## Working Rules

- Prefer updating canonical docs when product decisions change.
- Do not treat `newplan1.md` or `newplan2.md` as the current active planning baseline.
- Any middle-stage wording should describe it as `Tapnow/TapFlow`-style executable infinite canvas with `Figma/Miro` collaboration enhancements.
- Avoid reintroducing “Figma/Miro-style middle stage” as the primary description.

## Current Implementation Reality

The codebase is still in an early phase relative to the target blueprint.
Current UI contains workspace shells and edition gating foundations, but does not yet implement the full three-stage production system or a true executable canvas.

When planning or coding, distinguish clearly between:

- current implementation state
- target product blueprint
- phase-specific delivery scope
