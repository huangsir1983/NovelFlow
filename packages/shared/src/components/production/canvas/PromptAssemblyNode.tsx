'use client';

import { memo, useState, useEffect, useRef } from 'react';
import { type NodeProps, type Node, Handle, Position } from '@xyflow/react';
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

  const cardBg = selected ? '#1f2129' : hovered ? '#1a1c23' : '#16181e';
  const cardBorder = selected ? 'rgba(255,255,255,0.16)' : hovered ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.06)';

  return (
    <div onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)} style={{ width: 260, position: 'relative' }}>
      <Handle type="target" position={Position.Left} />
      <Handle type="source" position={Position.Right} />
      <div className="flex items-center gap-1.5 mb-2 pl-1">
        <span className="text-[12px] text-white/20">✦</span>
        <span style={{ fontSize: 12, fontWeight: 500, letterSpacing: '0.03em', color: selected ? 'rgba(74,222,128,0.9)' : 'rgba(74,222,128,0.5)' }}>Prompt</span>
      </div>

      <div style={{
        borderRadius: 16, position: 'relative', overflow: 'hidden',
        backgroundColor: cardBg, border: `1px solid ${cardBorder}`,
        boxShadow: selected ? '0 2px 24px rgba(255,255,255,0.03)' : 'none',
        transition: 'background-color 0.2s, border-color 0.2s',
      }}>
        <div style={{ position: 'relative', zIndex: 1, padding: 20 }}>
          <div style={{
            width: '100%', minHeight: 70, borderRadius: 12, padding: 14, marginBottom: 12,
            backgroundColor: selected ? 'rgba(255,255,255,0.03)' : 'rgba(255,255,255,0.015)',
          }}>
            <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.25)', display: '-webkit-box', WebkitLineClamp: 4, WebkitBoxOrient: 'vertical', overflow: 'hidden', lineHeight: 1.7, fontFamily: 'monospace' }}>
              {data.assembledPrompt || '等待组装...'}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {data.characterRefs.map((n) => (
              <span key={n} style={{ fontSize: 9, color: 'rgba(167,139,250,0.35)', backgroundColor: 'rgba(139,92,246,0.05)', padding: '2px 8px', borderRadius: 99 }}>{n}</span>
            ))}
            {data.locationRef && (
              <span style={{ fontSize: 9, color: 'rgba(252,211,77,0.35)', backgroundColor: 'rgba(245,158,11,0.05)', padding: '2px 8px', borderRadius: 99 }}>{data.locationRef}</span>
            )}
          </div>
        </div>
      </div>

      {/* + button */}
      <div style={{
        position: 'absolute', top: '50%', transform: 'translateY(-50%)',
        right: hovered || menuOpen ? -44 : -12,
        opacity: hovered || menuOpen ? 1 : 0,
        pointerEvents: hovered || menuOpen ? 'auto' : 'none',
        transition: 'right 0.3s ease-out, opacity 0.3s ease-out', zIndex: 10,
      }}>
        <button onClick={(e) => { e.stopPropagation(); setMenuOpen((v) => !v); }}
          style={{
            width: 32, height: 32, borderRadius: '50%', border: '1px solid rgba(255,255,255,0.15)',
            backgroundColor: '#1a1c24', display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'rgba(255,255,255,0.35)', fontSize: 18, cursor: 'pointer',
          }}>
          +
        </button>
      </div>

      {/* Menu */}
      {menuOpen && (
        <div ref={menuRef} style={{ position: 'absolute', top: '50%', transform: 'translateY(-50%)', left: 'calc(100% + 56px)', zIndex: 20 }}>
          <div style={{ width: 220, borderRadius: 16, backgroundColor: '#1e2028', border: '1px solid rgba(255,255,255,0.08)', boxShadow: '0 8px 40px rgba(0,0,0,0.6)', overflow: 'hidden' }}>
            <div style={{ padding: '12px 16px', fontSize: 11, color: 'rgba(255,255,255,0.3)', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>引用该节点生成</div>
            {[{ icon: '◧', label: '图片生成', key: 'image' }, { icon: '▶', label: '视频生成', key: 'video' }].map((item) => (
              <button key={item.key} onClick={(e) => { e.stopPropagation(); setMenuOpen(false); }}
                style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', textAlign: 'left', border: 'none', backgroundColor: 'transparent', cursor: 'pointer', color: 'inherit' }}>
                <span style={{ width: 32, height: 32, borderRadius: 8, backgroundColor: 'rgba(255,255,255,0.04)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, color: 'rgba(255,255,255,0.35)', flexShrink: 0 }}>{item.icon}</span>
                <span style={{ fontSize: 13, color: 'rgba(255,255,255,0.7)', fontWeight: 500 }}>{item.label}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export const PromptAssemblyNode = memo(PromptAssemblyNodeComponent);
