export { SceneNode } from './SceneNode';
export { ShotNode } from './ShotNode';
export { PromptAssemblyNode } from './PromptAssemblyNode';
export { ImageGenerationNode } from './ImageGenerationNode';
export { VideoGenerationNode } from './VideoGenerationNode';
export { PipelineEdge } from './CanvasEdge';
export { SelectionToolbar } from './SelectionToolbar';

/* React Flow nodeTypes / edgeTypes registries */
import { SceneNode } from './SceneNode';
import { ShotNode } from './ShotNode';
import { PromptAssemblyNode } from './PromptAssemblyNode';
import { ImageGenerationNode } from './ImageGenerationNode';
import { VideoGenerationNode } from './VideoGenerationNode';
import { PipelineEdge } from './CanvasEdge';

export const canvasNodeTypes = {
  scene: SceneNode,
  shot: ShotNode,
  promptAssembly: PromptAssemblyNode,
  imageGeneration: ImageGenerationNode,
  videoGeneration: VideoGenerationNode,
} as const;

export const canvasEdgeTypes = {
  pipeline: PipelineEdge,
} as const;
