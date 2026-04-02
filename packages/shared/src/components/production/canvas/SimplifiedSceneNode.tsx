'use client';

import React, { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { SceneNodeData, CanvasNodeStatus } from '../../../types';

/**
 * Simplified scene rendering for low-zoom virtualization.
 *
 * At zoom 0.1-0.2 (simplified mode): colored block with heading + shot count.
 * At zoom < 0.1 (collapsed mode): minimal rectangle with scene number.
 */

const STATUS_COLORS: Record<CanvasNodeStatus, string> = {
  idle: 'rgba(255,255,255,0.08)',
  queued: 'rgba(186,117,23,0.3)',
  running: 'rgba(55,138,221,0.3)',
  success: 'rgba(29,158,117,0.3)',
  error: 'rgba(226,75,74,0.3)',
};

const MODULE_COLORS: Record<string, string> = {
  dialogue: '#378ADD',
  action: '#D85A30',
  suspense: '#534AB7',
  landscape: '#1D9E75',
  emotion: '#D4537E',
};

function SimplifiedSceneNodeComponent({ data }: NodeProps) {
  const d = data as SceneNodeData;
  const color = d.moduleType ? MODULE_COLORS[d.moduleType] || '#fff' : '#fff';
  const bgColor = d.moduleType ? `${color}22` : 'rgba(255,255,255,0.05)';
  const borderColor = d.moduleType ? `${color}66` : 'rgba(255,255,255,0.1)';

  return (
    <div
      style={{
        width: 280,
        height: 60,
        borderRadius: 8,
        background: bgColor,
        border: `1px solid ${borderColor}`,
        display: 'flex',
        alignItems: 'center',
        padding: '0 12px',
        gap: 8,
        overflow: 'hidden',
      }}
    >
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />

      {/* Scene number badge */}
      <div
        style={{
          width: 24,
          height: 24,
          borderRadius: 6,
          background: `${color}33`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 11,
          fontWeight: 600,
          color: color,
          flexShrink: 0,
        }}
      >
        {d.order}
      </div>

      {/* Heading */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 12,
            fontWeight: 500,
            color: 'rgba(255,255,255,0.85)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {d.heading || `Scene ${d.order}`}
        </div>
        <div
          style={{
            fontSize: 10,
            color: 'rgba(255,255,255,0.4)',
            marginTop: 2,
          }}
        >
          {d.shotCount} shots
        </div>
      </div>

      {/* Status indicator */}
      <div
        style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: STATUS_COLORS[d.status] || STATUS_COLORS.idle,
          flexShrink: 0,
        }}
      />
    </div>
  );
}

export const SimplifiedSceneNode = memo(SimplifiedSceneNodeComponent);

/**
 * Collapsed scene node for very low zoom (< 0.1).
 * Minimal colored rectangle with just the scene number.
 */
function CollapsedSceneNodeComponent({ data }: NodeProps) {
  const d = data as SceneNodeData;
  const color = d.moduleType ? MODULE_COLORS[d.moduleType] || '#888' : '#888';

  return (
    <div
      style={{
        width: 120,
        height: 30,
        borderRadius: 4,
        background: `${color}33`,
        border: `1px solid ${color}55`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 10,
        fontWeight: 600,
        color: `${color}cc`,
      }}
    >
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
      S{d.order} ({d.shotCount})
    </div>
  );
}

export const CollapsedSceneNode = memo(CollapsedSceneNodeComponent);
