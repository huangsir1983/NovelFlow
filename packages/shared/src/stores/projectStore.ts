'use client';

import { create } from 'zustand';
import type { Project, Chapter, Beat, Scene, Character, Location } from '../types/project';

interface ProjectStoreState {
  // Data
  project: Project | null;
  chapters: Chapter[];
  beats: Beat[];
  scenes: Scene[];
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

  // Actions
  setProject: (project: Project | null) => void;
  setChapters: (chapters: Chapter[]) => void;
  setBeats: (beats: Beat[]) => void;
  setScenes: (scenes: Scene[]) => void;
  setCharacters: (characters: Character[]) => void;
  setLocations: (locations: Location[]) => void;
  setWorldBuilding: (wb: Record<string, unknown>) => void;
  setStyleGuide: (sg: Record<string, unknown>) => void;

  selectChapter: (id: string | null) => void;
  selectBeat: (id: string | null) => void;
  selectScene: (id: string | null) => void;
  selectCharacter: (id: string | null) => void;
  setActiveSection: (section: 'chapters' | 'characters' | 'scenes' | 'locations') => void;

  setLoading: (loading: boolean) => void;
  setImporting: (importing: boolean) => void;

  updateBeat: (id: string, updates: Partial<Beat>) => void;
  updateScene: (id: string, updates: Partial<Scene>) => void;

  reset: () => void;
}

const initialState = {
  project: null,
  chapters: [],
  beats: [],
  scenes: [],
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
};

export const useProjectStore = create<ProjectStoreState>((set) => ({
  ...initialState,

  setProject: (project) => set({ project }),
  setChapters: (chapters) => set({ chapters }),
  setBeats: (beats) => set({ beats }),
  setScenes: (scenes) => set({ scenes }),
  setCharacters: (characters) => set({ characters }),
  setLocations: (locations) => set({ locations }),
  setWorldBuilding: (worldBuilding) => set({ worldBuilding }),
  setStyleGuide: (styleGuide) => set({ styleGuide }),

  selectChapter: (id) => set({ selectedChapterId: id }),
  selectBeat: (id) => set({ selectedBeatId: id }),
  selectScene: (id) => set({ selectedSceneId: id }),
  selectCharacter: (id) => set({ selectedCharacterId: id }),
  setActiveSection: (section) => set({ activeSection: section }),

  setLoading: (loading) => set({ loading }),
  setImporting: (importing) => set({ importing }),

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
