'use client';

import { memo, useState, useCallback, useRef } from 'react';
import { type NodeProps, type Node, Handle, Position } from '@xyflow/react';
import type { SceneBGNodeData, ViewPoint } from '../../../types/canvas';
import { PanoramaViewer } from '../../panorama/PanoramaViewer';
import { useProjectStore } from '../../../stores/projectStore';
import { useCanvasStore } from '../../../stores/canvasStore';
import { API_BASE_URL } from '../../../lib/api';

type SceneBGNode = Node<SceneBGNodeData, 'sceneBG'>;

function SceneBGNodeComponent({ id, data, selected }: NodeProps<SceneBGNode>) {
  const [hovered, setHovered] = useState(false);
  const [panoramaOpen, setPanoramaOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);

  const cardBorder = selected ? 'rgba(255,255,255,0.16)' : hovered ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.06)';
  const accent = selected ? 'rgba(6,182,212,0.9)' : 'rgba(6,182,212,0.5)';

  const previewUrl = data.screenshotUrl || data.panoramaUrl || data.visualRefUrl;

  // Resolve active viewpoint
  const activeVp = data.viewpoints?.find(v => v.id === data.activeViewpointId);
  const displayYaw = activeVp?.yaw ?? data.viewAngle?.yaw ?? 0;
  const displayPitch = activeVp?.pitch ?? data.viewAngle?.pitch ?? 0;
  const displayFov = activeVp?.fov ?? data.viewAngle?.fov ?? 75;
  const hasPosition = activeVp && ((activeVp.posX ?? 0) !== 0 || (activeVp.posY ?? 0) !== 0 || (activeVp.posZ ?? 0) !== 0);
  const hasCorrection = activeVp && (activeVp.correctionStrength ?? 0.5) !== 0.5;

  // Handle panorama screenshot: upload + update this node's data
  const handleScreenshot = useCallback(async (base64: string, viewAngle: { yaw: number; pitch: number; fov: number }) => {
    const projectId = useProjectStore.getState().project?.id;
    const screenshotUrl = `data:image/jpeg;base64,${base64}`;

    // Immediately update this node's screenshotUrl + viewAngle via store
    const currentNodes = useCanvasStore.getState().nodes;
    useCanvasStore.getState().setNodes(currentNodes.map((n) =>
      n.id === id
        ? { ...n, data: { ...n.data, screenshotUrl, viewAngle, status: 'success', progress: 100 } }
        : n,
    ));

    // Reset all downstream nodes' green dots
    useCanvasStore.getState().resetDownstreamNodes(id);

    setPanoramaOpen(false);

    if (!projectId) return;

    try {
      const blob = await fetch(`data:image/jpeg;base64,${base64}`).then((r) => r.blob());
      const formData = new FormData();
      formData.append('file', blob, 'scene_bg_screenshot.jpg');

      const resp = await fetch(
        `${API_BASE_URL}/api/projects/${projectId}/asset-images/upload`,
        { method: 'POST', body: formData },
      );
      if (!resp.ok) return;
      const { storage_key } = await resp.json();

      const persistentUrl = `${API_BASE_URL}/uploads/${storage_key}`;
      const shotId = id.replace('scenebg-', '');
      const compositeId = `composite-${shotId}`;

      const store = useCanvasStore.getState();
      const storeNodes = store.nodes;
      const edges = store.edges;

      // Find hdUpscale downstream (if any)
      let bgSourceId = id;
      const directDown = edges.filter(e => e.source === id);
      for (const edge of directDown) {
        const tgt = storeNodes.find(n => n.id === edge.target);
        if (tgt && (tgt.data as Record<string, unknown>).nodeType === 'imageProcess') {
          bgSourceId = edge.target;
        }
      }

      const updatedNodes = storeNodes.map(n => {
        if (n.id === id) {
          return { ...n, data: { ...n.data, screenshotUrl: persistentUrl, panoramaStorageKey: storage_key, viewAngle } };
        }
        if (n.id === bgSourceId && bgSourceId !== id) {
          return { ...n, data: { ...n.data, inputImageUrl: persistentUrl, inputStorageKey: storage_key, outputImageUrl: persistentUrl, outputStorageKey: storage_key } };
        }
        if (n.id === compositeId) {
          const compData = n.data as Record<string, unknown>;
          const existing = ((compData.layers || []) as Array<Record<string, unknown>>).slice();
          const bgIdx = existing.findIndex(l => l.type === 'background');
          if (bgIdx >= 0) {
            existing[bgIdx] = { ...existing[bgIdx], imageUrl: persistentUrl, sourceNodeId: bgSourceId };
          } else {
            existing.unshift({
              id: bgSourceId, type: 'background', sourceNodeId: bgSourceId,
              imageUrl: persistentUrl,
              x: 0, y: 0, width: 1920, height: 1080,
              rotation: 0, zIndex: 0, opacity: 1, visible: true, flipX: false,
            });
          }
          return { ...n, data: { ...n.data, layers: existing, outputImageUrl: undefined } };
        }
        return n;
      });

      store.setNodes(updatedNodes);

      const compNode = updatedNodes.find(n => n.id === compositeId);
      if (compNode) {
        const compLayers = (compNode.data as Record<string, unknown>).layers as Array<Record<string, unknown>> | undefined;
        if (compLayers && compLayers.length > 0) {
          useCanvasStore.getState().persistCompositeLayers(compositeId, compLayers);
        }
      }

      fetch(`${API_BASE_URL}/api/canvas/nodes/${id}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ node_type: 'sceneBG', content: { screenshotStorageKey: storage_key } }),
      }).catch(() => {});
    } catch (e) {
      console.error('Failed to upload scene BG screenshot:', e);
    }
  }, [id]);

  // Debounced viewpoint persist to backend
  const persistTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const persistViewpoints = useCallback((vps: ViewPoint[]) => {
    const projectId = useProjectStore.getState().project?.id;
    const locationId = data.locationId;
    if (!projectId || !locationId) return;
    if (persistTimerRef.current) clearTimeout(persistTimerRef.current);
    persistTimerRef.current = setTimeout(() => {
      const payload = vps.map(vp => ({
        label: vp.label,
        yaw: vp.yaw,
        pitch: vp.pitch,
        fov: vp.fov,
        pos_x: vp.posX ?? 0,
        pos_y: vp.posY ?? 0,
        pos_z: vp.posZ ?? 0,
        correction_strength: vp.correctionStrength ?? 0.5,
        is_default: vp.isDefault ?? false,
      }));
      fetch(`${API_BASE_URL}/api/projects/${projectId}/locations/${locationId}/viewpoints`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }).catch(e => console.error('Failed to persist viewpoints:', e));
    }, 500);
  }, [data.locationId]);

  // Handle viewpoint change from PanoramaViewer
  const handleViewpointChange = useCallback((vpId: string) => {
    const store = useCanvasStore.getState();
    const nodes = store.nodes;
    const currentNode = nodes.find(n => n.id === id);
    const vps = (currentNode?.data as SceneBGNodeData)?.viewpoints ?? [];
    // Mark the selected viewpoint as default for persistence
    const updatedVps = vps.map(vp => ({ ...vp, isDefault: vp.id === vpId }));
    store.setNodes(nodes.map(n =>
      n.id === id
        ? { ...n, data: { ...n.data, activeViewpointId: vpId, viewpoints: updatedVps } }
        : n,
    ));
    persistViewpoints(updatedVps);
  }, [id, persistViewpoints]);

  // Handle viewpoints update from PanoramaViewer edit mode
  const handleViewpointsUpdate = useCallback((vps: ViewPoint[]) => {
    const store = useCanvasStore.getState();
    const nodes = store.nodes;
    store.setNodes(nodes.map(n =>
      n.id === id
        ? { ...n, data: { ...n.data, viewpoints: vps } }
        : n,
    ));
    persistViewpoints(vps);
  }, [id, persistViewpoints]);

  const handleCardClick = useCallback(() => {
    if (data.panoramaUrl) {
      setPanoramaOpen(true);
    } else {
      // Even without panorama, toggle detail view so card is always clickable
      setDetailOpen(prev => !prev);
    }
  }, [data.panoramaUrl]);

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{ width: 260, position: 'relative' }}
    >
      <Handle type="target" position={Position.Left} className="target-handle" style={{ top: '55%' }} />
      <Handle type="source" position={Position.Right} style={{ top: '55%' }} />

      <div className="flex items-center gap-1.5 mb-2 pl-1">
        <span className="text-[13px]">🌐</span>
        <span className="text-[12px] font-medium tracking-wide" style={{ color: accent }}>场景背景</span>
      </div>

      <div className="canvas-card" style={{
        borderRadius: 16, position: 'relative', overflow: 'hidden',
        border: `1px solid ${cardBorder}`,
        transition: 'border-color 0.2s',
        cursor: 'pointer',
      }} onClick={handleCardClick}>
        <div style={{
          width: '100%', aspectRatio: '16 / 9',
          backgroundColor: '#0c0e12',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          {previewUrl ? (
            <img src={previewUrl} alt="scene preview" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          ) : (
            <div style={{ textAlign: 'center', padding: '0 12px' }}>
              <span style={{ fontSize: 28, display: 'block', color: 'rgba(255,255,255,0.06)', marginBottom: 4 }}>🌐</span>
              <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.15)' }}>
                {data.panoramaUrl ? '点击截取全景' : data.locationName ? '点击查看详情' : '无场景数据'}
              </span>
            </div>
          )}
        </div>

        {/* Location name overlay at top */}
        {data.locationName && (
          <div style={{
            position: 'absolute', top: 0, left: 0, right: 0,
            background: previewUrl ? 'linear-gradient(rgba(0,0,0,0.5), transparent)' : 'none',
            padding: '8px 10px 16px',
            display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <span style={{
              fontSize: 11, fontWeight: 500, letterSpacing: '0.02em',
              color: previewUrl ? 'rgba(255,255,255,0.85)' : 'rgba(255,255,255,0.4)',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {data.locationName}
            </span>
            {data.lighting && (
              <span style={{
                fontSize: 9, padding: '1px 6px', borderRadius: 4, flexShrink: 0,
                backgroundColor: 'rgba(255,180,50,0.12)', color: 'rgba(255,180,50,0.6)',
              }}>
                {data.lighting}
              </span>
            )}
          </div>
        )}

        {/* Overlay info at bottom */}
        {(data.panoramaUrl || data.screenshotUrl) && (
          <div style={{
            position: 'absolute', bottom: 0, left: 0, right: 0,
            background: 'linear-gradient(transparent, rgba(0,0,0,0.7))',
            padding: '20px 12px 10px',
            display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap',
          }}>
            <span style={{
              fontSize: 9, padding: '2px 8px', borderRadius: 4,
              backgroundColor: 'rgba(6,182,212,0.2)', color: 'rgba(6,182,212,0.8)',
            }}>
              偏航 {displayYaw.toFixed(0)}°
            </span>
            <span style={{
              fontSize: 9, padding: '2px 8px', borderRadius: 4,
              backgroundColor: 'rgba(6,182,212,0.2)', color: 'rgba(6,182,212,0.8)',
            }}>
              俯仰 {displayPitch.toFixed(0)}°
            </span>
            <span style={{
              fontSize: 9, padding: '2px 8px', borderRadius: 4,
              backgroundColor: 'rgba(6,182,212,0.2)', color: 'rgba(6,182,212,0.8)',
            }}>
              FOV {displayFov.toFixed(0)}°
            </span>
            {activeVp && (
              <span style={{
                fontSize: 9, padding: '2px 8px', borderRadius: 4,
                backgroundColor: 'rgba(52,211,153,0.15)', color: 'rgba(52,211,153,0.7)',
              }}>
                {activeVp.label}
              </span>
            )}
            {hasPosition && (
              <span style={{
                fontSize: 9, padding: '2px 6px', borderRadius: 4,
                backgroundColor: 'rgba(168,85,247,0.15)', color: 'rgba(168,85,247,0.7)',
              }}>
                位移
              </span>
            )}
            {hasCorrection && (
              <span style={{
                fontSize: 9, padding: '2px 6px', borderRadius: 4,
                backgroundColor: 'rgba(251,191,36,0.15)', color: 'rgba(251,191,36,0.7)',
              }}>
                矫正 {((activeVp!.correctionStrength ?? 0.5) * 100).toFixed(0)}%
              </span>
            )}
            {data.screenshotUrl && (
              <span style={{
                fontSize: 9, padding: '2px 6px', borderRadius: 4,
                backgroundColor: 'rgba(52,211,153,0.15)', color: 'rgba(52,211,153,0.7)',
              }}>已截图</span>
            )}
          </div>
        )}

        {/* Mood/description overlay at bottom (when no panorama/screenshot data) */}
        {!data.panoramaUrl && !data.screenshotUrl && data.mood && (
          <div style={{
            position: 'absolute', bottom: 0, left: 0, right: 0,
            padding: '6px 10px',
            display: 'flex', alignItems: 'center', gap: 4,
          }}>
            <span style={{
              fontSize: 9, padding: '2px 6px', borderRadius: 4,
              backgroundColor: 'rgba(168,85,247,0.12)', color: 'rgba(168,85,247,0.5)',
            }}>
              {data.mood}
            </span>
          </div>
        )}

        {/* Viewpoint count badge */}
        {(data.viewpoints?.length ?? 0) > 0 && (
          <div style={{
            position: 'absolute', top: data.locationName ? 28 : 10, left: 10, zIndex: 2,
            fontSize: 9, padding: '2px 6px', borderRadius: 4,
            backgroundColor: 'rgba(6,182,212,0.2)', color: 'rgba(6,182,212,0.8)',
          }}>
            {data.viewpoints!.length} 点位
          </div>
        )}

        {/* Status dot */}
        <div style={{
          position: 'absolute', top: 10, right: 10, width: 8, height: 8,
          borderRadius: '50%', zIndex: 2,
          backgroundColor:
            data.status === 'running' ? '#60a5fa'
            : data.status === 'success' ? '#34d399'
            : data.status === 'error' ? '#f87171'
            : 'transparent',
        }} />

        {/* Progress bar */}
        {data.status === 'running' && (
          <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 3, backgroundColor: 'rgba(0,0,0,0.3)' }}>
            <div style={{ height: '100%', backgroundColor: 'rgba(6,182,212,0.6)', width: `${data.progress ?? 0}%` }} />
          </div>
        )}
      </div>

      {/* Location detail panel (shown when no panorama and user clicks) */}
      {detailOpen && !data.panoramaUrl && (data.locationDescription || data.mood || data.lighting) && (
        <div style={{
          marginTop: 8, borderRadius: 12, padding: '10px 12px',
          backgroundColor: 'rgba(15,17,22,0.95)',
          border: '1px solid rgba(255,255,255,0.06)',
        }}>
          {data.locationDescription && (
            <p style={{
              fontSize: 11, lineHeight: 1.6, margin: '0 0 6px',
              color: 'rgba(255,255,255,0.35)',
              display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden',
            }}>
              {data.locationDescription}
            </p>
          )}
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {data.mood && (
              <span style={{ fontSize: 9, padding: '2px 6px', borderRadius: 4, backgroundColor: 'rgba(168,85,247,0.12)', color: 'rgba(168,85,247,0.5)' }}>
                {data.mood}
              </span>
            )}
            {data.lighting && (
              <span style={{ fontSize: 9, padding: '2px 6px', borderRadius: 4, backgroundColor: 'rgba(255,180,50,0.12)', color: 'rgba(255,180,50,0.5)' }}>
                {data.lighting}
              </span>
            )}
            {data.colorPalette && data.colorPalette.length > 0 && (
              <div style={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                {data.colorPalette.slice(0, 5).map((c, i) => (
                  <div key={i} style={{ width: 10, height: 10, borderRadius: 2, backgroundColor: c, border: '1px solid rgba(255,255,255,0.1)' }} />
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Panorama Viewer Modal */}
      {data.panoramaUrl && (
        <PanoramaViewer
          panoramaUrl={data.panoramaUrl}
          isOpen={panoramaOpen}
          onClose={() => setPanoramaOpen(false)}
          onScreenshot={handleScreenshot}
          viewpoints={data.viewpoints}
          activeViewpointId={data.activeViewpointId}
          onViewpointChange={handleViewpointChange}
          onViewpointsUpdate={handleViewpointsUpdate}
          editMode={true}
        />
      )}
    </div>
  );
}

export const SceneBGNode = memo(SceneBGNodeComponent);
