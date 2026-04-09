'use client';

import { memo } from 'react';

interface CanvasSkeletonProps {
  className?: string;
}

/**
 * Skeleton placeholder displayed while the canvas chunk is downloading
 * and graph is being built. Mimics the React Flow dot-grid + node cards.
 */
export const CanvasSkeleton = memo(function CanvasSkeleton({ className }: CanvasSkeletonProps) {
  return (
    <div
      data-testid="canvas-skeleton"
      className={`relative h-full w-full overflow-hidden bg-[#0a0a0f] ${className ?? ''}`}
    >
      {/* Dot grid background — matches React Flow BackgroundVariant.Dots */}
      <svg
        data-testid="canvas-skeleton-dotgrid"
        className="absolute inset-0 h-full w-full"
        aria-hidden="true"
      >
        <defs>
          <pattern id="skeleton-dots" x="0" y="0" width="20" height="20" patternUnits="userSpaceOnUse">
            <circle cx="1" cy="1" r="0.8" fill="rgba(255,255,255,0.06)" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#skeleton-dots)" />
      </svg>

      {/* Placeholder scene + shot node cards */}
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="flex gap-6">
          {/* Scene node skeleton */}
          <div
            data-testid="skeleton-node-scene"
            className="h-36 w-48 rounded-xl bg-white/[0.04] ring-1 ring-inset ring-white/[0.08]"
          />
          {/* Shot node skeleton */}
          <div
            data-testid="skeleton-node-shot"
            className="h-44 w-36 rounded-xl bg-white/[0.04] ring-1 ring-inset ring-white/[0.08]"
            style={{ animationDelay: '150ms' }}
          />
          {/* Pipeline node skeleton */}
          <div
            data-testid="skeleton-node-pipeline"
            className="h-32 w-36 rounded-xl bg-white/[0.04] ring-1 ring-inset ring-white/[0.08]"
            style={{ animationDelay: '300ms' }}
          />
        </div>
      </div>

      {/* Connecting line skeletons between cards */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="flex items-center gap-0" style={{ transform: 'translateX(-6px)' }}>
          <div className="w-48" />
          <div className="h-px w-6 bg-white/[0.08]" />
          <div className="w-36" />
          <div className="h-px w-6 bg-white/[0.08]" />
        </div>
      </div>

      {/* Loading hint */}
      <div className="absolute inset-x-0 bottom-12 flex justify-center">
        <div
          data-testid="canvas-skeleton-hint"
          className="flex items-center gap-2 rounded-full bg-white/[0.04] px-4 py-2 text-xs text-white/30"
        >
          <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          正在装配画布…
        </div>
      </div>
    </div>
  );
});
