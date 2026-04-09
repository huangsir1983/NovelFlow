# Canvas Layout - Quick Reference Guide

## TL;DR - Spacing Constants

All spacing constants are in **one file**: 
📍 `packages/shared/src/lib/canvasLayout.ts` (lines 31-35)

```typescript
const COL_X = [0, 420, 860, 1300, 1740];    // Horizontal positions
const SCENE_PADDING = 240;                   // Gap between scene rows
const SHOT_GAP = 300;                        // Gap between shots in scene
const NODE_WIDTH = 280;                      // Card width
const NODE_HEIGHT = 200;                     // Card height
```

---

## Horizontal Spacing (Between Columns)

| From | To | Distance | Notes |
|------|----|-----------|----|
| Scene (x=0) | Shot (x=420) | **420px** | First gap, largest |
| Shot (x=420) | Prompt (x=860) | **440px** | More compact |
| Prompt (x=860) | Image (x=1300) | **440px** | More compact |
| Image (x=1300) | Video (x=1740) | **440px** | More compact |

**To adjust:** Edit `COL_X` array
```typescript
// Current
const COL_X = [0, 420, 860, 1300, 1740];

// Make more compact (reduce by 50px per gap)
const COL_X = [0, 370, 810, 1250, 1690];

// Make more spacious (add 50px per gap)
const COL_X = [0, 470, 910, 1350, 1790];
```

---

## Vertical Spacing (Between Rows)

### Within a Scene Row
- **Between shots in same scene:** `SHOT_GAP = 300px`
- **Example:** Shot 1 (y=0), Shot 2 (y=300), Shot 3 (y=600)

**To adjust:** Edit `SHOT_GAP`
```typescript
// Current
const SHOT_GAP = 300;

// More compact
const SHOT_GAP = 250;

// More spacious
const SHOT_GAP = 350;
```

### Between Scene Groups
- **Gap after all shots of scene, before next scene:** `SCENE_PADDING = 240px`
- **Formula:** `currentY += Math.max(NODE_HEIGHT, shotsHeight) + SCENE_PADDING`

**To adjust:** Edit `SCENE_PADDING`
```typescript
// Current
const SCENE_PADDING = 240;

// More compact
const SCENE_PADDING = 180;

// More spacious  
const SCENE_PADDING = 300;
```

---

## Position Calculation Logic

### Shot Y Position (within a scene)
```typescript
baseY = currentY (starting position of scene group)
shotY = baseY + shotIndex * SHOT_GAP

// Example with SHOT_GAP=300:
// Shot 0: y = baseY + 0*300 = baseY
// Shot 1: y = baseY + 1*300 = baseY + 300
// Shot 2: y = baseY + 2*300 = baseY + 600
```

### Scene Y Position (centered vertically over shots)
```typescript
shotsGroupHeight = Math.max(0, sceneShots.length - 1) * SHOT_GAP
sceneCenterY = baseY + shotsGroupHeight / 2

// Example with 3 shots, SHOT_GAP=300:
// shotsGroupHeight = (3-1)*300 = 600
// sceneCenterY = baseY + 600/2 = baseY + 300
```

### Next Scene Y Offset
```typescript
shotsHeight = Math.max(1, sceneShots.length) * SHOT_GAP
currentY += Math.max(NODE_HEIGHT, shotsHeight) + SCENE_PADDING

// Example with 3 shots, SHOT_GAP=300, SCENE_PADDING=240, NODE_HEIGHT=200:
// shotsHeight = 3*300 = 900
// currentY += max(200, 900) + 240 = 1140
```

---

## Node Types → Column Mapping

| Node Type | Column # | X Coord | React Flow Type |
|-----------|----------|--------|-----------------|
| Scene | 0 | 0 | `'scene'` |
| Shot | 1 | 420 | `'shot'` |
| Prompt Assembly | 2 | 860 | `'promptAssembly'` |
| Image Generation | 3 | 1300 | `'imageGeneration'` |
| Video Generation | 4 | 1740 | `'videoGeneration'` |

Each node also has a **Y coordinate** that's calculated based on:
- Its scene's base Y
- Its shot's index within that scene
- The `SHOT_GAP` multiplier

---

## Key Functions

### Main Layout Builder
📍 **`buildCanvasGraph(scenes, shots, options)`**
- File: `packages/shared/src/lib/canvasLayout.ts`, lines 135-316
- What it does: Converts scene/shot data into React Flow nodes + edges
- Returns: `{ nodes: Node[], edges: Edge[] }`

### Optimized for Large Projects
📍 **`buildCanvasGraphIncremental(scenes, shots, visibleSceneIds, existingNodes, options)`**
- File: `packages/shared/src/lib/canvasLayout.ts`, lines 326-417
- What it does: Only builds visible scenes, preserves offscreen positions
- Used by: Scene-level virtualization hook

### Position Caching (User Drags)
📍 **`useCanvasStore.cacheNodePosition(nodeId, x, y)`**
- File: `packages/shared/src/stores/canvasStore.ts`, lines 157-158
- What it does: Saves user-dragged position so it persists across rebuilds
- Position lookup: `position: positionCache[nodeId] ?? calculatedPosition`

---

## Where to Make Changes

### 1. Change Horizontal Spacing Between Columns
```
File: packages/shared/src/lib/canvasLayout.ts
Line: 31
Edit: const COL_X = [0, 420, 860, 1300, 1740];
```

### 2. Change Vertical Gap Between Shots
```
File: packages/shared/src/lib/canvasLayout.ts
Line: 33
Edit: const SHOT_GAP = 300;
```

### 3. Change Vertical Gap Between Scene Groups
```
File: packages/shared/src/lib/canvasLayout.ts
Line: 32
Edit: const SCENE_PADDING = 240;
```

### 4. Change Node Dimensions
```
File: packages/shared/src/lib/canvasLayout.ts
Lines: 34-35
Edit: const NODE_WIDTH = 280;
      const NODE_HEIGHT = 200;
```

### 5. Change Initial Canvas Zoom/Pan
```
File: packages/shared/src/components/production/ShotProductionBoard.tsx
Line: 169
Edit: defaultViewport={{ x: 50, y: 50, zoom: 0.4 }}
```

---

## Common Adjustments

### Make Layout More Compact
```typescript
const COL_X = [0, 350, 750, 1150, 1550];  // 350px gaps instead of 420-440
const SCENE_PADDING = 180;                 // Reduced from 240
const SHOT_GAP = 250;                      // Reduced from 300
```

### Make Layout More Spacious
```typescript
const COL_X = [0, 500, 1000, 1500, 2000]; // 500px gaps
const SCENE_PADDING = 300;                 // Increased from 240
const SHOT_GAP = 350;                      // Increased from 300
```

### Optimize for Wider Screens
```typescript
const COL_X = [0, 480, 1020, 1560, 2100]; // More horizontal space
```

### Optimize for Taller Screens
```typescript
const SHOT_GAP = 400;      // More vertical breathing room
const SCENE_PADDING = 300; // More separation between scenes
```

---

## Testing Your Changes

1. Edit the constant in `canvasLayout.ts`
2. The app rebuilds automatically (dev mode)
3. Canvas redraws with new spacing
4. **Position cache is preserved** → User drags still work after reload

---

## Performance Considerations

- **Virtualization enabled:** Only visible scenes render (set via `useCanvasVirtualization`)
- **Position caching:** Prevents layout recalculation on every drag
- **React Flow optimizations:** `onlyRenderVisibleElements` culls offscreen nodes
- **Change detection:** Only rebuilds when domain data changes, not on UI interaction

---

## Related Files

```
packages/shared/src/
├── lib/
│   └── canvasLayout.ts              ◄── LAYOUT ENGINE (main file)
├── stores/
│   ├── canvasStore.ts               ◄── Position cache storage
│   └── boardStore.ts                ◄── Production state
├── hooks/
│   ├── useCanvasSync.ts             ◄── Syncs data → nodes
│   └── useCanvasVirtualization.ts   ◄── Scene virtualization
└── components/production/
    ├── ShotProductionBoard.tsx       ◄── Canvas renderer
    └── canvas/
        ├── ShotNode.tsx             ◄── Shot card component
        ├── PromptAssemblyNode.tsx   ◄── Prompt card component
        ├── ImageGenerationNode.tsx  ◄── Image card component
        └── VideoGenerationNode.tsx  ◄── Video card component
```

