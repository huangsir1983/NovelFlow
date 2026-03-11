'use client';

import React from 'react';

interface ImportStep {
  id: string;
  label: string;
  status: 'pending' | 'running' | 'done' | 'error';
  detail?: string;
  progress?: { current: number; total: number };
}

interface ImportProgressProps {
  steps: ImportStep[];
  error?: string | null;
  entities?: string[];
  onRetry?: () => void;
}

export function ImportProgress({ steps, error, entities, onRetry }: ImportProgressProps) {
  return (
    <div className="space-y-3">
      {steps.map((step, i) => (
        <div key={step.id} className="flex items-start gap-3">
          {/* Status indicator */}
          <div className="flex h-8 w-8 shrink-0 items-center justify-center">
            {step.status === 'done' && (
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-green-500 text-xs text-white">
                &#10003;
              </span>
            )}
            {step.status === 'running' && (
              <span className="flex h-6 w-6 items-center justify-center rounded-full border-2 border-indigo-500 text-xs text-indigo-400">
                <span className="h-3 w-3 animate-spin rounded-full border-2 border-indigo-400 border-t-transparent" />
              </span>
            )}
            {step.status === 'error' && (
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-red-500 text-xs text-white">
                !
              </span>
            )}
            {step.status === 'pending' && (
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white/10 text-xs text-white/30">
                {i + 1}
              </span>
            )}
          </div>

          {/* Label + details */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span
                className={`text-sm ${
                  step.status === 'done'
                    ? 'text-green-400'
                    : step.status === 'running'
                      ? 'text-indigo-400'
                      : step.status === 'error'
                        ? 'text-red-400'
                        : 'text-white/30'
                }`}
              >
                {step.label}
              </span>
              {step.progress && step.status === 'running' && (
                <span className="text-xs text-white/40">
                  {step.progress.current}/{step.progress.total}
                </span>
              )}
            </div>
            {step.detail && (
              <p className="mt-0.5 text-xs text-white/30 truncate">{step.detail}</p>
            )}
            {/* Progress bar for running steps with progress */}
            {step.progress && step.status === 'running' && step.progress.total > 0 && (
              <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-white/10">
                <div
                  className="h-full rounded-full bg-indigo-500 transition-all duration-300"
                  style={{ width: `${Math.round((step.progress.current / step.progress.total) * 100)}%` }}
                />
              </div>
            )}
          </div>
        </div>
      ))}

      {/* Extracted entities display */}
      {entities && entities.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {entities.map((name) => (
            <span
              key={name}
              className="inline-flex items-center rounded-md bg-indigo-500/10 px-2 py-0.5 text-xs text-indigo-300 ring-1 ring-inset ring-indigo-500/20"
            >
              {name}
            </span>
          ))}
        </div>
      )}

      {error && (
        <div className="mt-4 rounded-lg border border-red-500/20 bg-red-500/10 p-3">
          <p className="text-sm text-red-400">{error}</p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="mt-2 rounded-md bg-red-500/20 px-3 py-1 text-xs text-red-300 hover:bg-red-500/30 transition-colors"
            >
              重试
            </button>
          )}
        </div>
      )}
    </div>
  );
}
