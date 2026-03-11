// Core data types — from PRD Section 6.5

export type ImportSource = 'novel' | 'script' | 'blank';

export type ProjectStage =
  | 'import'
  | 'knowledge'
  | 'beat_sheet'
  | 'script'
  | 'storyboard'
  | 'visual_prompt'
  | 'generation'
  | 'complete';

export interface Project {
  id: string;
  name: string;
  description: string;
  import_source: ImportSource;
  edition: string;
  stage: ProjectStage;
  created_at: string;
  updated_at: string;
}

export interface Chapter {
  id: string;
  project_id: string;
  title: string;
  content: string;
  order: number;
  word_count: number;
}

export interface Beat {
  id: string;
  project_id: string;
  chapter_id?: string;
  title: string;
  description: string;
  beat_type: string;
  emotional_value: number;
  order: number;
}

export interface Scene {
  id: string;
  project_id: string;
  beat_id?: string;
  heading: string;
  location: string;
  time_of_day: string;
  description: string;
  action: string;
  dialogue: SceneDialogue[];
  order: number;
  tension_score?: number;
  characters_present?: string[];
  key_props?: string[];
  dramatic_purpose?: string;
}

export interface SceneDialogue {
  character: string;
  line: string;
  parenthetical?: string;
}

export interface Shot {
  id: string;
  scene_id: string;
  project_id: string;
  shot_number: number;
  goal: string;
  composition: string;
  camera_angle: string;
  camera_movement: string;
  framing: string;
  duration_estimate: string;
  characters_in_frame: string[];
  emotion_target: string;
  dramatic_intensity: number;
  transition_in: string;
  transition_out: string;
  description: string;
  visual_prompt: string;
  order: number;
}

export interface Character {
  id: string;
  project_id: string;
  name: string;
  aliases: string[];
  role: 'protagonist' | 'antagonist' | 'supporting' | 'minor';
  description: string;
  personality: string;
  arc: string;
  relationships: CharacterRelationship[];
  // Extended fields
  age_range?: string;
  appearance?: {
    face?: string;
    body?: string;
    hair?: string;
    distinguishing_features?: string;
  };
  costume?: {
    typical_outfit?: string;
    color_palette?: string[];
    texture_keywords?: string[];
  };
  casting_tags?: string[];
  visual_reference?: string;
  desire?: string;
  flaw?: string;
}

export interface CharacterRelationship {
  target_character_id: string;
  relationship_type: string;
  description: string;
}

export interface Location {
  id: string;
  project_id: string;
  name: string;
  description: string;
  visual_description: string;
  mood: string;
  chapter_id?: string;
  sensory?: string;
  narrative_function?: string;
}

export interface KnowledgeBase {
  id: string;
  project_id: string;
  characters: Character[];
  locations: Location[];
  world_building: Record<string, unknown>;
  style_guide: Record<string, unknown>;
}

export interface ShotGroup {
  id: string;
  project_id: string;
  scene_id?: string;
  shot_ids: string[];
  segment_number: number;
  duration: string;
  transition_type: string;
  emotional_beat: string;
  continuity: string;
  vff_body: string;
  merge_rationale: string;
  style_metadata: Record<string, unknown>;
  visual_prompt_positive: string;
  visual_prompt_negative: string;
  style_tags: string[];
  order: number;
}

// Import task types for async pipeline
export interface ImportTaskInfo {
  task_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  current_phase: string;
}

export interface ImportStatusInfo extends ImportTaskInfo {
  progress: Record<string, number>;
  error?: string | null;
}

export type ImportSSEEvent =
  | { type: 'phase_start'; phase: string }
  | { type: 'phase_done'; phase: string; data?: Record<string, unknown> }
  | { type: 'item_ready'; phase: string; sub?: string; data?: Record<string, unknown> }
  | { type: 'chapter_progress'; phase: string; index: number; total: number; beats?: number; scenes?: number }
  | { type: 'window_progress'; phase: string; index: number; total: number; scenes_in_window?: number }
  | { type: 'scene_progress'; phase: string; index: number; total: number; shots?: number }
  | { type: 'pipeline_complete'; summary: Record<string, number> }
  | { type: 'error'; message: string; phase?: string; retryable?: boolean };
