'use client';

import { useCallback, useMemo, useDeferredValue } from 'react';
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  ReactFlowProvider,
  type OnSelectionChangeParams,
  type Edge,
  type Connection,
  addEdge,
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
  width: 1px !important;
  height: 1px !important;
  min-width: 0 !important;
  min-height: 0 !important;
  border: none !important;
  background: transparent !important;
  padding: 0 !important;
  margin: 0 !important;
}
.react-flow__handle-left {
  left: 0 !important;
  transform: translateY(-50%) !important;
}
.react-flow__handle-right {
  right: 0 !important;
  transform: translateY(-50%) !important;
}
.react-flow__handle.plus-source {
  opacity: 0 !important;
  pointer-events: auto !important;
  width: 32px !important;
  height: 32px !important;
  border-radius: 50% !important;
  border: none !important;
  background: transparent !important;
  position: absolute !important;
  top: 0 !important;
  left: 0 !important;
  transform: none !important;
  cursor: crosshair !important;
  z-index: 11 !important;
}
.react-flow__handle-left.target-handle {
  opacity: 0 !important;
  pointer-events: none !important;
  width: 1px !important;
  height: 1px !important;
  left: 0 !important;
  background: transparent !important;
  border: none !important;
}
.react-flow.connecting .react-flow__handle-left.target-handle {
  opacity: 1 !important;
  pointer-events: auto !important;
  width: 14px !important;
  height: 14px !important;
  background: rgba(52,211,153,0.5) !important;
  border: 2px solid rgba(52,211,153,0.8) !important;
  border-radius: 50% !important;
  left: -7px !important;
  transition: transform 0.15s !important;
}
.react-flow.connecting .react-flow__handle-left.target-handle:hover {
  transform: scale(1.5) !important;
  background: rgba(52,211,153,0.9) !important;
  box-shadow: 0 0 8px rgba(52,211,153,0.4) !important;
}
.react-flow__connection-path {
  stroke: rgba(0,200,255,0.5) !important;
  stroke-width: 2 !important;
  stroke-dasharray: 6 3 !important;
}
.canvas-card {
  box-shadow: none !important;
}
.react-flow__node:hover .canvas-card {
  box-shadow: none !important;
}
.react-flow__node.selected .canvas-card {
  box-shadow: 0 0 0 1px rgba(0,200,255,0.4) !important;
}
.react-flow__pane {
  background: transparent !important;
}
.react-flow__attribution {
  display: none !important;
}
input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #fff;
  cursor: pointer;
  box-shadow: 0 1px 4px rgba(0,0,0,0.4);
}
input[type="range"]::-moz-range-thumb {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #fff;
  cursor: pointer;
  border: none;
  box-shadow: 0 1px 4px rgba(0,0,0,0.4);
}
`;

import { useProjectStore } from '../../stores/projectStore';
import { useBoardStore } from '../../stores/boardStore';
import { useCanvasStore } from '../../stores/canvasStore';
import { useCanvasSync } from '../../hooks/useCanvasSync';
import { useCanvasVirtualization } from '../../hooks/useCanvasVirtualization';
import { canvasNodeTypes, canvasEdgeTypes, SelectionToolbar } from './canvas';
import { SceneListPanel } from './canvas/SceneListPanel';
import { VideoPreviewPanel } from './canvas/VideoPreviewPanel';
import { PromptBar } from './canvas/PromptBar';
import { AIAssistantPanel } from './canvas/AIAssistantPanel';
import { NodeFloatingToolbar } from './canvas/NodeFloatingToolbar';
import { SceneNavigatorWheel } from './canvas/SceneNavigatorWheel';
import { CanvasLeftToolbar } from './canvas/CanvasLeftToolbar';
import { BoxSelectExecutor } from './canvas/BoxSelectExecutor';
import { CanvasLiteMinimap } from './canvas/CanvasLiteMinimap';
import { CanvasBottomToolbar } from './canvas/CanvasBottomToolbar';
import { CompositeEditor } from './canvas/CompositeEditor';
import { API_BASE_URL } from '../../lib/api';
import type { CompositeLayerItem } from '../../types/canvas';
import { useNodeExecution } from '../../hooks/useNodeExecution';

interface ShotProductionBoardProps {
  projectName: string;
  onOpenPreview: () => void;
}

function CanvasInner({ projectName, onOpenPreview }: ShotProductionBoardProps) {
  // Sync domain data → React Flow nodes/edges
  useCanvasSync();

  // Scene-level virtualization (updates sceneGroups, visibleSceneIds, renderMode)
  useCanvasVirtualization();

  const { propagateOutput } = useNodeExecution();

  const rawNodes = useCanvasStore((s) => s.nodes);
  const rawEdges = useCanvasStore((s) => s.edges);
  const visibleSceneIds = useCanvasStore((s) => s.visibleSceneIds);
  const focusedSceneId = useCanvasStore((s) => s.focusedSceneId);

  // Filter nodes/edges to only visible scenes — avoids React Flow processing thousands of offscreen nodes
  // Always include focusedSceneId so navigation (fan wheel) can fitView to it immediately
  const filteredNodes = useMemo(() => {
    if (!visibleSceneIds || visibleSceneIds.size === 0) return rawNodes;
    return rawNodes.filter((n) => {
      const sceneId = (n.data as Record<string, unknown>)?.sceneId as string | undefined;
      return !sceneId || visibleSceneIds.has(sceneId) || sceneId === focusedSceneId;
    });
  }, [rawNodes, visibleSceneIds, focusedSceneId]);

  const visibleNodeIds = useMemo(() => new Set(filteredNodes.map((n) => n.id)), [filteredNodes]);

  const filteredEdges = useMemo(() => {
    if (!visibleSceneIds || visibleSceneIds.size === 0) return rawEdges;
    return rawEdges.filter((e) => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target));
  }, [rawEdges, visibleNodeIds, visibleSceneIds]);

  const nodes = useDeferredValue(filteredNodes);
  const edges = useDeferredValue(filteredEdges);
  const onNodesChange = useCanvasStore((s) => s.onNodesChange);
  const onEdgesChange = useCanvasStore((s) => s.onEdgesChange);
  const setViewport = useCanvasStore((s) => s.setViewport);
  const selectNodes = useCanvasStore((s) => s.selectNodes);
  const selectedNodeIds = useCanvasStore((s) => s.selectedNodeIds);
  const setInspectedNode = useCanvasStore((s) => s.setInspectedNode);
  const setFocusedSceneId = useCanvasStore((s) => s.setFocusedSceneId);

  const setEdges = useCanvasStore((s) => s.setEdges);
  const addManualEdge = useCanvasStore((s) => s.addManualEdge);
  const disconnectEdge = useCanvasStore((s) => s.disconnectEdge);

  const handleConnect = useCallback(
    (connection: Connection) => {
      const newEdge: Edge = {
        id: `manual-${connection.source}-${connection.target}`,
        source: connection.source,
        target: connection.target,
        type: 'pipeline',
        data: { manual: true },
      };
      // Store in manualEdges (survives graph rebuilds) and also add to current edges
      addManualEdge(newEdge);
      const currentEdges = useCanvasStore.getState().edges;
      setEdges(addEdge(newEdge, currentEdges));
    },
    [addManualEdge, setEdges],
  );

  const handleEdgeClick = useCallback(
    (_: React.MouseEvent, edge: Edge) => {
      // Only pipeline edges with segment data can be disconnected; bypass is not clickable
      if (edge.type === 'bypass') return;
      const edgeData = edge.data as { shotId?: string; segment?: string } | undefined;
      if (edgeData?.shotId && edgeData?.segment) {
        disconnectEdge(edgeData.shotId, edgeData.segment);
      }
    },
    [disconnectEdge],
  );

  const leftPanelOpen = useCanvasStore((s) => s.leftPanelOpen);
  const rightPanelOpen = useCanvasStore((s) => s.rightPanelOpen);
  const toggleLeftPanel = useCanvasStore((s) => s.toggleLeftPanel);
  const toggleRightPanel = useCanvasStore((s) => s.toggleRightPanel);
  const aiPanelOpen = useCanvasStore((s) => s.aiPanelOpen);
  const toggleAIPanel = useCanvasStore((s) => s.toggleAIPanel);
  const viewport = useCanvasStore((s) => s.viewport);
  const snapToGrid = useCanvasStore((s) => s.snapToGrid);
  const miniMapOpen = useCanvasStore((s) => s.miniMapOpen);

  const scenes = useProjectStore((s) => s.scenes);

  // Composite editor state
  const compositeEditorOpen = useCanvasStore((s) => s.compositeEditorOpen);
  const compositeEditorShotId = useCanvasStore((s) => s.compositeEditorShotId);
  const closeCompositeEditor = useCanvasStore((s) => s.closeCompositeEditor);

  // Find composite node data when editor is open
  const compositeNode = useMemo(() => {
    if (!compositeEditorOpen || !compositeEditorShotId) return null;
    return rawNodes.find((n) => n.id === `composite-${compositeEditorShotId}`);
  }, [compositeEditorOpen, compositeEditorShotId, rawNodes]);

  const handleCompositeEditorSave = useCallback(
    async (imageDataUrl: string, updatedLayers: CompositeLayerItem[]) => {
      if (!compositeNode) return;
      const nodeId = compositeNode.id;

      // Update node locally with layers + output preview
      const allNodes = useCanvasStore.getState().nodes;
      useCanvasStore.getState().setNodes(
        allNodes.map((n) =>
          n.id === nodeId
            ? { ...n, data: { ...n.data, layers: updatedLayers, outputImageUrl: imageDataUrl } }
            : n,
        ),
      );
      // Persist layer positions/sizes to backend
      useCanvasStore.getState().persistCompositeLayers(nodeId, updatedLayers as unknown as Array<Record<string, unknown>>);
      closeCompositeEditor();

      // Upload the exported image to backend
      try {
        const blob = await fetch(imageDataUrl).then((r) => r.blob());
        const formData = new FormData();
        formData.append('file', blob, 'composite_output.png');

        const projectId = useProjectStore.getState().project?.id;
        if (!projectId) return;

        const resp = await fetch(
          `${API_BASE_URL}/api/projects/${projectId}/asset-images/upload`,
          { method: 'POST', body: formData },
        );
        if (!resp.ok) return;
        const { storage_key } = await resp.json();
        const persistentUrl = `${API_BASE_URL}/uploads/${storage_key}`;

        // Update node with persistent URL
        const latestNodes = useCanvasStore.getState().nodes;
        useCanvasStore.getState().setNodes(
          latestNodes.map((n) =>
            n.id === nodeId
              ? { ...n, data: { ...n.data, outputImageUrl: persistentUrl } }
              : n,
          ),
        );

        // Persist to backend
        await fetch(`${API_BASE_URL}/api/canvas/nodes/${nodeId}/execute`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            node_type: 'composite',
            content: { outputStorageKey: storage_key },
          }),
        });

        // Propagate output to downstream nodes (e.g. BlendRefine)
        propagateOutput(nodeId, persistentUrl, storage_key);
      } catch (e) {
        console.error('Failed to persist composite output:', e);
      }
    },
    [compositeNode, closeCompositeEditor, propagateOutput],
  );

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
  if (scenes.length === 0 && rawNodes.length === 0) {
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
        onConnect={handleConnect}
        onViewportChange={setViewport}
        onSelectionChange={handleSelectionChange}
        onNodeClick={handleNodeClick}
        onEdgeClick={handleEdgeClick}
        onPaneClick={handlePaneClick}
        defaultViewport={{ x: 50, y: 50, zoom: 0.4 }}
        minZoom={0.02}
        maxZoom={3}
        proOptions={{ hideAttribution: true }}
        defaultEdgeOptions={{
          type: 'pipeline',
          animated: false,
        }}
        snapToGrid={snapToGrid}
        snapGrid={[20, 20]}
        onlyRenderVisibleElements
        selectNodesOnDrag={false}
        nodesDraggable
        panOnDrag={[1, 2]}
        zoomOnScroll
      >
        {/* Background: always render for consistent #000 color; dots only when zoomed in */}
        <Background
          variant={BackgroundVariant.Dots}
          gap={40}
          size={viewport.zoom > 0.35 ? Math.max(0.3, 0.8 * viewport.zoom) : 0}
          color={viewport.zoom > 0.35 ? `rgba(255,255,255,${Math.min(0.12, viewport.zoom * 0.15)})` : 'transparent'}
          style={{ backgroundColor: '#000000' }}
        />
        {/* MiniMap removed — replaced by lightweight CanvasLiteMinimap outside ReactFlow */}
      </ReactFlow>

      {/* Lightweight canvas-based minimap — reads rawNodes from store, no ReactFlow overhead */}
      {miniMapOpen && <CanvasLiteMinimap />}

      {/* Bottom toolbar: minimap toggle, snap, fit view, zoom slider */}
      <CanvasBottomToolbar />

      {/* Left toolbar: icon bar + expandable panels */}
      <CanvasLeftToolbar />

      {/* Fan-shaped scene navigator (right of toolbar) */}
      <SceneNavigatorWheel />

      {/* Box Select Executor (Shift+drag overlay) */}
      <BoxSelectExecutor />

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

      {/* Composite Editor — full-screen portal overlay */}
      {compositeEditorOpen && compositeNode && (
        <CompositeEditor
          layers={(compositeNode.data as any).layers ?? []}
          canvasWidth={(compositeNode.data as any).canvasWidth ?? 1920}
          canvasHeight={(compositeNode.data as any).canvasHeight ?? 1080}
          onSave={handleCompositeEditorSave}
          onClose={closeCompositeEditor}
        />
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
