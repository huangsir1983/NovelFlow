'use client';

import { memo, useCallback, useEffect, useRef } from 'react';
import { useReactFlow } from '@xyflow/react';
import { useProjectStore } from '../../../stores/projectStore';
import { useBoardStore } from '../../../stores/boardStore';
import { useCanvasStore } from '../../../stores/canvasStore';

function VideoPreviewPanelInner() {
  const scenes = useProjectStore((s) => s.scenes);
  const shots = useProjectStore((s) => s.shots);
  const artifactsByShotId = useBoardStore((s) => s.artifactsByShotId);
  const rightPanelOpen = useCanvasStore((s) => s.rightPanelOpen);
  const focusedSceneId = useCanvasStore((s) => s.focusedSceneId);
  const setInspectedNode = useCanvasStore((s) => s.setInspectedNode);
  const setFocusedSceneId = useCanvasStore((s) => s.setFocusedSceneId);
  const nodes = useCanvasStore((s) => s.nodes);
  const reactFlow = useReactFlow();
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to focused scene
  useEffect(() => {
    if (!focusedSceneId || !scrollRef.current) return;
    const el = scrollRef.current.querySelector(`[data-scene-id="${focusedSceneId}"]`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [focusedSceneId]);

  const handleVideoClick = useCallback(
    (shotId: string, sceneId: string) => {
      const videoNodeId = `video-${shotId}`;
      setInspectedNode(videoNodeId);
      setFocusedSceneId(sceneId);

      const videoNode = nodes.find((n) => n.id === videoNodeId);
      if (videoNode) {
        reactFlow.fitView({
          nodes: [videoNode],
          padding: 0.5,
          duration: 400,
        });
      }
    },
    [nodes, reactFlow, setInspectedNode, setFocusedSceneId],
  );

  if (!rightPanelOpen) return null;

  const sortedScenes = [...scenes].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));

  return (
    <div className="pointer-events-auto absolute right-3 top-[60px] z-20 w-[280px] max-h-[calc(100%-120px)] flex flex-col rounded-xl border border-white/[0.08] bg-[#0a0f1a] backdrop-blur-xl overflow-hidden shadow-2xl">
      {/* Header */}
      <div className="shrink-0 border-b border-white/[0.06] px-4 py-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-white/70">视频预览</span>
          <span className="text-[10px] text-white/30">
            {Object.values(artifactsByShotId).flat().filter((a) => a?.type === 'video').length} 个视频
          </span>
        </div>
      </div>

      {/* Video list grouped by scene */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-2 space-y-3 scrollbar-thin">
        {sortedScenes.length === 0 ? (
          <div className="py-8 text-center text-[11px] text-white/25">
            暂无视频
          </div>
        ) : (
          sortedScenes.map((scene) => {
            const sceneShots = shots
              .filter((s) => s.scene_id === scene.id)
              .sort((a, b) => (a.shot_number || 0) - (b.shot_number || 0));

            const hasAnyVideo = sceneShots.some(
              (s) => (artifactsByShotId[s.id] || []).some((a) => a?.type === 'video'),
            );

            return (
              <div key={scene.id} data-scene-id={scene.id}>
                {/* Scene group header */}
                <div className={`text-[10px] font-medium mb-1.5 px-1 ${
                  focusedSceneId === scene.id ? 'text-cyan-300/70' : 'text-white/35'
                }`}>
                  S{scene.order ?? 0} · {scene.heading || '未命名'}
                </div>

                {/* Shot video cards */}
                <div className="space-y-1.5">
                  {sceneShots.map((shot) => {
                    const artifacts = artifactsByShotId[shot.id] || [];
                    const videoArtifact = artifacts.find((a) => a?.type === 'video');

                    return (
                      <button
                        key={shot.id}
                        onClick={() => handleVideoClick(shot.id, scene.id)}
                        className="w-full rounded-lg border border-white/[0.06] bg-white/[0.02] p-2 text-left hover:bg-white/[0.04] transition-all"
                      >
                        <div className="flex gap-2">
                          {/* Thumbnail */}
                          <div className="w-[72px] h-[48px] rounded bg-white/5 flex-shrink-0 overflow-hidden flex items-center justify-center">
                            {videoArtifact ? (
                              <span className="text-[9px] text-emerald-400/50">▶</span>
                            ) : (
                              <span className="text-[9px] text-white/15">▶</span>
                            )}
                          </div>

                          {/* Info */}
                          <div className="flex-1 min-w-0">
                            <div className="text-[10px] text-white/60 font-medium">
                              Shot {shot.shot_number || 0}
                            </div>
                            <div className="text-[9px] text-white/30 mt-0.5 truncate">
                              {shot.description || '暂无描述'}
                            </div>
                            {videoArtifact ? (
                              <span className="inline-block mt-1 text-[8px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400/70">
                                {videoArtifact.status === 'approved' ? '已审批' : '已生成'}
                              </span>
                            ) : (
                              <span className="inline-block mt-1 text-[8px] px-1.5 py-0.5 rounded bg-white/5 text-white/25">
                                待生成
                              </span>
                            )}
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

export const VideoPreviewPanel = memo(VideoPreviewPanelInner);
