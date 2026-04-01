// ============================================================
// CanvasRenderer.tsx - 虚拟化节点渲染器（懒加载）
// ============================================================
import React, { useMemo } from 'react';
import { useCanvasStore } from '../../store/canvasStore';
import { StoryboardNode } from '../Nodes/StoryboardNode';
import { ImageNode } from '../Nodes/ImageNode';
import { VideoNode } from '../Nodes/VideoNode';
import { NodeData } from '../../types';

export const CanvasRenderer: React.FC = () => {
  const { getVisibleNodes, view } = useCanvasStore();
  const { transform } = view;

  // 只渲染视口内（+缓冲区）的节点
  const visibleNodes = useMemo(() => {
    return getVisibleNodes();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [transform.offsetX, transform.offsetY, transform.scale, getVisibleNodes]);

  return (
    <>
      {visibleNodes.map(node => (
        <NodeWrapper key={node.id} node={node} />
      ))}
    </>
  );
};

const NodeWrapper: React.FC<{ node: NodeData }> = ({ node }) => {
  const style: React.CSSProperties = {
    position: 'absolute',
    left: node.position.x,
    top: node.position.y,
    width: node.size.width,
  };

  return (
    <div style={style}>
      {node.type === 'storyboard' && <StoryboardNode node={node} />}
      {node.type === 'image' && <ImageNode node={node} />}
      {node.type === 'video' && <VideoNode node={node} />}
    </div>
  );
};


// ============================================================
// ConnectionLayer.tsx - SVG 贝塞尔曲线连线层
// ============================================================
import React, { useMemo } from 'react';
import { useCanvasStore } from '../../store/canvasStore';
import { NodeData, Connection } from '../../types';

const STATUS_COLORS: Record<string, string> = {
  done: '#1D9E75',
  processing: '#BA7517',
  pending: '#888780',
  ready: '#378ADD',
  outdated: '#D85A30',
  error: '#E24B4A',
  idle: '#B4B2A9',
};

export const ConnectionLayer: React.FC = () => {
  const { connections, nodes, view } = useCanvasStore();
  const { transform } = view;
  const { scale, offsetX, offsetY } = transform;

  // 计算连线坐标（世界坐标 → 屏幕坐标）
  const renderedConnections = useMemo(() => {
    return connections.map(conn => {
      const fromNode = nodes.get(conn.fromNodeId);
      const toNode = nodes.get(conn.toNodeId);
      if (!fromNode || !toNode) return null;

      // 出口：from节点右侧中心
      const ax = (fromNode.position.x + fromNode.size.width) * scale + offsetX;
      const ay = (fromNode.position.y + fromNode.size.height * 0.5) * scale + offsetY;

      // 入口：to节点左侧中心
      const bx = toNode.position.x * scale + offsetX;
      const by = (toNode.position.y + toNode.size.height * 0.5) * scale + offsetY;

      // 贝塞尔控制点
      const mx = (ax + bx) / 2;

      // 连线颜色根据from节点状态
      const color = STATUS_COLORS[fromNode.status] || '#B4B2A9';

      return { id: conn.id, ax, ay, bx, by, mx, color, fromStatus: fromNode.status };
    }).filter(Boolean);
  }, [connections, nodes, scale, offsetX, offsetY]);

  return (
    <svg
      style={{
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        overflow: 'visible',
        zIndex: 0,
      }}
    >
      <defs>
        {Object.entries(STATUS_COLORS).map(([status, color]) => (
          <marker
            key={status}
            id={`arrow-${status}`}
            viewBox="0 0 10 10"
            refX="8"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path
              d="M2 1L8 5L2 9"
              fill="none"
              stroke={color}
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </marker>
        ))}
      </defs>

      {renderedConnections.map(conn => conn && (
        <path
          key={conn.id}
          d={`M${conn.ax},${conn.ay} C${conn.mx},${conn.ay} ${conn.mx},${conn.by} ${conn.bx},${conn.by}`}
          fill="none"
          stroke={conn.color}
          strokeWidth={1.5}
          strokeOpacity={conn.fromStatus === 'done' ? 0.8 : 0.4}
          strokeDasharray={conn.fromStatus === 'pending' ? '5 4' : undefined}
          markerEnd={`url(#arrow-${conn.fromStatus})`}
        />
      ))}
    </svg>
  );
};


// ============================================================
// MiniMap.tsx - 小地图
// ============================================================
import React, { useRef, useEffect, useCallback } from 'react';
import { useCanvasStore } from '../../store/canvasStore';

const MM_WIDTH = 160;
const MM_HEIGHT = 100;
const WORLD_W = 3000;
const WORLD_H = 2000;
const scaleX = MM_WIDTH / WORLD_W;
const scaleY = MM_HEIGHT / WORLD_H;

const STATUS_COLORS_MM: Record<string, string> = {
  done: '#1D9E75',
  processing: '#BA7517',
  pending: '#B4B2A9',
  ready: '#378ADD',
  outdated: '#D85A30',
  error: '#E24B4A',
  idle: '#D3D1C7',
};

interface MiniMapProps {
  style?: React.CSSProperties;
}

export const MiniMap: React.FC<MiniMapProps> = ({ style }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { nodes, modules, view, setTransform } = useCanvasStore();
  const { transform, visibleRect } = view;

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, MM_WIDTH, MM_HEIGHT);

    // 模块区域
    modules.forEach(mod => {
      ctx.fillStyle = mod.color + '22';
      ctx.strokeStyle = mod.color + '88';
      ctx.lineWidth = 0.5;
      ctx.beginPath();
      ctx.roundRect(mod.position.x * scaleX, mod.position.y * scaleY, mod.size.width * scaleX, mod.size.height * scaleY, 2);
      ctx.fill();
      ctx.stroke();
    });

    // 节点
    nodes.forEach(node => {
      const color = STATUS_COLORS_MM[node.status] || '#D3D1C7';
      ctx.fillStyle = color + 'CC';
      ctx.fillRect(
        node.position.x * scaleX,
        node.position.y * scaleY,
        Math.max(2, node.size.width * scaleX),
        Math.max(2, node.size.height * scaleY)
      );
    });

    // 视口框
    const vpX = (-transform.offsetX / transform.scale) * scaleX;
    const vpY = (-transform.offsetY / transform.scale) * scaleY;
    const vpW = (visibleRect.width / transform.scale) * scaleX;
    const vpH = (visibleRect.height / transform.scale) * scaleY;

    ctx.strokeStyle = '#3B8BD4';
    ctx.lineWidth = 1.5;
    ctx.strokeRect(vpX, vpY, vpW, vpH);
    ctx.fillStyle = 'rgba(59,139,212,0.05)';
    ctx.fillRect(vpX, vpY, vpW, vpH);
  }, [nodes, modules, transform, visibleRect]);

  useEffect(() => {
    draw();
  }, [draw]);

  // 点击小地图跳转
  const onClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current!.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    const worldX = mx / scaleX;
    const worldY = my / scaleY;

    setTransform({
      ...transform,
      offsetX: -(worldX * transform.scale) + visibleRect.width / 2,
      offsetY: -(worldY * transform.scale) + visibleRect.height / 2,
    });
  }, [transform, visibleRect, setTransform]);

  return (
    <div style={{
      width: MM_WIDTH,
      height: MM_HEIGHT,
      background: 'var(--color-background-primary)',
      border: '0.5px solid var(--color-border-tertiary)',
      borderRadius: 8,
      overflow: 'hidden',
      ...style,
    }}>
      <canvas
        ref={canvasRef}
        width={MM_WIDTH}
        height={MM_HEIGHT}
        onClick={onClick}
        style={{ cursor: 'pointer', display: 'block' }}
      />
    </div>
  );
};


// ============================================================
// Toolbar.tsx - 工具栏
// ============================================================
import React from 'react';
import { useCanvasStore } from '../../store/canvasStore';
import { useWorkflow } from '../../hooks/useWorkflow';

type CanvasMode = 'select' | 'pan';

interface ToolbarProps {
  mode: CanvasMode;
  onModeChange: (mode: CanvasMode) => void;
}

export const Toolbar: React.FC<ToolbarProps> = ({ mode, onModeChange }) => {
  const { fitToContent, toggleCollapseAll, isRunning, nodes } = useCanvasStore();
  const { runBatch, runAgentAssign } = useWorkflow();

  const pendingCount = Array.from(nodes.values())
    .filter(n => n.status === 'ready' || n.status === 'outdated').length;

  return (
    <div style={{
      position: 'absolute',
      top: 12,
      left: '50%',
      transform: 'translateX(-50%)',
      zIndex: 50,
      display: 'flex',
      gap: 6,
      background: 'var(--color-background-primary)',
      border: '0.5px solid var(--color-border-tertiary)',
      borderRadius: 10,
      padding: '6px 10px',
      alignItems: 'center',
    }}>
      <TbBtn active={mode === 'select'} onClick={() => onModeChange('select')}>选择 V</TbBtn>
      <TbBtn active={mode === 'pan'} onClick={() => onModeChange('pan')}>平移 H</TbBtn>
      <TbSep />
      <TbBtn onClick={fitToContent}>适应画布 ⌘0</TbBtn>
      <TbBtn onClick={toggleCollapseAll}>折叠模块</TbBtn>
      <TbSep />
      <TbBtn onClick={runAgentAssign} disabled={isRunning}>
        Agent 自动分配
      </TbBtn>
      <TbSep />
      <TbBtn
        onClick={runBatch}
        disabled={isRunning || pendingCount === 0}
        style={{ color: pendingCount > 0 ? '#378ADD' : undefined }}
      >
        批量执行 {pendingCount > 0 ? `(${pendingCount})` : ''}
      </TbBtn>
    </div>
  );
};

const TbBtn: React.FC<{
  children: React.ReactNode;
  active?: boolean;
  disabled?: boolean;
  onClick?: () => void;
  style?: React.CSSProperties;
}> = ({ children, active, disabled, onClick, style }) => (
  <button
    onClick={onClick}
    disabled={disabled}
    style={{
      padding: '5px 12px',
      fontSize: 12,
      border: `0.5px solid ${active ? 'var(--color-border-primary)' : 'var(--color-border-tertiary)'}`,
      borderRadius: 6,
      background: active ? 'var(--color-background-secondary)' : 'transparent',
      color: disabled ? 'var(--color-text-tertiary)' : 'var(--color-text-primary)',
      cursor: disabled ? 'not-allowed' : 'pointer',
      whiteSpace: 'nowrap',
      ...style,
    }}
  >
    {children}
  </button>
);

const TbSep: React.FC = () => (
  <div style={{ width: 0.5, height: 20, background: 'var(--color-border-tertiary)', margin: '0 4px' }} />
);
