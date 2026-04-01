'use client';

import type { StageRoute } from '../../hooks/useStageNavigation';
import { useStageNavigation } from '../../hooks/useStageNavigation';

interface StageNavigationProps {
  projectId: string;
  activeStage: StageRoute;
  onNavigate?: (stage: StageRoute, path: string) => void;
  disabledStages?: StageRoute[];
  stageLabels?: Partial<Record<StageRoute, string>>;
  className?: string;
}

export function StageNavigation({
  projectId,
  activeStage,
  onNavigate,
  disabledStages = [],
  stageLabels = {},
  className = '',
}: StageNavigationProps) {
  const { stages, isReady, getStagePath } = useStageNavigation(projectId);

  return (
    <nav className={`flex flex-wrap items-center gap-2 ${className}`}>
      {stages.map((stage) => {
        const isActive = stage.id === activeStage;
        const isDisabled = !isReady || disabledStages.includes(stage.id);
        const path = getStagePath(stage.id);
        const label = stageLabels[stage.id] || stage.label;

        return (
          <button
            key={stage.id}
            type="button"
            disabled={isDisabled}
            title={stage.description}
            onClick={() => {
              if (isDisabled || path === '#') {
                return;
              }
              if (onNavigate) {
                onNavigate(stage.id, path);
                return;
              }
              window.location.href = path;
            }}
            className={[
              'rounded-full border px-3 py-1.5 text-xs font-medium transition-all',
              isActive
                ? 'border-brand bg-brand text-white'
                : isDisabled
                  ? 'cursor-not-allowed border-white/10 text-white/30'
                  : 'border-white/15 text-white/70 hover:border-white/30 hover:text-white',
            ].join(' ')}
          >
            {label}
          </button>
        );
      })}
    </nav>
  );
}
