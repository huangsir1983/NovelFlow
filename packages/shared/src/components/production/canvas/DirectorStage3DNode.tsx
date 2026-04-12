/**
 * DirectorStage3DNode — 3D Director Stage canvas node.
 *
 * Wraps ParallaxStage3D for in-canvas 3D scene composition.
 * Receives VR panorama + depth map from SceneBG, character refs from CharacterProcess.
 * Outputs scene screenshot + per-character screenshots for downstream GeminiComposite.
 */

'use client';

import { memo, useCallback, useEffect, useMemo, useState, lazy, Suspense } from 'react';
import { createPortal } from 'react-dom';
import { Handle, Position, useEdges, useNodes, useReactFlow, type NodeProps } from '@xyflow/react';
import type { DirectorStage3DNodeData, SceneBGNodeData, CharacterProcessNodeData } from '../../../types/canvas';
import type { StageCharacter } from '../../panorama/stageCharacter';
import type { StageScreenshots } from '../../panorama/stageScreenshot';
import { STAGE_CHAR_COLORS } from '../../panorama/stageCharacter';
import { matchActionToPreset } from '../../../lib/actionPresetMatcher';
import { useProjectStore } from '../../../stores/projectStore';
import { useCanvasStore } from '../../../stores/canvasStore';
import { API_BASE_URL } from '../../../lib/api';

const LazyParallaxStage3D = lazy(() => import('../../panorama/ParallaxStage3D'));

const STATUS_COLORS: Record<string, string> = {
  idle: 'border-zinc-700',
  queued: 'border-blue-500',
  running: 'border-blue-400 animate-pulse',
  success: 'border-emerald-500',
  error: 'border-red-500',
};

/** Extract upstream node data by matching node type from incoming edges */
function findUpstreamData<T>(
  edges: Array<{ source: string; target: string }>,
  allNodes: Array<{ id: string; data: Record<string, unknown> }>,
  targetId: string,
  nodeType: string,
): T | undefined {
  for (const e of edges) {
    if (e.target !== targetId) continue;
    const upstream = allNodes.find(n => n.id === e.source);
    if (upstream && upstream.data.nodeType === nodeType) return upstream.data as T;
  }
  return undefined;
}

/** Find all upstream nodes of a given type */
function findAllUpstreamData<T>(
  edges: Array<{ source: string; target: string }>,
  allNodes: Array<{ id: string; data: Record<string, unknown> }>,
  targetId: string,
  nodeType: string,
): T[] {
  const result: T[] = [];
  for (const e of edges) {
    if (e.target !== targetId) continue;
    const upstream = allNodes.find(n => n.id === e.source);
    if (upstream && upstream.data.nodeType === nodeType) result.push(upstream.data as T);
  }
  return result;
}

function DirectorStage3DNodeInner({ id, data }: NodeProps) {
  const d = data as unknown as DirectorStage3DNodeData;
  const [isStageOpen, setIsStageOpen] = useState(false);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number } | null>(null);
  const edges = useEdges();
  const allNodes = useNodes();
  const { setNodes } = useReactFlow();

  // Copy/paste store
  const clipboard = useCanvasStore(s => s.stage3DClipboard);
  const copyStage3D = useCanvasStore(s => s.copyStage3D);
  const pasteStage3D = useCanvasStore(s => s.pasteStage3D);

  const statusClass = STATUS_COLORS[d.status] || STATUS_COLORS.idle;
  const hasScreenshot = !!d.screenshotBase64 || !!d.screenshotStorageKey;
  const screenshotSrc = d.screenshotBase64
    ? `data:image/jpeg;base64,${d.screenshotBase64}`
    : d.screenshotStorageKey
      ? `${API_BASE_URL}/uploads/${d.screenshotStorageKey}`
      : '';

  // Read upstream SceneBG data
  const sceneBGData = useMemo(
    () => findUpstreamData<SceneBGNodeData>(edges, allNodes as never[], id, 'sceneBG'),
    [edges, allNodes, id],
  );

  // Read upstream CharacterProcess data
  const charProcessDatas = useMemo(
    () => findAllUpstreamData<CharacterProcessNodeData>(edges, allNodes as never[], id, 'characterProcess'),
    [edges, allNodes, id],
  );

  const panoramaUrl = d.panoramaUrl || sceneBGData?.panoramaUrl;
  const depthMapUrl = d.depthMapUrl || sceneBGData?.depthMapUrl;
  const hasPanorama = !!panoramaUrl;
  const hasDepthMap = !!depthMapUrl;

  // Build character list for the stage
  const stageCharacters = useMemo<StageCharacter[]>(() => {
    if (d.stageCharacters?.length) return d.stageCharacters;
    // Auto-create from upstream CharacterProcess nodes
    return charProcessDatas.map((cp, i) => {
      const charAction = d.characterActions?.[cp.characterName];
      const presetName = matchActionToPreset(charAction?.action);
      return {
        id: `char-${i}`,
        name: cp.characterName,
        x: -2 + i * 2,
        y: 0,
        z: 0,
        rotationY: 0,
        color: STAGE_CHAR_COLORS[i % STAGE_CHAR_COLORS.length],
        scale: 1,
        jointAngles: {},
        presetName,
      };
    });
  }, [d.stageCharacters, charProcessDatas, d.characterActions]);

  const handleOpenStage = useCallback(() => {
    if (!hasPanorama) return;
    setIsStageOpen(true);
  }, [hasPanorama]);

  const handleCloseStage = useCallback(() => {
    setIsStageOpen(false);
  }, []);

  // Camera state persistence
  const handleCameraStateChange = useCallback(
    (state: { position: { x: number; y: number; z: number }; fov: number; target: { x: number; y: number; z: number } }) => {
      setNodes(nds =>
        nds.map(n =>
          n.id === id ? { ...n, data: { ...n.data, cameraState: state } } : n,
        ),
      );
    },
    [id, setNodes],
  );

  // Right-click context menu
  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({ x: e.clientX, y: e.clientY });
  }, []);

  const handleCopy = useCallback(() => {
    copyStage3D(id);
    setContextMenu(null);
  }, [id, copyStage3D]);

  const handlePaste = useCallback(() => {
    pasteStage3D(id);
    setContextMenu(null);
  }, [id, pasteStage3D]);

  // Close context menu on outside click
  useEffect(() => {
    if (!contextMenu) return;
    const close = () => setContextMenu(null);
    window.addEventListener('click', close);
    return () => window.removeEventListener('click', close);
  }, [contextMenu]);

  const canPaste = !!clipboard && clipboard.sceneId === d.sceneId;

  const handleCharactersUpdate = useCallback(
    (chars: StageCharacter[]) => {
      setNodes(nds =>
        nds.map(n =>
          n.id === id
            ? { ...n, data: { ...n.data, stageCharacters: chars } }
            : n,
        ),
      );
    },
    [id, setNodes],
  );

  const handleScreenshots = useCallback(
    (screenshots: StageScreenshots) => {
      // 1. Immediately update store with base64 data (instant feedback)
      setNodes(nds =>
        nds.map(n => {
          if (n.id === id) {
            return {
              ...n,
              data: {
                ...n.data,
                screenshotBase64: screenshots.base,
                characterScreenshots: screenshots.characters,
                status: 'success',
              },
            };
          }
          // Also propagate to downstream GeminiComposite
          const downEdge = edges.find(e => e.source === id && e.target === n.id);
          if (downEdge && (n.data as Record<string, unknown>).nodeType === 'geminiComposite') {
            const mappings = screenshots.characters.map(sc => {
              const cpData = charProcessDatas.find(
                cp => cp.characterName === sc.stageCharName,
              );
              return {
                stageCharId: sc.stageCharId,
                stageCharName: sc.stageCharName,
                color: sc.color,
                poseScreenshot: sc.screenshot,
                bbox: sc.bbox,
                referenceImageUrl: cpData?.visualRefUrl,
                referenceStorageKey: cpData?.visualRefStorageKey,
              };
            });
            return {
              ...n,
              data: {
                ...n.data,
                sceneScreenshotBase64: screenshots.base,
                characterMappings: mappings,
                status: 'idle',
              },
            };
          }
          return n;
        }),
      );

      // 2. Upload screenshots to storage & persist (async, non-blocking)
      const projectId = useProjectStore.getState().project?.id;
      if (!projectId) return;

      (async () => {
        try {
          const uploadBlob = async (base64: string, filename: string) => {
            const blob = await fetch(`data:image/jpeg;base64,${base64}`).then(r => r.blob());
            const formData = new FormData();
            formData.append('file', blob, filename);
            const resp = await fetch(
              `${API_BASE_URL}/api/projects/${projectId}/asset-images/upload`,
              { method: 'POST', body: formData },
            );
            if (!resp.ok) return null;
            const { storage_key } = await resp.json();
            return storage_key as string;
          };

          // Upload base scene screenshot
          const sceneKey = await uploadBlob(screenshots.base, 'stage3d_scene.jpg');

          // Upload each character screenshot
          const charKeys: Array<{ stageCharId: string; storageKey: string }> = [];
          for (const cs of screenshots.characters) {
            const key = await uploadBlob(cs.screenshot, `stage3d_char_${cs.stageCharId}.jpg`);
            if (key) charKeys.push({ stageCharId: cs.stageCharId, storageKey: key });
          }

          if (!sceneKey) return;

          // Update store with persistent URLs (replace base64 preview)
          const store = useCanvasStore.getState();
          store.setNodes(store.nodes.map(n => {
            if (n.id === id) {
              return {
                ...n,
                data: {
                  ...n.data,
                  screenshotStorageKey: sceneKey,
                  screenshotBase64: screenshots.base, // keep base64 for display
                },
              };
            }
            return n;
          }));

          // Persist to backend: stageCharacters + screenshot keys
          const currentChars = (useCanvasStore.getState().nodes.find(n => n.id === id)
            ?.data as Record<string, unknown>)?.stageCharacters;
          fetch(`${API_BASE_URL}/api/canvas/nodes/${id}/execute`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              node_type: 'directorStage3D',
              content: {
                screenshotStorageKey: sceneKey,
                stageCharacters: currentChars || stageCharacters,
                characterScreenshots: screenshots.characters.map(cs => {
                  const ck = charKeys.find(k => k.stageCharId === cs.stageCharId);
                  return {
                    stageCharId: cs.stageCharId,
                    stageCharName: cs.stageCharName,
                    color: cs.color,
                    storageKey: ck?.storageKey || '',
                    bbox: cs.bbox,
                  };
                }),
                sceneDescription: d.sceneDescription,
              },
            }),
          }).catch(() => {});
        } catch (e) {
          console.error('Failed to upload stage screenshots:', e);
        }
      })();
    },
    [id, edges, charProcessDatas, setNodes, stageCharacters, d.sceneDescription],
  );

  return (
    <>
      <div
        className={`relative rounded-lg border-2 bg-zinc-900 text-white shadow-lg ${statusClass}`}
        style={{ width: 320, minHeight: 200 }}
        onContextMenu={handleContextMenu}
      >
        {/* Handles */}
        <Handle type="target" position={Position.Left} className="!bg-cyan-500 !w-3 !h-3" />
        <Handle type="source" position={Position.Right} className="!bg-cyan-500 !w-3 !h-3" />

        {/* Header */}
        <div className="flex items-center gap-2 px-3 py-2 border-b border-zinc-700">
          <span className="text-sm font-medium">3D导演台</span>
          {hasPanorama && <span className="w-2 h-2 rounded-full bg-emerald-500" title="VR全景已加载" />}
          {hasDepthMap && <span className="w-2 h-2 rounded-full bg-blue-500" title="深度图已加载" />}
          <span className="ml-auto text-xs text-zinc-400">{d.status}</span>
        </div>

        {/* Body */}
        <div className="p-3">
          {hasScreenshot ? (
            <img
              src={screenshotSrc}
              alt="3D导演台截图"
              className="w-full rounded object-cover cursor-pointer hover:opacity-90 transition-opacity"
              style={{ maxHeight: 160 }}
              onClick={handleOpenStage}
            />
          ) : hasPanorama ? (
            <div
              className="flex flex-col items-center justify-center gap-2 rounded bg-zinc-800 cursor-pointer hover:bg-zinc-750 transition-colors"
              style={{ height: 120 }}
              onClick={handleOpenStage}
            >
              <span className="text-2xl">🎬</span>
              <span className="text-xs text-zinc-400">点击打开3D导演台</span>
              {!hasDepthMap && <span className="text-[10px] text-yellow-500/60">无深度图 (无视差效果)</span>}
            </div>
          ) : (
            <div
              className="flex flex-col items-center justify-center gap-2 rounded bg-zinc-800"
              style={{ height: 120 }}
            >
              <span className="text-xs text-zinc-500">等待VR全景图...</span>
            </div>
          )}

          {/* Character indicators */}
          {charProcessDatas.length > 0 && (
            <div className="mt-2 flex gap-1 flex-wrap">
              {charProcessDatas.map((cp, i) => (
                <span
                  key={i}
                  className="text-xs px-1.5 py-0.5 rounded"
                  style={{
                    backgroundColor: STAGE_CHAR_COLORS[i % STAGE_CHAR_COLORS.length],
                    color: '#fff',
                  }}
                >
                  {cp.characterName}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Right-click context menu (portal to body to escape ReactFlow transform) */}
      {contextMenu && createPortal(
        <div
          className="fixed z-[9999] bg-zinc-800 border border-zinc-600 rounded-lg shadow-xl py-1 min-w-[160px]"
          style={{ left: contextMenu.x, top: contextMenu.y }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            className="w-full text-left px-3 py-1.5 text-xs text-zinc-200 hover:bg-zinc-700 transition-colors"
            onClick={handleCopy}
          >
            复制导演台设置
          </button>
          <button
            className={`w-full text-left px-3 py-1.5 text-xs transition-colors ${
              canPaste ? 'text-zinc-200 hover:bg-zinc-700' : 'text-zinc-500 cursor-not-allowed'
            }`}
            onClick={canPaste ? handlePaste : undefined}
            disabled={!canPaste}
          >
            粘贴导演台设置
          </button>
        </div>,
        document.body,
      )}

      {/* ParallaxStage3D fullscreen modal */}
      {isStageOpen && panoramaUrl && (
        <Suspense fallback={null}>
          <LazyParallaxStage3D
            panoramaUrl={panoramaUrl}
            depthMapUrl={depthMapUrl || ''}
            isOpen={isStageOpen}
            onClose={handleCloseStage}
            characters={stageCharacters}
            onCharactersUpdate={handleCharactersUpdate}
            onScreenshots={handleScreenshots}
            onCameraStateChange={handleCameraStateChange}
            initialCameraState={d.cameraState}
          />
        </Suspense>
      )}
    </>
  );
}

export const DirectorStage3DNode = memo(DirectorStage3DNodeInner);
