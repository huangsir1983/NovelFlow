'use client';

// ══════════════════════════════════════════════════════════════
// MiniMap.tsx — 小地图
// ══════════════════════════════════════════════════════════════

import React, { useRef, useEffect, useCallback } from 'react';
import { useInfiniteCanvasStore } from '../../../stores/infiniteCanvasStore';

const MM_WIDTH = 160;
const MM_HEIGHT = 100;
const WORLD_W = 3000;
const WORLD_H = 2000;
const scaleX = MM_WIDTH / WORLD_W;
const scaleY = MM_HEIGHT / WORLD_H;

const STATUS_COLORS_MM: Record<string, string> = {
  done: '#22c55e', processing: '#f59e0b', idle: 'rgba(255,255,255,0.2)',
  ready: '#3b82f6', outdated: '#f97316', error: '#ef4444',
};

export const MiniMap: React.FC<{ style?: React.CSSProperties }> = ({ style }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const nodes = useInfiniteCanvasStore((s) => s.nodes);
  const modules = useInfiniteCanvasStore((s) => s.modules);
  const view = useInfiniteCanvasStore((s) => s.view);
  const setTransform = useInfiniteCanvasStore((s) => s.setTransform);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, MM_WIDTH, MM_HEIGHT);

    modules.forEach((mod) => {
      ctx.fillStyle = mod.color + '22';
      ctx.strokeStyle = mod.color + '88';
      ctx.lineWidth = 0.5;
      ctx.beginPath();
      ctx.roundRect(mod.position.x * scaleX, mod.position.y * scaleY, mod.size.width * scaleX, mod.size.height * scaleY, 2);
      ctx.fill();
      ctx.stroke();
    });

    nodes.forEach((node) => {
      const color = STATUS_COLORS_MM[node.status] || 'rgba(255,255,255,0.2)';
      ctx.fillStyle = color + 'CC';
      ctx.fillRect(
        node.position.x * scaleX, node.position.y * scaleY,
        Math.max(2, node.size.width * scaleX), Math.max(2, node.size.height * scaleY),
      );
    });

    const { transform, visibleRect } = view;
    const vpX = (-transform.offsetX / transform.scale) * scaleX;
    const vpY = (-transform.offsetY / transform.scale) * scaleY;
    const vpW = (visibleRect.width / transform.scale) * scaleX;
    const vpH = (visibleRect.height / transform.scale) * scaleY;

    ctx.strokeStyle = '#6366f1';
    ctx.lineWidth = 1.5;
    ctx.strokeRect(vpX, vpY, vpW, vpH);
    ctx.fillStyle = 'rgba(99,102,241,0.05)';
    ctx.fillRect(vpX, vpY, vpW, vpH);
  }, [nodes, modules, view]);

  useEffect(() => { draw(); }, [draw]);

  const onClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current!.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const worldX = mx / scaleX;
    const worldY = my / scaleY;
    setTransform({
      ...view.transform,
      offsetX: -(worldX * view.transform.scale) + view.visibleRect.width / 2,
      offsetY: -(worldY * view.transform.scale) + view.visibleRect.height / 2,
    });
  }, [view, setTransform]);

  return (
    <div style={{
      width: MM_WIDTH, height: MM_HEIGHT,
      background: '#12122a', border: '0.5px solid rgba(255,255,255,0.08)',
      borderRadius: 8, overflow: 'hidden', ...style,
    }}>
      <canvas ref={canvasRef} width={MM_WIDTH} height={MM_HEIGHT} onClick={onClick} style={{ cursor: 'pointer', display: 'block' }} />
    </div>
  );
};
