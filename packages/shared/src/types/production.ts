export type ProductionAssetType = 'character' | 'location' | 'prop' | 'style';
export type AssetAnchorStatus = 'missing' | 'partial' | 'ready';
export type ShotProductionReadiness = 'blocked' | 'ready';
export type StoryboardReadinessStatus = 'ready' | 'patchable' | 'blocked';
export type ShotStoryboardStatus = 'ready' | 'fallback_only' | 'blocked';
export type StoryboardVideoMode = 'text_to_video' | 'image_to_video' | 'scene_character_to_video';
export type WorkflowModuleCategory =
  | 'dialogue'
  | 'fight'
  | 'lyrical'
  | 'transition'
  | 'establishing'
  | 'emotion_closeup'
  | 'tracking_action'
  | 'custom';
export type WorkflowNodeKind =
  | 'story_input'
  | 'shot_check'
  | 'mode_decision'
  | 'prompt_pack'
  | 'initial_frame_generation'
  | 'initial_frame_approval'
  | 'scene_anchor'
  | 'character_anchor'
  | 'storyboard_animatic_checkpoint'
  | 'video_animatic_checkpoint'
  | 'shot_input'
  | 'asset_anchor'
  | 'prompt_assembly'
  | 'image_candidate'
  | 'image_compare'
  | 'image_approval'
  | 'animatic_checkpoint'
  | 'video_generation'
  | 'video_compare'
  | 'video_approval'
  | 'writeback';
export type WorkflowNodeStatus = 'idle' | 'blocked' | 'running' | 'succeeded' | 'failed';
export type ArtifactStatus = 'draft' | 'approved' | 'rejected';
export type AnimaticHeatLevel = 'stable' | 'watch' | 'conflict';
export type ChecklistStatus = 'pass' | 'warn' | 'fail';

export interface StoryboardChecklistItem {
  id: string;
  label: string;
  status: ChecklistStatus;
  detail: string;
  hardGate: boolean;
}

export interface SceneStoryboardReadinessReport {
  sceneId: string;
  heading?: string;
  order: number;
  status: StoryboardReadinessStatus;
  totalShotCount: number;
  readyShotIds: string[];
  patchableShotIds: string[];
  blockedShotIds: string[];
  beatCoverage: {
    total: number;
    covered: number;
  };
  checklist: StoryboardChecklistItem[];
  blockedReasons: string[];
  patchableReasons: string[];
}

export interface ShotStoryboardCheck {
  shotId: string;
  sceneId: string;
  shotNumber: number;
  status: ShotStoryboardStatus;
  promptCompleteness: 'complete' | 'partial' | 'insufficient';
  continuityAnchorStatus: AssetAnchorStatus;
  checklist: StoryboardChecklistItem[];
  blockedReasons: string[];
  fallbackReasons: string[];
}

export interface VideoModeDecision {
  recommendedMode?: StoryboardVideoMode;
  selectedMode?: StoryboardVideoMode;
  availableModes: StoryboardVideoMode[];
  blockedModes: Partial<Record<StoryboardVideoMode, string>>;
  defaultVideoModePolicy: 'auto_recommend_override';
  rationale: string;
}

export interface AssetAnchor {
  assetId: string;
  assetType: ProductionAssetType;
  assetName?: string;
  selectedReferenceKey?: string;
  lockedImageSlots: Record<string, string>;
  status: AssetAnchorStatus;
  negativePrompt?: string;
  styleAffinity?: string;
  required?: boolean;
  missingReason?: string;
}

export interface ShotProductionSpec {
  shotId: string;
  shotNumber: number;
  sceneId: string;
  sceneHeading?: string;
  sceneOrder?: number;
  title: string;
  moduleId: string;
  recommendedModuleIds: string[];
  narrativeIntent: string;
  visualGoal: string;
  motionGoal?: string;
  anchors: AssetAnchor[];
  stylePreset?: string;
  readiness: ShotProductionReadiness;
  blockedReasons: string[];
  estimatedDurationMs: number;
  transitionHint?: string;
  charactersInFrame: string[];
  storyboardStatus: ShotStoryboardStatus;
  storyboardChecklist: StoryboardChecklistItem[];
  storyboardBlockedReasons: string[];
  storyboardFallbackReasons: string[];
  storyboardAnimaticEligible: boolean;
  sceneReadinessStatus: StoryboardReadinessStatus;
  videoModeDecision: VideoModeDecision;
}

export interface WorkflowModuleNodeTemplate {
  id: string;
  kind: WorkflowNodeKind;
  title: string;
  description: string;
  resultType?: 'text' | 'image' | 'video' | 'writeback';
  required: boolean;
}

export interface WorkflowModule {
  id: string;
  name: string;
  category: WorkflowModuleCategory;
  description: string;
  inputContract: string[];
  outputContract: string[];
  requiredAssets: ProductionAssetType[];
  optionalAssets: ProductionAssetType[];
  nodeTemplate: WorkflowModuleNodeTemplate[];
  shareMode: 'private' | 'team' | 'public';
  version: number;
  approvalGates: WorkflowNodeKind[];
  costProfile: 'low' | 'medium' | 'high';
  recommendedModelSet: string[];
  supportedVideoModes: StoryboardVideoMode[];
  defaultVideoModePolicy: 'auto_recommend_override';
}

export interface AssetRequirement {
  shotId: string;
  shotTitle: string;
  sceneId: string;
  assetId: string;
  assetType: ProductionAssetType;
  assetName: string;
  status: AssetAnchorStatus;
  reason: string;
  blocking: boolean;
  recommendedModuleIds: string[];
}

export interface BoardReadinessSummary {
  totalShots: number;
  readyShots: number;
  blockedShots: number;
  missingCharacterAnchors: number;
  missingLocationAnchors: number;
  missingPropAnchors: number;
  missingStyleAnchors: number;
}

export interface ShotRuntimeArtifact {
  id: string;
  shotId: string;
  nodeId: string;
  type: 'image' | 'video';
  label: string;
  status: ArtifactStatus;
  prompt: string;
  thumbnailText: string;
  version: number;
  durationMs?: number;
  costCredits: number;
  createdAt: string;
  sourceAnchorKeys: string[];
  mode?: StoryboardVideoMode;
  riskTag?: 'standard' | 'high_consistency_risk';
}

export interface ShotNodeRun {
  id: string;
  shotId: string;
  nodeId: string;
  kind: WorkflowNodeKind;
  label: string;
  status: WorkflowNodeStatus;
  durationMs?: number;
  costCredits?: number;
  errorMessage?: string;
  updatedAt: string;
}

export interface WritebackPreview {
  shotId: string;
  recommendedImageArtifactId?: string;
  approvedVideoArtifactId?: string;
  reusableAnchorAssetIds: string[];
  transitionHint?: string;
  audioPlaceholder: string;
  subtitlePlaceholder: string;
}

export interface BoardConsoleEntry {
  id: string;
  shotId: string;
  level: 'info' | 'warning' | 'error';
  message: string;
  createdAt: string;
}

export interface AnimaticClipRef {
  shotId: string;
  sourceType: 'image' | 'video';
  artifactId: string;
  durationMs: number;
  transitionHint?: string;
  cameraMove?: string;
  sourceNodeId?: string;
  sourceModuleId?: string;
  sourceArtifactVersion?: number;
  heat: AnimaticHeatLevel;
  issueSummary?: string;
  label: string;
  phase: 'storyboard' | 'video';
  mode?: StoryboardVideoMode;
  riskTag?: 'standard' | 'high_consistency_risk';
}

export interface ShotVideoSequenceBundle {
  id: string;
  projectId: string;
  shotIds: string[];
  videoArtifactIds: string[];
  animaticBundleId?: string;
  status: 'draft' | 'approved';
  exportTarget: 'preview' | 'jianying';
  shotOrder: string[];
  transitionHints: string[];
  audioPlaceholders: string[];
  subtitlePlaceholders: string[];
  createdAt: string;
  consistencyRiskShotIds: string[];
  videoModesByShot: Record<string, StoryboardVideoMode | undefined>;
}

export interface ShotProductionProjection {
  sceneReports: SceneStoryboardReadinessReport[];
  specs: ShotProductionSpec[];
  requirements: AssetRequirement[];
  readiness: BoardReadinessSummary;
  modules: WorkflowModule[];
}
