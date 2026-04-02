'use client';

import { memo, useState, useEffect, useRef } from 'react';
import { type NodeProps, type Node, Handle, Position } from '@xyflow/react';
import type { ImageGenerationNodeData } from '../../../types/canvas';

type ImageGenerationNode = Node<ImageGenerationNodeData, 'imageGeneration'>;

function ImageGenerationNodeComponent({ data, selected }: NodeProps<ImageGenerationNode>) {
  const [hovered, setHovered] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const h = (e: MouseEvent) => { if (menuRef.current && !menuRef.current.contains(e.target as HTMLElement)) setMenuOpen(false); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, [menuOpen]);

  return (
    <div onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)} style={{ width: 260, position: 'relative' }}>
      <Handle type="target" position={Position.Left} className="target-handle" />
      <div className="flex items-center gap-1.5 mb-2 pl-1">
        <span className="text-[12px] text-white/20">◧</span>
        <span className={`text-[12px] font-medium tracking-wide ${selected ? 'text-yellow-400/90' : 'text-yellow-400/50'}`}>Image</span>
      </div>

      <div style={{
        borderRadius: 16, position: 'relative', overflow: 'hidden',
        backgroundColor: selected ? '#1f2129' : hovered ? '#1a1c23' : '#16181e',
        border: `1px solid ${selected ? 'rgba(255,255,255,0.16)' : hovered ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.06)'}`,
        boxShadow: selected ? '0 2px 24px rgba(255,255,255,0.03)' : 'none',
        transition: 'background-color 0.2s, border-color 0.2s',
      }}>
        <div className="relative z-[1] p-5">
          <div className="flex items-center gap-2 mb-3">
            <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${selected ? 'text-yellow-300/70 bg-yellow-400/10' : 'text-white/25 bg-white/[0.04]'}`}>T2I</span>
            {data.candidates.length > 0 && <span className="text-[10px] text-white/22">{data.candidates.length} 候选</span>}
          </div>

          <div className="grid grid-cols-2 gap-2 mb-3">
            {data.candidates.length > 0 ? data.candidates.slice(0, 4).map((c) => (
              <div key={c.id} className={`relative w-full aspect-square rounded-xl overflow-hidden ${selected ? 'bg-white/[0.03]' : 'bg-white/[0.015]'} ${c.id === data.selectedCandidateId ? 'ring-1.5 ring-emerald-400/50' : ''}`}>
                {c.url ? <img src={c.url} alt="" className="w-full h-full object-cover" /> : <div className="w-full h-full flex items-center justify-center"><span className="text-[9px] text-white/8">...</span></div>}
              </div>
            )) : (
              <div className={`col-span-2 h-[80px] rounded-xl flex items-center justify-center ${selected ? 'bg-white/[0.03]' : 'bg-white/[0.015]'}`}>
                <span className="text-[10px] text-white/10">{data.status === 'running' ? '生成中...' : '待生成'}</span>
              </div>
            )}
          </div>

          {data.status === 'running' && (
            <div className="flex items-center gap-2">
              <div className="h-1 flex-1 rounded-full bg-white/[0.03] overflow-hidden"><div className="h-full bg-yellow-400/50 rounded-full" style={{ width: `${data.progress}%` }} /></div>
              <span className="text-[10px] text-white/22">{data.progress}%</span>
            </div>
          )}
        </div>

        <div className="absolute bottom-2 right-2 z-[1]"><svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M9 1L1 9M9 4.5L4.5 9M9 8L8 9" stroke="white" strokeOpacity="0.06" strokeWidth="1" strokeLinecap="round" /></svg></div>
      </div>

      <div className="nodrag nopan" style={{
        position: 'absolute', zIndex: 10, top: '50%', transform: 'translateY(-50%)',
        right: hovered || menuOpen ? -44 : -12,
        opacity: hovered || menuOpen ? 1 : 0,
        pointerEvents: hovered || menuOpen ? 'auto' as const : 'none' as const,
        transition: 'right 0.3s ease-out, opacity 0.3s ease-out',
        width: 32, height: 32,
      }}>
        <Handle type="source" position={Position.Right} className="plus-source" />
        <div onClick={(e) => { e.stopPropagation(); setMenuOpen((v) => !v); }}
          className="w-8 h-8 rounded-full border border-white/15 bg-[#1a1c24] flex items-center justify-center text-white/35 hover:text-white/60 hover:border-white/30 hover:bg-[#22252e] transition-all duration-150 cursor-crosshair"
          style={{ position: 'absolute', top: 0, left: 0 }}>
          <span className="text-lg leading-none font-light">+</span>
        </div>
      </div>

      {menuOpen && (
        <div ref={menuRef} className="absolute z-20" style={{ top: '50%', transform: 'translateY(-50%)', left: 'calc(100% + 56px)' }}>
          <div className="w-[220px] rounded-2xl bg-[#1e2028] border border-white/[0.08] shadow-[0_8px_40px_rgba(0,0,0,0.6)] overflow-hidden">
            <div className="px-4 py-3 text-[11px] text-white/30 border-b border-white/[0.04]">引用该节点生成</div>
            <button onClick={(e) => { e.stopPropagation(); setMenuOpen(false); }} className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-white/[0.04] transition-colors">
              <span className="w-8 h-8 rounded-lg bg-white/[0.04] flex items-center justify-center text-[14px] text-white/35 flex-shrink-0">▶</span>
              <span className="text-[13px] text-white/70 font-medium">视频生成</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export const ImageGenerationNode = memo(ImageGenerationNodeComponent);
