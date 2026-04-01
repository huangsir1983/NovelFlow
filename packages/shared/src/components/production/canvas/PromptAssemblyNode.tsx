'use client';

import { memo, useState, useEffect, useRef } from 'react';
import { type NodeProps, type Node } from '@xyflow/react';
import type { PromptAssemblyNodeData } from '../../../types/canvas';

type PromptAssemblyNode = Node<PromptAssemblyNodeData, 'promptAssembly'>;

function PromptAssemblyNodeComponent({ data, selected }: NodeProps<PromptAssemblyNode>) {
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
        <span className="text-[12px] text-white/20">✦</span>
        <span className={`text-[12px] font-medium tracking-wide ${selected ? 'text-green-400/90' : 'text-green-400/50'}`}>Prompt</span>
      </div>

      <div className={`relative overflow-hidden transition-all duration-200 ${selected ? 'shadow-[0_2px_24px_rgba(255,255,255,0.03)]' : ''}`} style={{ borderRadius: 16 }}>
        <div style={{ borderRadius: 16 }} className={`absolute inset-0 transition-colors duration-200 ${selected ? 'bg-[#1f2129]' : hovered ? 'bg-[#1a1c23]' : 'bg-[#16181e]'}`} />
        <div style={{ borderRadius: 16 }} className={`absolute inset-0 pointer-events-none transition-colors duration-200 border ${selected ? 'border-white/[0.16]' : hovered ? 'border-white/[0.12]' : 'border-white/[0.06]'}`} />
        <div className="absolute top-0 right-0 z-[1]"><svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M0 0L20 0L20 20Z" fill="white" fillOpacity="0.04" /></svg></div>

        <div className="relative z-[1] p-5">
          <div className={`w-full min-h-[70px] rounded-xl p-3.5 mb-3 ${selected ? 'bg-white/[0.03]' : 'bg-white/[0.015]'}`}>
            <p className="text-[11px] text-white/25 line-clamp-4 leading-[1.7] font-mono">{data.assembledPrompt || '等待组装...'}</p>
          </div>
          <div className="flex gap-1.5 flex-wrap">
            {data.characterRefs.map((n) => <span key={n} className="text-[9px] text-violet-300/35 bg-violet-500/[0.05] px-2 py-0.5 rounded-full">{n}</span>)}
            {data.locationRef && <span className="text-[9px] text-amber-300/35 bg-amber-500/[0.05] px-2 py-0.5 rounded-full">{data.locationRef}</span>}
          </div>
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
            {[{ icon: '◧', label: '图片生成', key: 'image' }, { icon: '▶', label: '视频生成', key: 'video' }].map((item) => (
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

export const PromptAssemblyNode = memo(PromptAssemblyNodeComponent);
