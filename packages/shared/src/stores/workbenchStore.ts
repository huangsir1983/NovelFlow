'use client';

import { create } from 'zustand';
import type {
  WorkbenchAISuggestion,
  WorkbenchBeatDraft,
  WorkbenchConsistencyIssue,
  WorkbenchSceneDraft,
} from '../types/workbench';

interface WorkbenchStoreState {
  projectId: string | null;
  beats: WorkbenchBeatDraft[];
  scenes: WorkbenchSceneDraft[];
  suggestions: WorkbenchAISuggestion[];
  consistencyIssues: WorkbenchConsistencyIssue[];
  focusedBeatId: string | null;
  focusedSceneId: string | null;

  setProjectId: (projectId: string | null) => void;
  setBeats: (beats: WorkbenchBeatDraft[]) => void;
  setScenes: (scenes: WorkbenchSceneDraft[]) => void;
  setSuggestions: (suggestions: WorkbenchAISuggestion[]) => void;
  setConsistencyIssues: (issues: WorkbenchConsistencyIssue[]) => void;
  focusBeat: (beatId: string | null) => void;
  focusScene: (sceneId: string | null) => void;
  markSuggestionApplied: (suggestionId: string) => void;
  reset: () => void;
}

const initialState = {
  projectId: null,
  beats: [],
  scenes: [],
  suggestions: [],
  consistencyIssues: [],
  focusedBeatId: null,
  focusedSceneId: null,
};

export const useWorkbenchStore = create<WorkbenchStoreState>((set) => ({
  ...initialState,

  setProjectId: (projectId) => set({ projectId }),
  setBeats: (beats) => set({ beats }),
  setScenes: (scenes) => set({ scenes }),
  setSuggestions: (suggestions) => set({ suggestions }),
  setConsistencyIssues: (consistencyIssues) => set({ consistencyIssues }),
  focusBeat: (focusedBeatId) => set({ focusedBeatId }),
  focusScene: (focusedSceneId) => set({ focusedSceneId }),
  markSuggestionApplied: (suggestionId) =>
    set((state) => ({
      suggestions: state.suggestions.map((suggestion) =>
        suggestion.id === suggestionId ? { ...suggestion, applied: true } : suggestion,
      ),
    })),
  reset: () => set(initialState),
}));
