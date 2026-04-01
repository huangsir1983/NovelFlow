'use client';

import { create } from 'zustand';
import { createEmptyWritebackPreview, createInitialNodeRuns } from '../lib/production';
import type { BoardViewMode, CinemaLabConfig, ShotCard, SpatialRelation } from '../types/board';
import type {
  BoardConsoleEntry,
  SceneStoryboardReadinessReport,
  ShotNodeRun,
  ShotProductionSpec,
  ShotRuntimeArtifact,
  StoryboardVideoMode,
  VideoModeDecision,
  WorkflowModule,
  WritebackPreview,
} from '../types/production';

type BoardEntryMode = 'production' | 'patch';

function resolveSelectedMode(
  decision: VideoModeDecision,
  module: WorkflowModule | undefined,
  preferredMode?: StoryboardVideoMode,
) {
  const supportedModes = module
    ? decision.availableModes.filter((mode) => module.supportedVideoModes.includes(mode))
    : decision.availableModes;

  if (preferredMode && supportedModes.includes(preferredMode)) {
    return preferredMode;
  }
  if (decision.recommendedMode && supportedModes.includes(decision.recommendedMode)) {
    return decision.recommendedMode;
  }
  if (supportedModes.length > 0) {
    return supportedModes[0];
  }
  if (preferredMode && decision.availableModes.includes(preferredMode)) {
    return preferredMode;
  }
  return decision.recommendedMode || decision.availableModes[0];
}

function withResolvedMode(
  spec: ShotProductionSpec,
  module: WorkflowModule | undefined,
  preferredMode?: StoryboardVideoMode,
): ShotProductionSpec {
  return {
    ...spec,
    videoModeDecision: {
      ...spec.videoModeDecision,
      selectedMode: resolveSelectedMode(spec.videoModeDecision, module, preferredMode),
    },
  };
}

interface BoardStoreState {
  projectId: string | null;
  viewMode: BoardViewMode;
  shotCards: ShotCard[];
  relations: SpatialRelation[];
  cinemaLabConfig: CinemaLabConfig;
  selectedShotCardId: string | null;

  sceneReports: SceneStoryboardReadinessReport[];
  productionSpecs: ShotProductionSpec[];
  shotQueue: string[];
  workflowModules: WorkflowModule[];
  selectedShotId: string | null;
  selectedModuleId: string | null;
  focusedSceneId: string | null;
  entryMode: BoardEntryMode;
  nodeRunsByShotId: Record<string, ShotNodeRun[]>;
  artifactsByShotId: Record<string, ShotRuntimeArtifact[]>;
  writebacksByShotId: Record<string, WritebackPreview>;
  runConsole: BoardConsoleEntry[];

  setProjectId: (projectId: string | null) => void;
  setViewMode: (viewMode: BoardViewMode) => void;
  setShotCards: (shotCards: ShotCard[]) => void;
  upsertShotCard: (shotCard: ShotCard) => void;
  setRelations: (relations: SpatialRelation[]) => void;
  setCinemaLabConfig: (config: CinemaLabConfig) => void;
  selectShotCard: (shotCardId: string | null) => void;

  hydrateProductionBoard: (
    projectId: string | null,
    sceneReports: SceneStoryboardReadinessReport[],
    productionSpecs: ShotProductionSpec[],
    workflowModules: WorkflowModule[],
  ) => void;
  setBoardEntryContext: (sceneId: string | null, entryMode: BoardEntryMode) => void;
  selectShot: (shotId: string | null) => void;
  instantiateModuleForShot: (shotId: string, moduleId: string) => void;
  setShotVideoMode: (shotId: string, mode: StoryboardVideoMode) => void;
  setShotNodeRuns: (shotId: string, runs: ShotNodeRun[]) => void;
  setShotArtifacts: (shotId: string, artifacts: ShotRuntimeArtifact[]) => void;
  setShotWriteback: (shotId: string, writeback: WritebackPreview) => void;
  appendRunConsole: (entry: BoardConsoleEntry) => void;
  reset: () => void;
}

const defaultCinemaLabConfig: CinemaLabConfig = {
  director_method_enabled: false,
  sound_narrative_enabled: false,
  motif_tracking_enabled: false,
  cross_culture_preset: 'auto',
};

const initialState = {
  projectId: null,
  viewMode: 'creative' as BoardViewMode,
  shotCards: [],
  relations: [],
  cinemaLabConfig: defaultCinemaLabConfig,
  selectedShotCardId: null,
  sceneReports: [] as SceneStoryboardReadinessReport[],
  productionSpecs: [] as ShotProductionSpec[],
  shotQueue: [] as string[],
  workflowModules: [] as WorkflowModule[],
  selectedShotId: null,
  selectedModuleId: null,
  focusedSceneId: null,
  entryMode: 'production' as BoardEntryMode,
  nodeRunsByShotId: {} as Record<string, ShotNodeRun[]>,
  artifactsByShotId: {} as Record<string, ShotRuntimeArtifact[]>,
  writebacksByShotId: {} as Record<string, WritebackPreview>,
  runConsole: [] as BoardConsoleEntry[],
};

export const useBoardStore = create<BoardStoreState>((set) => ({
  ...initialState,

  setProjectId: (projectId) => set({ projectId }),
  setViewMode: (viewMode) => set({ viewMode }),
  setShotCards: (shotCards) => set({ shotCards }),
  upsertShotCard: (shotCard) =>
    set((state) => {
      const hit = state.shotCards.find((item) => item.id === shotCard.id);
      if (!hit) {
        return { shotCards: [...state.shotCards, shotCard] };
      }
      return {
        shotCards: state.shotCards.map((item) => (item.id === shotCard.id ? shotCard : item)),
      };
    }),
  setRelations: (relations) => set({ relations }),
  setCinemaLabConfig: (cinemaLabConfig) => set({ cinemaLabConfig }),
  selectShotCard: (selectedShotCardId) => set({ selectedShotCardId }),

  hydrateProductionBoard: (projectId, sceneReports, productionSpecs, workflowModules) =>
    set((state) => {
      const nextSpecs = productionSpecs.map((spec) => {
        const existingSpec = state.productionSpecs.find((candidate) => candidate.shotId === spec.shotId);
        const module =
          workflowModules.find((candidate) => candidate.id === (existingSpec?.moduleId || spec.moduleId)) ||
          workflowModules.find((candidate) => candidate.id === spec.moduleId) ||
          workflowModules[0];

        return withResolvedMode(spec, module, existingSpec?.videoModeDecision.selectedMode);
      });
      const nextShotQueue = nextSpecs.map((spec) => spec.shotId);
      const nextNodeRunsByShotId: Record<string, ShotNodeRun[]> = {};
      const nextArtifactsByShotId: Record<string, ShotRuntimeArtifact[]> = {};
      const nextWritebacksByShotId: Record<string, WritebackPreview> = {};

      nextSpecs.forEach((spec) => {
        const module =
          workflowModules.find((candidate) => candidate.id === spec.moduleId) || workflowModules[0];
        nextNodeRunsByShotId[spec.shotId] =
          state.nodeRunsByShotId[spec.shotId] || (module ? createInitialNodeRuns(spec, module) : []);
        nextArtifactsByShotId[spec.shotId] = state.artifactsByShotId[spec.shotId] || [];
        nextWritebacksByShotId[spec.shotId] =
          state.writebacksByShotId[spec.shotId] || createEmptyWritebackPreview(spec);
      });

      const selectedShotId =
        state.selectedShotId && nextShotQueue.includes(state.selectedShotId)
          ? state.selectedShotId
          : nextShotQueue[0] || null;
      const selectedSpec = nextSpecs.find((spec) => spec.shotId === selectedShotId);
      const focusedSceneId =
        state.focusedSceneId && sceneReports.some((report) => report.sceneId === state.focusedSceneId)
          ? state.focusedSceneId
          : selectedSpec?.sceneId || sceneReports[0]?.sceneId || null;

      return {
        projectId,
        sceneReports,
        productionSpecs: nextSpecs,
        shotQueue: nextShotQueue,
        workflowModules,
        selectedShotId,
        selectedModuleId: selectedSpec?.moduleId || workflowModules[0]?.id || null,
        focusedSceneId,
        nodeRunsByShotId: nextNodeRunsByShotId,
        artifactsByShotId: nextArtifactsByShotId,
        writebacksByShotId: nextWritebacksByShotId,
      };
    }),

  setBoardEntryContext: (focusedSceneId, entryMode) =>
    set((state) => {
      const sceneShots = state.productionSpecs.filter((spec) => spec.sceneId === focusedSceneId);
      const selectedShotId =
        sceneShots.find((spec) => spec.storyboardStatus !== 'blocked')?.shotId ||
        sceneShots[0]?.shotId ||
        state.selectedShotId;
      const selectedSpec = state.productionSpecs.find((spec) => spec.shotId === selectedShotId);

      return {
        focusedSceneId,
        entryMode,
        selectedShotId,
        selectedModuleId: selectedSpec?.moduleId || state.selectedModuleId,
      };
    }),

  selectShot: (selectedShotId) =>
    set((state) => {
      const selectedSpec = state.productionSpecs.find((spec) => spec.shotId === selectedShotId);
      return {
        selectedShotId,
        focusedSceneId: selectedSpec?.sceneId || state.focusedSceneId,
        selectedModuleId: selectedSpec?.moduleId || state.selectedModuleId,
      };
    }),

  instantiateModuleForShot: (shotId, moduleId) =>
    set((state) => {
      const module = state.workflowModules.find((candidate) => candidate.id === moduleId);
      const nextSpecs = state.productionSpecs.map((spec) =>
        spec.shotId === shotId && module
          ? {
              ...withResolvedMode(spec, module, spec.videoModeDecision.selectedMode),
              moduleId,
            }
          : spec,
      );
      const targetSpec = nextSpecs.find((spec) => spec.shotId === shotId);

      return {
        productionSpecs: nextSpecs,
        selectedShotId: shotId,
        selectedModuleId: moduleId,
        nodeRunsByShotId:
          targetSpec && module
            ? {
                ...state.nodeRunsByShotId,
                [shotId]: createInitialNodeRuns(targetSpec, module),
              }
            : state.nodeRunsByShotId,
        artifactsByShotId:
          targetSpec && module
            ? {
                ...state.artifactsByShotId,
                [shotId]: [],
              }
            : state.artifactsByShotId,
        writebacksByShotId:
          targetSpec && module
            ? {
                ...state.writebacksByShotId,
                [shotId]: createEmptyWritebackPreview(targetSpec),
              }
            : state.writebacksByShotId,
      };
    }),

  setShotVideoMode: (shotId, mode) =>
    set((state) => {
      const currentSpec = state.productionSpecs.find((spec) => spec.shotId === shotId);
      if (!currentSpec || !currentSpec.videoModeDecision.availableModes.includes(mode)) {
        return {};
      }

      const currentModule = state.workflowModules.find((candidate) => candidate.id === currentSpec.moduleId);
      const preferredModuleIds = [currentSpec.moduleId, ...currentSpec.recommendedModuleIds];
      const resolvedModule =
        (currentModule?.supportedVideoModes.includes(mode) ? currentModule : undefined) ||
        preferredModuleIds
          .map((moduleId) => state.workflowModules.find((candidate) => candidate.id === moduleId))
          .find((candidate) => candidate?.supportedVideoModes.includes(mode)) ||
        state.workflowModules.find((candidate) => candidate.supportedVideoModes.includes(mode)) ||
        currentModule;

      if (!resolvedModule) {
        return {};
      }

      const nextSpecs = state.productionSpecs.map((spec) =>
        spec.shotId === shotId
          ? {
              ...withResolvedMode(spec, resolvedModule, mode),
              moduleId: resolvedModule.id,
            }
          : spec,
      );
      const targetSpec = nextSpecs.find((spec) => spec.shotId === shotId);

      return {
        productionSpecs: nextSpecs,
        selectedShotId: shotId,
        selectedModuleId: resolvedModule.id,
        nodeRunsByShotId:
          targetSpec
            ? {
                ...state.nodeRunsByShotId,
                [shotId]: createInitialNodeRuns(targetSpec, resolvedModule),
              }
            : state.nodeRunsByShotId,
        artifactsByShotId:
          targetSpec
            ? {
                ...state.artifactsByShotId,
                [shotId]: [],
              }
            : state.artifactsByShotId,
        writebacksByShotId:
          targetSpec
            ? {
                ...state.writebacksByShotId,
                [shotId]: createEmptyWritebackPreview(targetSpec),
              }
            : state.writebacksByShotId,
      };
    }),

  setShotNodeRuns: (shotId, runs) =>
    set((state) => ({
      nodeRunsByShotId: {
        ...state.nodeRunsByShotId,
        [shotId]: runs,
      },
    })),

  setShotArtifacts: (shotId, artifacts) =>
    set((state) => ({
      artifactsByShotId: {
        ...state.artifactsByShotId,
        [shotId]: artifacts,
      },
    })),

  setShotWriteback: (shotId, writeback) =>
    set((state) => ({
      writebacksByShotId: {
        ...state.writebacksByShotId,
        [shotId]: writeback,
      },
    })),

  appendRunConsole: (entry) =>
    set((state) => ({
      runConsole: [entry, ...state.runConsole].slice(0, 40),
    })),

  reset: () => set(initialState),
}));
