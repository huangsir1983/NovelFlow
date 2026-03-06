'use client';

import React from 'react';

interface ImportStep {
  id: string;
  label: string;
  status: 'pending' | 'running' | 'done' | 'error';
}

interface ImportProgressProps {
  steps: ImportStep[];
  error?: string | null;
}

export function ImportProgress({ steps, error }: ImportProgressProps) {
  return (
    <div className="space-y-3">
      {steps.map((step, i) => (
        <div key={step.id} className="flex items-center gap-3">
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

          {/* Label */}
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
        </div>
      ))}

      {error && (
        <div className="mt-4 rounded-lg border border-red-500/20 bg-red-500/10 p-3">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}
    </div>
  );
}
