'use client';

import { useEffect, useMemo, useState } from 'react';
import { buildShotProductionProjection } from '../../lib/production';
import type {
  Character,
  CharacterVariant,
  Location,
  Project,
  Prop,
  Scene,
  Shot,
} from '../../types/project';
import { AssetLibraryGrid } from '../asset-library/AssetLibraryGrid';
import type { AssetFilter } from '../../stores/projectStore';

interface ProductionAssetHubProps {
  project: Project | null;
  scenes: Scene[];
  shots: Shot[];
  characters: Character[];
  locations: Location[];
  props: Prop[];
  characterVariants: CharacterVariant[];
  assetFilter: AssetFilter;
  importing: boolean;
  locked?: boolean;
  projectId?: string;
  onFileUpload?: (file: File) => void;
  uploadDisabled?: boolean;
  uploadLabel?: string;
  uploadHint?: string;
  stylePreset?: string | null;
  assetImages: Record<string, Record<string, string>>;
  assetImageKeys: Record<string, Record<string, string>>;
  onEnterProduction: (shotIds: string[]) => void;
}

function SummaryCard({
  label,
  value,
  tone = 'default',
}: {
  label: string;
  value: string | number;
  tone?: 'default' | 'success' | 'warning';
}) {
  const toneClass =
    tone === 'success'
      ? 'border-emerald-500/20 bg-emerald-500/[0.08] text-emerald-200'
      : tone === 'warning'
        ? 'border-amber-500/20 bg-amber-500/[0.08] text-amber-200'
        : 'border-white/[0.08] bg-white/[0.03] text-white';

  return (
    <div className={`rounded-xl border p-4 ${toneClass}`}>
      <div className="text-[10px] uppercase tracking-[0.24em] text-white/40">{label}</div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
    </div>
  );
}

export function ProductionAssetHub({
  project,
  scenes,
  shots,
  characters,
  locations,
  props,
  characterVariants,
  assetFilter,
  importing,
  locked,
  projectId,
  onFileUpload,
  uploadDisabled,
  uploadLabel,
  uploadHint,
  stylePreset,
  assetImages,
  assetImageKeys,
  onEnterProduction,
}: ProductionAssetHubProps) {
  const projection = useMemo(
    () =>
      buildShotProductionProjection({
        project,
        scenes,
        shots,
        characters,
        locations,
        props,
        assetImages,
        assetImageKeys,
        stylePreset,
      }),
    [project, scenes, shots, characters, locations, props, assetImages, assetImageKeys, stylePreset],
  );

  const readyShotIds = projection.specs
    .filter((spec) => spec.readiness === 'ready')
    .map((spec) => spec.shotId);
  const [selectedShotId, setSelectedShotId] = useState<string | null>(projection.specs[0]?.shotId || null);
  const selectedSpec =
    projection.specs.find((spec) => spec.shotId === selectedShotId) || projection.specs[0] || null;
  const selectedRequirements = projection.requirements.filter(
    (requirement) => requirement.shotId === selectedSpec?.shotId,
  );

  useEffect(() => {
    if (!selectedShotId && projection.specs[0]) {
      setSelectedShotId(projection.specs[0].shotId);
      return;
    }

    if (selectedShotId && !projection.specs.some((spec) => spec.shotId === selectedShotId)) {
      setSelectedShotId(projection.specs[0]?.shotId || null);
    }
  }, [projection.specs, selectedShotId]);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="border-b border-white/[0.06] bg-[#0b1020] px-5 py-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-[10px] uppercase tracking-[0.28em] text-cyan-300/70">
              Production Asset Hub
            </div>
            <h2 className="mt-1 text-xl font-semibold text-white/90">
              资产库先变成 Shot 生产入口，再进入 TapNow 式画布
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-white/45">
              这里不再只是看角色和地点，而是先判断每个 Shot 是否具备可生产的角色锚、地点锚、道具锚和风格约束。
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => selectedSpec && onEnterProduction([selectedSpec.shotId])}
              disabled={!selectedSpec || selectedSpec.readiness !== 'ready'}
              className={`rounded-xl px-4 py-2 text-sm font-medium transition-colors ${
                !selectedSpec || selectedSpec.readiness !== 'ready'
                  ? 'cursor-not-allowed bg-white/[0.05] text-white/25'
                  : 'bg-cyan-500/20 text-cyan-100 hover:bg-cyan-500/30'
              }`}
            >
              进入当前 Shot
            </button>
            <button
              type="button"
              onClick={() => onEnterProduction(readyShotIds)}
              disabled={readyShotIds.length === 0}
              className={`rounded-xl px-4 py-2 text-sm font-medium transition-colors ${
                readyShotIds.length === 0
                  ? 'cursor-not-allowed bg-white/[0.05] text-white/25'
                  : 'bg-white text-black hover:bg-white/90'
              }`}
            >
              进入镜头生产
            </button>
          </div>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-4">
          <SummaryCard label="Ready Shots" value={projection.readiness.readyShots} tone="success" />
          <SummaryCard label="Blocked Shots" value={projection.readiness.blockedShots} tone="warning" />
          <SummaryCard label="Missing Character Anchors" value={projection.readiness.missingCharacterAnchors} />
          <SummaryCard label="Missing Style Anchors" value={projection.readiness.missingStyleAnchors} />
        </div>
      </div>

      <div className="grid shrink-0 gap-4 border-b border-white/[0.06] bg-[#090e1a] px-5 py-4 lg:grid-cols-[1.8fr_1fr]">
        <div className="min-h-0 rounded-2xl border border-white/[0.08] bg-white/[0.02]">
          <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3">
            <div>
              <div className="text-sm font-medium text-white/80">Board Readiness</div>
              <div className="text-xs text-white/35">Shot-first queue, recommended modules, and blocking reasons</div>
            </div>
            <div className="rounded-full bg-white/[0.05] px-3 py-1 text-[11px] text-white/45">
              {projection.specs.length} shots
            </div>
          </div>

          <div className="max-h-[320px] overflow-y-auto px-3 py-3">
            <div className="space-y-2">
              {projection.specs.map((spec) => (
                <button
                  key={spec.shotId}
                  type="button"
                  onClick={() => setSelectedShotId(spec.shotId)}
                  className={`w-full rounded-2xl border px-4 py-3 text-left transition-colors ${
                    selectedSpec?.shotId === spec.shotId
                      ? 'border-cyan-400/50 bg-cyan-400/[0.08]'
                      : 'border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.04]'
                  }`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <div className="text-[11px] uppercase tracking-[0.22em] text-white/30">
                        Scene {spec.sceneId}
                      </div>
                      <div className="mt-1 text-sm font-medium text-white/85">{spec.title}</div>
                    </div>
                    <span
                      className={`rounded-full px-2.5 py-1 text-[10px] font-medium ${
                        spec.readiness === 'ready'
                          ? 'bg-emerald-500/15 text-emerald-200'
                          : 'bg-amber-500/15 text-amber-200'
                      }`}
                    >
                      {spec.readiness === 'ready' ? 'ready' : 'blocked'}
                    </span>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-white/45">
                    <span className="rounded-full bg-white/[0.05] px-2 py-1">
                      模块: {projection.modules.find((module) => module.id === spec.moduleId)?.name || spec.moduleId}
                    </span>
                    <span className="rounded-full bg-white/[0.05] px-2 py-1">
                      角色: {spec.charactersInFrame.length}
                    </span>
                    <span className="rounded-full bg-white/[0.05] px-2 py-1">
                      锚点: {spec.anchors.filter((anchor) => anchor.status === 'ready').length}/{spec.anchors.length}
                    </span>
                  </div>
                  {spec.blockedReasons.length > 0 && (
                    <div className="mt-2 text-xs text-amber-200/80">
                      {spec.blockedReasons.slice(0, 2).join(' · ')}
                    </div>
                  )}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="min-h-0 rounded-2xl border border-white/[0.08] bg-white/[0.02]">
          <div className="border-b border-white/[0.06] px-4 py-3">
            <div className="text-sm font-medium text-white/80">Asset Requirement</div>
            <div className="text-xs text-white/35">当前 Shot 缺什么，就在这里先补齐</div>
          </div>

          <div className="space-y-4 px-4 py-4">
            {selectedSpec ? (
              <>
                <div>
                  <div className="text-[11px] uppercase tracking-[0.22em] text-white/30">
                    Current Shot
                  </div>
                  <div className="mt-1 text-base font-semibold text-white/90">{selectedSpec.title}</div>
                  <div className="mt-1 text-sm text-white/45">{selectedSpec.narrativeIntent}</div>
                </div>

                <div className="rounded-xl border border-white/[0.06] bg-black/20 p-3">
                  <div className="text-[11px] uppercase tracking-[0.22em] text-white/30">
                    推荐模块
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {selectedSpec.recommendedModuleIds.map((moduleId) => {
                      const module = projection.modules.find((candidate) => candidate.id === moduleId);
                      return (
                        <span
                          key={moduleId}
                          className="rounded-full bg-cyan-500/10 px-2.5 py-1 text-xs text-cyan-100/85"
                        >
                          {module?.name || moduleId}
                        </span>
                      );
                    })}
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="text-[11px] uppercase tracking-[0.22em] text-white/30">
                    资产锚点状态
                  </div>
                  {selectedSpec.anchors.map((anchor) => (
                    <div
                      key={`${anchor.assetType}:${anchor.assetId}`}
                      className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <div className="text-sm text-white/85">{anchor.assetName || anchor.assetId}</div>
                          <div className="text-[11px] uppercase tracking-[0.2em] text-white/30">
                            {anchor.assetType}
                          </div>
                        </div>
                        <span
                          className={`rounded-full px-2 py-1 text-[10px] font-medium ${
                            anchor.status === 'ready'
                              ? 'bg-emerald-500/15 text-emerald-200'
                              : anchor.status === 'partial'
                                ? 'bg-amber-500/15 text-amber-200'
                                : 'bg-rose-500/15 text-rose-200'
                          }`}
                        >
                          {anchor.status}
                        </span>
                      </div>
                      {anchor.missingReason && (
                        <div className="mt-2 text-xs text-white/40">{anchor.missingReason}</div>
                      )}
                    </div>
                  ))}
                </div>

                <div className="space-y-2">
                  <div className="text-[11px] uppercase tracking-[0.22em] text-white/30">
                    缺失项
                  </div>
                  {selectedRequirements.length > 0 ? (
                    selectedRequirements.map((requirement) => (
                      <div
                        key={`${requirement.shotId}:${requirement.assetId}`}
                        className="rounded-xl border border-amber-500/15 bg-amber-500/[0.06] px-3 py-2 text-sm text-amber-100/85"
                      >
                        <div className="font-medium">{requirement.assetName}</div>
                        <div className="mt-1 text-xs text-amber-100/70">{requirement.reason}</div>
                      </div>
                    ))
                  ) : (
                    <div className="rounded-xl border border-emerald-500/15 bg-emerald-500/[0.08] px-3 py-3 text-sm text-emerald-100/85">
                      当前 Shot 已满足进入生产画布的基础要求。
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-4 text-sm text-white/40">
                当前还没有 Shot 生产规格。先完成脚本拆解或资产导入。
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1">
        <AssetLibraryGrid
          characters={characters}
          scenes={scenes}
          locations={locations}
          props={props}
          characterVariants={characterVariants}
          assetFilter={assetFilter}
          importing={importing}
          locked={locked}
          projectId={projectId}
          onFileUpload={onFileUpload}
          uploadDisabled={uploadDisabled}
          uploadLabel={uploadLabel}
          uploadHint={uploadHint}
        />
      </div>
    </div>
  );
}
