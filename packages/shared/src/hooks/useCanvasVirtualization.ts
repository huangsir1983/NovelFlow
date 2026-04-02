'use client';

import { useEffect, useRef, useCallback } from 'react';
import { useCanvasStore } from '../stores/canvasStore';
import { useProjectStore } from '../stores';
import { getSceneBounds } from '../lib/canvasLayout';
import type { SceneGroup, CanvasRenderMode } from '../types';

/** Zoom thresholds for render mode transitions */
const ZOOM_SIMPLIFIED = 0.2;
const ZOOM_COLLAPSED = 0.1;

/** Extra padding (in world pixels) added around viewport for pre-loading adjacent scenes */
const VIEWPORT_PADDING = 800;

/** Debounce interval for viewport change processing (ms) */
const DEBOUNCE_MS = 100;

/**
 * Scene-level virtualization hook.
 *
 * Subscribes to viewport changes and determines:
 * 1. Which scenes are currently visible (within expanded viewport)
 * 2. What render mode to use based on zoom level
 * 3. Scene group metadata (bounds, progress, counts)
 *
 * Updates canvasStore: sceneGroups, visibleSceneIds, renderMode.
 */
export function useCanvasVirtualization() {
  const nodes = useCanvasStore((s) => s.nodes);
  const viewport = useCanvasStore((s) => s.viewport);
  const setSceneGroups = useCanvasStore((s) => s.setSceneGroups);
  const updateVisibleScenes = useCanvasStore((s) => s.updateVisibleScenes);
  const setRenderMode = useCanvasStore((s) => s.setRenderMode);
  const scenes = useProjectStore((s) => s.scenes);

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Build scene groups from current nodes (memoized by scenes identity)
  const buildSceneGroups = useCallback((): SceneGroup[] => {
    if (!scenes.length || !nodes.length) return [];

    return scenes.map((scene) => {
      const bounds = getSceneBounds(scene.id, nodes);
      const sceneNodes = nodes.filter(
        (n) => (n.data as Record<string, unknown>)?.sceneId === scene.id,
      );

      let completedCount = 0;
      let processingCount = 0;
      let errorCount = 0;
      let shotCount = 0;

      for (const n of sceneNodes) {
        const data = n.data as Record<string, unknown>;
        const status = data.status as string;
        const nodeType = data.nodeType as string;

        if (nodeType === 'shot') shotCount++;
        if (status === 'success') completedCount++;
        else if (status === 'running' || status === 'queued') processingCount++;
        else if (status === 'error') errorCount++;
      }

      return {
        sceneId: scene.id,
        heading: scene.heading || `Scene ${scene.order}`,
        order: scene.order,
        nodeIds: sceneNodes.map((n) => n.id),
        bounds: bounds ?? { minX: 0, minY: 0, maxX: 0, maxY: 0 },
        shotCount,
        completedCount,
        processingCount,
        errorCount,
      };
    }).sort((a, b) => a.order - b.order);
  }, [scenes, nodes]);

  // Determine which scenes are visible in the current viewport
  const computeVisibility = useCallback(
    (groups: SceneGroup[], vp: typeof viewport): Set<string> => {
      if (!groups.length) return new Set();

      // Convert viewport to world coordinates
      // React Flow viewport: world_x = (screen_x - vp.x) / vp.zoom
      // So visible world rect:
      //   left   = -vp.x / vp.zoom
      //   top    = -vp.y / vp.zoom
      //   right  = (screenWidth - vp.x) / vp.zoom
      //   bottom = (screenHeight - vp.y) / vp.zoom
      //
      // We approximate screen size — not critical since we add padding
      const screenW = typeof window !== 'undefined' ? window.innerWidth : 1920;
      const screenH = typeof window !== 'undefined' ? window.innerHeight : 1080;

      const worldLeft = -vp.x / vp.zoom - VIEWPORT_PADDING;
      const worldTop = -vp.y / vp.zoom - VIEWPORT_PADDING;
      const worldRight = (screenW - vp.x) / vp.zoom + VIEWPORT_PADDING;
      const worldBottom = (screenH - vp.y) / vp.zoom + VIEWPORT_PADDING;

      const visible = new Set<string>();

      for (const group of groups) {
        const b = group.bounds;
        // AABB overlap test
        if (
          b.maxX >= worldLeft &&
          b.minX <= worldRight &&
          b.maxY >= worldTop &&
          b.minY <= worldBottom
        ) {
          visible.add(group.sceneId);
        }
      }

      // Always include at least some scenes if none are visible
      // (e.g., when all scenes are offscreen, show first few)
      if (visible.size === 0 && groups.length > 0) {
        for (let i = 0; i < Math.min(3, groups.length); i++) {
          visible.add(groups[i].sceneId);
        }
      }

      return visible;
    },
    [],
  );

  // Determine render mode from zoom level
  const getRenderMode = useCallback((zoom: number): CanvasRenderMode => {
    if (zoom < ZOOM_COLLAPSED) return 'collapsed';
    if (zoom < ZOOM_SIMPLIFIED) return 'simplified';
    return 'full';
  }, []);

  // Debounced update on viewport/nodes change
  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);

    timerRef.current = setTimeout(() => {
      const groups = buildSceneGroups();
      setSceneGroups(groups);

      const visible = computeVisibility(groups, viewport);
      updateVisibleScenes(visible);

      const mode = getRenderMode(viewport.zoom);
      setRenderMode(mode);
    }, DEBOUNCE_MS);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [viewport, nodes, scenes, buildSceneGroups, computeVisibility, getRenderMode, setSceneGroups, updateVisibleScenes, setRenderMode]);
}
