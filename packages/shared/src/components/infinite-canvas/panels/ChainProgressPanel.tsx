'use client';

// ══════════════════════════════════════════════════════════════
// ChainProgressPanel.tsx — 分镜链进度面板
// ══════════════════════════════════════════════════════════════

import React, { useMemo } from 'react';
import { useInfiniteCanvasStore } from '../../../stores/infiniteCanvasStore';
import { useCanvasProjectStore } from '../../../stores/canvasProjectStore';

export const ChainProgressPanel: React.FC = () => {
  const nodes = useInfiniteCanvasStore((s) => s.nodes);
  const chapters = useCanvasProjectStore((s) => s.chapters);

  const chapterStats = useMemo(() => chapters.map((chapter) => {
    const chapterNodes = Array.from(nodes.values()).filter((n) => n.chapterId === chapter.id);
    const done = chapterNodes.filter((n) => n.status === 'done').length;
    const total = chapterNodes.length;
    return { chapter, done, total };
  }), [chapters, nodes]);

  const moduleStats = useMemo(() => {
    const stats: Record<string, { done: number; total: number; color: string }> = {};
    const moduleColors: Record<string, string> = {
      dialogue: '#378ADD', action: '#D85A30', suspense: '#534AB7', landscape: '#1D9E75', emotion: '#D4537E',
    };
    const moduleLabels: Record<string, string> = {
      dialogue: '对话场景', action: '打斗动作', suspense: '悬疑揭秘', landscape: '环境转场', emotion: '情感内心',
    };

    nodes.forEach((node) => {
      if (node.moduleType) {
        if (!stats[node.moduleType]) stats[node.moduleType] = { done: 0, total: 0, color: moduleColors[node.moduleType] || '#888' };
        stats[node.moduleType].total++;
        if (node.status === 'done') stats[node.moduleType].done++;
      }
    });

    return Object.entries(stats).map(([type, s]) => ({ label: moduleLabels[type] || type, ...s }));
  }, [nodes]);

  const displayItems = chapterStats.length > 0
    ? chapterStats.map((s) => ({ label: s.chapter.title, done: s.done, total: s.total, color: '#6366f1' }))
    : moduleStats;

  if (displayItems.length === 0) return null;

  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{
        fontSize: 11, color: 'rgba(255,255,255,0.5)', fontWeight: 500,
        textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8,
      }}>
        分镜链进度
      </div>
      {displayItems.map((item, i) => (
        <ProgressRow key={i} {...item} />
      ))}
    </div>
  );
};

const ProgressRow: React.FC<{ label: string; done: number; total: number; color: string }> = ({ label, done, total, color }) => {
  if (total === 0) return null;
  const pct = Math.round((done / total) * 100);
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 3 }}>
        <span style={{ color: 'rgba(255,255,255,0.85)' }}>{label}</span>
        <span style={{ color }}>{done}/{total}</span>
      </div>
      <div style={{ height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 2, transition: 'width 0.4s ease' }} />
      </div>
    </div>
  );
};
