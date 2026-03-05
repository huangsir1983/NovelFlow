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
  shot_size: string;
  camera_angle: string;
  camera_movement: string;
  duration: number;
  description: string;
  dialogue?: string;
  sound_narrative?: Record<string, unknown>;
  mise_en_scene?: Record<string, unknown>;
  tension_score?: number;
  visual_motifs?: Record<string, unknown>;
  cultural_preset?: string;
  thrill_type?: string;
  thrill_visual_strategy?: Record<string, unknown>;
  visual_prompt?: string;
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
}

export interface KnowledgeBase {
  id: string;
  project_id: string;
  characters: Character[];
  locations: Location[];
  world_building: Record<string, unknown>;
  style_guide: Record<string, unknown>;
}
