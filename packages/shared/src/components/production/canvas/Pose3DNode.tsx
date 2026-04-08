'use client';

import { memo, useState, useCallback } from 'react';
import { type NodeProps, type Node, Handle, Position } from '@xyflow/react';
import type { Pose3DNodeData } from '../../../types/canvas';
import { Pose3DEditor } from './Pose3DEditor';
import { useProjectStore } from '../../../stores/projectStore';
import { useCanvasStore } from '../../../stores/canvasStore';
import { API_BASE_URL } from '../../../lib/api';

type Pose3DNode = Node<Pose3DNodeData, 'pose3D'>;

function Pose3DNodeComponent({ id, data, selected }: NodeProps<Pose3DNode>) {
  const [hovered, setHovered] = useState(false);
  const [editorOpen, setEditorOpen] = useState(false);

  const cardBorder = selected ? 'rgba(255,255,255,0.16)' : hovered ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.06)';
  const accent = selected ? 'rgba(168,85,247,0.9)' : 'rgba(168,85,247,0.5)';

  // Handle screenshot from editor
  const handleScreenshot = useCallback(async (base64: string) => {
    const projectId = useProjectStore.getState().project?.id;
    const screenshotUrl = `data:image/jpeg;base64,${base64}`;

    // Immediately update this node's screenshotUrl
    const currentNodes = useCanvasStore.getState().nodes;
    useCanvasStore.getState().setNodes(currentNodes.map(n =>
      n.id === id
        ? { ...n, data: { ...n.data, screenshotUrl, status: 'success', progress: 100 } }
        : n,
    ));

    // Reset downstream nodes
    useCanvasStore.getState().resetDownstreamNodes(id);

    setEditorOpen(false);

    if (!projectId) return;

    try {
      const blob = await fetch(`data:image/jpeg;base64,${base64}`).then(r => r.blob());
      const formData = new FormData();
      formData.append('file', blob, 'pose3d_screenshot.jpg');

      const resp = await fetch(
        `${API_BASE_URL}/api/projects/${projectId}/asset-images/upload`,
        { method: 'POST', body: formData },
      );
      if (!resp.ok) return;
      const { storage_key } = await resp.json();
      const persistentUrl = `${API_BASE_URL}/uploads/${storage_key}`;

      // Update with persistent URL
      const store = useCanvasStore.getState();
      const storeNodes = store.nodes;
      const edges = store.edges;

      const updatedNodes = storeNodes.map(n => {
        if (n.id === id) {
          return { ...n, data: { ...n.data, screenshotUrl: persistentUrl, screenshotStorageKey: storage_key } };
        }
        // Propagate to downstream expression nodes as poseReferenceUrl
        const isDownstream = edges.some(e => e.source === id && e.target === n.id);
        if (isDownstream && (n.data as Record<string, unknown>).nodeType === 'imageProcess' &&
            (n.data as Record<string, unknown>).processType === 'expression') {
          return { ...n, data: { ...n.data, poseReferenceUrl: persistentUrl, poseReferenceStorageKey: storage_key } };
        }
        return n;
      });

      store.setNodes(updatedNodes);

      // Notify backend — persist both screenshot and joint angles
      const currentNode = store.nodes.find(n => n.id === id);
      const currentAngles = (currentNode?.data as Record<string, unknown>)?.jointAngles || {};
      fetch(`${API_BASE_URL}/api/canvas/nodes/${id}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ node_type: 'pose3D', content: {
          screenshotStorageKey: storage_key,
          jointAngles: currentAngles,
        } }),
      }).catch(() => {});
    } catch (e) {
      console.error('Failed to upload pose screenshot:', e);
    }
  }, [id]);

  // Handle pose change from editor
  const handlePoseChange = useCallback((angles: Record<string, { x: number; y: number; z: number }>) => {
    const store = useCanvasStore.getState();
    store.setNodes(store.nodes.map(n =>
      n.id === id
        ? { ...n, data: { ...n.data, jointAngles: angles } }
        : n,
    ));
  }, [id]);

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{ width: 260, position: 'relative' }}
    >
      <Handle type="target" position={Position.Left} className="target-handle" style={{ top: '55%' }} />
      <Handle type="source" position={Position.Right} style={{ top: '55%' }} />

      <div className="flex items-center gap-1.5 mb-2 pl-1">
        <span className="text-[13px]">🦴</span>
        <span className="text-[12px] font-medium tracking-wide" style={{ color: accent }}>3D摆姿</span>
      </div>

      <div className="canvas-card" style={{
        borderRadius: 16, position: 'relative', overflow: 'hidden',
        border: `1px solid ${cardBorder}`,
        transition: 'border-color 0.2s',
        cursor: 'pointer',
      }} onClick={() => setEditorOpen(true)}>
        <div style={{
          width: '100%', aspectRatio: '16 / 9',
          backgroundColor: '#0c0e12',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          {data.screenshotUrl ? (
            <img src={data.screenshotUrl} alt="pose preview" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          ) : (
            <div style={{ textAlign: 'center', padding: '0 12px' }}>
              <span style={{ fontSize: 28, display: 'block', color: 'rgba(255,255,255,0.06)', marginBottom: 4 }}>🦴</span>
              <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.15)' }}>
                点击摆姿
              </span>
            </div>
          )}
        </div>

        {/* Preset name badge */}
        {data.presetName && (
          <div style={{
            position: 'absolute', bottom: 8, left: 8,
            fontSize: 9, padding: '2px 8px', borderRadius: 4,
            backgroundColor: 'rgba(168,85,247,0.2)', color: 'rgba(168,85,247,0.8)',
          }}>
            {data.presetName}
          </div>
        )}

        {/* Screenshot indicator */}
        {data.screenshotUrl && (
          <div style={{
            position: 'absolute', bottom: 8, right: 8,
            fontSize: 9, padding: '2px 6px', borderRadius: 4,
            backgroundColor: 'rgba(52,211,153,0.15)', color: 'rgba(52,211,153,0.7)',
          }}>
            已截图
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
            <div style={{ height: '100%', backgroundColor: 'rgba(168,85,247,0.6)', width: `${data.progress ?? 0}%` }} />
          </div>
        )}
      </div>

      {/* Pose3D Editor Modal */}
      <Pose3DEditor
        isOpen={editorOpen}
        onClose={() => setEditorOpen(false)}
        onScreenshot={handleScreenshot}
        initialJointAngles={data.jointAngles}
        onPoseChange={handlePoseChange}
      />
    </div>
  );
}

export const Pose3DNode = memo(Pose3DNodeComponent);
