'use client';

import { memo, useState, useEffect, useRef } from 'react';
import { type NodeProps, type Node, Handle, Position } from '@xyflow/react';
import type { ShotNodeData, CanvasModuleType } from '../../../types/canvas';

type ShotNode = Node<ShotNodeData, 'shot'>;

const CONNECT_MENU = [
  { icon: '✦', label: 'Prompt 组装', key: 'prompt' },
  { icon: '◧', label: '图片生成', key: 'image' },
  { icon: '▶', label: '视频生成', key: 'video' },
];

const MODULE_COLORS: Record<CanvasModuleType, { color: string; label: string }> = {
  dialogue:  { color: '#378ADD', label: '对话' },
  action:    { color: '#D85A30', label: '动作' },
  suspense:  { color: '#534AB7', label: '悬疑' },
  landscape: { color: '#1D9E75', label: '转场' },
  emotion:   { color: '#D4537E', label: '情感' },
};

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
    <div onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)} style={{ width: 260, position: 'relative' }}>
      <Handle type="target" position={Position.Left} />
      <Handle type="source" position={Position.Right} />
      <div className="flex items-center gap-1.5 mb-2 pl-1">
        <span className="text-[12px] text-white/20">◎</span>
        <span className={`text-[12px] font-medium tracking-wide ${selected ? 'text-orange-400/90' : 'text-orange-400/50'}`}>Shot</span>
      </div>

      <div style={{
        borderRadius: 16, position: 'relative', overflow: 'hidden',
        backgroundColor: selected ? '#1f2129' : hovered ? '#1a1c23' : '#16181e',
        border: `1px solid ${selected ? 'rgba(255,255,255,0.16)' : hovered ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.06)'}`,
        boxShadow: selected ? '0 2px 24px rgba(255,255,255,0.03)' : 'none',
        transition: 'background-color 0.2s, border-color 0.2s',
      }}>

        <div style={{ position: 'absolute', top: 14, right: 14, width: 8, height: 8, borderRadius: '50%', zIndex: 1,
          backgroundColor: data.status === 'running' ? '#60a5fa' : data.status === 'success' ? '#34d399' : data.status === 'error' ? '#f87171' : 'rgba(255,255,255,0.1)' }} />

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

          {/* 模块类型 + 提示词状态 */}
          <div className="flex items-center gap-1.5 mt-3 flex-wrap">
            {data.moduleType && MODULE_COLORS[data.moduleType] && (
              <span className="text-[9px] px-1.5 py-0.5 rounded-md font-medium"
                style={{
                  backgroundColor: MODULE_COLORS[data.moduleType].color + '18',
                  color: MODULE_COLORS[data.moduleType].color,
                }}>
                {data.agentAssigned ? '🤖 ' : ''}{MODULE_COLORS[data.moduleType].label}
              </span>
            )}
            {data.imagePrompt && (
              <span className="text-[9px] px-1.5 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400/70">图✓</span>
            )}
            {data.videoPrompt && (
              <span className="text-[9px] px-1.5 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400/70">视✓</span>
            )}
          </div>
        </div>

        <div className="absolute bottom-2 right-2 z-[1]"><svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M9 1L1 9M9 4.5L4.5 9M9 8L8 9" stroke="white" strokeOpacity="0.06" strokeWidth="1" strokeLinecap="round" /></svg></div>
      </div>

      <div style={{
        position: 'absolute', zIndex: 10, top: '50%', transform: 'translateY(-50%)',
        right: hovered || menuOpen ? -44 : -12,
        opacity: hovered || menuOpen ? 1 : 0,
        pointerEvents: hovered || menuOpen ? 'auto' as const : 'none' as const,
        transition: 'right 0.3s ease-out, opacity 0.3s ease-out',
      }}>
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
