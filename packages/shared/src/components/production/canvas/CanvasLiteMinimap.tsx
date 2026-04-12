'use client';

import { useRef, useEffect, useCallback } from 'react';
import { useCanvasStore } from '../../../stores/canvasStore';

/**
 * Lightweight canvas-based minimap.
 *
 * Reads ALL nodes from the zustand store (not the filtered subset passed to ReactFlow),
 * so every scene is always visible in the minimap regardless of virtualization.
 *
 * Performance strategy:
 *  - Node rects are drawn to an offscreen canvas and only redrawn when `nodes` identity changes.
 *  - The viewport indicator is redrawn on every rAF frame (cheap — one strokeRect).
 *  - store.subscribe is used instead of React re-renders — zero React reconciliation cost.
 */

const WIDTH = 180;
const HEIGHT = 110;
const DPR = typeof window !== 'undefined' ? Math.min(window.devicePixelRatio || 1, 2) : 1;

const NODE_COLORS: Record<string, string> = {
  scene: '#00c8ff',
  shot: '#ff9632',
  promptAssembly: '#32c864',
  imageGeneration: '#ffc832',
  videoGeneration: '#c832ff',
  characterProcess: '#ff6eb4',
  imageProcess: '#b4a0ff',
  composite: '#64d8cb',
  sceneBG: '#5ac8fa',
  blendRefine: '#c89664',
  finalHD: '#d85aff',
};
const DEFAULT_COLOR = '#666666';
const BG_COLOR = 'rgba(10,14,24,0.92)';

/** Cached transform from world → minimap pixel space */
interface WorldTransform {
  minX: number;
  minY: number;
  scale: number;
  offX: number;
  offY: number;
}

export function CanvasLiteMinimap() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const offscreenRef = useRef<HTMLCanvasElement | null>(null);
  const transformRef = useRef<WorldTransform | null>(null);
  const prevNodesRef = useRef<unknown>(null);
  const rafRef = useRef<number>(0);

  /** Get the filtered nodes matching what ReactFlow actually renders */
  const getVisibleNodes = useCallback(() => {
    const { nodes, visibleSceneIds, focusedSceneId } = useCanvasStore.getState();
    if (!visibleSceneIds || visibleSceneIds.size === 0) return nodes;
    return nodes.filter((n) => {
      const sceneId = (n.data as Record<string, unknown>)?.sceneId as string | undefined;
      return !sceneId || visibleSceneIds.has(sceneId) || sceneId === focusedSceneId;
    });
  }, []);

  /** Rebuild the offscreen node layer */
  const rebuildNodeLayer = useCallback(() => {
    const nodes = getVisibleNodes();
    if (nodes.length === 0) {
      transformRef.current = null;
      return;
    }

    // Lazy-create offscreen canvas
    if (!offscreenRef.current) {
      offscreenRef.current = document.createElement('canvas');
      offscreenRef.current.width = WIDTH * DPR;
      offscreenRef.current.height = HEIGHT * DPR;
    }
    const oc = offscreenRef.current;
    const ctx = oc.getContext('2d')!;
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);

    // Bounding box
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const n of nodes) {
      const x = n.position.x;
      const y = n.position.y;
      const w = (n.measured?.width ?? n.width ?? 200) as number;
      const h = (n.measured?.height ?? n.height ?? 150) as number;
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x + w > maxX) maxX = x + w;
      if (y + h > maxY) maxY = y + h;
    }
    const pad = 300;
    minX -= pad; minY -= pad; maxX += pad; maxY += pad;
    const worldW = maxX - minX || 1;
    const worldH = maxY - minY || 1;
    const scale = Math.min(WIDTH / worldW, HEIGHT / worldH);
    const offX = (WIDTH - worldW * scale) / 2;
    const offY = (HEIGHT - worldH * scale) / 2;

    transformRef.current = { minX, minY, scale, offX, offY };

    // Clear & draw background
    ctx.clearRect(0, 0, WIDTH, HEIGHT);
    ctx.fillStyle = BG_COLOR;
    ctx.fillRect(0, 0, WIDTH, HEIGHT);

    // Draw node rects
    ctx.globalAlpha = 0.85;
    for (const n of nodes) {
      const x = (n.position.x - minX) * scale + offX;
      const y = (n.position.y - minY) * scale + offY;
      const w = Math.max(2, ((n.measured?.width ?? n.width ?? 200) as number) * scale);
      const h = Math.max(1.5, ((n.measured?.height ?? n.height ?? 150) as number) * scale);
      ctx.fillStyle = NODE_COLORS[n.type || ''] || DEFAULT_COLOR;
      ctx.fillRect(x, y, w, h);
    }
    ctx.globalAlpha = 1;
  }, []);

  /** Composite: blit offscreen node layer + draw viewport rect */
  const compositeFrame = useCallback(() => {
    const cvs = canvasRef.current;
    if (!cvs) return;
    const ctx = cvs.getContext('2d');
    if (!ctx) return;
    const t = transformRef.current;
    const oc = offscreenRef.current;

    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    ctx.clearRect(0, 0, WIDTH, HEIGHT);

    if (!t || !oc) {
      ctx.fillStyle = BG_COLOR;
      ctx.fillRect(0, 0, WIDTH, HEIGHT);
      return;
    }

    // Blit cached node layer
    ctx.drawImage(oc, 0, 0, WIDTH * DPR, HEIGHT * DPR, 0, 0, WIDTH, HEIGHT);

    // Draw viewport indicator
    const { viewport } = useCanvasStore.getState();
    const container = cvs.closest('.relative');
    const containerW = container?.clientWidth ?? 1200;
    const containerH = container?.clientHeight ?? 800;
    const vZoom = viewport.zoom || 0.4;

    const vx = (-viewport.x / vZoom - t.minX) * t.scale + t.offX;
    const vy = (-viewport.y / vZoom - t.minY) * t.scale + t.offY;
    const vw = (containerW / vZoom) * t.scale;
    const vh = (containerH / vZoom) * t.scale;

    ctx.strokeStyle = 'rgba(0,200,255,0.6)';
    ctx.lineWidth = 1.5;
    ctx.strokeRect(vx, vy, vw, vh);
  }, []);

  useEffect(() => {
    let mounted = true;

    let prevVisible: unknown = null;
    const unsub = useCanvasStore.subscribe((state) => {
      if (!mounted) return;

      // Rebuild node layer when nodes or visible scene set changes
      if (state.nodes !== prevNodesRef.current || state.visibleSceneIds !== prevVisible) {
        prevNodesRef.current = state.nodes;
        prevVisible = state.visibleSceneIds;
        rebuildNodeLayer();
      }

      // Always schedule viewport composite (cheap)
      cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(compositeFrame);
    });

    // Initial build
    prevNodesRef.current = useCanvasStore.getState().nodes;
    rebuildNodeLayer();
    rafRef.current = requestAnimationFrame(compositeFrame);

    return () => {
      mounted = false;
      unsub();
      cancelAnimationFrame(rafRef.current);
    };
  }, [rebuildNodeLayer, compositeFrame]);

  return (
    <canvas
      ref={canvasRef}
      width={WIDTH * DPR}
      height={HEIGHT * DPR}
      style={{
        position: 'absolute',
        left: 12,
        bottom: 44,
        width: WIDTH,
        height: HEIGHT,
        borderRadius: 10,
        border: '1px solid rgba(255,255,255,0.1)',
        pointerEvents: 'none',
        zIndex: 55,
      }}
    />
  );
}
