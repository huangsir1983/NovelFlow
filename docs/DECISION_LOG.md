# Decision Log

> Record architectural and design decisions for the UnrealMake（虚幻造物）project.

## Decisions

### DEC-001: Monorepo with pnpm + Turborepo
- **Date**: 2026-03-05
- **Status**: Accepted
- **Context**: Need shared code between web and future desktop app
- **Decision**: Use pnpm workspaces with Turborepo for build orchestration
- **Consequences**: High code sharing, centralized package management

### DEC-002: Dark theme as default
- **Date**: 2026-03-05
- **Status**: Accepted
- **Context**: Creative tool targeting long-session content creators
- **Decision**: Dark mode default, light mode optional
- **Consequences**: All components designed dark-first

### DEC-003: Four-tier edition system
- **Date**: 2026-03-06
- **Status**: Accepted
- **Context**: Different user groups require different complexity envelopes
- **Decision**: Use `Normal` / `Canvas` / `Hidden` / `Ultimate` as user-facing product tiers
- **Consequences**: Feature gating, onboarding, workflow visibility and pricing all align with user maturity

### DEC-004: Three-stage creative workbench
- **Date**: 2026-03-06
- **Status**: Accepted
- **Context**: Writing, orchestration and preview require different cognitive modes
- **Decision**: Adopt a three-stage product form: front-stage writing, middle-stage orchestration, back-stage preview and delivery
- **Consequences**: UI architecture, routing, shared state and milestone planning all follow the three-stage model

### DEC-005: Middle stage uses executable infinite canvas
- **Date**: 2026-03-06
- **Status**: Accepted
- **Context**: The middle stage must support execution, traceability, writeback and review, not just freeform collaboration
- **Decision**: Use `Tapnow/TapFlow`-style executable infinite canvas as the core, and absorb `Figma/Miro` strengths only for collaboration enhancement
- **Consequences**: Template-first workflows, result-first node cards, progressive unlock of advanced graph editing, and review/presence/frame capabilities as an enhancement layer
