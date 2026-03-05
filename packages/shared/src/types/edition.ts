// Edition system — from PRD Section 4.2

export enum Edition {
  NORMAL = 'normal',
  CANVAS = 'canvas',
  HIDDEN = 'hidden',
  ULTIMATE = 'ultimate',
}

export interface FeatureConfig {
  ui_mode: 'wizard' | 'workspace';
  import_sources: string[];
  max_projects: number;
  collaboration: boolean;
  agents: string[];
  knowledge_level: 'core' | 'advanced' | 'full';
  screenwriter_mode: string;
  director_capabilities: string[] | 'all';
  visual_capabilities: string[] | 'all';
  sound_narrative: boolean;
  mise_en_scene: boolean;
  visual_motif_tracking: boolean;
  tension_engine: 'simplified' | 'standard' | 'full';
  cultural_presets: string[] | 'all';
  data_feedback: false | 'basic' | 'full_loop';
  ip_extension?: boolean;
  thrill_visual_linkage?: boolean;
  candidates_per_generation: number;
  export_formats: string[] | 'all';
  model_selection: boolean;
  default_model: 'haiku' | 'sonnet' | 'opus';
  custom_prompts: false | 'tune' | 'full';
  custom_knowledge: false | 'view' | 'edit' | 'full';
  desktop_app: boolean;
  api_access: boolean;
  white_label?: boolean;
  debug_panel: boolean;
  auto_pipeline?: boolean;
  experimental?: boolean;
}

export const FEATURE_FLAGS: Record<Edition, FeatureConfig> = {
  [Edition.NORMAL]: {
    ui_mode: 'wizard',
    import_sources: ['novel'],
    max_projects: 5,
    collaboration: false,
    agents: [],
    knowledge_level: 'core',
    screenwriter_mode: 'basic',
    director_capabilities: ['core'],
    visual_capabilities: ['core'],
    sound_narrative: false,
    mise_en_scene: false,
    visual_motif_tracking: false,
    tension_engine: 'simplified',
    cultural_presets: ['auto'],
    data_feedback: false,
    candidates_per_generation: 1,
    export_formats: ['pdf', 'json'],
    model_selection: false,
    default_model: 'haiku',
    custom_prompts: false,
    custom_knowledge: false,
    desktop_app: false,
    api_access: false,
    debug_panel: false,
  },
  [Edition.CANVAS]: {
    ui_mode: 'workspace',
    import_sources: ['novel', 'script'],
    max_projects: -1,
    collaboration: true,
    agents: ['analyst', 'consistency', 'screenwriter'],
    knowledge_level: 'advanced',
    screenwriter_mode: 'origin',
    director_capabilities: ['core', 'advanced'],
    visual_capabilities: ['core', 'advanced'],
    sound_narrative: false,
    mise_en_scene: false,
    visual_motif_tracking: false,
    tension_engine: 'standard',
    cultural_presets: ['auto', 'manual'],
    data_feedback: false,
    candidates_per_generation: 3,
    export_formats: ['pdf', 'json', 'fountain', 'fdx', 'csv', 'docx'],
    model_selection: false,
    default_model: 'sonnet',
    custom_prompts: 'tune',
    custom_knowledge: 'view',
    desktop_app: true,
    api_access: false,
    debug_panel: false,
  },
  [Edition.HIDDEN]: {
    ui_mode: 'workspace',
    import_sources: ['novel', 'script'],
    max_projects: -1,
    collaboration: true,
    agents: ['analyst', 'consistency', 'screenwriter', 'director', 'visual', 'reviewer'],
    knowledge_level: 'full',
    screenwriter_mode: 'origin_enhanced',
    director_capabilities: ['core', 'advanced', 'sequences', 'sound', 'mise_en_scene', 'cultural'],
    visual_capabilities: ['core', 'advanced', 'platform_adapt', 'edge_cases'],
    sound_narrative: true,
    mise_en_scene: true,
    visual_motif_tracking: true,
    tension_engine: 'full',
    cultural_presets: 'all',
    data_feedback: 'basic',
    ip_extension: true,
    candidates_per_generation: 5,
    export_formats: 'all',
    model_selection: true,
    default_model: 'sonnet',
    custom_prompts: 'full',
    custom_knowledge: 'edit',
    desktop_app: true,
    api_access: true,
    white_label: true,
    debug_panel: false,
  },
  [Edition.ULTIMATE]: {
    ui_mode: 'workspace',
    import_sources: ['novel', 'script', 'blank'],
    max_projects: -1,
    collaboration: true,
    agents: [
      'analyst', 'consistency', 'screenwriter', 'micro_drama_writer',
      'director', 'visual', 'reviewer', 'data_optimizer', 'coordinator',
    ],
    knowledge_level: 'full',
    screenwriter_mode: 'origin+micro_drama',
    director_capabilities: 'all',
    visual_capabilities: 'all',
    sound_narrative: true,
    mise_en_scene: true,
    visual_motif_tracking: true,
    tension_engine: 'full',
    cultural_presets: 'all',
    data_feedback: 'full_loop',
    ip_extension: true,
    thrill_visual_linkage: true,
    candidates_per_generation: -1,
    export_formats: 'all',
    model_selection: true,
    default_model: 'opus',
    custom_prompts: 'full',
    custom_knowledge: 'full',
    desktop_app: true,
    api_access: true,
    debug_panel: true,
    auto_pipeline: true,
    experimental: true,
  },
};

/** Edition hierarchy for comparison */
export const EDITION_ORDER: Edition[] = [
  Edition.NORMAL,
  Edition.CANVAS,
  Edition.HIDDEN,
  Edition.ULTIMATE,
];
