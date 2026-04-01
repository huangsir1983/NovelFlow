'use client';

import { memo, useCallback, useRef } from 'react';
import { useReactFlow } from '@xyflow/react';
import { useProjectStore } from '../../../stores/projectStore';
import { useBoardStore } from '../../../stores/boardStore';
import { useCanvasStore } from '../../../stores/canvasStore';
import { getSceneNodeIds } from '../../../lib/canvasLayout';

function SceneListPanelInner() {
  const scenes = useProjectStore((s) => s.scenes);
  const productionSpecs = useBoardStore((s) => s.productionSpecs);
  const leftPanelOpen = useCanvasStore((s) => s.leftPanelOpen);
  const focusedSceneId = useCanvasStore((s) => s.focusedSceneId);
  const setFocusedSceneId = useCanvasStore((s) => s.setFocusedSceneId);
  const nodes = useCanvasStore((s) => s.nodes);
  const reactFlow = useReactFlow();

  const handleSceneClick = useCallback(
    (sceneId: string) => {
      setFocusedSceneId(sceneId);

      // Navigate canvas to this scene's nodes
      const sceneNodeIds = getSceneNodeIds(sceneId, nodes);
      if (sceneNodeIds.length > 0) {
        const sceneNodes = nodes.filter((n) => sceneNodeIds.includes(n.id));
        reactFlow.fitView({
          nodes: sceneNodes,
          padding: 0.3,
          duration: 400,
        });
      }
    },
    [nodes, reactFlow, setFocusedSceneId],
  );

  if (!leftPanelOpen) return null;

  const sortedScenes = [...scenes].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));

  return (
    <div className="pointer-events-auto absolute left-3 top-[60px] z-20 w-[260px] max-h-[calc(100%-120px)] flex flex-col rounded-xl border border-white/[0.08] bg-[#0a0f1a] backdrop-blur-xl overflow-hidden shadow-2xl">
      {/* Header */}
      <div className="shrink-0 border-b border-white/[0.06] px-4 py-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-white/70">剧本场景</span>
          <span className="text-[10px] text-white/30">{sortedScenes.length} 场</span>
        </div>
      </div>

      {/* Scene list */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5 scrollbar-thin">
        {sortedScenes.length === 0 ? (
          <div className="py-8 text-center text-[11px] text-white/25">
            暂无场景数据
          </div>
        ) : (
          sortedScenes.map((scene) => {
            const sceneShots = productionSpecs.filter((s) => s.sceneId === scene.id);
            const isFocused = focusedSceneId === scene.id;

            return (
              <button
                key={scene.id}
                data-scene-id={scene.id}
                onClick={() => handleSceneClick(scene.id)}
                className={`
                  w-full text-left rounded-lg p-2.5 transition-all
                  ${isFocused
                    ? 'bg-cyan-500/15 border border-cyan-400/30'
                    : 'bg-white/[0.02] border border-transparent hover:bg-white/[0.04] hover:border-white/[0.06]'
                  }
                `}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${
                    isFocused ? 'text-cyan-300 bg-cyan-400/15' : 'text-white/40 bg-white/5'
                  }`}>
                    S{scene.order ?? 0}
                  </span>
                  <span className={`text-[11px] font-medium truncate flex-1 ${
                    isFocused ? 'text-white/90' : 'text-white/60'
                  }`}>
                    {scene.heading || '未命名场景'}
                  </span>
                </div>

                {/* Location + shot count */}
                <div className="flex items-center gap-1.5 mt-1">
                  {scene.location && (
                    <span className="text-[9px] text-white/30 truncate max-w-[120px]">
                      {scene.location}
                    </span>
                  )}
                  <span className="text-[9px] text-white/20 ml-auto">
                    {sceneShots.length} 镜头
                  </span>
                </div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}

export const SceneListPanel = memo(SceneListPanelInner);
