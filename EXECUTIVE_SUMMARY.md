# Canvas Layout Control - Executive Summary

## One-Sentence Answer
All React Flow canvas layout is controlled by **5 constants in one file** (`packages/shared/src/lib/canvasLayout.ts`, lines 31-35).

---

## The 5 Constants You Need to Know

```typescript
// File: packages/shared/src/lib/canvasLayout.ts, Lines 31-35

const COL_X = [0, 420, 860, 1300, 1740];    // Horizontal column positions (X coords)
const SCENE_PADDING = 240;                   // Vertical gap between scene groups
const SHOT_GAP = 300;                        // Vertical gap between shots within scene
const NODE_WIDTH = 280;                      // Width of all node cards
const NODE_HEIGHT = 200;                     // Height of all node cards
```

---

## What Each Controls

| Constant | Current Value | Controls | To Change |
|----------|---|----------|-----------|
| `COL_X[0]` | 0 | Scene node X position | N/A (always 0) |
| `COL_X[1]` | 420 | Shot node X position | Adjust all values equally |
| `COL_X[2]` | 860 | Prompt node X position | Adjust all values equally |
| `COL_X[3]` | 1300 | Image node X position | Adjust all values equally |
| `COL_X[4]` | 1740 | Video node X position | Adjust all values equally |
| `SHOT_GAP` | 300 | Distance between shots in same scene (Y) | Direct edit |
| `SCENE_PADDING` | 240 | Distance between scene groups (Y) | Direct edit |
| `NODE_WIDTH` | 280 | Width of Shot/Prompt/Image/Video cards | Direct edit |
| `NODE_HEIGHT` | 200 | Height of all cards | Direct edit |

---

## Visual Overview

```
Horizontal Layout:
Scene(x=0) ─420px─ Shot(x=420) ─440px─ Prompt(x=860) ─440px─ Image(x=1300) ─440px─ Video(x=1740)

Vertical Layout (within one scene):
Shot 1 (y=baseY)
  ↓ 300px (SHOT_GAP)
Shot 2 (y=baseY+300)
  ↓ 300px (SHOT_GAP)
Shot 3 (y=baseY+600)

[Scene ends]
  ↓ 240px (SCENE_PADDING)
[Next scene begins]
```

---

## Quick Edit Guide

### To make columns closer together:
1. Edit line 31 in `canvasLayout.ts`
2. Reduce all numbers in `COL_X` array equally
3. Example: `[0, 350, 750, 1150, 1550]` (50px tighter spacing)

### To make shots closer together:
1. Edit line 33 in `canvasLayout.ts`  
2. Change `SHOT_GAP` value
3. Example: `const SHOT_GAP = 250;` (50px tighter)

### To make scene groups closer together:
1. Edit line 32 in `canvasLayout.ts`
2. Change `SCENE_PADDING` value
3. Example: `const SCENE_PADDING = 180;` (50px tighter)

---

## Key Implementation Details

### Position Calculation Algorithm
```
For each scene:
  baseY = cumulative offset
  
  For each shot in scene:
    shotY = baseY + (shotIndex × SHOT_GAP)
    
    Create 5 nodes all at same Y:
    - Scene:  { x: COL_X[0], y: sceneCenterY }
    - Shot:   { x: COL_X[1], y: shotY }
    - Prompt: { x: COL_X[2], y: shotY }
    - Image:  { x: COL_X[3], y: shotY }
    - Video:  { x: COL_X[4], y: shotY }
  
  Advance for next scene:
    baseY += max(NODE_HEIGHT, shotsHeight) + SCENE_PADDING
```

### Position Persistence (User Drags)
- When user drags a node, position is cached in `canvasStore.positionCache`
- Next rebuild: `position = positionCache[nodeId] ?? calculatedPosition`
- **Result:** User adjustments persist across data updates

---

## Critical Files

| File | Purpose | Key Lines |
|------|---------|-----------|
| `canvasLayout.ts` | **Layout engine** | 31-35 (constants) |
| | | 135-316 (main layout) |
| `canvasStore.ts` | Position caching | 48, 157-160 |
| `useCanvasSync.ts` | Data → nodes conversion | Calls buildCanvasGraph() |
| `ShotProductionBoard.tsx` | Canvas renderer | Line 169 (viewport) |

---

## Visual Spacing Reference

### Horizontal (Fixed Grid)
```
X=0      X=420    X=860    X=1300   X=1740
│        │        │        │        │
Scene    Shot     Prompt   Image    Video
├─420px──┤
         ├─440px──┤
                  ├─440px──┤
                           ├─440px──┤
```

### Vertical (Dynamic, Scene-Relative)
```
Scene 1 Group (baseY=0):
  Shot 1: y=0     ─┐
          y=300   ─┤ SHOT_GAP = 300px
  Shot 2: y=300   ─┤
          y=600   ─┤ SHOT_GAP = 300px
  Shot 3: y=600   ─┘
                    SCENE_PADDING = 240px gap
Scene 2 Group (baseY=1140):
  Shot 1: y=1140  ─┐
          y=1440  ─┤ SHOT_GAP = 300px
  Shot 2: y=1440  ─┤
  ...
```

---

## Example: Adjusting Spacing

### Current (Default)
```typescript
const COL_X = [0, 420, 860, 1300, 1740];
const SCENE_PADDING = 240;
const SHOT_GAP = 300;
```

### Compact Layout (-50px)
```typescript
const COL_X = [0, 370, 810, 1250, 1690];
const SCENE_PADDING = 190;
const SHOT_GAP = 250;
```

### Spacious Layout (+50px)
```typescript
const COL_X = [0, 470, 910, 1350, 1790];
const SCENE_PADDING = 290;
const SHOT_GAP = 350;
```

---

## Node Type → Column Mapping

| Type | Column | X | React Flow Type | Color (MiniMap) |
|------|--------|---|-----------------|-----------------|
| Scene | 0 | 0 | 'scene' | Cyan |
| Shot | 1 | 420 | 'shot' | Orange |
| Prompt | 2 | 860 | 'promptAssembly' | Green |
| Image | 3 | 1300 | 'imageGeneration' | Yellow |
| Video | 4 | 1740 | 'videoGeneration' | Purple |

---

## Performance Notes

✅ **Optimizations in place:**
- Scene virtualization: Only visible scenes render
- Position caching: User drags don't trigger recalculation
- React Flow culling: `onlyRenderVisibleElements` hides offscreen nodes
- Incremental builds: `buildCanvasGraphIncremental()` for large projects

✅ **Changes are safe:**
- Constants are isolated in one file
- Position cache survives constant changes
- No hardcoded values scattered throughout codebase

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Nodes overlapping | Increase `COL_X` spacing or `NODE_WIDTH` |
| Layout too tight | Increase `SHOT_GAP` or `SCENE_PADDING` |
| Layout too loose | Decrease `SHOT_GAP` or `SCENE_PADDING` |
| Initial view zoomed wrong | Edit line 169 of `ShotProductionBoard.tsx`, `defaultViewport` |
| Spacing not changing | Clear browser cache (constants loaded at build time) |
| User drags lost after reload | Check `canvasStore.positionCache` initialization |

---

## Next Steps

1. **To understand the layout:** Read `LAYOUT_DIAGRAM.txt`
2. **For implementation details:** Read `LAYOUT_SPACING_REPORT.md`
3. **For quick edits:** Use `QUICK_REFERENCE.md`
4. **To modify spacing:** Edit constants in `canvasLayout.ts` lines 31-35

---

**Last Updated:** 2026-04-02  
**Author:** Claude Code Analysis  
**Repository:** G:\涛项目\claude版\模块二
