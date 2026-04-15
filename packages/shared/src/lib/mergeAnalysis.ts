/**
 * Shared merge analysis utilities — used by CanvasBottomToolbar and BoxSelectExecutor.
 */
import type { Node } from '@xyflow/react';
import { fetchAPI } from './api';
import type { MergeAnalysisResult, MergeAnalysisRequest } from '../types';
import { useCanvasStore } from '../stores/canvasStore';

/**
 * Call AI merge analysis endpoint for a set of nodes.
 * Filters for shot-type nodes, extracts storyboard data, and POSTs to backend.
 */
export async function analyzeMerge(
  sceneId: string,
  nodes: Node[],
  projectId?: string,
): Promise<MergeAnalysisResult> {
  const storyboardNodes = nodes
    .filter((n) => (n.data as Record<string, unknown>).nodeType === 'shot')
    .map((n) => {
      const d = n.data as Record<string, unknown>;
      return {
        id: n.id,
        label: (d.label as string) || '',
        text: (d.description as string) || '',
        emotion: (d.emotion as string) || '',
        shotType: (d.framing as string) || 'medium',
        estimatedDuration: ((d.durationEstimateMs as number) || 5000) / 1000,
      };
    });

  return fetchAPI<MergeAnalysisResult>(
    '/api/canvas/agent/merge-analysis',
    {
      method: 'POST',
      body: JSON.stringify({
        scene_id: sceneId,
        storyboard_nodes: storyboardNodes,
        project_id: projectId,
      } satisfies MergeAnalysisRequest),
    },
  );
}

/**
 * Apply merge decisions: POST to backend, update canvasStore.mergeGroups.
 * Returns the created groups array.
 */
export async function applyMergeDecisions(
  result: MergeAnalysisResult,
  sceneId: string,
  projectId: string,
) {
  const resp = await fetchAPI<{
    groups: Array<{
      groupId: string;
      shotIds: string[];
      totalDuration: number;
      driftRisk: string;
      recommendedProvider: string;
      mergeRationale: string;
    }>;
  }>('/api/canvas/shot-groups', {
    method: 'POST',
    body: JSON.stringify({
      project_id: projectId,
      scene_id: sceneId,
      decisions: result.decisions.map((d) => ({
        groupId: d.groupId,
        shotNodeIds: d.shotNodeIds,
        totalDuration: d.totalDuration,
        reason: d.reason,
        driftRisk: d.driftRisk,
        recommendedProvider: d.recommendedProvider,
      })),
    }),
  });

  const groups = (resp.groups || []).map((g) => ({
    groupId: g.groupId,
    shotIds: g.shotIds,
    totalDuration: g.totalDuration,
    driftRisk: g.driftRisk as 'low' | 'medium' | 'high',
    recommendedProvider: g.recommendedProvider,
    mergeRationale: g.mergeRationale,
    // assembledPrompt 将由 MergedVideoPanel 在展开时通过 assembleSegmentPrompt 生成
  }));

  useCanvasStore.getState().setMergeGroups(groups);
  return groups;
}
