'use client';

import { memo, useEffect, useRef } from 'react';
import { type NodeProps, type Node, Handle, Position } from '@xyflow/react';
import type { PromptAssemblyNodeData } from '../../../types/canvas';
import { useMagneticButton } from '../../../hooks/useMagneticButton';

type PromptAssemblyNode = Node<PromptAssemblyNodeData, 'promptAssembly'>;

const CARD_W = 260;

function PromptAssemblyNodeComponent({ data, selected }: NodeProps<PromptAssemblyNode>) {
  const cardRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const { showBtn, btnPos, isSnapped, menuOpen, setMenuOpen, BTN_SIZE } = useMagneticButton(cardRef, CARD_W);

  const hovered = showBtn;

  useEffect(() => {
    if (!menuOpen) return;
    const h = (e: MouseEvent) => { if (menuRef.current && !menuRef.current.contains(e.target as HTMLElement)) setMenuOpen(false); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, [menuOpen, setMenuOpen]);

  const cardBg = selected ? '#1f2129' : hovered ? '#1a1c23' : '#16181e';
  const cardBorder = selected ? 'rgba(255,255,255,0.16)' : hovered ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.06)';

  return (
    <div ref={cardRef} style={{ width: CARD_W, position: 'relative' }}>
      <Handle type="target" position={Position.Left} className="target-handle" style={{ top: '55%' }} />
      <div className="flex items-center gap-1.5 mb-2 pl-1">
        <span className="text-[12px] text-white/20">✦</span>
        <span style={{ fontSize: 12, fontWeight: 500, letterSpacing: '0.03em', color: selected ? 'rgba(74,222,128,0.9)' : 'rgba(74,222,128,0.5)' }}>Prompt</span>
      </div>

      <div className="canvas-card" style={{
        borderRadius: 16, position: 'relative', overflow: 'hidden',
        backgroundColor: cardBg, border: `1px solid ${cardBorder}`,
        transition: 'background-color 0.2s, border-color 0.2s',
      }}>
        <div style={{ position: 'relative', zIndex: 1, padding: 20 }}>
          <div className="nodrag nowheel" style={{
            width: '100%', minHeight: 70, maxHeight: 120, borderRadius: 12, padding: 14, marginBottom: 12,
            backgroundColor: selected ? 'rgba(255,255,255,0.03)' : 'rgba(255,255,255,0.015)',
            overflowY: 'auto',
          }}>
            <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.25)', lineHeight: 1.7, fontFamily: 'monospace' }}>
              {data.assembledPrompt || '等待组装...'}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {data.characterRefs.map((c) => (
              <span key={c.name} style={{ fontSize: 9, color: 'rgba(167,139,250,0.35)', backgroundColor: 'rgba(139,92,246,0.05)', padding: '2px 8px', borderRadius: 99, display: 'flex', alignItems: 'center', gap: 3 }}>
                {c.visualRefUrl && <img src={c.visualRefUrl} alt="" style={{ width: 12, height: 12, borderRadius: '50%', objectFit: 'cover' }} />}
                {c.name}
              </span>
            ))}
            {data.locationRef && (
              <span style={{ fontSize: 9, color: 'rgba(252,211,77,0.35)', backgroundColor: 'rgba(245,158,11,0.05)', padding: '2px 8px', borderRadius: 99 }}>{data.locationRef.name}</span>
            )}
            {data.negativePrompt && (
              <span style={{ fontSize: 9, color: 'rgba(248,113,113,0.35)', backgroundColor: 'rgba(239,68,68,0.05)', padding: '2px 8px', borderRadius: 99 }}>neg</span>
            )}
          </div>
        </div>
      </div>

      {/* + button — magnetic snap + connection drag source */}
      <div
        className="nodrag nopan"
        style={{
          position: 'absolute',
          left: isSnapped ? btnPos.x - BTN_SIZE / 2 : undefined,
          top: isSnapped ? btnPos.y - BTN_SIZE / 2 : '50%',
          right: isSnapped ? undefined : (showBtn ? -44 : -12),
          transform: isSnapped ? undefined : 'translateY(-50%)',
          opacity: showBtn ? 1 : 0,
          pointerEvents: showBtn ? 'auto' as const : 'none' as const,
          transition: isSnapped ? 'none' : 'right 0.3s ease-out, opacity 0.3s ease-out',
          zIndex: 10,
          width: BTN_SIZE,
          height: BTN_SIZE,
        }}
      >
        <Handle type="source" position={Position.Right} className="plus-source" />
        <div
          onClick={(e) => { e.stopPropagation(); setMenuOpen((v) => !v); }}
          style={{
            position: 'absolute', top: 0, left: 0,
            width: 32, height: 32, borderRadius: '50%', border: '1px solid rgba(255,255,255,0.15)',
            backgroundColor: '#1a1c24', display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'rgba(255,255,255,0.35)', fontSize: 18, cursor: 'crosshair',
          }}>
          +
        </div>
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
