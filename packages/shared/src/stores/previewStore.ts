'use client';

import { create } from 'zustand';
import type { AnimaticBundle, TimelineTrack, Transition } from '../types/preview';
import type { AnimaticClipRef, ShotVideoSequenceBundle } from '../types/production';

type PreviewPhase = 'storyboard' | 'video';

function buildBundle(
  projectId: string | null,
  phase: PreviewPhase,
  clips: AnimaticClipRef[],
  tracks: TimelineTrack[],
) {
  if (!projectId || clips.length === 0) {
    return null;
  }

  const durationMs = clips.reduce((sum, clip) => sum + clip.durationMs, 0);
  const bundleType =
    clips.length === 0
      ? 'image'
      : clips.every((clip) => clip.sourceType === 'video')
        ? 'video'
        : clips.some((clip) => clip.sourceType === 'video')
          ? 'hybrid'
          : 'image';

  return {
    id: `animatic:${phase}:${projectId}`,
    project_id: projectId,
    track_ids: tracks.map((track) => track.id),
    clip_ids: clips.map((clip) => clip.artifactId),
    bundle_type: bundleType,
    fps: 24,
    duration_ms: durationMs,
    generated_at: new Date().toISOString(),
  } satisfies AnimaticBundle;
}

function buildTransitions(clips: AnimaticClipRef[]) {
  return clips.slice(1).map((clip, index) => ({
    id: `transition:${clips[index].artifactId}:${clip.artifactId}`,
    from_clip_id: clips[index].artifactId,
    to_clip_id: clip.artifactId,
    type:
      (clip.transitionHint || '').toLowerCase().includes('fade')
        ? 'fade'
        : (clip.transitionHint || '').toLowerCase().includes('wipe')
          ? 'wipe'
          : 'cut',
    duration_ms: 300,
  })) satisfies Transition[];
}

interface PreviewStoreState {
  projectId: string | null;
  tracks: TimelineTrack[];
  transitions: Transition[];
  currentBundle: AnimaticBundle | null;
  animaticClips: AnimaticClipRef[];
  storyboardClips: AnimaticClipRef[];
  videoClips: AnimaticClipRef[];
  activeClips: AnimaticClipRef[];
  selectedPhase: PreviewPhase;
  sequenceBundles: ShotVideoSequenceBundle[];
  selectedSequenceBundleId: string | null;
  clipDurationOverrides: Record<string, number>;
  playheadMs: number;
  isPlaying: boolean;

  setProjectId: (projectId: string | null) => void;
  setTracks: (tracks: TimelineTrack[]) => void;
  setTransitions: (transitions: Transition[]) => void;
  setCurrentBundle: (bundle: AnimaticBundle | null) => void;
  setAnimaticClips: (clips: AnimaticClipRef[]) => void;
  setSequenceBundles: (bundles: ShotVideoSequenceBundle[]) => void;
  setPreviewPhase: (phase: PreviewPhase) => void;
  selectSequenceBundle: (bundleId: string | null) => void;
  setClipDurationOverride: (shotId: string, durationMs: number) => void;
  hydratePreview: (
    projectId: string | null,
    clips: AnimaticClipRef[],
    bundles: ShotVideoSequenceBundle[],
  ) => void;
  setPlayheadMs: (playheadMs: number) => void;
  setPlaying: (isPlaying: boolean) => void;
  reset: () => void;
}

const defaultTracks: TimelineTrack[] = [
  {
    id: 'main-track',
    type: 'video',
    name: 'Main Animatic',
    order: 0,
    locked: false,
  },
];

const initialState = {
  projectId: null,
  tracks: defaultTracks,
  transitions: [] as Transition[],
  currentBundle: null as AnimaticBundle | null,
  animaticClips: [] as AnimaticClipRef[],
  storyboardClips: [] as AnimaticClipRef[],
  videoClips: [] as AnimaticClipRef[],
  activeClips: [] as AnimaticClipRef[],
  selectedPhase: 'storyboard' as PreviewPhase,
  sequenceBundles: [] as ShotVideoSequenceBundle[],
  selectedSequenceBundleId: null,
  clipDurationOverrides: {} as Record<string, number>,
  playheadMs: 0,
  isPlaying: false,
};

export const usePreviewStore = create<PreviewStoreState>((set) => ({
  ...initialState,

  setProjectId: (projectId) => set({ projectId }),
  setTracks: (tracks) => set({ tracks }),
  setTransitions: (transitions) => set({ transitions }),
  setCurrentBundle: (currentBundle) => set({ currentBundle }),
  setAnimaticClips: (animaticClips) => set({ animaticClips }),
  setSequenceBundles: (sequenceBundles) => set({ sequenceBundles }),
  setPreviewPhase: (selectedPhase) =>
    set((state) => {
      const activeClips = selectedPhase === 'video' ? state.videoClips : state.storyboardClips;
      return {
        selectedPhase,
        activeClips,
        transitions: buildTransitions(activeClips),
        currentBundle: buildBundle(state.projectId, selectedPhase, activeClips, state.tracks),
        playheadMs: Math.min(state.playheadMs, activeClips.reduce((sum, clip) => sum + clip.durationMs, 0)),
      };
    }),
  selectSequenceBundle: (selectedSequenceBundleId) => set({ selectedSequenceBundleId }),
  setClipDurationOverride: (shotId, durationMs) =>
    set((state) => ({
      clipDurationOverrides: {
        ...state.clipDurationOverrides,
        [shotId]: durationMs,
      },
    })),

  hydratePreview: (projectId, clips, bundles) =>
    set((state) => {
      const storyboardClips = clips.filter((clip) => clip.phase === 'storyboard');
      const videoClips = clips.filter((clip) => clip.phase === 'video');
      const selectedPhase =
        state.selectedPhase === 'video'
          ? videoClips.length > 0
            ? 'video'
            : 'storyboard'
          : storyboardClips.length > 0
            ? 'storyboard'
            : videoClips.length > 0
              ? 'video'
              : 'storyboard';
      const activeClips = selectedPhase === 'video' ? videoClips : storyboardClips;
      const tracks = state.tracks.length > 0 ? state.tracks : defaultTracks;

      return {
        projectId,
        animaticClips: clips,
        storyboardClips,
        videoClips,
        activeClips,
        selectedPhase,
        sequenceBundles: bundles,
        selectedSequenceBundleId:
          state.selectedSequenceBundleId &&
          bundles.some((bundle) => bundle.id === state.selectedSequenceBundleId)
            ? state.selectedSequenceBundleId
            : bundles[0]?.id || null,
        tracks,
        transitions: buildTransitions(activeClips),
        currentBundle: buildBundle(projectId, selectedPhase, activeClips, tracks),
        playheadMs: Math.min(state.playheadMs, activeClips.reduce((sum, clip) => sum + clip.durationMs, 0)),
      };
    }),

  setPlayheadMs: (playheadMs) => set({ playheadMs }),
  setPlaying: (isPlaying) => set({ isPlaying }),
  reset: () => set(initialState),
}));
