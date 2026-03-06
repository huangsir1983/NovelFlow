'use client';

import React from 'react';
import type { Beat } from '../../types/project';
import { BeatCard } from './BeatCard';

interface BeatListProps {
  beats: Beat[];
  selectedBeatId?: string;
  onSelectBeat?: (beatId: string) => void;
  onUpdateBeat?: (beatId: string, updates: Partial<Beat>) => void;
}

export function BeatList({ beats, selectedBeatId, onSelectBeat, onUpdateBeat }: BeatListProps) {
  // Emotional curve SVG
  const curveWidth = 600;
  const curveHeight = 80;
  const padding = 20;

  const points = beats.map((beat, i) => ({
    x: padding + (i / Math.max(beats.length - 1, 1)) * (curveWidth - padding * 2),
    y: curveHeight / 2 - beat.emotional_value * (curveHeight / 2 - 10),
  }));

  const pathD =
    points.length > 1
      ? `M ${points.map((p) => `${p.x},${p.y}`).join(' L ')}`
      : '';

  return (
    <div className="space-y-4">
      {/* Emotional Curve */}
      {beats.length > 1 && (
        <div className="rounded-lg border border-white/[0.06] bg-bg-1 p-3">
          <h4 className="mb-2 text-xs font-medium text-white/40">情感曲线</h4>
          <svg
            viewBox={`0 0 ${curveWidth} ${curveHeight}`}
            className="w-full"
            preserveAspectRatio="none"
          >
            {/* Zero line */}
            <line
              x1={padding}
              y1={curveHeight / 2}
              x2={curveWidth - padding}
              y2={curveHeight / 2}
              stroke="rgba(255,255,255,0.1)"
              strokeDasharray="4 4"
            />
            {/* Curve */}
            <path
              d={pathD}
              fill="none"
              stroke="url(#emotionGradient)"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            {/* Points */}
            {points.map((p, i) => (
              <circle
                key={beats[i].id}
                cx={p.x}
                cy={p.y}
                r={selectedBeatId === beats[i].id ? 5 : 3}
                fill={
                  beats[i].emotional_value >= 0
                    ? 'rgb(34,197,94)'
                    : 'rgb(239,68,68)'
                }
                className="cursor-pointer"
                onClick={() => onSelectBeat?.(beats[i].id)}
              />
            ))}
            <defs>
              <linearGradient id="emotionGradient" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="rgb(99,102,241)" />
                <stop offset="100%" stopColor="rgb(139,92,246)" />
              </linearGradient>
            </defs>
          </svg>
        </div>
      )}

      {/* Beat Cards */}
      <div className="space-y-2">
        {beats.map((beat) => (
          <BeatCard
            key={beat.id}
            beat={beat}
            isSelected={selectedBeatId === beat.id}
            onSelect={() => onSelectBeat?.(beat.id)}
            onUpdate={onUpdateBeat ? (updates) => onUpdateBeat(beat.id, updates) : undefined}
          />
        ))}
        {beats.length === 0 && (
          <p className="py-8 text-center text-sm text-white/30">
            暂无节拍数据，请先导入小说或手动创建
          </p>
        )}
      </div>
    </div>
  );
}
