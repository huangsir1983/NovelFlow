export interface TimelineTrack {
  id: string;
  type: 'video' | 'audio' | 'subtitle' | 'tts';
  name: string;
  order: number;
  locked: boolean;
}

export interface Transition {
  id: string;
  from_clip_id: string;
  to_clip_id: string;
  type: 'cut' | 'fade' | 'wipe';
  duration_ms: number;
}

export interface TimelineClip {
  id: string;
  track_id: string;
  shot_id: string;
  source_artifact_id: string;
  source_type: 'image' | 'video';
  start_ms: number;
  duration_ms: number;
  heat: 'stable' | 'watch' | 'conflict';
}

export interface AnimaticBundle {
  id: string;
  project_id: string;
  track_ids: string[];
  clip_ids: string[];
  bundle_type: 'image' | 'video' | 'hybrid';
  fps: number;
  duration_ms: number;
  generated_at: string;
}

export interface PreviewExportMapping {
  version_id: string;
  bundle_id: string;
  capcut_draft_path?: string;
  timeline_revision: number;
}
