// ══════════════════════════════════════════════════════════════
// infinite-canvas/index.ts — 模块导出
// ══════════════════════════════════════════════════════════════

export { InfiniteCanvas } from './InfiniteCanvas';
export { CanvasRenderer } from './CanvasRenderer';
export { ConnectionLayer } from './ConnectionLayer';

export { BaseNode, StatusPill } from './nodes/BaseNode';
export { StoryboardNode } from './nodes/StoryboardNode';
export { ImageNode } from './nodes/ImageNode';
export { VideoNode } from './nodes/VideoNode';

export { MODULE_TEMPLATES, detectModuleType } from './modules/ModuleTemplates';

export { Toolbar } from './toolbar/Toolbar';
export { MiniMap } from './toolbar/MiniMap';

export { NodeInspector } from './panels/NodeInspector';
export { ChainProgressPanel } from './panels/ChainProgressPanel';
