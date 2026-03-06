'use client';

import React from 'react';
import type { Beat } from '../../types/project';

interface BeatCardProps {
  beat: Beat;
  isSelected?: boolean;
  onSelect?: () => void;
  onUpdate?: (updates: Partial<Beat>) => void;
}

export function BeatCard({ beat, isSelected, onSelect, onUpdate }: BeatCardProps) {
  const typeColors: Record<string, string> = {
    event: 'bg-blue-500/20 text-blue-400',
    dialogue: 'bg-green-500/20 text-green-400',
    action: 'bg-orange-500/20 text-orange-400',
    transition: 'bg-purple-500/20 text-purple-400',
    revelation: 'bg-yellow-500/20 text-yellow-400',
  };

  const emotionalColor =
    beat.emotional_value > 0
      ? `rgba(34,197,94,${Math.abs(beat.emotional_value)})`
      : beat.emotional_value < 0
        ? `rgba(239,68,68,${Math.abs(beat.emotional_value)})`
        : 'rgba(255,255,255,0.1)';

  return (
    <div
      className={`
        cursor-pointer rounded-lg border p-3 transition-all
        ${isSelected ? 'border-indigo-500/50 bg-indigo-500/10' : 'border-white/[0.06] bg-bg-1 hover:border-white/10'}
      `}
      onClick={onSelect}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <h4 className="text-sm font-medium text-white">{beat.title || '未命名节拍'}</h4>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs ${typeColors[beat.beat_type] || typeColors.event}`}>
          {beat.beat_type}
        </span>
      </div>

      {beat.description && (
        <p className="mb-2 line-clamp-2 text-xs text-white/40">{beat.description}</p>
      )}

      {/* Emotional value bar */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-white/30">情感</span>
        <div className="h-1.5 flex-1 rounded-full bg-white/5">
          <div
            className="h-full rounded-full transition-all"
            style={{
              width: `${Math.abs(beat.emotional_value) * 50 + 50}%`,
              backgroundColor: emotionalColor,
              marginLeft: beat.emotional_value < 0 ? 0 : '50%',
              marginRight: beat.emotional_value > 0 ? 0 : '50%',
            }}
          />
        </div>
        <span className="w-8 text-right text-xs text-white/30">
          {beat.emotional_value > 0 ? '+' : ''}{beat.emotional_value.toFixed(1)}
        </span>
      </div>
    </div>
  );
}
