'use client';

// ══════════════════════════════════════════════════════════════
// Canvas Page — 无限画布独立页面入口
// /projects/[id]/canvas
// ══════════════════════════════════════════════════════════════

import { useEffect, useCallback, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useProjectStore } from '@unrealmake/shared/stores/projectStore';
import { useInfiniteCanvasStore } from '@unrealmake/shared/stores/infiniteCanvasStore';
import { useCanvasProjectStore } from '@unrealmake/shared/stores/canvasProjectStore';
import { useCanvasAgentStore } from '@unrealmake/shared/stores/canvasAgentStore';
import { InfiniteCanvas } from '@unrealmake/shared/components/infinite-canvas';
import { NodeInspector } from '@unrealmake/shared/components/infinite-canvas/panels/NodeInspector';
import { ChainProgressPanel } from '@unrealmake/shared/components/infinite-canvas/panels/ChainProgressPanel';
import { loadProjectToCanvas } from '@unrealmake/shared/services/canvasIntegrationAdapter';
import { fetchAPI } from '@unrealmake/shared/lib';
import type { Project, Scene, Shot, Character, Location, Prop, Chapter } from '@unrealmake/shared/types';

export default function CanvasPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params?.id as string;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const selectedNodeIds = useInfiniteCanvasStore((s) => s.selectedNodeIds);
  const firstSelectedId = Array.from(selectedNodeIds)[0];

  // 加载项目数据到画布
  useEffect(() => {
    if (!projectId) return;

    async function loadData() {
      try {
        setLoading(true);
        setError(null);

        // 从后端获取项目数据
        const [project, chapters, scenes, shots, characters, locations, props] = await Promise.all([
          fetchAPI(`/api/projects/${projectId}`) as Promise<Project>,
          fetchAPI(`/api/projects/${projectId}/chapters`) as Promise<Chapter[]>,
          fetchAPI(`/api/projects/${projectId}/scenes`) as Promise<Scene[]>,
          fetchAPI(`/api/projects/${projectId}/shots`) as Promise<Shot[]>,
          fetchAPI(`/api/projects/${projectId}/characters`) as Promise<Character[]>,
          fetchAPI(`/api/projects/${projectId}/locations`) as Promise<Location[]>,
          fetchAPI(`/api/projects/${projectId}/props`) as Promise<Prop[]>,
        ]);

        // 转换为画布节点
        loadProjectToCanvas({
          projectId,
          projectName: project.name,
          chapters: chapters || [],
          scenes: scenes || [],
          shots: shots || [],
          characters: characters || [],
          locations: locations || [],
          props: props || [],
        });
      } catch (err) {
        console.error('Failed to load canvas data:', err);
        setError(err instanceof Error ? err.message : '加载画布数据失败');
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [projectId]);

  // 批量执行回调
  const handleRunBatch = useCallback(() => {
    // TODO: Phase 3 实现
    console.log('Batch execute triggered');
  }, []);

  // Agent 自动分配回调
  const handleRunAgentAssign = useCallback(() => {
    // TODO: Phase 2 实现
    console.log('Agent assign triggered');
  }, []);

  // 节点操作回调
  const handleRunNode = useCallback((nodeId: string) => {
    console.log('Run node:', nodeId);
  }, []);

  const handleEditPrompt = useCallback((nodeId: string) => {
    console.log('Edit prompt:', nodeId);
  }, []);

  const handleViewChain = useCallback((nodeId: string) => {
    console.log('View chain:', nodeId);
  }, []);

  if (loading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center" style={{ background: '#0a0a1a' }}>
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
          <span className="text-sm text-white/40">加载画布数据中...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-screen w-screen items-center justify-center" style={{ background: '#0a0a1a' }}>
        <div className="flex flex-col items-center gap-3">
          <span className="text-sm text-red-400">{error}</span>
          <button
            onClick={() => router.back()}
            className="rounded-md border border-white/10 px-4 py-2 text-sm text-white/60 hover:text-white/80"
          >
            返回
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen w-screen" style={{ background: '#0a0a1a' }}>
      {/* 顶部导航条 */}
      <div className="absolute top-0 left-0 right-0 z-50 flex h-12 items-center justify-between border-b px-4"
        style={{ background: '#12122a', borderColor: 'rgba(255,255,255,0.06)' }}>
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.back()}
            className="text-sm text-white/40 hover:text-white/70"
          >
            ← 返回
          </button>
          <span className="text-sm font-medium text-white/80">
            {useCanvasProjectStore.getState().projectName || '无限画布'}
          </span>
          <span className="rounded-md px-2 py-0.5 text-xs" style={{ background: 'rgba(99,102,241,0.15)', color: '#6366f1' }}>
            画布模式
          </span>
        </div>
      </div>

      {/* 主画布区域 */}
      <div className="flex flex-1 pt-12">
        <div className="flex-1">
          <InfiniteCanvas
            onRunBatch={handleRunBatch}
            onRunAgentAssign={handleRunAgentAssign}
          />
        </div>

        {/* 右侧面板 */}
        <div className="flex w-[268px] shrink-0 flex-col overflow-hidden border-l"
          style={{ background: '#12122a', borderColor: 'rgba(255,255,255,0.06)' }}>
          <div className="border-b px-3.5 py-3 text-[13px] font-medium text-white/80"
            style={{ borderColor: 'rgba(255,255,255,0.06)' }}>
            场景资产 & 工作流
          </div>
          <div className="flex-1 overflow-y-auto p-3">
            <ChainProgressPanel />
            {firstSelectedId && (
              <NodeInspector
                nodeId={firstSelectedId}
                onRunNode={handleRunNode}
                onEditPrompt={handleEditPrompt}
                onViewChain={handleViewChain}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
