'use client';

import { useEffect, useMemo, useState } from 'react';
import { usePreviewStore } from '../../stores/previewStore';

interface PreviewAnimaticWorkspaceProps {
  projectName: string;
  onJumpBackToShot: (shotId: string) => void;
}

export function PreviewAnimaticWorkspace({
  projectName,
  onJumpBackToShot,
}: PreviewAnimaticWorkspaceProps) {
  const currentBundle = usePreviewStore((state) => state.currentBundle);
  const storyboardClips = usePreviewStore((state) => state.storyboardClips);
  const videoClips = usePreviewStore((state) => state.videoClips);
  const activeClips = usePreviewStore((state) => state.activeClips);
  const selectedPhase = usePreviewStore((state) => state.selectedPhase);
  const sequenceBundles = usePreviewStore((state) => state.sequenceBundles);
  const selectedSequenceBundleId = usePreviewStore((state) => state.selectedSequenceBundleId);
  const playheadMs = usePreviewStore((state) => state.playheadMs);
  const isPlaying = usePreviewStore((state) => state.isPlaying);
  const setPlayheadMs = usePreviewStore((state) => state.setPlayheadMs);
  const setPlaying = usePreviewStore((state) => state.setPlaying);
  const setPreviewPhase = usePreviewStore((state) => state.setPreviewPhase);
  const setClipDurationOverride = usePreviewStore((state) => state.setClipDurationOverride);
  const selectSequenceBundle = usePreviewStore((state) => state.selectSequenceBundle);

  const [selectedClipId, setSelectedClipId] = useState<string | null>(activeClips[0]?.artifactId || null);
  const selectedClip =
    activeClips.find((clip) => clip.artifactId === selectedClipId) || activeClips[0] || null;
  const totalDuration =
    currentBundle?.duration_ms || activeClips.reduce((sum, clip) => sum + clip.durationMs, 0);
  const activeSequenceBundle =
    sequenceBundles.find((bundle) => bundle.id === selectedSequenceBundleId) || sequenceBundles[0] || null;

  useEffect(() => {
    if (!selectedClipId && activeClips[0]) {
      setSelectedClipId(activeClips[0].artifactId);
      return;
    }

    if (selectedClipId && !activeClips.some((clip) => clip.artifactId === selectedClipId)) {
      setSelectedClipId(activeClips[0]?.artifactId || null);
    }
  }, [activeClips, selectedClipId]);

  useEffect(() => {
    if (!isPlaying || totalDuration <= 0) {
      return undefined;
    }

    const timer = window.setInterval(() => {
      setPlayheadMs((playheadMs + 240) % totalDuration);
    }, 240);

    return () => window.clearInterval(timer);
  }, [isPlaying, playheadMs, setPlayheadMs, totalDuration]);

  const clipOffsets = useMemo(() => {
    let offset = 0;
    return activeClips.map((clip) => {
      const start = offset;
      offset += clip.durationMs;
      return { clip, start };
    });
  }, [activeClips]);

  if (!currentBundle || activeClips.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-white/40">
        当前还没有可预演的 Animatic。先在造物画布里通过 Storyboard 或 Video Checkpoint。
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[#090d18]">
      <div className="border-b border-white/[0.06] px-5 py-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-[10px] uppercase tracking-[0.28em] text-cyan-300/70">
              Animatic Preview
            </div>
            <h2 className="mt-1 text-xl font-semibold text-white/90">
              {projectName} · {selectedPhase === 'storyboard' ? 'Storyboard Animatic' : 'Video Animatic'}
            </h2>
            <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-white/40">
              <span className="rounded-full bg-white/[0.05] px-2.5 py-1">
                {currentBundle.bundle_type}
              </span>
              <span className="rounded-full bg-white/[0.05] px-2.5 py-1">
                {activeClips.length} clips
              </span>
              <span className="rounded-full bg-white/[0.05] px-2.5 py-1">
                {Math.round(totalDuration / 100) / 10}s
              </span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setPreviewPhase('storyboard')}
              className={`rounded-xl px-4 py-2 text-sm font-medium ${
                selectedPhase === 'storyboard'
                  ? 'bg-cyan-500/20 text-cyan-100'
                  : 'bg-white/[0.06] text-white/70 hover:bg-white/[0.10]'
              }`}
            >
              Storyboard
            </button>
            <button
              type="button"
              onClick={() => setPreviewPhase('video')}
              disabled={videoClips.length === 0}
              className={`rounded-xl px-4 py-2 text-sm font-medium ${
                selectedPhase === 'video'
                  ? 'bg-cyan-500/20 text-cyan-100'
                  : videoClips.length > 0
                    ? 'bg-white/[0.06] text-white/70 hover:bg-white/[0.10]'
                    : 'cursor-not-allowed bg-white/[0.04] text-white/25'
              }`}
            >
              Video
            </button>
            <button
              type="button"
              onClick={() => setPlaying(!isPlaying)}
              className="rounded-xl bg-cyan-500/20 px-4 py-2 text-sm font-medium text-cyan-100 hover:bg-cyan-500/30"
            >
              {isPlaying ? '暂停' : '播放'}
            </button>
            <button
              type="button"
              onClick={() => selectedClip && onJumpBackToShot(selectedClip.shotId)}
              className="rounded-xl bg-white px-4 py-2 text-sm font-medium text-black hover:bg-white/90"
            >
              回到来源 Shot
            </button>
          </div>
        </div>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_340px] gap-4 px-4 py-4">
        <section className="grid min-h-0 grid-rows-[auto_auto_1fr] gap-4">
          <div className="rounded-2xl border border-white/[0.08] bg-white/[0.02] px-4 py-4">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <div className="text-sm font-medium text-white/80">Playhead</div>
                <div className="text-xs text-white/35">节奏判断围绕 clip strip，而不是旧版大桌面</div>
              </div>
              <div className="text-sm text-white/60">
                {Math.round(playheadMs / 100) / 10}s / {Math.round(totalDuration / 100) / 10}s
              </div>
            </div>

            <input
              type="range"
              min={0}
              max={Math.max(totalDuration, 1)}
              value={playheadMs}
              onChange={(event) => setPlayheadMs(Number(event.target.value))}
              className="mt-4 w-full accent-cyan-400"
            />
          </div>

          <div className="rounded-2xl border border-white/[0.08] bg-white/[0.02] px-4 py-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-medium text-white/80">Clip Strip</div>
                <div className="text-xs text-white/35">双击任意 clip 可回跳到来源 Shot / Module / Artifact</div>
              </div>
              <button
                type="button"
                onClick={() => activeSequenceBundle && selectSequenceBundle(activeSequenceBundle.id)}
                className="rounded-full bg-white/[0.06] px-3 py-1.5 text-xs text-white/70 hover:bg-white/[0.10]"
              >
                Sequence Bundle
              </button>
            </div>

            <div className="mt-4 flex gap-2 overflow-x-auto pb-1">
              {clipOffsets.map(({ clip, start }) => (
                <button
                  key={clip.artifactId}
                  type="button"
                  onClick={() => setSelectedClipId(clip.artifactId)}
                  onDoubleClick={() => onJumpBackToShot(clip.shotId)}
                  className={`rounded-2xl border px-3 py-3 text-left transition-colors ${
                    selectedClip?.artifactId === clip.artifactId
                      ? 'border-cyan-400/40 bg-cyan-400/[0.08]'
                      : 'border-white/[0.06] bg-black/20 hover:bg-white/[0.04]'
                  }`}
                  style={{ minWidth: Math.max(140, clip.durationMs / 30) }}
                >
                  <div className="text-sm font-medium text-white/85">{clip.label}</div>
                  <div className="mt-1 text-[11px] text-white/35">
                    {Math.round(start / 100) / 10}s → {Math.round((start + clip.durationMs) / 100) / 10}s
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <span
                      className={`h-2 w-2 rounded-full ${
                        clip.heat === 'stable'
                          ? 'bg-emerald-400'
                          : clip.heat === 'watch'
                            ? 'bg-amber-400'
                            : 'bg-rose-400'
                      }`}
                    />
                    <span className="text-[11px] text-white/45">{clip.sourceType}</span>
                    {clip.riskTag === 'high_consistency_risk' && (
                      <span className="rounded-full bg-amber-500/15 px-2 py-1 text-[10px] text-amber-100/85">
                        风险
                      </span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div className="min-h-0 overflow-hidden rounded-2xl border border-white/[0.08] bg-white/[0.02]">
            <div className="border-b border-white/[0.06] px-4 py-3">
              <div className="text-sm font-medium text-white/80">Heatmap / Rhythm Notes</div>
              <div className="text-xs text-white/35">把节奏风险和一致性风险提前给客户看</div>
            </div>

            <div className="max-h-[calc(100vh-420px)] space-y-3 overflow-y-auto px-4 py-4">
              {clipOffsets.map(({ clip }) => (
                <div
                  key={`heat-${clip.artifactId}`}
                  className={`rounded-2xl border px-4 py-3 ${
                    clip.heat === 'stable'
                      ? 'border-emerald-500/20 bg-emerald-500/[0.06]'
                      : clip.heat === 'watch'
                        ? 'border-amber-500/20 bg-amber-500/[0.06]'
                        : 'border-rose-500/20 bg-rose-500/[0.06]'
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-medium text-white/85">{clip.label}</div>
                    <div className="rounded-full bg-black/20 px-2 py-1 text-[10px] text-white/55">
                      {clip.heat}
                    </div>
                  </div>
                  <div className="mt-2 text-sm text-white/60">
                    {clip.issueSummary || '当前 clip 节奏稳定，可继续推进。'}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <aside className="grid min-h-0 grid-rows-[auto_auto_1fr] gap-4">
          <div className="rounded-2xl border border-white/[0.08] bg-white/[0.02] px-4 py-4">
            <div className="text-sm font-medium text-white/80">Selected Clip</div>
            {selectedClip ? (
              <div className="mt-3 space-y-3 text-sm">
                <div>
                  <div className="text-[11px] uppercase tracking-[0.22em] text-white/30">来源</div>
                  <div className="mt-1 text-white/75">
                    Shot {selectedClip.shotId} · Module {selectedClip.sourceModuleId}
                  </div>
                </div>
                <div>
                  <div className="text-[11px] uppercase tracking-[0.22em] text-white/30">模式</div>
                  <div className="mt-1 text-white/60">{selectedClip.mode || '未标注'}</div>
                </div>
                <div>
                  <div className="text-[11px] uppercase tracking-[0.22em] text-white/30">时长</div>
                  <div className="mt-2 flex items-center gap-2">
                    <input
                      type="number"
                      min={500}
                      step={100}
                      value={selectedClip.durationMs}
                      onChange={(event) =>
                        setClipDurationOverride(selectedClip.shotId, Number(event.target.value))
                      }
                      className="w-28 rounded-xl border border-white/[0.08] bg-black/20 px-3 py-2 text-sm text-white/80 outline-none"
                    />
                    <span className="text-xs text-white/40">ms</span>
                  </div>
                </div>
                <div>
                  <div className="text-[11px] uppercase tracking-[0.22em] text-white/30">Transition Hint</div>
                  <div className="mt-1 text-white/60">{selectedClip.transitionHint || 'cut'}</div>
                </div>
                {selectedClip.riskTag === 'high_consistency_risk' && (
                  <div className="rounded-xl border border-amber-500/15 bg-amber-500/[0.08] px-3 py-2 text-sm text-amber-100/85">
                    当前 clip 来自高一致性风险路径，下游预剪辑会继续保留这个标记。
                  </div>
                )}
                <button
                  type="button"
                  onClick={() => onJumpBackToShot(selectedClip.shotId)}
                  className="w-full rounded-xl bg-white/[0.06] px-3 py-2 text-sm text-white/75 hover:bg-white/[0.10]"
                >
                  双击回跳来源 Shot
                </button>
              </div>
            ) : (
              <div className="mt-3 text-sm text-white/40">选择一个 clip 查看详情。</div>
            )}
          </div>

          <div className="rounded-2xl border border-white/[0.08] bg-white/[0.02] px-4 py-4">
            <div className="text-sm font-medium text-white/80">Bundle State</div>
            {activeSequenceBundle ? (
              <div className="mt-3 space-y-2 text-sm text-white/60">
                <div>状态: {activeSequenceBundle.status}</div>
                <div>目标: {activeSequenceBundle.exportTarget}</div>
                <div>Shots: {activeSequenceBundle.shotIds.length}</div>
                <div>视频素材: {activeSequenceBundle.videoArtifactIds.length}</div>
                <div>风险 Shot: {activeSequenceBundle.consistencyRiskShotIds.length}</div>
              </div>
            ) : (
              <div className="mt-3 rounded-xl border border-dashed border-white/[0.08] px-3 py-4 text-sm text-white/35">
                还没有达到 Sequence Bundle。先在画布里批准视频结果。
              </div>
            )}
          </div>

          <div className="min-h-0 overflow-hidden rounded-2xl border border-white/[0.08] bg-white/[0.02]">
            <div className="border-b border-white/[0.06] px-4 py-3">
              <div className="text-sm font-medium text-white/80">Sequence Bundle Detail</div>
              <div className="text-xs text-white/35">下一阶段会从这里接入预剪辑，并最终导出到剪映</div>
            </div>

            <div className="max-h-[calc(100vh-460px)] space-y-3 overflow-y-auto px-4 py-4">
              {activeSequenceBundle ? (
                activeSequenceBundle.shotOrder.map((shotId, index) => (
                  <div
                    key={`${shotId}:${index}`}
                    className="rounded-2xl border border-white/[0.06] bg-black/20 px-4 py-3"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm font-medium text-white/85">{shotId}</div>
                      {activeSequenceBundle.consistencyRiskShotIds.includes(shotId) && (
                        <span className="rounded-full bg-amber-500/15 px-2 py-1 text-[10px] text-amber-100/85">
                          风险
                        </span>
                      )}
                    </div>
                    <div className="mt-1 text-xs text-white/40">
                      transition: {activeSequenceBundle.transitionHints[index] || 'cut'}
                    </div>
                    <div className="mt-1 text-xs text-white/40">
                      mode: {activeSequenceBundle.videoModesByShot[shotId] || 'unknown'}
                    </div>
                    <div className="mt-1 text-xs text-white/40">
                      audio: {activeSequenceBundle.audioPlaceholders[index] || 'placeholder'}
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-xl border border-dashed border-white/[0.08] px-3 py-4 text-sm text-white/35">
                  画布内 Shot 视频批准之后，这里会输出可发送到预剪辑阶段的 sequence bundle。
                </div>
              )}
            </div>
          </div>
        </aside>
      </div>

      <div className="border-t border-white/[0.06] px-4 py-3 text-xs text-white/35">
        Storyboard clips {storyboardClips.length} · Video clips {videoClips.length}
      </div>
    </div>
  );
}
