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
  adaptation_direction?: string;
  screen_format?: string;
  style_preset?: string;
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

export interface ScriptDialogue {
  character: string | null;
  line: string;
  subtext: string;
  delivery: string;
}

export interface ScriptShot {
  shot_type: string;
  camera_move: string;
  angle: string;
  subject: string;
  action: string;
  dialogue: ScriptDialogue | null;
  characters?: Array<{ name: string; expression?: string; action?: string; position?: string }>;
  sfx?: string;
  music?: string;
  transition?: string;
  close_up_target?: string;
}

export interface ScriptBeat {
  beat_id: string;
  timestamp: string;
  type: string;
  shots: ScriptShot[];
}

export interface ScriptSceneSummary {
  hook: string;
  core_reversal: string;
  sweet_spot: string;
  cliffhanger: string;
  spreadable_moment: string;
}

export interface GeneratedScript {
  scene_id: string;
  duration_estimate_s: number;
  total_word_count: number;
  dialogue_ratio: number;
  beats: ScriptBeat[];
  scene_summary: ScriptSceneSummary;
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
  window_index?: number;
  core_event?: string;
  key_dialogue?: string;
  emotional_peak?: string;
  estimated_duration_s?: number;
  visual_reference?: string;
  visual_prompt_negative?: string;
  source_text_start?: string;
  source_text_end?: string;
  generated_script?: string;
  edited_source_text?: string | null;
  // 短剧增强字段
  narrative_mode?: string;
  hook_type?: string;
  cliffhanger?: string;
  reversal_points?: string[];
  sweet_spot?: string;
  emotion_beat?: string;
  dialogue_budget?: string;
  generated_script_json?: GeneratedScript;
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
  visual_prompt_negative?: string;
  desire?: string;
  flaw?: string;
  scene_presence?: string;
}

export interface CharacterRelationship {
  target_character_id?: string;
  target?: string;
  relationship_type?: string;
  type?: string;
  description?: string;
  dynamic?: string;
  function?: string;
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
  type?: string;
  era_style?: string;
  visual_reference?: string;
  visual_prompt_negative?: string;
  atmosphere?: string;
  color_palette?: string[];
  lighting?: string;
  key_features?: string[];
  narrative_scene_ids?: string[];
  scene_count?: number;
  time_variations?: string[];
  emotional_range?: string;
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

// Prop (道具) types
export interface Prop {
  id: string;
  project_id: string;
  name: string;
  category: string;
  description: string;
  visual_reference?: string;
  visual_prompt_negative?: string;
  emotional_association?: string;
  narrative_function?: string;
  is_motif?: boolean;
  is_major?: boolean;
  scenes_present?: string[];
  appearance_count?: number;
}

// Character variant types
export interface CharacterVariant {
  id: string;
  project_id: string;
  character_id: string;
  character_name: string;
  variant_type: string;
  variant_name: string;
  tags: string[];
  scene_ids?: string[];
  visual_reference?: string;
  visual_prompt_negative?: string;
  trigger?: string;
  appearance_delta?: Record<string, unknown>;
  costume_override?: Record<string, unknown>;
  emotional_tone?: string;
}

// Pipeline phase status
export interface PipelinePhaseStatus {
  status: 'pending' | 'running' | 'done' | 'error';
  detail?: string;
  progress?: { current: number; total: number };
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
  | { type: 'character_found'; phase: string; data: { name: string; role: string; index: number; aliases?: string[]; personality?: string; age_range?: string; appearance?: Character['appearance']; costume?: Character['costume']; casting_tags?: string[]; desire?: string; flaw?: string } }
  | { type: 'scene_found'; phase: string; data: { scene_id: string; location: string; core_event: string; index: number } }
  | { type: 'location_card'; phase: string; data: { name: string; scene_count: number; index: number; total: number } }
  | { type: 'prop_card'; phase: string; data: { name: string; category: string; index: number; total: number } }
  | { type: 'variant'; phase: string; data: { character: string; variant_count: number } }
  | { type: 'variant_card'; phase: string; data: { character_name: string; variant_name: string; variant_type: string; index: number } }
  | { type: 'warning'; phase: string; data: { message: string; character?: string } }
  | { type: 'item_ready'; phase: string; sub?: string; data?: Record<string, unknown> }
  | { type: 'chapter_progress'; phase: string; index: number; total: number; beats?: number; scenes?: number }
  | { type: 'window_progress'; phase: string; index: number; total: number; scenes_in_window?: number }
  | { type: 'scene_progress'; phase: string; index: number; total: number; shots?: number }
  | { type: 'pipeline_complete'; summary: Record<string, number> }
  | { type: 'error'; message: string; phase?: string; retryable?: boolean };
