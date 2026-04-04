'use client';

import { memo, useState, useCallback } from 'react';
import { type NodeProps, type Node, Handle, Position, useReactFlow } from '@xyflow/react';
import type { SceneBGNodeData } from '../../../types/canvas';
import { PanoramaViewer } from '../../panorama/PanoramaViewer';
import { useProjectStore } from '../../../stores/projectStore';
import { API_BASE_URL } from '../../../lib/api';

type SceneBGNode = Node<SceneBGNodeData, 'sceneBG'>;

function SceneBGNodeComponent({ id, data, selected }: NodeProps<SceneBGNode>) {
  const [hovered, setHovered] = useState(false);
  const [panoramaOpen, setPanoramaOpen] = useState(false);
  const reactFlow = useReactFlow();

  const cardBorder = selected ? 'rgba(255,255,255,0.16)' : hovered ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.06)';
  const accent = selected ? 'rgba(6,182,212,0.9)' : 'rgba(6,182,212,0.5)';

  const previewUrl = data.screenshotUrl || data.panoramaUrl;

  // Handle panorama screenshot: upload + update this node's data
  const handleScreenshot = useCallback(async (base64: string) => {
    const projectId = useProjectStore.getState().project?.id;
    const screenshotUrl = `data:image/jpeg;base64,${base64}`;

    // Immediately update this node's screenshotUrl
    const allNodes = reactFlow.getNodes();
    reactFlow.setNodes(allNodes.map((n) =>
      n.id === id
        ? { ...n, data: { ...n.data, screenshotUrl } }
        : n,
    ));

    setPanoramaOpen(false);

    if (!projectId) return;

    try {
      // Upload screenshot to backend
      const blob = await fetch(`data:image/jpeg;base64,${base64}`).then((r) => r.blob());
      const formData = new FormData();
      formData.append('file', blob, 'scene_bg_screenshot.jpg');

      const resp = await fetch(
        `${API_BASE_URL}/api/projects/${projectId}/asset-images/upload`,
        { method: 'POST', body: formData },
      );
      if (!resp.ok) return;
      const { storage_key } = await resp.json();

      // Update node with storage key
      const currentNodes = reactFlow.getNodes();
      reactFlow.setNodes(currentNodes.map((n) =>
        n.id === id
          ? { ...n, data: { ...n.data, screenshotUrl, panoramaStorageKey: storage_key } }
          : n,
      ));
    } catch (e) {
      console.error('Failed to upload scene BG screenshot:', e);
    }
  }, [id, reactFlow]);

  const handleCardClick = useCallback(() => {
    if (data.panoramaUrl) {
      setPanoramaOpen(true);
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

      {/* Tapnow style: image fills the card edge-to-edge */}
      <div className="canvas-card" style={{
        borderRadius: 16, position: 'relative', overflow: 'hidden',
        border: `1px solid ${cardBorder}`,
        transition: 'border-color 0.2s',
        cursor: data.panoramaUrl ? 'pointer' : 'default',
      }} onClick={handleCardClick}>
        {/* Image area — fills entire card */}
        <div style={{
          width: '100%', height: 150,
          backgroundColor: '#0c0e12',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          {previewUrl ? (
            <img src={previewUrl} alt="scene preview" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          ) : (
            <div style={{ textAlign: 'center' }}>
              <span style={{ fontSize: 28, display: 'block', color: 'rgba(255,255,255,0.06)', marginBottom: 4 }}>🌐</span>
              <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.15)' }}>
                {data.panoramaUrl ? '点击截取全景' : '无全景数据'}
              </span>
            </div>
          )}
        </div>

        {/* Overlay info at bottom */}
        <div style={{
          position: 'absolute', bottom: 0, left: 0, right: 0,
          background: 'linear-gradient(transparent, rgba(0,0,0,0.7))',
          padding: '20px 12px 10px',
          display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <span style={{
            fontSize: 9, padding: '2px 8px', borderRadius: 4,
            backgroundColor: 'rgba(6,182,212,0.2)', color: 'rgba(6,182,212,0.8)',
          }}>
            偏航 {data.viewAngle?.yaw ?? 0}°
          </span>
          <span style={{
            fontSize: 9, padding: '2px 8px', borderRadius: 4,
            backgroundColor: 'rgba(6,182,212,0.2)', color: 'rgba(6,182,212,0.8)',
          }}>
            俯仰 {data.viewAngle?.pitch ?? 0}°
          </span>
          {data.screenshotUrl && (
            <span style={{
              fontSize: 9, padding: '2px 6px', borderRadius: 4,
              backgroundColor: 'rgba(52,211,153,0.15)', color: 'rgba(52,211,153,0.7)',
            }}>已截图</span>
          )}
        </div>

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

      {/* Panorama Viewer Modal */}
      {data.panoramaUrl && (
        <PanoramaViewer
          panoramaUrl={data.panoramaUrl}
          isOpen={panoramaOpen}
          onClose={() => setPanoramaOpen(false)}
          onScreenshot={handleScreenshot}
        />
      )}
    </div>
  );
}

export const SceneBGNode = memo(SceneBGNodeComponent);
