'use client';

import React from 'react';
import type { PipelinePhaseStatus } from '../../types/project';

const PHASE_LABELS: Record<string, string> = {
  streaming: '双流提取',
  enrichment: '资产丰富化',
  knowledge: '知识库构建',
  shots: '分镜拆解',
  merging: '镜头合并',
  prompts: '视觉提示词',
};

interface PipelineStatusBarProps {
  pipelineStatus: Record<string, PipelinePhaseStatus>;
  importPhase: string | null;
  characterCount: number;
  sceneCount: number;
  locationCount: number;
  propCount: number;
  error?: string | null;
  onRetry?: () => void;
  onCancel?: () => void;
}

export function PipelineStatusBar({
  pipelineStatus,
  importPhase,
  characterCount,
  sceneCount,
  locationCount,
  propCount,
  error,
  onRetry,
  onCancel,
}: PipelineStatusBarProps) {
  if (error) {
    return (
      <div className="flex w-full items-center justify-between">
        <span className="flex items-center gap-1.5 text-error">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="15" y1="9" x2="9" y2="15" />
            <line x1="9" y1="9" x2="15" y2="15" />
          </svg>
          导入出错: {error}
        </span>
        {onRetry && (
          <button type="button" onClick={onRetry} className="text-brand hover:text-brand-light transition-colors">
            重试
          </button>
        )}
      </div>
    );
  }

  // Calculate overall progress
  const phases = Object.values(pipelineStatus);
  const doneCount = phases.filter((p) => p.status === 'done').length;
  const total = phases.length || 1;
  const pct = Math.round((doneCount / total) * 100);

  // Current running phase progress
  const currentPhase = importPhase ? pipelineStatus[importPhase] : null;
  let phasePct = 0;
  if (currentPhase?.progress) {
    phasePct = Math.round((currentPhase.progress.current / (currentPhase.progress.total || 1)) * 100);
  }

  const overallPct = doneCount === total ? 100 : Math.round(((doneCount + phasePct / 100) / total) * 100);

  return (
    <div className="flex w-full items-center gap-3">
      {/* Progress bar */}
      <div className="h-1 w-24 overflow-hidden rounded-full bg-white/[0.06]">
        <div
          className="h-full rounded-full bg-brand transition-all duration-300"
          style={{ width: `${overallPct}%` }}
        />
      </div>

      {/* Current phase */}
      <span className="flex items-center gap-1.5">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand" />
        {importPhase ? (PHASE_LABELS[importPhase] || importPhase) : '准备中'}
      </span>

      {/* Entity counts */}
      <span className="ml-auto flex items-center gap-2">
        <span>角色 {characterCount}</span>
        <span className="text-white/20">|</span>
        <span>场景 {sceneCount}</span>
        <span className="text-white/20">|</span>
        <span>地点 {locationCount}</span>
        {propCount > 0 && (
          <>
            <span className="text-white/20">|</span>
            <span>道具 {propCount}</span>
          </>
        )}
        {onCancel && (
          <>
            <span className="text-white/20">|</span>
            <button type="button" onClick={onCancel} className="text-red-400 hover:text-red-300 transition-colors">
              停止
            </button>
          </>
        )}
      </span>
    </div>
  );
}
