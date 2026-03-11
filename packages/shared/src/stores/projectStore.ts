'use client';

import { create } from 'zustand';
import type { Project, Chapter, Beat, Scene, Shot, ShotGroup, Character, Location } from '../types/project';

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
  worldBuilding: Record<string, unknown>;
  styleGuide: Record<string, unknown>;

  // Selection state
  selectedChapterId: string | null;
  selectedBeatId: string | null;
  selectedSceneId: string | null;
  selectedCharacterId: string | null;
  activeSection: 'chapters' | 'characters' | 'scenes' | 'locations';

  // Loading state
  loading: boolean;
  importing: boolean;

  // Import task state
  importTaskId: string | null;
  importPhase: string | null;
  importProgress: Record<string, number>;

  // Actions
  setProject: (project: Project | null) => void;
  setChapters: (chapters: Chapter[]) => void;
  setBeats: (beats: Beat[]) => void;
  setScenes: (scenes: Scene[]) => void;
  setShots: (shots: Shot[]) => void;
  setShotGroups: (groups: ShotGroup[]) => void;
  setCharacters: (characters: Character[]) => void;
  setLocations: (locations: Location[]) => void;
  setWorldBuilding: (wb: Record<string, unknown>) => void;
  setStyleGuide: (sg: Record<string, unknown>) => void;

  // Incremental update actions (for SSE)
  addCharacter: (character: Character) => void;
  addScene: (scene: Scene) => void;
  addBeat: (beat: Beat) => void;
  addLocation: (location: Location) => void;
  addShot: (shot: Shot) => void;
  addShotGroup: (group: ShotGroup) => void;

  selectChapter: (id: string | null) => void;
  selectBeat: (id: string | null) => void;
  selectScene: (id: string | null) => void;
  selectCharacter: (id: string | null) => void;
  setActiveSection: (section: 'chapters' | 'characters' | 'scenes' | 'locations') => void;

  setLoading: (loading: boolean) => void;
  setImporting: (importing: boolean) => void;
  setImportTaskId: (taskId: string | null) => void;
  setImportPhase: (phase: string | null) => void;
  setImportProgress: (progress: Record<string, number>) => void;

  updateBeat: (id: string, updates: Partial<Beat>) => void;
  updateScene: (id: string, updates: Partial<Scene>) => void;

  reset: () => void;
}

const initialState = {
  project: null,
  chapters: [],
  beats: [],
  scenes: [],
  shots: [],
  shotGroups: [],
  characters: [],
  locations: [],
  worldBuilding: {},
  styleGuide: {},
  selectedChapterId: null,
  selectedBeatId: null,
  selectedSceneId: null,
  selectedCharacterId: null,
  activeSection: 'chapters' as const,
  loading: false,
  importing: false,
  importTaskId: null,
  importPhase: null,
  importProgress: {},
};

export const useProjectStore = create<ProjectStoreState>((set) => ({
  ...initialState,

  setProject: (project) => set({ project }),
  setChapters: (chapters) => set({ chapters }),
  setBeats: (beats) => set({ beats }),
  setScenes: (scenes) => set({ scenes }),
  setShots: (shots) => set({ shots }),
  setShotGroups: (shotGroups) => set({ shotGroups }),
  setCharacters: (characters) => set({ characters }),
  setLocations: (locations) => set({ locations }),
  setWorldBuilding: (worldBuilding) => set({ worldBuilding }),
  setStyleGuide: (styleGuide) => set({ styleGuide }),

  // Incremental updates for SSE streaming
  addCharacter: (character) =>
    set((state) => ({ characters: [...state.characters, character] })),
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

  selectChapter: (id) => set({ selectedChapterId: id }),
  selectBeat: (id) => set({ selectedBeatId: id }),
  selectScene: (id) => set({ selectedSceneId: id }),
  selectCharacter: (id) => set({ selectedCharacterId: id }),
  setActiveSection: (section) => set({ activeSection: section }),

  setLoading: (loading) => set({ loading }),
  setImporting: (importing) => set({ importing }),
  setImportTaskId: (importTaskId) => set({ importTaskId }),
  setImportPhase: (importPhase) => set({ importPhase }),
  setImportProgress: (importProgress) => set({ importProgress }),

  updateBeat: (id, updates) =>
    set((state) => ({
      beats: state.beats.map((b) => (b.id === id ? { ...b, ...updates } : b)),
    })),

  updateScene: (id, updates) =>
    set((state) => ({
      scenes: state.scenes.map((s) => (s.id === id ? { ...s, ...updates } : s)),
    })),

  reset: () => set(initialState),
}));
