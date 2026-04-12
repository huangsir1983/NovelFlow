'use client';

import { memo, useState } from 'react';
import { type NodeProps, type Node, Handle, Position } from '@xyflow/react';
import type { VideoGenerationNodeData } from '../../../types/canvas';

type VideoGenerationNode = Node<VideoGenerationNodeData, 'videoGeneration'>;

const MODE_LABEL: Record<string, string> = { text_to_video: 'T2V', image_to_video: 'I2V', scene_character_to_video: 'SC2V' };

function VideoGenerationNodeComponent({ data, selected }: NodeProps<VideoGenerationNode>) {
  const [hovered, setHovered] = useState(false);
  const inputImageUrl = (data as unknown as Record<string, unknown>).inputImageUrl as string | undefined;

  const cardBg = selected ? '#1f2129' : hovered ? '#1a1c23' : '#16181e';
  const cardBorder = selected ? 'rgba(255,255,255,0.16)' : hovered ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.06)';

  return (
    <div onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)} className="relative" style={{ width: 290 }}>
      <Handle type="target" position={Position.Left} className="target-handle" style={{ top: '55%' }} />
      <Handle type="source" position={Position.Right} style={{ top: '55%' }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8, paddingLeft: 4 }}>
        <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.2)' }}>▶</span>
        <span style={{ fontSize: 12, fontWeight: 500, letterSpacing: '0.03em', color: selected ? 'rgba(232,121,249,0.9)' : 'rgba(232,121,249,0.5)' }}>Video</span>
      </div>

      <div className="canvas-card" style={{
        borderRadius: 16, position: 'relative', overflow: 'hidden',
        backgroundColor: cardBg, border: `1px solid ${cardBorder}`,
        transition: 'background-color 0.2s, border-color 0.2s',
      }}>
        <div style={{ position: 'relative', zIndex: 1, padding: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <span style={{
              fontSize: 10, fontFamily: 'monospace', padding: '2px 6px', borderRadius: 4,
              color: selected ? 'rgba(232,121,249,0.7)' : 'rgba(255,255,255,0.25)',
              backgroundColor: selected ? 'rgba(232,121,249,0.1)' : 'rgba(255,255,255,0.04)',
            }}>{MODE_LABEL[data.mode] || 'Video'}</span>
            {data.durationMs > 0 && <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.22)' }}>{(data.durationMs / 1000).toFixed(1)}s</span>}
          </div>

          <div style={{
            width: '100%', height: 100, borderRadius: 12, marginBottom: 12, overflow: 'hidden',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            backgroundColor: selected ? 'rgba(255,255,255,0.03)' : 'rgba(255,255,255,0.015)',
          }}>
            {data.videoUrl ? (
              <video src={data.videoUrl} style={{ width: '100%', height: '100%', objectFit: 'cover' }} muted loop playsInline
                onMouseEnter={(e) => (e.target as HTMLVideoElement).play()}
                onMouseLeave={(e) => { const v = e.target as HTMLVideoElement; v.pause(); v.currentTime = 0; }} />
            ) : inputImageUrl ? (
              <img src={inputImageUrl} alt="源图" style={{ width: '100%', height: '100%', objectFit: 'cover', opacity: 0.7 }} />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                <span style={{ fontSize: 18, color: 'rgba(255,255,255,0.05)' }}>▶</span>
                <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.1)' }}>{data.status === 'running' ? '生成中...' : '待生成'}</span>
              </div>
            )}
          </div>

          {data.status === 'running' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ height: 4, flex: 1, borderRadius: 99, backgroundColor: 'rgba(255,255,255,0.03)', overflow: 'hidden' }}>
                <div style={{ height: '100%', backgroundColor: 'rgba(232,121,249,0.5)', borderRadius: 99, width: `${data.progress}%` }} />
              </div>
              <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.22)' }}>{data.progress}%</span>
            </div>
          )}
          {data.status === 'success' && data.videoUrl && <div style={{ fontSize: 10, color: 'rgba(52,211,153,0.35)' }}>生成完成</div>}
          {data.status === 'error' && data.errorMessage && <div style={{ fontSize: 10, color: 'rgba(248,113,113,0.45)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{data.errorMessage}</div>}
        </div>
      </div>
    </div>
  );
}

export const VideoGenerationNode = memo(VideoGenerationNodeComponent);
