'use client';

import { create } from 'zustand';
import type {
  Project, Chapter, Beat, Scene, Shot, ShotGroup, Character, Location,
  Prop, CharacterVariant, PipelinePhaseStatus,
} from '../types/project';

export type StageTab = 'info' | 'assets' | 'script' | 'canvas' | 'preview';
export type AssetFilter = 'all' | 'character' | 'location' | 'prop';

interface ProjectStoreState {
  // Data
  project: Project | null;
  chapters: Chapter[];
  beats: Beat[];
  scenes: Scene[];
  shots: Shot[];
  shotGroups: ShotGroup[];
  characters: Character[];
  locations: Location[];
  props: Prop[];
  characterVariants: CharacterVariant[];
  worldBuilding: Record<string, unknown>;
  styleGuide: Record<string, unknown>;

  // Selection state
  selectedChapterId: string | null;
  selectedBeatId: string | null;
  selectedSceneId: string | null;
  selectedCharacterId: string | null;
  activeSection: 'chapters' | 'characters' | 'scenes' | 'locations' | 'props' | 'variants' | 'all';

  // Asset detail selection
  selectedAssetId: string | null;
  selectedAssetType: 'character' | 'scene' | 'location' | 'prop' | 'variant' | null;
  assetImages: Record<string, Record<string, string>>; // {assetId: {slot: base64}}
  assetImageKeys: Record<string, Record<string, string>>; // {assetId: {slot: storage_key}}
  assetLoadingSlots: Record<string, Set<string>>; // {assetId: Set<slotKey>}
  assetErrorSlots: Record<string, Set<string>>; // {assetId: Set<slotKey>}

  // Stage tabs & asset filter
  activeStageTab: StageTab;
  assetFilter: AssetFilter;

  // Middle column view mode
  middleColumnMode: 'all' | 'single';

  // Loading state
  loading: boolean;
  importing: boolean;
  assetLibraryLocked: boolean;

  // Import task state
  importTaskId: string | null;
  importPhase: string | null;
  importProgress: Record<string, number>;

  // Novel analysis state (basic info tab)
  adaptationDirection: 'oscar_film' | 's_level_drama' | null;
  screenFormat: 'horizontal' | 'vertical' | null;
  stylePreset: 'realistic' | '3d_chinese' | '2d_chinese' | null;
  novelAnalysis: string;
  novelAnalysisJson: Record<string, unknown> | null;
  novelAnalysisStreaming: boolean;
  novelFullText: string;

  // Pipeline status (replaces page-local importSteps)
  pipelineStatus: Record<string, PipelinePhaseStatus>;
  pipelineError: string | null;

  // Actions
  setProject: (project: Project | null) => void;
  setChapters: (chapters: Chapter[]) => void;
  setBeats: (beats: Beat[]) => void;
  setScenes: (scenes: Scene[]) => void;
  setShots: (shots: Shot[]) => void;
  setShotGroups: (groups: ShotGroup[]) => void;
  setCharacters: (characters: Character[]) => void;
  setLocations: (locations: Location[]) => void;
  setProps: (props: Prop[]) => void;
  setCharacterVariants: (variants: CharacterVariant[]) => void;
  setWorldBuilding: (wb: Record<string, unknown>) => void;
  setStyleGuide: (sg: Record<string, unknown>) => void;

  // Incremental update actions (for SSE)
  addCharacter: (character: Character) => void;
  addScene: (scene: Scene) => void;
  addBeat: (beat: Beat) => void;
  addLocation: (location: Location) => void;
  addShot: (shot: Shot) => void;
  addShotGroup: (group: ShotGroup) => void;
  addProp: (prop: Prop) => void;
  addCharacterVariant: (variant: CharacterVariant) => void;

  selectChapter: (id: string | null) => void;
  selectBeat: (id: string | null) => void;
  selectScene: (id: string | null) => void;
  selectCharacter: (id: string | null) => void;
  setActiveSection: (section: 'chapters' | 'characters' | 'scenes' | 'locations' | 'props' | 'variants' | 'all') => void;

  // Asset detail selection
  selectAsset: (id: string | null, type: 'character' | 'scene' | 'location' | 'prop' | 'variant' | null) => void;
  setAssetImage: (assetId: string, slot: string, base64: string) => void;
  setAssetImageKey: (assetId: string, slot: string, storageKey: string) => void;
  addAssetLoadingSlot: (assetId: string, slot: string) => void;
  removeAssetLoadingSlot: (assetId: string, slot: string) => void;
  addAssetErrorSlot: (assetId: string, slot: string) => void;
  removeAssetErrorSlot: (assetId: string, slot: string) => void;

  // Stage tabs & filter
  setActiveStageTab: (tab: StageTab) => void;
  setAssetFilter: (filter: AssetFilter) => void;

  // Middle column
  setMiddleColumnMode: (mode: 'all' | 'single') => void;

  setLoading: (loading: boolean) => void;
  setImporting: (importing: boolean) => void;
  setAssetLibraryLocked: (locked: boolean) => void;
  setImportTaskId: (taskId: string | null) => void;
  setImportPhase: (phase: string | null) => void;
  setImportProgress: (progress: Record<string, number>) => void;

  // Novel analysis actions
  setAdaptationDirection: (dir: 'oscar_film' | 's_level_drama' | null) => void;
  setScreenFormat: (format: 'horizontal' | 'vertical' | null) => void;
  setStylePreset: (preset: 'realistic' | '3d_chinese' | '2d_chinese' | null) => void;
  setNovelAnalysis: (text: string) => void;
  setNovelAnalysisJson: (data: Record<string, unknown> | null) => void;
  appendNovelAnalysis: (chunk: string) => void;
  setNovelAnalysisStreaming: (streaming: boolean) => void;
  setNovelFullText: (text: string) => void;

  // Optimistic project creation — store project in memory before backend confirms
  pendingSaveError: string | null;
  setPendingSaveError: (error: string | null) => void;

  // Pipeline status
  updatePipelinePhase: (phase: string, update: Partial<PipelinePhaseStatus>) => void;
  initPipelineStatus: () => void;
  setPipelineError: (error: string | null) => void;

  updateBeat: (id: string, updates: Partial<Beat>) => void;
  updateScene: (id: string, updates: Partial<Scene>) => void;

  removeCharacter: (id: string) => void;
  removeLocation: (id: string) => void;
  removeProp: (id: string) => void;
  removeCharacterVariant: (id: string) => void;

  reset: () => void;
}

const PIPELINE_PHASES = ['streaming', 'enrichment', 'knowledge', 'shots', 'merging', 'prompts'] as const;

const initialPipelineStatus: Record<string, PipelinePhaseStatus> = {};
PIPELINE_PHASES.forEach((p) => {
  initialPipelineStatus[p] = { status: 'pending' };
});

const initialState = {
  project: null,
  chapters: [],
  beats: [],
  scenes: [],
  shots: [],
  shotGroups: [],
  characters: [],
  locations: [],
  props: [],
  characterVariants: [],
  worldBuilding: {},
  styleGuide: {},
  selectedChapterId: null,
  selectedBeatId: null,
  selectedSceneId: null,
  selectedCharacterId: null,
  activeSection: 'chapters' as const,
  selectedAssetId: null,
  selectedAssetType: null,
  assetImages: {},
  assetImageKeys: {},
  assetLoadingSlots: {},
  assetErrorSlots: {},
  activeStageTab: 'info' as StageTab,
  assetFilter: 'all' as AssetFilter,
  middleColumnMode: 'all' as const,
  loading: false,
  importing: false,
  assetLibraryLocked: false,
  importTaskId: null,
  importPhase: null,
  importProgress: {},
  adaptationDirection: null,
  screenFormat: null,
  stylePreset: null,
  novelAnalysis: '',
  novelAnalysisJson: null,
  novelAnalysisStreaming: false,
  novelFullText: '',
  pendingSaveError: null,
  pipelineStatus: { ...initialPipelineStatus },
  pipelineError: null,
};

export const useProjectStore = create<ProjectStoreState>((set) => ({
  ...initialState,

  setProject: (project) => set({ project }),
  setChapters: (chapters) => set({ chapters }),
  setBeats: (beats) => set({ beats }),
  setScenes: (scenes) => set({ scenes }),
  setShots: (shots) => set({ shots }),
  setShotGroups: (shotGroups) => set({ shotGroups }),
  setCharacters: (characters) => {
    // Deduplicate by name (keep first occurrence)
    const seen = new Set<string>();
    const deduped = characters.filter((c) => {
      const key = c.name.trim();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
    set({ characters: deduped });
  },
  setLocations: (locations) => set({ locations }),
  setProps: (props) => set({ props }),
  setCharacterVariants: (characterVariants) => set({ characterVariants }),
  setWorldBuilding: (worldBuilding) => set({ worldBuilding }),
  setStyleGuide: (styleGuide) => set({ styleGuide }),

  // Incremental updates for SSE streaming
  addCharacter: (character) =>
    set((state) => {
      const exists = state.characters.some((c) => c.name.trim() === character.name.trim());
      if (exists) return state;
      return { characters: [...state.characters, character] };
    }),
  addScene: (scene) =>
    set((state) => ({ scenes: [...state.scenes, scene] })),
  addBeat: (beat) =>
    set((state) => ({ beats: [...state.beats, beat] })),
  addLocation: (location) =>
    set((state) => ({ locations: [...state.locations, location] })),
  addShot: (shot) =>
    set((state) => ({ shots: [...state.shots, shot] })),
  addShotGroup: (group) =>
    set((state) => ({ shotGroups: [...state.shotGroups, group] })),
  addProp: (prop) =>
    set((state) => ({ props: [...state.props, prop] })),
  addCharacterVariant: (variant) =>
    set((state) => ({ characterVariants: [...state.characterVariants, variant] })),

  selectChapter: (id) => set({ selectedChapterId: id }),
  selectBeat: (id) => set({ selectedBeatId: id }),
  selectScene: (id) => set({ selectedSceneId: id }),
  selectCharacter: (id) => set({ selectedCharacterId: id }),
  setActiveSection: (section) => set({ activeSection: section }),

  selectAsset: (id, type) => set({ selectedAssetId: id, selectedAssetType: type }),
  setAssetImage: (assetId, slot, value) =>
    set((state) => {
      const next = {
        ...state.assetImages,
        [assetId]: { ...state.assetImages[assetId], [slot]: value },
      };
      // Persist to localStorage scoped by current project (skip for URL values)
      if (!value.startsWith('http')) {
        try {
          const pid = state.scenes[0]?.project_id || state.characters[0]?.project_id || '';
          if (pid) localStorage.setItem(`assetImages_${pid}`, JSON.stringify(next));
        } catch { /* quota exceeded — ignore */ }
      }
      return { assetImages: next };
    }),
  setAssetImageKey: (assetId, slot, storageKey) =>
    set((state) => ({
      assetImageKeys: {
        ...state.assetImageKeys,
        [assetId]: { ...state.assetImageKeys[assetId], [slot]: storageKey },
      },
    })),
  addAssetLoadingSlot: (assetId, slot) =>
    set((state) => {
      const prev = state.assetLoadingSlots[assetId] || new Set();
      const next = new Set(prev);
      next.add(slot);
      return { assetLoadingSlots: { ...state.assetLoadingSlots, [assetId]: next } };
    }),
  removeAssetLoadingSlot: (assetId, slot) =>
    set((state) => {
      const prev = state.assetLoadingSlots[assetId];
      if (!prev) return state;
      const next = new Set(prev);
      next.delete(slot);
      return { assetLoadingSlots: { ...state.assetLoadingSlots, [assetId]: next } };
    }),
  addAssetErrorSlot: (assetId, slot) =>
    set((state) => {
      const prev = state.assetErrorSlots[assetId] || new Set();
      const next = new Set(prev);
      next.add(slot);
      return { assetErrorSlots: { ...state.assetErrorSlots, [assetId]: next } };
    }),
  removeAssetErrorSlot: (assetId, slot) =>
    set((state) => {
      const prev = state.assetErrorSlots[assetId];
      if (!prev) return state;
      const next = new Set(prev);
      next.delete(slot);
      return { assetErrorSlots: { ...state.assetErrorSlots, [assetId]: next } };
    }),

  setActiveStageTab: (tab) => set({ activeStageTab: tab }),
  setAssetFilter: (filter) => set({ assetFilter: filter }),
  setMiddleColumnMode: (middleColumnMode) => set({ middleColumnMode }),

  setLoading: (loading) => set({ loading }),
  setImporting: (importing) => set({ importing }),
  setAssetLibraryLocked: (assetLibraryLocked) => set({ assetLibraryLocked }),
  setImportTaskId: (importTaskId) => set({ importTaskId }),
  setImportPhase: (importPhase) => set({ importPhase }),
  setImportProgress: (importProgress) => set({ importProgress }),

  // Novel analysis actions
  setAdaptationDirection: (adaptationDirection) => set({ adaptationDirection }),
  setScreenFormat: (screenFormat) => set({ screenFormat }),
  setStylePreset: (stylePreset) => set({ stylePreset }),
  setNovelAnalysis: (novelAnalysis) => set({ novelAnalysis }),
  setNovelAnalysisJson: (novelAnalysisJson) => set({ novelAnalysisJson }),
  appendNovelAnalysis: (chunk) =>
    set((state) => ({ novelAnalysis: state.novelAnalysis + chunk })),
  setNovelAnalysisStreaming: (novelAnalysisStreaming) => set({ novelAnalysisStreaming }),
  setNovelFullText: (novelFullText) => set({ novelFullText }),

  // Optimistic project creation
  setPendingSaveError: (pendingSaveError) => set({ pendingSaveError }),

  updatePipelinePhase: (phase, update) =>
    set((state) => ({
      pipelineStatus: {
        ...state.pipelineStatus,
        [phase]: { ...state.pipelineStatus[phase], ...update },
      },
    })),

  initPipelineStatus: () =>
    set({ pipelineStatus: { ...initialPipelineStatus }, pipelineError: null }),

  setPipelineError: (pipelineError) => set({ pipelineError }),

  updateBeat: (id, updates) =>
    set((state) => ({
      beats: state.beats.map((b) => (b.id === id ? { ...b, ...updates } : b)),
    })),

  updateScene: (id, updates) =>
    set((state) => ({
      scenes: state.scenes.map((s) => (s.id === id ? { ...s, ...updates } : s)),
    })),

  removeCharacter: (id) =>
    set((state) => ({
      characters: state.characters.filter((c) => c.id !== id),
      selectedAssetId: state.selectedAssetId === id ? null : state.selectedAssetId,
      selectedAssetType: state.selectedAssetId === id ? null : state.selectedAssetType,
    })),
  removeLocation: (id) =>
    set((state) => ({
      locations: state.locations.filter((l) => l.id !== id),
      selectedAssetId: state.selectedAssetId === id ? null : state.selectedAssetId,
      selectedAssetType: state.selectedAssetId === id ? null : state.selectedAssetType,
    })),
  removeProp: (id) =>
    set((state) => ({
      props: state.props.filter((p) => p.id !== id),
      selectedAssetId: state.selectedAssetId === id ? null : state.selectedAssetId,
      selectedAssetType: state.selectedAssetId === id ? null : state.selectedAssetType,
    })),
  removeCharacterVariant: (id) =>
    set((state) => ({
      characterVariants: state.characterVariants.filter((v) => v.id !== id),
      selectedAssetId: state.selectedAssetId === id ? null : state.selectedAssetId,
      selectedAssetType: state.selectedAssetId === id ? null : state.selectedAssetType,
    })),

  reset: () => set(initialState),
}));
