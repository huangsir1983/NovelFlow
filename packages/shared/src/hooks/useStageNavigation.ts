'use client';

import { useMemo } from 'react';

export type StageRoute = 'workbench' | 'board' | 'preview';

export interface StageDescriptor {
  id: StageRoute;
  label: string;
  description: string;
}

const STAGE_DESCRIPTORS: StageDescriptor[] = [
  {
    id: 'workbench',
    label: 'Workbench',
    description: 'Sudowrite-style writing and story structure workbench.',
  },
  {
    id: 'board',
    label: 'Board',
    description: 'Tapnow/TapFlow-style executable infinite canvas.',
  },
  {
    id: 'preview',
    label: 'Preview',
    description: 'Premiere/CapCut-style previsualization and delivery.',
  },
];

export const STAGE_ROUTE_ORDER: StageRoute[] = STAGE_DESCRIPTORS.map((item) => item.id);

export function buildStagePath(projectId: string, stage: StageRoute): string {
  return `/projects/${projectId}/${stage}`;
}

export function getNextStageRoute(current: StageRoute): StageRoute | null {
  const index = STAGE_ROUTE_ORDER.indexOf(current);
  if (index === -1 || index === STAGE_ROUTE_ORDER.length - 1) {
    return null;
  }
  return STAGE_ROUTE_ORDER[index + 1];
}

export function getPreviousStageRoute(current: StageRoute): StageRoute | null {
  const index = STAGE_ROUTE_ORDER.indexOf(current);
  if (index <= 0) {
    return null;
  }
  return STAGE_ROUTE_ORDER[index - 1];
}

export function useStageNavigation(projectId?: string) {
  const normalizedProjectId = (projectId || '').trim();

  const stages = useMemo(() => STAGE_DESCRIPTORS, []);

  const getStagePath = (stage: StageRoute): string => {
    if (!normalizedProjectId) {
      return '#';
    }
    return buildStagePath(normalizedProjectId, stage);
  };

  return {
    stages,
    isReady: normalizedProjectId.length > 0,
    getStagePath,
    getNextStage: getNextStageRoute,
    getPreviousStage: getPreviousStageRoute,
  };
}
