# Decision Log

> Record architectural and design decisions for the NovelFlow project.

## Template

### DEC-XXX: [Decision Title]
- **Date**: YYYY-MM-DD
- **Status**: Proposed / Accepted / Deprecated / Superseded
- **Context**: Why this decision was needed
- **Decision**: What was decided
- **Alternatives Considered**:
  - Option A: ...
  - Option B: ...
- **Consequences**: Trade-offs and implications
- **Related**: Links to PRD sections, issues, or other decisions

---

## Decisions

### DEC-001: Monorepo with pnpm + Turborepo
- **Date**: 2026-03-05
- **Status**: Accepted
- **Context**: Need shared code between web and future desktop app
- **Decision**: Use pnpm workspaces with Turborepo for build orchestration
- **Consequences**: 95% code sharing between platforms; requires pnpm

### DEC-002: Dark theme as default
- **Date**: 2026-03-05
- **Status**: Accepted
- **Context**: Creative tool targeting content creators
- **Decision**: Dark mode default, light mode available via toggle
- **Consequences**: All components must be designed dark-first

### DEC-003: SQLite for initial development
- **Date**: 2026-03-05
- **Status**: Accepted
- **Context**: Simplify Phase 0 setup, migrate to PostgreSQL later
- **Decision**: Use SQLite via SQLAlchemy (easy swap to PG)
- **Consequences**: No concurrent write concerns for single-dev phase

### DEC-004: Tauri 2.0 for desktop (Phase 5)
- **Date**: 2026-03-05
- **Status**: Accepted
- **Context**: Desktop app needed for offline use
- **Decision**: Tauri 2.0 over Electron (~10MB vs ~150MB)
- **Consequences**: Rust dependency for desktop builds

### DEC-005: Dual entry architecture
- **Date**: 2026-03-05
- **Status**: Accepted
- **Context**: Users may have novels or existing scripts
- **Decision**: Support both novel import and script import entry points
- **Consequences**: Need script adaptation engine for entry B
