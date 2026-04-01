'use client';

import { memo, useState, useEffect, useRef } from 'react';
import { type NodeProps, type Node } from '@xyflow/react';
import type { ShotNodeData } from '../../../types/canvas';

type ShotNode = Node<ShotNodeData, 'shot'>;

const CONNECT_MENU = [
  { icon: '✦', label: 'Prompt 组装', key: 'prompt' },
  { icon: '◧', label: '图片生成', key: 'image' },
  { icon: '▶', label: '视频生成', key: 'video' },
];

function ShotNodeComponent({ data, selected }: NodeProps<ShotNode>) {
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
    <div onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)} className="relative" style={{ width: 290, paddingRight: 50, marginRight: -50 }}>
      <div className="flex items-center gap-1.5 mb-2 pl-1">
        <span className="text-[12px] text-white/20">◎</span>
        <span className={`text-[12px] font-medium tracking-wide ${selected ? 'text-orange-400/90' : 'text-orange-400/50'}`}>Shot</span>
      </div>

      <div className={`relative overflow-hidden transition-all duration-200 ${selected ? 'shadow-[0_2px_24px_rgba(255,255,255,0.03)]' : ''}`} style={{ borderRadius: 16 }}>
        <div style={{ borderRadius: 16 }} className={`absolute inset-0 transition-colors duration-200 ${selected ? 'bg-[#1f2129]' : hovered ? 'bg-[#1a1c23]' : 'bg-[#16181e]'}`} />
        <div style={{ borderRadius: 16 }} className={`absolute inset-0 pointer-events-none transition-colors duration-200 border ${selected ? 'border-white/[0.16]' : hovered ? 'border-white/[0.12]' : 'border-white/[0.06]'}`} />
        <div className="absolute top-0 right-0 z-[1]"><svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M0 0L20 0L20 20Z" fill="white" fillOpacity="0.04" /></svg></div>

        <div className={`absolute top-3.5 right-3.5 w-2 h-2 rounded-full z-[1] ${
          data.status === 'running' ? 'bg-blue-400 animate-pulse' : data.status === 'success' ? 'bg-emerald-400' : data.status === 'error' ? 'bg-red-400' : 'bg-white/10'
        }`} />

        <div className="relative z-[1] p-5">
          <div className="flex items-center gap-2 mb-3">
            <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${selected ? 'text-orange-300/70 bg-orange-400/10' : 'text-white/25 bg-white/[0.04]'}`}>#{data.shotNumber}</span>
            <span className="text-[10px] text-white/25 bg-white/[0.04] px-2 py-0.5 rounded">{data.framing}</span>
            {data.cameraMovement && data.cameraMovement !== 'static' && (
              <span className="text-[10px] text-purple-400/35 bg-purple-400/[0.04] px-2 py-0.5 rounded">{data.cameraMovement}</span>
            )}
          </div>

          <div className={`w-full h-[72px] rounded-xl mb-3 flex items-center justify-center ${selected ? 'bg-white/[0.03]' : 'bg-white/[0.015]'}`}>
            {data.thumbnailUrl ? <img src={data.thumbnailUrl} alt="" className="w-full h-full object-cover rounded-xl" /> : <span className="text-[10px] text-white/10">待生成</span>}
          </div>

          <p className={`text-[12px] line-clamp-2 leading-[1.7] ${selected ? 'text-white/40' : 'text-white/22'}`}>{data.description || '暂无描述'}</p>
        </div>

        <div className="absolute bottom-2 right-2 z-[1]"><svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M9 1L1 9M9 4.5L4.5 9M9 8L8 9" stroke="white" strokeOpacity="0.06" strokeWidth="1" strokeLinecap="round" /></svg></div>
      </div>

      <div className={`absolute z-10 ${hovered || menuOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
        style={{ top: '50%', transform: 'translateY(-50%)', right: hovered || menuOpen ? -44 : -12, transition: 'right 0.3s ease-out, opacity 0.3s ease-out' }}>
        <button onClick={(e) => { e.stopPropagation(); setMenuOpen((v) => !v); }}
          className="w-8 h-8 rounded-full border border-white/15 bg-[#1a1c24] flex items-center justify-center text-white/35 hover:text-white/60 hover:border-white/30 hover:bg-[#22252e] transition-all duration-150 cursor-pointer">
          <span className="text-lg leading-none font-light">+</span>
        </button>
      </div>

      {menuOpen && (
        <div ref={menuRef} className="absolute z-20" style={{ top: '50%', transform: 'translateY(-50%)', left: 'calc(100% + 56px)' }}>
          <div className="w-[220px] rounded-2xl bg-[#1e2028] border border-white/[0.08] shadow-[0_8px_40px_rgba(0,0,0,0.6)] overflow-hidden">
            <div className="px-4 py-3 text-[11px] text-white/30 border-b border-white/[0.04]">引用该节点生成</div>
            {CONNECT_MENU.map((item) => (
              <button key={item.key} onClick={(e) => { e.stopPropagation(); setMenuOpen(false); }}
                className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-white/[0.04] transition-colors">
                <span className="w-8 h-8 rounded-lg bg-white/[0.04] flex items-center justify-center text-[14px] text-white/35 flex-shrink-0">{item.icon}</span>
                <span className="text-[13px] text-white/70 font-medium">{item.label}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export const ShotNode = memo(ShotNodeComponent);
