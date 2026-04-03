'use client';

import { useCallback } from 'react';
import { useReactFlow } from '@xyflow/react';
import { useCanvasStore } from '../../../stores/canvasStore';

/**
 * Bottom toolbar — horizontal capsule with:
 *  1. MiniMap toggle
 *  2. Grid snap toggle
 *  3. Fit view
 *  4. Zoom slider
 *
 * MiniMap is rendered inside <ReactFlow> and controlled by miniMapOpen state
 * exported from canvasStore.
 */

const MIN_ZOOM = 0.02;
const MAX_ZOOM = 3;

export function CanvasBottomToolbar() {
  const miniMapOpen = useCanvasStore((s) => s.miniMapOpen);
  const toggleMiniMap = useCanvasStore((s) => s.toggleMiniMap);
  const snapToGrid = useCanvasStore((s) => s.snapToGrid);
  const setSnapToGrid = useCanvasStore((s) => s.setSnapToGrid);
  const edgeFlowAnimation = useCanvasStore((s) => s.edgeFlowAnimation);
  const toggleEdgeFlowAnimation = useCanvasStore((s) => s.toggleEdgeFlowAnimation);
  const viewport = useCanvasStore((s) => s.viewport);
  const { fitView, zoomTo } = useReactFlow();

  const handleFitView = useCallback(() => {
    fitView({ padding: 0.12, duration: 300 });
  }, [fitView]);

  const handleZoomChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      zoomTo(parseFloat(e.target.value), { duration: 0 });
    },
    [zoomTo],
  );

  const toggleSnap = useCallback(() => {
    setSnapToGrid(!snapToGrid);
  }, [snapToGrid, setSnapToGrid]);

  const zoomPct = Math.round(viewport.zoom * 100);

  return (
    <div style={{ position: 'absolute', left: 12, bottom: 10, zIndex: 60, pointerEvents: 'auto' }}>
      {/* Capsule toolbar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 1,
        padding: '2px 4px',
        borderRadius: 999,
        backgroundColor: 'rgba(18,22,32,0.95)',
        border: '1px solid rgba(255,255,255,0.08)',
        backdropFilter: 'blur(16px)',
        boxShadow: '0 4px 24px rgba(0,0,0,0.5)',
      }}>
        {/* 1. MiniMap toggle */}
        <ToolBtn
          active={miniMapOpen}
          onClick={toggleMiniMap}
          title={miniMapOpen ? '关闭小地图' : '开启小地图'}
        >
          <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
            <rect x="1" y="3" width="14" height="10" rx="2" stroke="currentColor" strokeWidth="1.3" />
            <rect x="3" y="5" width="4" height="3" rx="0.5" fill="currentColor" opacity="0.5" />
            <rect x="9" y="7" width="4" height="3" rx="0.5" fill="currentColor" opacity="0.3" />
          </svg>
        </ToolBtn>

        <Separator />

        {/* 2. Grid snap toggle */}
        <ToolBtn
          active={snapToGrid}
          onClick={toggleSnap}
          title={snapToGrid ? '关闭网格吸附' : '开启网格吸附'}
        >
          <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
            <path d="M4 1v14M8 1v14M12 1v14M1 4h14M1 8h14M1 12h14" stroke="currentColor" strokeWidth="0.8" opacity="0.6" />
            <circle cx="8" cy="8" r="2" fill="currentColor" opacity="0.7" />
          </svg>
        </ToolBtn>

        <Separator />

        {/* 3. Edge flow animation toggle */}
        <ToolBtn
          active={edgeFlowAnimation}
          onClick={toggleEdgeFlowAnimation}
          title={edgeFlowAnimation ? '关闭流光效果' : '开启流光效果'}
        >
          <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
            <path d="M2 8c2-3 4-3 6 0s4 3 6 0" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" fill="none" />
            <circle cx="11" cy="6.5" r="1.5" fill="currentColor" opacity="0.7" />
          </svg>
        </ToolBtn>

        <Separator />

        {/* 4. Fit view */}
        <ToolBtn onClick={handleFitView} title="自适应视图">
          <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
            <path d="M2 5V3a1 1 0 011-1h2M11 2h2a1 1 0 011 1v2M14 11v2a1 1 0 01-1 1h-2M5 14H3a1 1 0 01-1-1v-2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
            <rect x="5" y="5" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1" opacity="0.4" />
          </svg>
        </ToolBtn>

        <Separator />

        {/* 4. Zoom slider */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '0 4px' }}>
          <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.3)', fontFamily: 'monospace', minWidth: 28, textAlign: 'right' }}>
            {zoomPct}%
          </span>
          <input
            type="range"
            min={MIN_ZOOM}
            max={MAX_ZOOM}
            step={0.01}
            value={viewport.zoom}
            onChange={handleZoomChange}
            style={{
              width: 60,
              height: 4,
              appearance: 'none',
              WebkitAppearance: 'none',
              background: `linear-gradient(to right, rgba(255,255,255,0.35) ${((viewport.zoom - MIN_ZOOM) / (MAX_ZOOM - MIN_ZOOM)) * 100}%, rgba(255,255,255,0.08) ${((viewport.zoom - MIN_ZOOM) / (MAX_ZOOM - MIN_ZOOM)) * 100}%)`,
              borderRadius: 99,
              cursor: 'pointer',
              outline: 'none',
            }}
            title={`缩放 ${zoomPct}%`}
          />
        </div>
      </div>
    </div>
  );
}

/* ── Sub-components ── */

function ToolBtn({
  children,
  onClick,
  active,
  title,
}: {
  children: React.ReactNode;
  onClick: () => void;
  active?: boolean;
  title?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      style={{
        width: 26,
        height: 26,
        borderRadius: '50%',
        border: 'none',
        background: active ? 'rgba(255,255,255,0.1)' : 'transparent',
        color: active ? 'rgba(255,255,255,0.8)' : 'rgba(255,255,255,0.4)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        transition: 'background 0.15s, color 0.15s',
      }}
      onMouseEnter={(e) => {
        if (!active) e.currentTarget.style.background = 'rgba(255,255,255,0.06)';
        e.currentTarget.style.color = 'rgba(255,255,255,0.8)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = active ? 'rgba(255,255,255,0.1)' : 'transparent';
        e.currentTarget.style.color = active ? 'rgba(255,255,255,0.8)' : 'rgba(255,255,255,0.4)';
      }}
    >
      {children}
    </button>
  );
}

function Separator() {
  return (
    <div style={{ width: 1, height: 12, backgroundColor: 'rgba(255,255,255,0.08)', margin: '0 1px' }} />
  );
}
