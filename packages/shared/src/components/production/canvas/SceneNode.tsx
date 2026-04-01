'use client';

import { memo, useState, useEffect, useRef, useCallback } from 'react';
import { type NodeProps, type Node, Handle, Position } from '@xyflow/react';
import type { SceneNodeData } from '../../../types/canvas';
import type { CanvasModuleType } from '../../../types/canvas';

type SceneNode = Node<SceneNodeData, 'scene'>;

const MODULE_BADGE: Record<CanvasModuleType, { color: string; label: string; icon: string }> = {
  dialogue:  { color: '#378ADD', label: '对话', icon: '💬' },
  action:    { color: '#D85A30', label: '动作', icon: '⚔️' },
  suspense:  { color: '#534AB7', label: '悬疑', icon: '🔍' },
  landscape: { color: '#1D9E75', label: '转场', icon: '🏔' },
  emotion:   { color: '#D4537E', label: '情感', icon: '💭' },
};

const CONNECT_MENU = [
  { icon: '≡', label: '文本生成', desc: '脚本、广告词、品牌文案', key: 'text' },
  { icon: '◧', label: '图片生成', desc: '', key: 'image' },
  { icon: '▶', label: '视频生成', desc: '', key: 'video' },
  { icon: '♫', label: '音频', desc: '', key: 'audio' },
];

const CARD_W = 320;
const BTN_SIZE = 32;
const BTN_REST_OFFSET_X = CARD_W + 60;
const SNAP_RADIUS = 50;

// Child card created after menu selection
interface ChildCard {
  key: string;
  icon: string;
  label: string;
  x: number; // position relative to parent node top-left
  y: number;
}

const CHILD_W = 200;
const CHILD_H = 100;

function SceneNodeComponent({ data, selected }: NodeProps<SceneNode>) {
  const [btnState, setBtnState] = useState<'hidden' | 'visible' | 'snapped'>('hidden');
  const [btnPos, setBtnPos] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [dragEnd, setDragEnd] = useState<{ x: number; y: number } | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [children, setChildren] = useState<ChildCard[]>([]);

  const cardRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const cardBodyRef = useRef<HTMLDivElement>(null);

  const getZoom = useCallback(() => {
    if (!cardRef.current) return 1;
    return cardRef.current.getBoundingClientRect().width / CARD_W;
  }, []);

  const getAnchorY = useCallback(() => {
    if (!cardBodyRef.current || !cardRef.current) return 128;
    const containerTop = cardRef.current.getBoundingClientRect().top;
    const bodyRect = cardBodyRef.current.getBoundingClientRect();
    const zoom = getZoom();
    return (bodyRect.top - containerTop + bodyRect.height / 2) / zoom;
  }, [getZoom]);

  // ── Mouse tracking: show + button when hovering card, snap when near rest pos ──
  useEffect(() => {
    if (dragging || menuOpen) return;

    const onMove = (e: MouseEvent) => {
      if (!cardRef.current) return;
      const rect = cardRef.current.getBoundingClientRect();
      const zoom = getZoom();
      const mx = (e.clientX - rect.left) / zoom;
      const my = (e.clientY - rect.top) / zoom;
      const restX = BTN_REST_OFFSET_X;
      const restY = getAnchorY();
      const dist = Math.sqrt((mx - restX) ** 2 + (my - restY) ** 2);

      if (dist < SNAP_RADIUS) {
        setBtnState('snapped');
        setBtnPos({ x: mx, y: my });
      } else {
        const localH = rect.height / zoom;
        const overCard = mx >= 0 && mx <= CARD_W + 200 && my >= -20 && my <= localH + 20;
        if (overCard) {
          setBtnState('visible');
          setBtnPos({ x: restX, y: restY });
        } else {
          setBtnState('hidden');
        }
      }
    };

    window.addEventListener('mousemove', onMove);
    return () => window.removeEventListener('mousemove', onMove);
  }, [dragging, menuOpen, getZoom, getAnchorY]);

  // ── Drag tracking ──
  useEffect(() => {
    if (!dragging) return;
    const onMove = (e: PointerEvent) => {
      if (!cardRef.current) return;
      const rect = cardRef.current.getBoundingClientRect();
      const zoom = getZoom();
      const localX = (e.clientX - rect.left) / zoom;
      const localY = (e.clientY - rect.top) / zoom;
      const anchorY = getAnchorY();
      setDragEnd({ x: localX - CARD_W, y: localY - anchorY });
      setBtnPos({ x: localX, y: localY });
    };
    const onUp = () => {
      setDragging(false);
      if (dragEnd && (Math.abs(dragEnd.x) > 20 || Math.abs(dragEnd.y) > 20)) {
        setMenuOpen(true);
      }
      setDragEnd(null);
      setBtnState('hidden');
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    return () => { window.removeEventListener('pointermove', onMove); window.removeEventListener('pointerup', onUp); };
  }, [dragging, dragEnd, getZoom, getAnchorY]);

  // ── Close menu on outside click ──
  useEffect(() => {
    if (!menuOpen) return;
    const h = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as HTMLElement)) setMenuOpen(false);
    };
    const t = setTimeout(() => document.addEventListener('mousedown', h), 100);
    return () => { clearTimeout(t); document.removeEventListener('mousedown', h); };
  }, [menuOpen]);

  const handleBtnPointerDown = useCallback((e: React.PointerEvent) => {
    e.stopPropagation();
    e.preventDefault();
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    setDragging(true);
    setDragEnd({ x: 0, y: 0 });
  }, []);

  const handleMenuSelect = useCallback((item: typeof CONNECT_MENU[0]) => {
    setMenuOpen(false);
    const ancY = getAnchorY();
    const idx = children.length;
    setChildren((prev) => [...prev, {
      key: `${item.key}-${Date.now()}`,
      icon: item.icon,
      label: item.label,
      x: CARD_W + 160 + idx * (CHILD_W + 60),
      y: ancY - CHILD_H / 2,
    }]);
  }, [children.length, getAnchorY]);

  // Child drag state
  const childDragRef = useRef<{ key: string; startX: number; startY: number; origX: number; origY: number } | null>(null);

  const handleChildPointerDown = useCallback((e: React.PointerEvent, childKey: string) => {
    e.stopPropagation();
    e.preventDefault();
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    const child = children.find((c) => c.key === childKey);
    if (!child) return;
    const zoom = getZoom();
    childDragRef.current = {
      key: childKey,
      startX: e.clientX / zoom,
      startY: e.clientY / zoom,
      origX: child.x,
      origY: child.y,
    };
  }, [children, getZoom]);

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      if (!childDragRef.current) return;
      const zoom = getZoom();
      const dx = e.clientX / zoom - childDragRef.current.startX;
      const dy = e.clientY / zoom - childDragRef.current.startY;
      const key = childDragRef.current.key;
      setChildren((prev) => prev.map((c) =>
        c.key === key
          ? { ...c, x: childDragRef.current!.origX + dx, y: childDragRef.current!.origY + dy }
          : c
      ));
    };
    const onUp = () => { childDragRef.current = null; };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    return () => { window.removeEventListener('pointermove', onMove); window.removeEventListener('pointerup', onUp); };
  }, [getZoom]);

  const cardBg = selected ? '#1f2129' : '#17191f';
  const cardBorder = selected ? 'rgba(255,255,255,0.16)' : 'rgba(255,255,255,0.07)';
  const anchorY = getAnchorY();
  const showBtn = btnState !== 'hidden' || dragging;

  return (
    <div ref={cardRef} style={{ width: CARD_W, position: 'relative' }}>
      <Handle type="target" position={Position.Left} />
      <Handle type="source" position={Position.Right} />
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8, paddingLeft: 4 }}>
        <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.2)' }}>≡</span>
        <span style={{ fontSize: 12, fontWeight: 500, letterSpacing: '0.03em', color: selected ? 'rgba(0,200,255,0.9)' : 'rgba(0,200,255,0.5)' }}>Scene</span>
      </div>

      {/* Card body */}
      <div ref={cardBodyRef} style={{
        position: 'relative', borderRadius: 16,
        backgroundColor: cardBg, border: `1px solid ${cardBorder}`,
        boxShadow: selected ? '0 2px 24px rgba(255,255,255,0.03)' : 'none',
        overflow: 'hidden', minHeight: 200,
        transition: 'background-color 0.2s, border-color 0.2s',
      }}>
        <svg style={{ position: 'absolute', top: 0, right: 0 }} width="20" height="20" viewBox="0 0 20 20" fill="none">
          <path d="M0 0L20 0L20 20Z" fill="white" fillOpacity="0.04" />
        </svg>

        <div style={{ padding: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
            <span style={{
              fontSize: 10, fontFamily: 'monospace', padding: '2px 6px', borderRadius: 4,
              color: selected ? 'rgba(0,200,255,0.7)' : 'rgba(255,255,255,0.25)',
              backgroundColor: selected ? 'rgba(0,200,255,0.1)' : 'rgba(255,255,255,0.04)',
            }}>S{data.order}</span>
            <span style={{ fontSize: 14, fontWeight: 500, color: selected ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.65)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {data.heading || '未命名场景'}
            </span>
          </div>

          <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
            {data.location && <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', backgroundColor: 'rgba(255,255,255,0.04)', padding: '4px 10px', borderRadius: 8 }}>{data.location}</span>}
            {data.timeOfDay && <span style={{ fontSize: 11, color: 'rgba(255,180,50,0.4)', backgroundColor: 'rgba(255,180,50,0.05)', padding: '4px 10px', borderRadius: 8 }}>{data.timeOfDay}</span>}
            {data.emotionalPeak && <span style={{ fontSize: 11, color: 'rgba(255,100,150,0.5)', backgroundColor: 'rgba(255,100,150,0.06)', padding: '4px 10px', borderRadius: 8 }}>{data.emotionalPeak}</span>}
          </div>

          <p style={{ fontSize: 12, lineHeight: 1.7, color: selected ? 'rgba(255,255,255,0.4)' : 'rgba(255,255,255,0.22)', marginBottom: 16, display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
            {data.coreEvent || data.description || '暂无描述'}
          </p>

          {data.characterNames.length > 0 && (
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
              {data.characterNames.slice(0, 5).map((name) => (
                <span key={name} style={{ fontSize: 10, color: 'rgba(180,150,255,0.45)', backgroundColor: 'rgba(140,100,255,0.06)', padding: '2px 8px', borderRadius: 12 }}>{name}</span>
              ))}
            </div>
          )}

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.18)' }}>{data.shotCount} 个镜头</div>
            {data.moduleType && MODULE_BADGE[data.moduleType] && (
              <span style={{
                fontSize: 10, padding: '2px 8px', borderRadius: 6, fontWeight: 500,
                backgroundColor: MODULE_BADGE[data.moduleType].color + '18',
                color: MODULE_BADGE[data.moduleType].color,
              }}>
                {MODULE_BADGE[data.moduleType].icon} {MODULE_BADGE[data.moduleType].label}
              </span>
            )}
          </div>
        </div>

        <svg style={{ position: 'absolute', bottom: 8, right: 8 }} width="10" height="10" viewBox="0 0 10 10" fill="none">
          <path d="M9 1L1 9M9 4.5L4.5 9M9 8L8 9" stroke="white" strokeOpacity="0.06" strokeWidth="1" strokeLinecap="round" />
        </svg>
      </div>

      {/* ── + button: snap to mouse near rest pos ── */}
      {showBtn && (
        <div
          className="nodrag nopan"
          onPointerDown={handleBtnPointerDown}
          style={{
            position: 'absolute',
            left: btnPos.x - BTN_SIZE / 2,
            top: btnPos.y - BTN_SIZE / 2,
            width: BTN_SIZE, height: BTN_SIZE, borderRadius: '50%',
            border: '1px solid rgba(255,255,255,0.18)',
            backgroundColor: '#1e2028',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: dragging ? 'grabbing' : 'grab',
            zIndex: 10, pointerEvents: 'auto',
          }}
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <line x1="7" y1="2" x2="7" y2="12" stroke="rgba(255,255,255,0.4)" strokeWidth="1.5" strokeLinecap="round" />
            <line x1="2" y1="7" x2="12" y2="7" stroke="rgba(255,255,255,0.4)" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </div>
      )}

      {/* ── Drag curve: SOLID line from card right-center to mouse ── */}
      {dragging && dragEnd && (
        <svg style={{ position: 'absolute', top: 0, left: 0, width: 2000, height: 2000, pointerEvents: 'none', zIndex: 5, overflow: 'visible' }}>
          <path
            d={(() => {
              const sx = CARD_W, sy = anchorY;
              const ex = CARD_W + dragEnd.x, ey = anchorY + dragEnd.y;
              const cpx = sx + (ex - sx) * 0.5;
              return `M ${sx} ${sy} C ${cpx} ${sy}, ${cpx} ${ey}, ${ex} ${ey}`;
            })()}
            stroke="rgba(255,255,255,0.25)"
            strokeWidth="2"
            fill="none"
          />
          <circle cx={CARD_W + dragEnd.x} cy={anchorY + dragEnd.y} r="4" fill="rgba(255,255,255,0.35)" />
        </svg>
      )}

      {/* ── Connect menu after drag release ── */}
      {menuOpen && (
        <div ref={menuRef} style={{ position: 'absolute', top: '50%', transform: 'translateY(-50%)', left: CARD_W + 60, zIndex: 20 }}>
          <div style={{ width: 230, borderRadius: 16, backgroundColor: '#1e2028', border: '1px solid rgba(255,255,255,0.08)', boxShadow: '0 8px 40px rgba(0,0,0,0.6)', overflow: 'hidden' }}>
            <div style={{ padding: '12px 16px', fontSize: 11, color: 'rgba(255,255,255,0.3)', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>引用该节点生成</div>
            {CONNECT_MENU.map((item, i) => (
              <button key={item.key}
                onClick={(e) => { e.stopPropagation(); handleMenuSelect(item); }}
                style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', textAlign: 'left', border: 'none', cursor: 'pointer', backgroundColor: i === 0 ? 'rgba(255,255,255,0.02)' : 'transparent', color: 'inherit' }}
                onMouseEnter={(e) => { (e.currentTarget).style.backgroundColor = 'rgba(255,255,255,0.04)'; }}
                onMouseLeave={(e) => { (e.currentTarget).style.backgroundColor = i === 0 ? 'rgba(255,255,255,0.02)' : 'transparent'; }}
              >
                <span style={{ width: 32, height: 32, borderRadius: 8, backgroundColor: 'rgba(255,255,255,0.04)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, color: 'rgba(255,255,255,0.35)', flexShrink: 0 }}>{item.icon}</span>
                <div>
                  <div style={{ fontSize: 13, color: 'rgba(255,255,255,0.7)', fontWeight: 500 }}>{item.label}</div>
                  {item.desc && <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)', marginTop: 2 }}>{item.desc}</div>}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Child cards + persistent bezier curves ── */}
      {children.map((child) => {
        // Curve: parent card right-center → child card left-center
        const childCenterY = child.y + CHILD_H / 2;

        return (
          <div key={child.key}>
            {/* Bezier curve: follows child position dynamically */}
            <svg style={{ position: 'absolute', top: 0, left: 0, width: 4000, height: 4000, pointerEvents: 'none', zIndex: 1, overflow: 'visible' }}>
              <path
                d={(() => {
                  const sx = CARD_W, sy = anchorY;
                  const ex = child.x, ey = childCenterY;
                  const cpOffset = Math.abs(ex - sx) * 0.4;
                  return `M ${sx} ${sy} C ${sx + cpOffset} ${sy}, ${ex - cpOffset} ${ey}, ${ex} ${ey}`;
                })()}
                stroke="rgba(255,255,255,0.15)"
                strokeWidth="1.5"
                fill="none"
              />
            </svg>

            {/* Child card — draggable */}
            <div
              className="nodrag nopan"
              onPointerDown={(e) => handleChildPointerDown(e, child.key)}
              style={{
                position: 'absolute',
                left: child.x,
                top: child.y,
                width: CHILD_W,
                borderRadius: 14,
                backgroundColor: '#17191f',
                border: '1px solid rgba(255,255,255,0.07)',
                overflow: 'hidden',
                zIndex: 2,
                cursor: 'grab',
                userSelect: 'none',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 14px', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                <span style={{ width: 28, height: 28, borderRadius: 6, backgroundColor: 'rgba(255,255,255,0.04)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, color: 'rgba(255,255,255,0.35)', flexShrink: 0 }}>{child.icon}</span>
                <span style={{ fontSize: 13, color: 'rgba(255,255,255,0.65)', fontWeight: 500 }}>{child.label}</span>
              </div>
              <div style={{ padding: 14, minHeight: 50 }}>
                <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.2)' }}>等待配置...</span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export const SceneNode = memo(SceneNodeComponent);
