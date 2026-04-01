'use client';

import { useCallback, useMemo } from 'react';
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  MiniMap,
  Controls,
  ReactFlowProvider,
  type OnSelectionChangeParams,
} from '@xyflow/react';
import '@xyflow/react/dist/base.css';

/* Override React Flow default node styles that kill our custom styling */
const RF_OVERRIDES = `
.react-flow__node {
  background: transparent !important;
  border: none !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  outline: none !important;
  padding: 0 !important;
}
.react-flow__node.selected {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  outline: none !important;
}
.react-flow__node:focus,
.react-flow__node:focus-visible {
  outline: none !important;
  box-shadow: none !important;
}
.react-flow__handle {
  opacity: 0 !important;
  pointer-events: none !important;
}
.react-flow__edge-path {
  stroke: rgba(255,255,255,0.12) !important;
  stroke-width: 1.5 !important;
}
.react-flow__pane {
  background: transparent !important;
}
.react-flow__attribution {
  display: none !important;
}
.react-flow__minimap {
  background: rgba(10,12,18,0.95) !important;
  border: 1px solid rgba(255,255,255,0.06) !important;
  border-radius: 12px !important;
}
.react-flow__controls {
  background: rgba(10,12,18,0.95) !important;
  border: 1px solid rgba(255,255,255,0.06) !important;
  border-radius: 12px !important;
}
.react-flow__controls button {
  background: transparent !important;
  border: none !important;
  color: rgba(255,255,255,0.5) !important;
  fill: rgba(255,255,255,0.5) !important;
}
.react-flow__controls button:hover {
  background: rgba(255,255,255,0.05) !important;
}
.react-flow__controls button svg {
  fill: rgba(255,255,255,0.5) !important;
}
`;

import { useProjectStore } from '../../stores/projectStore';
import { useBoardStore } from '../../stores/boardStore';
import { useCanvasStore } from '../../stores/canvasStore';
import { useCanvasSync } from '../../hooks/useCanvasSync';
import { canvasNodeTypes, canvasEdgeTypes, SelectionToolbar } from './canvas';
import { SceneListPanel } from './canvas/SceneListPanel';
import { VideoPreviewPanel } from './canvas/VideoPreviewPanel';
import { PromptBar } from './canvas/PromptBar';
import { AIAssistantPanel } from './canvas/AIAssistantPanel';
import { NodeFloatingToolbar } from './canvas/NodeFloatingToolbar';

interface ShotProductionBoardProps {
  projectName: string;
  onOpenPreview: () => void;
}

function CanvasInner({ projectName, onOpenPreview }: ShotProductionBoardProps) {
  // Sync domain data → React Flow nodes/edges
  useCanvasSync();

  const nodes = useCanvasStore((s) => s.nodes);
  const edges = useCanvasStore((s) => s.edges);
  const onNodesChange = useCanvasStore((s) => s.onNodesChange);
  const onEdgesChange = useCanvasStore((s) => s.onEdgesChange);
  const setViewport = useCanvasStore((s) => s.setViewport);
  const selectNodes = useCanvasStore((s) => s.selectNodes);
  const selectedNodeIds = useCanvasStore((s) => s.selectedNodeIds);
  const setInspectedNode = useCanvasStore((s) => s.setInspectedNode);
  const setFocusedSceneId = useCanvasStore((s) => s.setFocusedSceneId);

  const leftPanelOpen = useCanvasStore((s) => s.leftPanelOpen);
  const rightPanelOpen = useCanvasStore((s) => s.rightPanelOpen);
  const toggleLeftPanel = useCanvasStore((s) => s.toggleLeftPanel);
  const toggleRightPanel = useCanvasStore((s) => s.toggleRightPanel);
  const aiPanelOpen = useCanvasStore((s) => s.aiPanelOpen);
  const toggleAIPanel = useCanvasStore((s) => s.toggleAIPanel);
  const viewport = useCanvasStore((s) => s.viewport);

  const scenes = useProjectStore((s) => s.scenes);

  const handleSelectionChange = useCallback(
    ({ nodes: selectedNodes }: OnSelectionChangeParams) => {
      selectNodes(selectedNodes.map((n) => n.id));
    },
    [selectNodes],
  );

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: any) => {
      setInspectedNode(node.id);
      // Only update focusedSceneId — do NOT trigger fitView or any viewport change
    },
    [setInspectedNode],
  );

  const handlePaneClick = useCallback(() => {
    setInspectedNode(null);
    selectNodes([]);
  }, [setInspectedNode, selectNodes]);

  // Empty state
  if (scenes.length === 0 && nodes.length === 0) {
    return (
      <div className="flex h-full items-center justify-center bg-[#090d18]">
        <div className="text-center">
          <div className="text-4xl text-white/10 mb-4">◇</div>
          <div className="text-sm text-white/40">当前还没有场景数据</div>
          <div className="text-xs text-white/25 mt-1">请先在剧本构思阶段导入小说并生成场景</div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative h-full w-full bg-black" onContextMenu={(e) => e.preventDefault()}>
      <style dangerouslySetInnerHTML={{ __html: RF_OVERRIDES }} />
      {/* React Flow Canvas */}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={canvasNodeTypes}
        edgeTypes={canvasEdgeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onViewportChange={setViewport}
        onSelectionChange={handleSelectionChange}
        onNodeClick={handleNodeClick}
        onPaneClick={handlePaneClick}
        defaultViewport={{ x: 50, y: 50, zoom: 0.4 }}
        minZoom={0.02}
        maxZoom={3}
        proOptions={{ hideAttribution: true }}
        defaultEdgeOptions={{
          type: 'pipeline',
          animated: false,
        }}
        onlyRenderVisibleElements
        selectNodesOnDrag={false}
        nodesDraggable
        panOnDrag={[1, 2]}
        zoomOnScroll
      >
        {/* Dynamic background: hide dots when zoomed out */}
        {viewport.zoom > 0.25 && (
          <Background
            variant={BackgroundVariant.Dots}
            gap={20}
            size={Math.max(0.5, 1.5 * viewport.zoom)}
            color={`rgba(255,255,255,${Math.min(0.18, viewport.zoom * 0.3)})`}
            style={{ backgroundColor: '#000000' }}
          />
        )}
        <MiniMap
          nodeColor={(n) => {
            const nt = n.type;
            if (nt === 'scene') return 'rgba(0,200,255,0.5)';
            if (nt === 'shot') return 'rgba(255,150,50,0.5)';
            if (nt === 'promptAssembly') return 'rgba(50,200,100,0.5)';
            if (nt === 'imageGeneration') return 'rgba(255,200,50,0.5)';
            if (nt === 'videoGeneration') return 'rgba(200,50,255,0.5)';
            return 'rgba(255,255,255,0.2)';
          }}
          maskColor="rgba(0,0,0,0.8)"
          position="bottom-left"
          style={{
            backgroundColor: 'rgba(10,15,26,0.95)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: '8px',
          }}
          pannable
          zoomable
        />
        <Controls
          showInteractive={false}
          position="bottom-left"
          style={{
            backgroundColor: 'rgba(10,15,26,0.95)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: '8px',
          }}
        />
      </ReactFlow>

      {/* Top bar */}
      <div className="pointer-events-none absolute inset-x-0 top-0 z-10 p-3">
        <div className="pointer-events-auto inline-flex items-center gap-3 rounded-xl border border-white/[0.08] bg-[#0a0f1a]/90 px-4 py-2.5 backdrop-blur-xl">
          <div>
            <div className="text-[9px] uppercase tracking-[0.3em] text-cyan-300/60">Workflow Canvas</div>
            <div className="text-sm font-medium text-white/85">{projectName}</div>
          </div>
          <button
            type="button"
            onClick={onOpenPreview}
            className="ml-4 rounded-lg bg-cyan-500/20 px-3 py-1.5 text-xs font-medium text-cyan-100 hover:bg-cyan-500/30 transition-colors"
          >
            Preview
          </button>
        </div>
      </div>

      {/* Left panel - Scene list (initially hidden, toggle with button) */}
      {leftPanelOpen && <SceneListPanel />}

      {/* Right panel - Video preview (initially hidden, toggle with button) */}
      {rightPanelOpen && <VideoPreviewPanel />}

      {/* Bottom prompt bar */}
      <PromptBar />

      {/* Selection toolbar */}
      <SelectionToolbar
        selectedCount={selectedNodeIds.length}
        onRunSelected={() => {/* TODO: batch run */}}
        onDeleteSelected={() => {/* TODO: batch delete */}}
        onGroupSelected={() => {/* TODO: grouping */}}
      />

      {/* Floating toolbar for selected node (edit bar + AI input) */}
      {selectedNodeIds.length === 1 && (
        <NodeFloatingToolbar nodeId={selectedNodeIds[0]} />
      )}

      {/* Panel toggle buttons */}
      <button
        onClick={toggleLeftPanel}
        className={`
          pointer-events-auto absolute z-40 flex h-8 w-8 items-center justify-center
          rounded-full border border-white/[0.08] bg-[#0a0f1a]/90 text-[10px] text-white/60
          hover:bg-white/[0.10] transition-all
          ${leftPanelOpen ? 'left-[274px] top-[88px]' : 'left-3 top-[88px]'}
        `}
      >
        {leftPanelOpen ? '◀' : '▶'}
      </button>
      <button
        onClick={toggleRightPanel}
        className={`
          pointer-events-auto absolute z-40 flex h-8 w-8 items-center justify-center
          rounded-full border border-white/[0.08] bg-[#0a0f1a]/90 text-[10px] text-white/60
          hover:bg-white/[0.10] transition-all
          ${rightPanelOpen ? 'right-[294px] top-[88px]' : 'right-3 top-[88px]'}
        `}
      >
        {rightPanelOpen ? '▶' : '◀'}
      </button>

      {/* AI Assistant Panel */}
      <AIAssistantPanel />

      {/* AI Panel toggle — floating circle button (bottom-right) */}
      {!aiPanelOpen && (
        <div
          onClick={toggleAIPanel}
          onMouseEnter={(e) => { e.currentTarget.style.transform = 'scale(1.1)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.transform = 'scale(1)'; }}
          style={{
            position: 'absolute',
            bottom: 24,
            right: 24,
            zIndex: 100,
            width: 48,
            height: 48,
            borderRadius: '50%',
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            boxShadow: '0 4px 20px rgba(99, 102, 241, 0.4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontSize: 20,
            cursor: 'pointer',
            transition: 'transform 0.15s',
            pointerEvents: 'auto',
          }}
          title="AI 创作助手"
          role="button"
        >
          ✦
        </div>
      )}
    </div>
  );
}

/** Wraps the canvas in ReactFlowProvider to enable useReactFlow() in sub-components */
export function ShotProductionBoard(props: ShotProductionBoardProps) {
  return (
    <ReactFlowProvider>
      <CanvasInner {...props} />
    </ReactFlowProvider>
  );
}
