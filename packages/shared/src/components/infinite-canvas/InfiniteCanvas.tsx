'use client';

// ══════════════════════════════════════════════════════════════
// InfiniteCanvas.tsx — 无限画布主容器
// Tapnow/TapFlow 式可执行无限画布工作台
// ══════════════════════════════════════════════════════════════

import React, { useRef, useEffect, useCallback, useState } from 'react';
import { useInfiniteCanvasStore } from '../../stores/infiniteCanvasStore';
import { CanvasRenderer } from './CanvasRenderer';
import { ConnectionLayer } from './ConnectionLayer';
import { MiniMap } from './toolbar/MiniMap';
import { Toolbar, type CanvasMode } from './toolbar/Toolbar';
import type { CanvasPoint } from '../../types/canvas';

const ZOOM_SENSITIVITY = 0.001;
const MIN_SCALE = 0.1;
const MAX_SCALE = 3.0;

interface InfiniteCanvasProps {
  onRunBatch?: () => void;
  onRunAgentAssign?: () => void;
}

export const InfiniteCanvas: React.FC<InfiniteCanvasProps> = ({ onRunBatch, onRunAgentAssign }) => {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [mode, setMode] = useState<CanvasMode>('select');

  const view = useInfiniteCanvasStore((s) => s.view);
  const selectedNodeIds = useInfiniteCanvasStore((s) => s.selectedNodeIds);
  const setTransform = useInfiniteCanvasStore((s) => s.setTransform);
  const setZoom = useInfiniteCanvasStore((s) => s.setZoom);
  const panBy = useInfiniteCanvasStore((s) => s.panBy);
  const fitToContent = useInfiniteCanvasStore((s) => s.fitToContent);
  const deselectAll = useInfiniteCanvasStore((s) => s.deselectAll);
  const setVisibleRect = useInfiniteCanvasStore((s) => s.setVisibleRect);

  const { transform } = view;

  const panState = useRef({ active: false, startX: 0, startY: 0, startOX: 0, startOY: 0 });
  const spaceHeld = useRef(false);

  // 更新视口矩形
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const updateRect = () => {
      setVisibleRect({ x: 0, y: 0, width: el.clientWidth, height: el.clientHeight });
    };
    updateRect();
    const ro = new ResizeObserver(updateRect);
    ro.observe(el);
    return () => ro.disconnect();
  }, [setVisibleRect]);

  // 键盘快捷键
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.code === 'Space') spaceHeld.current = true;
      if (e.key === 'Escape') deselectAll();
      if ((e.metaKey || e.ctrlKey) && e.key === '0') fitToContent();
      if ((e.metaKey || e.ctrlKey) && e.key === '=') setZoom(Math.min(MAX_SCALE, transform.scale * 1.2));
      if ((e.metaKey || e.ctrlKey) && e.key === '-') setZoom(Math.max(MIN_SCALE, transform.scale * 0.8));
    };
    const onKeyUp = (e: KeyboardEvent) => {
      if (e.code === 'Space') spaceHeld.current = false;
    };
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keyup', onKeyUp);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('keyup', onKeyUp);
    };
  }, [transform.scale, fitToContent, deselectAll, setZoom]);

  // 滚轮缩放
  const onWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    if (e.ctrlKey || e.metaKey) {
      const delta = -e.deltaY * ZOOM_SENSITIVITY;
      const newScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, transform.scale * (1 + delta)));
      const rect = wrapRef.current!.getBoundingClientRect();
      const pivot: CanvasPoint = { x: e.clientX - rect.left, y: e.clientY - rect.top };
      setZoom(newScale, pivot);
    } else {
      panBy(-e.deltaX, -e.deltaY);
    }
  }, [transform.scale, setZoom, panBy]);

  // 鼠标平移
  const onMouseDown = useCallback((e: React.MouseEvent) => {
    const isPanMode = mode === 'pan' || spaceHeld.current;
    if (isPanMode || e.button === 1) {
      panState.current = {
        active: true, startX: e.clientX, startY: e.clientY,
        startOX: transform.offsetX, startOY: transform.offsetY,
      };
      e.preventDefault();
    }
  }, [mode, transform]);

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (!panState.current.active) return;
    const { startX, startY, startOX, startOY } = panState.current;
    setTransform({
      ...transform,
      offsetX: startOX + e.clientX - startX,
      offsetY: startOY + e.clientY - startY,
    });
  }, [transform, setTransform]);

  const onMouseUp = useCallback(() => {
    panState.current.active = false;
  }, []);

  const onBackgroundClick = useCallback((e: React.MouseEvent) => {
    if (e.target === e.currentTarget) deselectAll();
  }, [deselectAll]);

  const cursor = (mode === 'pan' || spaceHeld.current)
    ? (panState.current.active ? 'grabbing' : 'grab')
    : 'default';

  const canvasStyle: React.CSSProperties = {
    transform: `translate(${transform.offsetX}px, ${transform.offsetY}px) scale(${transform.scale})`,
    transformOrigin: '0 0',
    position: 'absolute',
    willChange: 'transform',
  };

  const nodeCount = useInfiniteCanvasStore((s) => s.nodes.size);

  return (
    <div style={{ display: 'flex', width: '100%', height: '100%', background: '#0a0a1a' }}>
      {/* 主画布区域 */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {/* 顶部工具栏 */}
        <Toolbar mode={mode} onModeChange={setMode} onRunBatch={onRunBatch} onRunAgentAssign={onRunAgentAssign} />

        {/* 画布容器 */}
        <div
          ref={wrapRef}
          style={{ position: 'absolute', inset: 0, cursor, userSelect: 'none' }}
          onWheel={onWheel}
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
          onMouseLeave={onMouseUp}
          onClick={onBackgroundClick}
        >
          {/* 网格背景 */}
          <GridBackground transform={transform} />

          {/* 连线层 */}
          <ConnectionLayer />

          {/* 主画布变换层 */}
          <div style={canvasStyle}>
            <CanvasRenderer />
          </div>
        </div>

        {/* 小地图 */}
        <MiniMap style={{ position: 'absolute', bottom: 16, left: 16 }} />

        {/* 状态栏 */}
        <div style={{
          position: 'absolute', bottom: 16, left: '50%', transform: 'translateX(-50%)',
          background: '#12122a', border: '0.5px solid rgba(255,255,255,0.08)',
          borderRadius: 8, padding: '4px 14px', fontSize: 12,
          color: 'rgba(255,255,255,0.5)', display: 'flex', gap: 12, alignItems: 'center',
          pointerEvents: 'none',
        }}>
          <span>{Math.round(transform.scale * 100)}%</span>
          <span style={{ opacity: 0.4 }}>·</span>
          <span>{nodeCount} 节点</span>
          {selectedNodeIds.size > 0 && (
            <>
              <span style={{ opacity: 0.4 }}>·</span>
              <span style={{ color: '#6366f1' }}>已选 {selectedNodeIds.size}</span>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

// ── 网格背景 ──

const GridBackground: React.FC<{ transform: { scale: number; offsetX: number; offsetY: number } }> = ({ transform }) => {
  const gridSize = 40 * transform.scale;
  const offsetX = transform.offsetX % gridSize;
  const offsetY = transform.offsetY % gridSize;

  return (
    <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}>
      <defs>
        <pattern id="grid-dot" x={offsetX} y={offsetY} width={gridSize} height={gridSize} patternUnits="userSpaceOnUse">
          <circle cx={0} cy={0} r={1} fill="rgba(255,255,255,0.06)" opacity={0.8} />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#grid-dot)" />
    </svg>
  );
};
