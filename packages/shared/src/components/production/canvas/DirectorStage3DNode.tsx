/**
 * DirectorStage3DNode — 3D Director Stage canvas node (Tapnow style).
 *
 * Card: ExpressionNode-style display shell (image + badges + status).
 * Left-click: opens ParallaxStage3D full-screen modal.
 * Right-click: copy/paste context menu.
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
import {
  getDirectorStage3DDisplayUrl,
  buildDirectorStage3DBadges,
} from '../../../lib/cardDisplayHelpers';

const LazyParallaxStage3D = lazy(() => import('../../panorama/ParallaxStage3D'));

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

function DirectorStage3DNodeInner({ id, data, selected }: NodeProps) {
  const d = data as unknown as DirectorStage3DNodeData;
  const [hovered, setHovered] = useState(false);
  const [isStageOpen, setIsStageOpen] = useState(false);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number } | null>(null);
  const edges = useEdges();
  const allNodes = useNodes();
  const { setNodes } = useReactFlow();

  // Copy/paste store
  const clipboard = useCanvasStore(s => s.stage3DClipboard);
  const copyStage3D = useCanvasStore(s => s.copyStage3D);
  const pasteStage3D = useCanvasStore(s => s.pasteStage3D);

  // ── Upstream data ──
  const sceneBGData = useMemo(
    () => findUpstreamData<SceneBGNodeData>(edges, allNodes as never[], id, 'sceneBG'),
    [edges, allNodes, id],
  );
  const charProcessDatas = useMemo(
    () => findAllUpstreamData<CharacterProcessNodeData>(edges, allNodes as never[], id, 'characterProcess'),
    [edges, allNodes, id],
  );

  const panoramaUrl = d.panoramaUrl || sceneBGData?.panoramaUrl;
  const depthMapUrl = d.depthMapUrl || sceneBGData?.depthMapUrl;
  const hasPanorama = !!panoramaUrl;
  const hasDepthMap = !!depthMapUrl;
  const hasScreenshot = !!d.screenshotBase64 || !!d.screenshotStorageKey;

  // ── Display ──
  const displayUrl = getDirectorStage3DDisplayUrl(d);
  const badges = buildDirectorStage3DBadges({
    hasPanorama,
    hasDepthMap,
    characterCount: charProcessDatas.length,
    hasScreenshot,
  });

  const cardBorder = selected ? 'rgba(255,255,255,0.16)' : hovered ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.06)';
  const accent = selected ? 'rgba(6,182,212,0.9)' : 'rgba(6,182,212,0.5)';

  // ── Stage characters ──
  const stageCharacters = useMemo<StageCharacter[]>(() => {
    if (d.stageCharacters?.length) return d.stageCharacters;
    return charProcessDatas.map((cp, i) => {
      const charAction = d.characterActions?.[cp.characterName];
      const presetName = matchActionToPreset(charAction?.action);
      return {
        id: `char-${i}`,
        name: cp.characterName,
        x: -2 + i * 2, y: 0, z: 0, rotationY: 0,
        color: STAGE_CHAR_COLORS[i % STAGE_CHAR_COLORS.length],
        scale: 1, jointAngles: {}, presetName,
      };
    });
  }, [d.stageCharacters, charProcessDatas, d.characterActions]);

  // ── Handlers ──
  const handleOpenStage = useCallback(() => {
    if (!hasPanorama) return;
    setIsStageOpen(true);
  }, [hasPanorama]);

  const handleCloseStage = useCallback(() => { setIsStageOpen(false); }, []);

  const handleCameraStateChange = useCallback(
    (state: { position: { x: number; y: number; z: number }; fov: number; target: { x: number; y: number; z: number } }) => {
      setNodes(nds => nds.map(n => n.id === id ? { ...n, data: { ...n.data, cameraState: state } } : n));
    },
    [id, setNodes],
  );

  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault(); e.stopPropagation();
    setContextMenu({ x: e.clientX, y: e.clientY });
  }, []);

  const handleCopy = useCallback(() => { copyStage3D(id); setContextMenu(null); }, [id, copyStage3D]);
  const handlePaste = useCallback(() => { pasteStage3D(id); setContextMenu(null); }, [id, pasteStage3D]);

  useEffect(() => {
    if (!contextMenu) return;
    const close = () => setContextMenu(null);
    window.addEventListener('click', close);
    return () => window.removeEventListener('click', close);
  }, [contextMenu]);

  const canPaste = useMemo(() => {
    if (!clipboard) return false;
    const findSceneLocation = (sceneId: string) => {
      const sceneNode = allNodes.find(n => (n.data as Record<string, unknown>).nodeType === 'scene' && (n.data as Record<string, unknown>).sceneId === sceneId);
      return (sceneNode?.data as Record<string, unknown>)?.location as string | undefined;
    };
    const srcLocation = findSceneLocation(clipboard.sceneId);
    const tgtLocation = findSceneLocation(d.sceneId);
    return !!srcLocation && !!tgtLocation && srcLocation === tgtLocation;
  }, [clipboard, allNodes, d.sceneId]);

  const handleCharactersUpdate = useCallback(
    (chars: StageCharacter[]) => {
      setNodes(nds => nds.map(n => n.id === id ? { ...n, data: { ...n.data, stageCharacters: chars } } : n));
    },
    [id, setNodes],
  );

  const handleScreenshots = useCallback(
    (screenshots: StageScreenshots) => {
      setNodes(nds =>
        nds.map(n => {
          if (n.id === id) {
            return { ...n, data: { ...n.data, screenshotBase64: screenshots.base, characterScreenshots: screenshots.characters, status: 'success' } };
          }
          const downEdge = edges.find(e => e.source === id && e.target === n.id);
          if (downEdge && (n.data as Record<string, unknown>).nodeType === 'geminiComposite') {
            const mappings = screenshots.characters.map(sc => {
              const cpData = charProcessDatas.find(cp => cp.characterName === sc.stageCharName);
              return {
                stageCharId: sc.stageCharId, stageCharName: sc.stageCharName, color: sc.color,
                poseScreenshot: sc.screenshot, bbox: sc.bbox,
                referenceImageUrl: cpData?.visualRefUrl, referenceStorageKey: cpData?.visualRefStorageKey,
              };
            });
            return { ...n, data: { ...n.data, sceneScreenshotBase64: screenshots.base, characterMappings: mappings, status: 'idle' } };
          }
          return n;
        }),
      );

      const projectId = useProjectStore.getState().project?.id;
      if (!projectId) return;

      (async () => {
        try {
          const uploadBlob = async (base64: string, filename: string) => {
            const blob = await fetch(`data:image/jpeg;base64,${base64}`).then(r => r.blob());
            const formData = new FormData();
            formData.append('file', blob, filename);
            const resp = await fetch(`${API_BASE_URL}/api/projects/${projectId}/asset-images/upload`, { method: 'POST', body: formData });
            if (!resp.ok) return null;
            const { storage_key } = await resp.json();
            return storage_key as string;
          };

          const sceneKey = await uploadBlob(screenshots.base, 'stage3d_scene.jpg');
          const charKeys: Array<{ stageCharId: string; storageKey: string }> = [];
          for (const cs of screenshots.characters) {
            const key = await uploadBlob(cs.screenshot, `stage3d_char_${cs.stageCharId}.jpg`);
            if (key) charKeys.push({ stageCharId: cs.stageCharId, storageKey: key });
          }

          if (!sceneKey) return;

          const store = useCanvasStore.getState();
          store.setNodes(store.nodes.map(n => {
            if (n.id === id) {
              return { ...n, data: { ...n.data, screenshotStorageKey: sceneKey, screenshotBase64: screenshots.base } };
            }
            return n;
          }));

          const currentChars = (useCanvasStore.getState().nodes.find(n => n.id === id)?.data as Record<string, unknown>)?.stageCharacters;
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
                  return { stageCharId: cs.stageCharId, stageCharName: cs.stageCharName, color: cs.color, storageKey: ck?.storageKey || '', bbox: cs.bbox };
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

  // ── Render (ExpressionNode-style) ──
  return (
    <>
      <div
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        onContextMenu={handleContextMenu}
        style={{ width: 300, position: 'relative' }}
      >
        <Handle type="target" position={Position.Left} className="target-handle" style={{ top: '55%' }} />
        <Handle type="source" position={Position.Right} style={{ top: '55%' }} />

        {/* Title bar (outside card) */}
        <div className="flex items-center gap-1.5 mb-2 pl-1">
          <span className="text-[13px]">🎬</span>
          <span className="text-[12px] font-medium tracking-wide" style={{ color: accent }}>3D导演台</span>
        </div>

        {/* Main card */}
        <div className="canvas-card" style={{
          borderRadius: 16, position: 'relative', overflow: 'hidden',
          border: `1px solid ${cardBorder}`,
          transition: 'border-color 0.2s',
          cursor: hasPanorama ? 'pointer' : 'default',
        }} onClick={handleOpenStage}>
          {/* Image area */}
          <div style={{
            width: '100%', minHeight: 100,
            backgroundColor: '#0c0e12',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            {displayUrl ? (
              <img src={displayUrl} alt="3D导演台截图" style={{ width: '100%', height: 'auto', display: 'block' }} />
            ) : (
              <div style={{ textAlign: 'center', padding: '40px 0' }}>
                <span style={{ fontSize: 28, display: 'block', color: 'rgba(255,255,255,0.06)', marginBottom: 4 }}>🎬</span>
                <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.15)' }}>
                  {hasPanorama ? '点击打开导演台' : '等待VR全景图'}
                </span>
              </div>
            )}
          </div>

          {/* Gradient overlay with badges */}
          <div style={{
            position: 'absolute', bottom: 0, left: 0, right: 0,
            background: 'linear-gradient(transparent, rgba(0,0,0,0.75))',
            padding: '24px 12px 10px',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
              {badges.map((b, i) => (
                <span key={i} style={{
                  fontSize: 9, padding: '2px 6px', borderRadius: 4,
                  backgroundColor: b.bgColor, color: b.textColor,
                }}>{b.text}</span>
              ))}
              {/* Character name chips */}
              {charProcessDatas.map((cp, i) => (
                <span key={`char-${i}`} style={{
                  fontSize: 9, padding: '2px 6px', borderRadius: 4,
                  backgroundColor: STAGE_CHAR_COLORS[i % STAGE_CHAR_COLORS.length],
                  color: '#fff', maxWidth: 60, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>{cp.characterName}</span>
              ))}
            </div>
          </div>

          {/* Status dot */}
          <div style={{
            position: 'absolute', top: 10, right: 10, width: 8, height: 8,
            borderRadius: '50%', zIndex: 2,
            backgroundColor:
              d.status === 'running' ? '#60a5fa'
              : d.status === 'success' ? '#34d399'
              : d.status === 'error' ? '#f87171'
              : 'transparent',
          }} />

          {/* Progress bar */}
          {d.status === 'running' && (
            <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 3, backgroundColor: 'rgba(0,0,0,0.3)' }}>
              <div style={{ height: '100%', backgroundColor: 'rgba(6,182,212,0.6)', width: `${d.progress ?? 0}%` }} />
            </div>
          )}
        </div>
      </div>

      {/* Right-click context menu */}
      {contextMenu && createPortal(
        <div
          className="fixed z-[9999] border border-zinc-500/40 rounded-lg shadow-xl py-1 min-w-[160px] backdrop-blur-xl"
          style={{ left: contextMenu.x, top: contextMenu.y, backgroundColor: 'rgba(39, 39, 42, 0.75)' }}
          onClick={(e) => e.stopPropagation()}
        >
          <button className="w-full text-left px-3 py-1.5 text-xs text-zinc-200 hover:bg-white/10 transition-colors" onClick={handleCopy}>
            复制导演台设置
          </button>
          <button
            className={`w-full text-left px-3 py-1.5 text-xs transition-colors ${canPaste ? 'text-zinc-200 hover:bg-white/10' : 'text-zinc-500 cursor-not-allowed'}`}
            onClick={canPaste ? handlePaste : undefined}
            disabled={!canPaste}
          >
            粘贴导演台设置{!clipboard ? '' : !canPaste ? ' (地点不同)' : ''}
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
