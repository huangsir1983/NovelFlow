export { SceneNode } from './SceneNode';
export { ShotNode } from './ShotNode';
export { PromptAssemblyNode } from './PromptAssemblyNode';
export { ImageGenerationNode } from './ImageGenerationNode';
export { VideoGenerationNode } from './VideoGenerationNode';
export { PipelineEdge, BypassEdge } from './CanvasEdge';
export { SelectionToolbar } from './SelectionToolbar';
export { SceneNavigatorWheel } from './SceneNavigatorWheel';
export { ChainTemplateSidebar, ChainDropTarget } from './ChainTemplateSidebar';
export { CanvasLeftToolbar } from './CanvasLeftToolbar';
export { BoxSelectExecutor, MergeAnalysisPanel } from './BoxSelectExecutor';
export { SimplifiedSceneNode, CollapsedSceneNode } from './SimplifiedSceneNode';
export { MODULE_TEMPLATES, detectModuleType } from './ModuleTemplates';
export { SceneBGNode } from './SceneBGNode';
export { CharacterProcessNode } from './CharacterProcessNode';
export { ViewAngleNode } from './ViewAngleNode';
export { ExpressionNode } from './ExpressionNode';
export { HDUpscaleNode } from './HDUpscaleNode';
export { MattingNode } from './MattingNode';
export { PropProcessNode } from './PropProcessNode';
export { PropAngleNode } from './PropAngleNode';
export { CompositeNode } from './CompositeNode';
export { BlendRefineNode } from './BlendRefineNode';
export { LightingNode } from './LightingNode';
export { FinalHDNode } from './FinalHDNode';
export { CompositeEditor } from './CompositeEditor';
export { ImageProcessNode } from './ImageProcessNode';

/* React Flow nodeTypes / edgeTypes registries */
import { SceneNode } from './SceneNode';
import { ShotNode } from './ShotNode';
import { PromptAssemblyNode } from './PromptAssemblyNode';
import { ImageGenerationNode } from './ImageGenerationNode';
import { VideoGenerationNode } from './VideoGenerationNode';
import { PipelineEdge, BypassEdge } from './CanvasEdge';
import { SimplifiedSceneNode, CollapsedSceneNode } from './SimplifiedSceneNode';
import { SceneBGNode } from './SceneBGNode';
import { CharacterProcessNode } from './CharacterProcessNode';
import { ViewAngleNode } from './ViewAngleNode';
import { ExpressionNode } from './ExpressionNode';
import { HDUpscaleNode } from './HDUpscaleNode';
import { MattingNode } from './MattingNode';
import { PropProcessNode } from './PropProcessNode';
import { PropAngleNode } from './PropAngleNode';
import { CompositeNode } from './CompositeNode';
import { BlendRefineNode } from './BlendRefineNode';
import { LightingNode } from './LightingNode';
import { FinalHDNode } from './FinalHDNode';
import { ImageProcessNode } from './ImageProcessNode';

export const canvasNodeTypes = {
  scene: SceneNode,
  shot: ShotNode,
  promptAssembly: PromptAssemblyNode,
  imageGeneration: ImageGenerationNode,
  videoGeneration: VideoGenerationNode,
  simplifiedScene: SimplifiedSceneNode,
  collapsedScene: CollapsedSceneNode,
  sceneBG: SceneBGNode,
  characterProcess: CharacterProcessNode,
  viewAngle: ViewAngleNode,
  expression: ExpressionNode,
  hdUpscale: HDUpscaleNode,
  matting: MattingNode,
  propProcess: PropProcessNode,
  propAngle: PropAngleNode,
  imageProcess: ImageProcessNode,
  composite: CompositeNode,
  blendRefine: BlendRefineNode,
  lighting: LightingNode,
  finalHD: FinalHDNode,
} as const;

export const canvasEdgeTypes = {
  pipeline: PipelineEdge,
  bypass: BypassEdge,
} as const;
