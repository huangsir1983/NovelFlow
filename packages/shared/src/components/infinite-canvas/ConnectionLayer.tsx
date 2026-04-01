'use client';

// ══════════════════════════════════════════════════════════════
// ConnectionLayer.tsx — SVG 贝塞尔曲线连线层
// ══════════════════════════════════════════════════════════════

import React, { useMemo } from 'react';
import { useInfiniteCanvasStore } from '../../../stores/infiniteCanvasStore';

const STATUS_COLORS: Record<string, string> = {
  done: '#22c55e',
  processing: '#f59e0b',
  ready: '#3b82f6',
  outdated: '#f97316',
  error: '#ef4444',
  idle: 'rgba(255,255,255,0.15)',
};

export const ConnectionLayer: React.FC = () => {
  const connections = useInfiniteCanvasStore((s) => s.connections);
  const nodes = useInfiniteCanvasStore((s) => s.nodes);
  const transform = useInfiniteCanvasStore((s) => s.view.transform);
  const { scale, offsetX, offsetY } = transform;

  const renderedConnections = useMemo(() => {
    return connections.map((conn) => {
      const fromNode = nodes.get(conn.fromNodeId);
      const toNode = nodes.get(conn.toNodeId);
      if (!fromNode || !toNode) return null;

      const ax = (fromNode.position.x + fromNode.size.width) * scale + offsetX;
      const ay = (fromNode.position.y + fromNode.size.height * 0.5) * scale + offsetY;
      const bx = toNode.position.x * scale + offsetX;
      const by = (toNode.position.y + toNode.size.height * 0.5) * scale + offsetY;
      const mx = (ax + bx) / 2;
      const color = STATUS_COLORS[fromNode.status] || 'rgba(255,255,255,0.15)';

      return { id: conn.id, ax, ay, bx, by, mx, color, fromStatus: fromNode.status };
    }).filter(Boolean);
  }, [connections, nodes, scale, offsetX, offsetY]);

  return (
    <svg style={{
      position: 'absolute', inset: 0, width: '100%', height: '100%',
      pointerEvents: 'none', overflow: 'visible', zIndex: 0,
    }}>
      <defs>
        {Object.entries(STATUS_COLORS).map(([status, color]) => (
          <marker
            key={status}
            id={`arrow-${status}`}
            viewBox="0 0 10 10"
            refX="8" refY="5"
            markerWidth="6" markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M2 1L8 5L2 9" fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </marker>
        ))}
      </defs>

      {renderedConnections.map((conn) => conn && (
        <path
          key={conn.id}
          d={`M${conn.ax},${conn.ay} C${conn.mx},${conn.ay} ${conn.mx},${conn.by} ${conn.bx},${conn.by}`}
          fill="none"
          stroke={conn.color}
          strokeWidth={1.5}
          strokeOpacity={conn.fromStatus === 'done' ? 0.8 : 0.4}
          strokeDasharray={conn.fromStatus === 'idle' ? '5 4' : undefined}
          markerEnd={`url(#arrow-${conn.fromStatus})`}
        />
      ))}
    </svg>
  );
};
