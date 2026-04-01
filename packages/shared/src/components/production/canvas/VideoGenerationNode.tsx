'use client';

import { memo, useState } from 'react';
import { type NodeProps, type Node } from '@xyflow/react';
import type { VideoGenerationNodeData } from '../../../types/canvas';

type VideoGenerationNode = Node<VideoGenerationNodeData, 'videoGeneration'>;

const MODE_LABEL: Record<string, string> = { text_to_video: 'T2V', image_to_video: 'I2V', scene_character_to_video: 'SC2V' };

function VideoGenerationNodeComponent({ data, selected }: NodeProps<VideoGenerationNode>) {
  const [hovered, setHovered] = useState(false);

  return (
    <div onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)} className="relative" style={{ width: 290 }}>
      <div className="flex items-center gap-1.5 mb-2 pl-1">
        <span className="text-[12px] text-white/20">▶</span>
        <span className={`text-[12px] font-medium tracking-wide ${selected ? 'text-fuchsia-400/90' : 'text-fuchsia-400/50'}`}>Video</span>
      </div>

      <div className={`relative overflow-hidden transition-all duration-200 ${selected ? 'shadow-[0_2px_24px_rgba(255,255,255,0.03)]' : ''}`} style={{ borderRadius: 16 }}>
        <div style={{ borderRadius: 16 }} className={`absolute inset-0 transition-colors duration-200 ${selected ? 'bg-[#1f2129]' : hovered ? 'bg-[#1a1c23]' : 'bg-[#16181e]'}`} />
        <div style={{ borderRadius: 16 }} className={`absolute inset-0 pointer-events-none transition-colors duration-200 border ${selected ? 'border-white/[0.16]' : hovered ? 'border-white/[0.12]' : 'border-white/[0.06]'}`} />
        <div className="absolute top-0 right-0 z-[1]"><svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M0 0L20 0L20 20Z" fill="white" fillOpacity="0.04" /></svg></div>

        <div className="relative z-[1] p-5">
          <div className="flex items-center gap-2 mb-3">
            <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${selected ? 'text-fuchsia-300/70 bg-fuchsia-400/10' : 'text-white/25 bg-white/[0.04]'}`}>{MODE_LABEL[data.mode] || 'Video'}</span>
            {data.durationMs > 0 && <span className="text-[10px] text-white/22">{(data.durationMs / 1000).toFixed(1)}s</span>}
          </div>

          <div className={`w-full h-[100px] rounded-xl mb-3 flex items-center justify-center overflow-hidden ${selected ? 'bg-white/[0.03]' : 'bg-white/[0.015]'}`}>
            {data.videoUrl ? (
              <video src={data.videoUrl} className="w-full h-full object-cover" muted loop playsInline
                onMouseEnter={(e) => (e.target as HTMLVideoElement).play()}
                onMouseLeave={(e) => { const v = e.target as HTMLVideoElement; v.pause(); v.currentTime = 0; }} />
            ) : (
              <div className="flex flex-col items-center gap-1">
                <span className="text-lg text-white/5">▶</span>
                <span className="text-[10px] text-white/10">{data.status === 'running' ? '生成中...' : '待生成'}</span>
              </div>
            )}
          </div>

          {data.status === 'running' && (
            <div className="flex items-center gap-2">
              <div className="h-1 flex-1 rounded-full bg-white/[0.03] overflow-hidden"><div className="h-full bg-fuchsia-400/50 rounded-full" style={{ width: `${data.progress}%` }} /></div>
              <span className="text-[10px] text-white/22">{data.progress}%</span>
            </div>
          )}
          {data.status === 'success' && data.videoUrl && <div className="text-[10px] text-emerald-400/35">生成完成</div>}
          {data.status === 'error' && data.errorMessage && <div className="text-[10px] text-red-400/45 truncate">{data.errorMessage}</div>}
        </div>

        <div className="absolute bottom-2 right-2 z-[1]"><svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M9 1L1 9M9 4.5L4.5 9M9 8L8 9" stroke="white" strokeOpacity="0.06" strokeWidth="1" strokeLinecap="round" /></svg></div>
      </div>
    </div>
  );
}

export const VideoGenerationNode = memo(VideoGenerationNodeComponent);
