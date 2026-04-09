# React Flow Canvas Layout & Positioning Report

## Overview
The canvas layout is controlled by a column-based grid system that positions nodes for the production workflow. Each scene has 5 columns representing stages: Scene → Shot → Prompt → Image → Video.

---

## Key Layout Constants

**File:** `packages/shared/src/lib/canvasLayout.ts` (Lines 31-35)

### Column Positions (Horizontal Spacing)
```typescript
const COL_X = [0, 420, 860, 1300, 1740];
```

**Column Layout:**
- **Col 0 (x=0):** Scene Node
- **Col 1 (x=420):** Shot Node(s) — **420px horizontal gap from Scene**
- **Col 2 (x=860):** Prompt Assembly Node(s) — **440px gap from Shot**
- **Col 3 (x=1300):** Image Generation Node(s) — **440px gap from Prompt**
- **Col 4 (x=1740):** Video Generation Node(s) — **440px gap from Image**

**Summary:** Shot, Prompt, Image, Video cards are spaced ~420-440px apart horizontally.

---

### Vertical Spacing Constants

| Constant | Value | Purpose | Lines |
|----------|-------|---------|-------|
| `SHOT_GAP` | 300px | Vertical gap between shots within a scene | 33 |
| `SCENE_PADDING` | 240px | Vertical padding between scene groups | 32 |
| `NODE_WIDTH` | 280px | Width of all nodes | 34 |
| `NODE_HEIGHT` | 200px | Height of all nodes | 35 |

**Vertical Spacing Breakdown:**
- **Between shots in same scene:** 300px (SHOT_GAP)
- **Between scene groups:** 240px (SCENE_PADDING)
- **Total vertical space per scene:** `Math.max(NODE_HEIGHT, shotsHeight) + SCENE_PADDING`
  - Where `shotsHeight = max(1, sceneShots.length) * SHOT_GAP`

---

## Position Calculation Logic

### Main Layout Function
**`buildCanvasGraph(scenes, shots, options)`** (Lines 135-316)

#### Algorithm:
1. **Iterate through scenes** sorted by `order` (line 145)
2. **Track cumulative Y offset:** `currentY` starts at 0 and grows for each scene
3. **For each scene:**
   - Calculate **scene center Y** relative to its shots' vertical span (lines 166-167)
   - Create scene node at position: `{ x: COL_X[0], y: sceneCenterY }`
   
4. **For each shot in the scene:**
   - Calculate shot Y: `shotY = baseY + shotIndex * SHOT_GAP` (line 198)
   - Create 4 nodes all at the same Y:
     - Shot node: `{ x: COL_X[1], y: shotY }`
     - Prompt node: `{ x: COL_X[2], y: shotY }`
     - Image node: `{ x: COL_X[3], y: shotY }`
     - Video node: `{ x: COL_X[4], y: shotY }`

5. **Advance to next scene:**
   ```typescript
   const shotsHeight = Math.max(1, sceneShots.length) * SHOT_GAP;
   currentY += Math.max(NODE_HEIGHT, shotsHeight) + SCENE_PADDING;
   ```
   (Lines 311-312)

---

## Position Cache (Persistent User Drags)

**File:** `packages/shared/src/stores/canvasStore.ts` (Lines 48, 157-160)

When a user drags a node, its position is cached:
```typescript
positionCache: Record<string, { x: number; y: number }>;

cacheNodePosition: (nodeId, x, y) =>
  set((s) => ({ positionCache: { ...s.positionCache, [nodeId]: { x, y } } }));
```

**Position lookup in graph builder (Line 175, 216, 241, 261, 285):**
```typescript
position: positionCache[nodeId] ?? { x: COL_X[column], y: calculatedY }
```

If a node ID exists in the cache, its cached position is used. Otherwise, the calculated position is applied. This preserves user-made adjustments across canvas rebuilds.

---

## Dynamic Y Calculation Example

**Scenario:** 2 scenes with 3 shots each

```
Scene 1 (order: 0)
├── baseY = 0
├── Shot 1: y = 0 + (0 * 300) = 0
├── Shot 2: y = 0 + (1 * 300) = 300
├── Shot 3: y = 0 + (2 * 300) = 600
└── Scene node centered: y = (600 - 0) / 2 = 300

[Scene 1 advancement]
shotsHeight = 3 * 300 = 900
currentY = max(200, 900) + 240 = 1140

Scene 2 (order: 1)
├── baseY = 1140
├── Shot 1: y = 1140 + (0 * 300) = 1140
├── Shot 2: y = 1140 + (1 * 300) = 1440
├── Shot 3: y = 1140 + (2 * 300) = 1740
└── Scene node centered: y = 1140 + 300 = 1440
```

---

## Node Type Mapping

Each node type is positioned horizontally at its designated column:

| Node Type | Column | X Position | Associated Color (MiniMap) |
|-----------|--------|------------|----------------------------|
| Scene | 0 | 0 | Cyan (0,200,255) |
| Shot | 1 | 420 | Orange (255,150,50) |
| Prompt Assembly | 2 | 860 | Green (50,200,100) |
| Image Generation | 3 | 1300 | Yellow (255,200,50) |
| Video Generation | 4 | 1740 | Purple (200,50,255) |

---

## Files Involved

| File | Purpose | Key Functions |
|------|---------|----------------|
| `packages/shared/src/lib/canvasLayout.ts` | **Main layout engine** | `buildCanvasGraph()`, `buildCanvasGraphIncremental()`, position calculations |
| `packages/shared/src/stores/canvasStore.ts` | **Canvas state store** | Position caching, node/edge management |
| `packages/shared/src/stores/boardStore.ts` | **Production state store** | Shot artifacts, node runs, production specs |
| `packages/shared/src/hooks/useCanvasSync.ts` | **Syncs domain → React Flow** | Converts scene/shot data to graph structure |
| `packages/shared/src/components/production/ShotProductionBoard.tsx` | **Canvas renderer** | ReactFlow wrapper, panel management |

---

## Incremental Virtualization

**File:** `packages/shared/src/lib/canvasLayout.ts` (Lines 326-417)

For large projects with many scenes, the `buildCanvasGraphIncremental()` function:
- Only rebuilds visible scenes
- Retains offscreen scene nodes (preserving positions, hidden by React Flow's `onlyRenderVisibleElements`)
- Uses the same position calculation logic

---

## Modifying Spacing

To adjust horizontal or vertical spacing:

1. **Change horizontal gaps (between columns):**
   - Edit `COL_X` array in `canvasLayout.ts` line 31
   - Example: `COL_X = [0, 450, 900, 1350, 1800]` increases gaps by 30px

2. **Change vertical gaps (between shots):**
   - Edit `SHOT_GAP` in line 33
   - Example: `const SHOT_GAP = 350` increases gap to 350px

3. **Change scene group padding:**
   - Edit `SCENE_PADDING` in line 32
   - Example: `const SCENE_PADDING = 300` increases between-scene gap to 300px

4. **Change node dimensions:**
   - Edit `NODE_WIDTH` (line 34) and `NODE_HEIGHT` (line 35)
   - Note: This affects bounding box calculations but not position calculations

---

## Summary Table

| Element | Value | Type | Impact |
|---------|-------|------|--------|
| Horizontal spacing (Scene to Shot) | 420px | Column position | Scene → Shot gap |
| Horizontal spacing (Shot to Prompt) | 440px | Column position | Shot → Prompt gap |
| Horizontal spacing (Prompt to Image) | 440px | Column position | Prompt → Image gap |
| Horizontal spacing (Image to Video) | 440px | Column position | Image → Video gap |
| **Vertical spacing (shots in row)** | **300px** | SHOT_GAP | Between shots in same scene |
| **Vertical spacing (scene rows)** | **240px** | SCENE_PADDING | Between scene groups |
| Node width | 280px | NODE_WIDTH | Card width (all types) |
| Node height | 200px | NODE_HEIGHT | Card height (all types) |

