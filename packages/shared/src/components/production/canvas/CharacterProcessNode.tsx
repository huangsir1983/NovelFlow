'use client';

import { memo, useState, useCallback } from 'react';
import { type NodeProps, type Node, Handle, Position } from '@xyflow/react';
import type { CharacterProcessNodeData } from '../../../types/canvas';
import { useCanvasStore } from '../../../stores/canvasStore';

type CharacterProcessNode = Node<CharacterProcessNodeData, 'characterProcess'>;

// Slot label mapping
const SLOT_LABELS: Record<string, string> = {
  visual_reference: '参考图',
  front_full: '正前全身',
  left_full: '左侧全身',
  right_full: '右侧全身',
  back_full: '背影全身',
  front_half: '正前半身',
};

// Display order for slots
const SLOT_ORDER = ['visual_reference', 'front_full', 'left_full', 'right_full', 'back_full', 'front_half'];

// Styles extracted to module level to avoid re-creation on each render
const outerStyle = { width: 180, position: 'relative' as const };
const imageContainerStyle = {
  width: '100%', height: 260,
  backgroundColor: '#0c0e12',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
};
const placeholderIconStyle = { fontSize: 28, display: 'block', color: 'rgba(255,255,255,0.06)', marginBottom: 4 };
const placeholderTextStyle = { fontSize: 10, color: 'rgba(255,255,255,0.15)' };
const overlayStyle = {
  position: 'absolute' as const, bottom: 0, left: 0, right: 0,
  background: 'linear-gradient(transparent, rgba(0,0,0,0.75))',
  padding: '24px 10px 10px',
  display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' as const,
};
const statusDotBase = {
  position: 'absolute' as const, top: 10, right: 10, width: 8, height: 8,
  borderRadius: '50%', zIndex: 2,
};

function CharacterProcessNodeComponent({ id, data, selected }: NodeProps<CharacterProcessNode>) {
  const [hovered, setHovered] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const cardBorder = selected ? 'rgba(255,255,255,0.16)' : hovered ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.06)';
  const accent = selected ? 'rgba(167,139,250,0.9)' : 'rgba(167,139,250,0.5)';

  const availableImages = data.availableImages;
  const availableCount = availableImages ? Object.values(availableImages).filter(Boolean).length : 0;
  const hasAnyImage = availableCount > 0;

  const handleCardClick = useCallback(() => {
    if (hasAnyImage) {
      setExpanded(prev => !prev);
    }
  }, [hasAnyImage]);

  const handleVariantSelect = useCallback((slotKey: string, url: string) => {
    const store = useCanvasStore.getState();
    const edges = store.edges;
    const downstream = edges.filter(e => e.source === id);
    const targetIds = new Set(downstream.map(e => e.target));

    // Find storageKey for this slot from availableImages context
    // The URL itself is sufficient for display; storageKey extracted from URL pattern
    const storageKeyMatch = url.match(/\/uploads\/(.+)$/);
    const storageKey = storageKeyMatch?.[1];

    const updatedNodes = store.nodes.map(n => {
      if (n.id === id) {
        return {
          ...n,
          data: {
            ...n.data,
            visualRefUrl: url,
            visualRefStorageKey: storageKey,
            selectedVariant: slotKey,
          },
        };
      }
      // Propagate to immediate downstream nodes (ViewAngle etc.)
      if (targetIds.has(n.id)) {
        return {
          ...n,
          data: {
            ...n.data,
            inputImageUrl: url,
            inputStorageKey: storageKey,
          },
        };
      }
      return n;
    });

    store.setNodes(updatedNodes);
    store.resetDownstreamNodes(id);
    setExpanded(false);
  }, [id]);

  // Build ordered list of ALL predefined slots (show empty ones as placeholders)
  const slotEntries = SLOT_ORDER
    .map(key => ({ key, label: SLOT_LABELS[key] || key, url: availableImages?.[key] || '' }));
  // Also include any extra keys not in SLOT_ORDER
  if (availableImages) {
    for (const key of Object.keys(availableImages)) {
      if (!SLOT_ORDER.includes(key) && availableImages[key]) {
        slotEntries.push({ key, label: SLOT_LABELS[key] || key, url: availableImages[key] });
      }
    }
  }

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={outerStyle}
    >
      <Handle type="target" position={Position.Left} className="target-handle" style={{ top: '55%' }} />
      <Handle type="source" position={Position.Right} style={{ top: '55%' }} />

      <div className="flex items-center gap-1.5 mb-2 pl-1">
        <span className="text-[13px]">👤</span>
        <span className="text-[12px] font-medium tracking-wide" style={{ color: accent }}>
          {data.characterName || '角色'}
        </span>
        {availableCount > 0 && (
          <span style={{
            fontSize: 9, padding: '1px 5px', borderRadius: 3,
            backgroundColor: 'rgba(167,139,250,0.15)', color: 'rgba(167,139,250,0.6)',
          }}>
            {availableCount}/{SLOT_ORDER.length}图
          </span>
        )}
      </div>

      {/* Portrait card */}
      <div className="canvas-card" style={{
        borderRadius: 16, position: 'relative', overflow: 'hidden',
        border: `1px solid ${cardBorder}`,
        transition: 'border-color 0.2s',
        cursor: hasAnyImage ? 'pointer' : 'default',
      }} onClick={handleCardClick}>
        <div style={imageContainerStyle}>
          {data.visualRefUrl ? (
            <img src={data.visualRefUrl} alt={data.characterName}
              style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          ) : (
            <div style={{ textAlign: 'center' }}>
              <span style={placeholderIconStyle}>👤</span>
              <span style={placeholderTextStyle}>选择角色图片</span>
            </div>
          )}
        </div>

        {/* Overlay: character name + badges at bottom */}
        <div style={overlayStyle}>
          <span style={{ fontSize: 11, fontWeight: 500, color: 'rgba(255,255,255,0.85)', width: '100%' }}>
            {data.characterName}
          </span>
          {data.selectedVariant && (
            <span style={{
              fontSize: 9, padding: '2px 6px', borderRadius: 4,
              backgroundColor: 'rgba(167,139,250,0.2)', color: 'rgba(167,139,250,0.8)',
            }}>
              {SLOT_LABELS[data.selectedVariant] || data.selectedVariant}
            </span>
          )}
          {data.visualRefUrl && (
            <span style={{
              fontSize: 9, padding: '2px 6px', borderRadius: 4,
              backgroundColor: 'rgba(52,211,153,0.15)', color: 'rgba(52,211,153,0.7)',
            }}>
              图片已选
            </span>
          )}
        </div>

        {/* Status dot */}
        <div style={{
          ...statusDotBase,
          backgroundColor:
            data.status === 'running' ? '#60a5fa'
            : data.status === 'success' ? '#34d399'
            : data.status === 'error' ? '#f87171'
            : 'transparent',
        }} />
      </div>

      {/* Expandable variant selection panel — opens to the right */}
      {expanded && slotEntries.length > 0 && (
        <div
          className="nopan nodrag nowheel"
          style={{
            position: 'absolute',
            top: 24,
            left: '100%',
            marginLeft: 8,
            borderRadius: 12,
            padding: '8px',
            backgroundColor: 'rgba(15,17,22,0.95)',
            border: '1px solid rgba(255,255,255,0.08)',
            zIndex: 10,
          }}
        >
          <div style={{
            display: 'flex', alignItems: 'center', gap: 6,
            marginBottom: 6, paddingBottom: 4,
            borderBottom: '1px solid rgba(255,255,255,0.06)',
          }}>
            <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)', fontWeight: 500, whiteSpace: 'nowrap' }}>
              选择角色图片
            </span>
            <span
              style={{ fontSize: 12, color: 'rgba(255,255,255,0.3)', cursor: 'pointer', lineHeight: 1, marginLeft: 'auto' }}
              onClick={(e) => { e.stopPropagation(); setExpanded(false); }}
            >
              ×
            </span>
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 80px)',
            gap: 6,
          }}>
            {slotEntries.map(({ key, label, url }) => {
              const isSelected = data.selectedVariant === key;
              const hasImage = !!url;
              return (
                <div
                  key={key}
                  onClick={(e) => { e.stopPropagation(); if (hasImage) handleVariantSelect(key, url); }}
                  style={{
                    borderRadius: 8,
                    overflow: 'hidden',
                    width: 80,
                    border: isSelected
                      ? '2px solid rgba(167,139,250,0.7)'
                      : '1px solid rgba(255,255,255,0.06)',
                    cursor: hasImage ? 'pointer' : 'default',
                    transition: 'border-color 0.15s',
                    backgroundColor: '#0c0e12',
                    opacity: hasImage ? 1 : 0.4,
                  }}
                >
                  <div style={{ width: '100%', aspectRatio: '3 / 4', position: 'relative' }}>
                    {hasImage ? (
                      <img
                        src={url}
                        alt={label}
                        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                      />
                    ) : (
                      <div style={{
                        width: '100%', height: '100%',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        backgroundColor: 'rgba(255,255,255,0.02)',
                      }}>
                        <span style={{ fontSize: 18, color: 'rgba(255,255,255,0.08)' }}>+</span>
                      </div>
                    )}
                    {isSelected && hasImage && (
                      <div style={{
                        position: 'absolute', top: 3, right: 3,
                        width: 14, height: 14, borderRadius: '50%',
                        backgroundColor: 'rgba(167,139,250,0.9)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 8, color: '#fff',
                      }}>
                        ✓
                      </div>
                    )}
                  </div>
                  <div style={{
                    padding: '4px 6px',
                    fontSize: 9,
                    color: isSelected ? 'rgba(167,139,250,0.9)' : hasImage ? 'rgba(255,255,255,0.4)' : 'rgba(255,255,255,0.2)',
                    textAlign: 'center',
                    fontWeight: isSelected ? 500 : 400,
                  }}>
                    {label}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export const CharacterProcessNode = memo(CharacterProcessNodeComponent);
