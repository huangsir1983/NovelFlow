'use client';

import { useState } from 'react';
import type { AssetFilter } from '../../stores/projectStore';
import { useProjectStore } from '../../stores/projectStore';
import type { PipelinePhaseStatus } from '../../types/project';

interface FilterItem {
  id: AssetFilter;
  label: string;
  generatable?: boolean; // whether this category supports on-demand generation
  generateLabel?: string;
}

const FILTERS: FilterItem[] = [
  { id: 'all',       label: '全部' },
  { id: 'character', label: '角色', generatable: true, generateLabel: '一键生成角色' },
  { id: 'location',  label: '地点', generatable: true, generateLabel: '一键生成地点' },
  { id: 'prop',      label: '道具', generatable: true, generateLabel: '一键生成道具' },
];

const PHASE_LABELS: Record<string, string> = {
  streaming: '双流提取',
  enrichment: '资产丰富化',
  knowledge: '知识库构建',
  shots: '分镜拆解',
  merging: '镜头合并',
  prompts: '视觉提示词',
};

interface AssetLibrarySidebarProps {
  activeFilter: AssetFilter;
  onFilterChange: (filter: AssetFilter) => void;
  counts: Record<AssetFilter, number>;
  importing: boolean;
  pipelineStatus: Record<string, PipelinePhaseStatus>;
  importPhase: string | null;
  locked?: boolean;
  onGenerate?: (type: 'character' | 'location' | 'prop', mode: 'overwrite' | 'enhance') => void;
  generating?: string | null; // currently generating type
}

export function AssetLibrarySidebar({
  activeFilter,
  onFilterChange,
  counts,
  importing,
  pipelineStatus,
  importPhase,
  locked,
  onGenerate,
  generating,
}: AssetLibrarySidebarProps) {
  const [modeDialog, setModeDialog] = useState<{ type: 'character' | 'location' | 'prop' } | null>(null);

  // Calculate how many assets have complete image sets
  const { assetImages, characters, locations, props: storeProps } = useProjectStore();

  const SLOT_COUNTS: Record<string, number> = {
    character: 5, // CHARACTER_SLOTS
    location: 4,  // LOCATION_SLOTS
    prop: 4,      // PROP_SLOTS
  };

  const countComplete = (assets: { id: string }[], type: string) => {
    const required = SLOT_COUNTS[type] || 0;
    return assets.filter(a => {
      const imgs = assetImages[a.id];
      return imgs && Object.keys(imgs).length >= required;
    }).length;
  };

  const completeCounts: Record<string, number> = {
    character: countComplete(characters, 'character'),
    location: countComplete(locations, 'location'),
    prop: countComplete(storeProps, 'prop'),
  };
  completeCounts.all = completeCounts.character + completeCounts.location + completeCounts.prop;

  const handleGenerateClick = (filter: FilterItem) => {
    if (!filter.generatable || !onGenerate || locked || generating) return;
    const assetType = filter.id as 'character' | 'location' | 'prop';
    const hasData = (counts[filter.id] ?? 0) > 0;
    if (hasData) {
      setModeDialog({ type: assetType });
    } else {
      onGenerate(assetType, 'overwrite');
    }
  };

  const handleModeSelect = (mode: 'overwrite' | 'enhance') => {
    if (modeDialog && onGenerate) {
      onGenerate(modeDialog.type, mode);
    }
    setModeDialog(null);
  };

  return (
    <div className="flex h-full flex-col p-4">
      <h3 className="mb-4 px-2 text-sm font-semibold uppercase tracking-wider text-white/30">资产分类</h3>

      <div className="flex flex-col gap-1">
        {FILTERS.map((f) => (
          <div key={f.id} className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => onFilterChange(f.id)}
              className={`
                flex flex-1 items-center justify-between rounded-lg px-3 py-2.5 text-base transition-colors
                ${activeFilter === f.id
                  ? 'bg-brand/10 text-brand font-medium'
                  : 'text-white/50 hover:bg-white/5 hover:text-white/70'
                }
              `}
            >
              <span>{f.label}</span>
              <span className={`
                min-w-[24px] rounded-full px-2 py-0.5 text-center text-xs font-medium
                ${activeFilter === f.id ? 'bg-brand/20 text-brand' : 'bg-white/[0.06] text-white/30'}
              `}>
                {completeCounts[f.id] > 0 ? `${completeCounts[f.id]}/` : ''}{counts[f.id] ?? 0}
              </span>
            </button>

            {f.generatable && (
              <button
                type="button"
                onClick={() => handleGenerateClick(f)}
                disabled={!!locked || !!generating}
                title={f.generateLabel}
                className={`
                  flex h-8 w-8 shrink-0 items-center justify-center rounded-md transition-colors
                  ${locked || generating
                    ? 'cursor-not-allowed text-white/10'
                    : generating === f.id
                      ? 'animate-pulse bg-brand/20 text-brand'
                      : 'text-white/30 hover:bg-white/10 hover:text-white/60'
                  }
                `}
              >
                {generating === f.id ? (
                  <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="40 60" />
                  </svg>
                ) : (
                  <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M12 5v14M5 12h14" strokeLinecap="round" />
                  </svg>
                )}
              </button>
            )}
          </div>
        ))}
      </div>

      {/* Mode selection dialog */}
      {modeDialog && (
        <div className="mt-3 rounded-lg border border-white/10 bg-white/[0.04] p-3">
          <p className="mb-2 text-xs text-white/60">已有数据，请选择模式：</p>
          <div className="flex flex-col gap-1.5">
            <button
              type="button"
              onClick={() => handleModeSelect('overwrite')}
              className="rounded-md bg-error/10 px-3 py-1.5 text-xs text-error/80 hover:bg-error/20 transition-colors"
            >
              覆盖替换
            </button>
            <button
              type="button"
              onClick={() => handleModeSelect('enhance')}
              className="rounded-md bg-brand/10 px-3 py-1.5 text-xs text-brand hover:bg-brand/20 transition-colors"
            >
              增强补全
            </button>
            <button
              type="button"
              onClick={() => setModeDialog(null)}
              className="rounded-md px-3 py-1.5 text-xs text-white/30 hover:bg-white/5 transition-colors"
            >
              取消
            </button>
          </div>
        </div>
      )}

      {importing && (
        <div className="mt-auto border-t border-white/[0.06] pt-3">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-white/30">导入进度</p>
          {importPhase && (
            <div className="mb-2 flex items-center gap-2">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand" />
              <span className="text-xs text-white/50">{PHASE_LABELS[importPhase] || importPhase}</span>
            </div>
          )}
          <div className="space-y-1">
            {Object.entries(pipelineStatus).map(([phase, status]) => (
              <div key={phase} className="flex items-center gap-2">
                <span className={`h-1 w-1 rounded-full ${
                  status.status === 'done' ? 'bg-success' :
                  status.status === 'running' ? 'bg-brand animate-pulse' :
                  status.status === 'error' ? 'bg-error' :
                  'bg-white/10'
                }`} />
                <span className="flex-1 truncate text-[10px] text-white/30">
                  {PHASE_LABELS[phase] || phase}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
