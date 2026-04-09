# Canvas Layout Documentation Index

This directory contains comprehensive documentation about the React Flow canvas layout system. Choose your starting point based on your needs.

---

## Documentation Files

### 1. EXECUTIVE_SUMMARY.md - START HERE
For: Quick overview, TL;DR answer
Contains:
- One-sentence summary
- The 5 key constants
- Quick edit guide
- Visual spacing reference
- Common adjustments

When to read: First! Get the big picture in 5 minutes.

---

### 2. QUICK_REFERENCE.md 
For: Implementation and common tasks
Contains:
- Exact file locations and line numbers
- Current constant values
- How to adjust spacing
- Common layout presets
- Testing checklist
- Troubleshooting table

When to read: When you need to make a specific change.

---

### 3. LAYOUT_SPACING_REPORT.md
For: Deep technical understanding
Contains:
- Detailed spacing constants breakdown
- Position calculation logic with examples
- Position cache mechanism
- Dynamic Y calculation walkthrough
- Node type mapping
- Incremental virtualization explanation
- File dependencies

When to read: When you need to understand how it works.

---

### 4. LAYOUT_DIAGRAM.txt
For: Visual learner
Contains:
- ASCII art diagrams
- Horizontal layout visualization
- Vertical layout visualization
- Position cache flow
- Dynamic calculation flow
- Key files reference tree

When to read: When you want to see the layout visually.

---

## Common Tasks

### Make the canvas more compact
1. Read: QUICK_REFERENCE.md - Make Layout More Compact
2. Edit: packages/shared/src/lib/canvasLayout.ts, lines 31-35
3. Test: Reload browser

### Understand position caching
1. Read: LAYOUT_SPACING_REPORT.md - Position Cache
2. Read: LAYOUT_DIAGRAM.txt - Position Cache Mechanism
3. Files: canvasStore.ts lines 48, 157-160

### Adjust horizontal spacing
1. Read: QUICK_REFERENCE.md - Horizontal Spacing
2. Edit: COL_X array in canvasLayout.ts line 31
3. Adjust all values equally to maintain column width

### Adjust vertical spacing within scenes
1. Read: QUICK_REFERENCE.md - Vertical Spacing
2. Edit: SHOT_GAP in canvasLayout.ts line 33
3. Test: Verify shot cards are not overlapping

### Adjust vertical spacing between scenes
1. Read: QUICK_REFERENCE.md - Vertical Spacing
2. Edit: SCENE_PADDING in canvasLayout.ts line 32
3. Test: Verify scenes have proper separation

---

## Single Source of Truth

All layout is controlled by 5 constants in 1 file:

File: packages/shared/src/lib/canvasLayout.ts
Lines: 31-35

const COL_X = [0, 420, 860, 1300, 1740];    // Horizontal
const SCENE_PADDING = 240;                   // Vertical (between scenes)
const SHOT_GAP = 300;                        // Vertical (between shots)
const NODE_WIDTH = 280;                      // Node width
const NODE_HEIGHT = 200;                     // Node height

---

## Related Files

packages/shared/src/
├── lib/
│   └── canvasLayout.ts                    (MAIN LAYOUT FILE)
│       ├── buildCanvasGraph()              (Lines 135-316)
│       └── buildCanvasGraphIncremental()   (Lines 326-417)
│
├── stores/
│   ├── canvasStore.ts                     (POSITION CACHE)
│   │   ├── positionCache                   (Line 48)
│   │   └── cacheNodePosition()             (Lines 157-158)
│   │
│   └── boardStore.ts                      (PRODUCTION STATE)
│
├── hooks/
│   ├── useCanvasSync.ts                   (DATA -> NODES)
│   │   └── useCanvasSync()                 (Lines 17-115)
│   │
│   └── useCanvasVirtualization.ts         (SCENE VIRTUALIZATION)
│
└── components/production/
    ├── ShotProductionBoard.tsx            (CANVAS RENDERER)
    │   └── defaultViewport                 (Line 169)
    │
    └── canvas/
        ├── ShotNode.tsx
        ├── PromptAssemblyNode.tsx
        ├── ImageGenerationNode.tsx
        └── VideoGenerationNode.tsx

---

## Current Default Values

Element                  | Value   | Purpose
Scene node X             | 0       | Always at far left
Shot node X              | 420     | First card column
Prompt node X            | 860     | Second card column
Image node X             | 1300    | Third card column
Video node X             | 1740    | Fourth card column
Shot gap Y               | 300px   | Between shots in scene
Scene gap Y              | 240px   | Between scene groups
Node width               | 280px   | Card width (all types)
Node height              | 200px   | Card height (all types)

---

## Performance & Optimization

Built-in optimizations:
- Scene virtualization: Only visible scenes render
- Position caching: User drags don't recalculate layout
- React Flow culling: Offscreen nodes hidden via onlyRenderVisibleElements
- Incremental builds: buildCanvasGraphIncremental() for large projects

Safe to modify:
- All constants are isolated in one file
- Position cache survives constant changes
- No hardcoded magic numbers elsewhere
- Changes take effect immediately (with browser reload)

---

## If Something Goes Wrong

Problem                      | Solution
Spacing has not changed      | Clear browser cache or do hard refresh
Constants don't exist        | Verify file: canvasLayout.ts
Nodes are in old position    | Restart dev server
Layout looks broken          | Check COL_X array syntax and values
Shots overlapping            | Increase SHOT_GAP value
Scenes overlapping           | Increase SCENE_PADDING value

---

## Frequently Asked Questions

Q: Where are the spacing constants?
A: packages/shared/src/lib/canvasLayout.ts, lines 31-35

Q: Can I make columns have different spacing?
A: Yes! Edit COL_X array. Each value is a separate X position.

Q: Do user-dragged nodes get lost when I change constants?
A: No. Position cache preserves them.

Q: What if I set SHOT_GAP to 100?
A: Shots will be 100px apart. They might overlap if NODE_HEIGHT is 200px!

Q: Is there a UI to adjust spacing?
A: Not built-in. Edit constants in the code file.

Q: How do I test layout changes?
A: 1) Edit constant, 2) Save, 3) Browser reloads, 4) Check canvas.

Q: Can I have different spacing for different scenes?
A: Not without refactoring. Currently all scenes use same constants.

---

Documentation Last Updated: 2026-04-02
Repository: G:\涛项目\claude版\模块二
