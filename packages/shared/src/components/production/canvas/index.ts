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

/* React Flow nodeTypes / edgeTypes registries */
import { SceneNode } from './SceneNode';
import { ShotNode } from './ShotNode';
import { PromptAssemblyNode } from './PromptAssemblyNode';
import { ImageGenerationNode } from './ImageGenerationNode';
import { VideoGenerationNode } from './VideoGenerationNode';
import { PipelineEdge, BypassEdge } from './CanvasEdge';
import { SimplifiedSceneNode, CollapsedSceneNode } from './SimplifiedSceneNode';

export const canvasNodeTypes = {
  scene: SceneNode,
  shot: ShotNode,
  promptAssembly: PromptAssemblyNode,
  imageGeneration: ImageGenerationNode,
  videoGeneration: VideoGenerationNode,
  simplifiedScene: SimplifiedSceneNode,
  collapsedScene: CollapsedSceneNode,
} as const;

export const canvasEdgeTypes = {
  pipeline: PipelineEdge,
  bypass: BypassEdge,
} as const;
