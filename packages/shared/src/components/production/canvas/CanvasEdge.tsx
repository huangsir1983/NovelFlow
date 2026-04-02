'use client';

import { memo } from 'react';
import { BaseEdge, getBezierPath, type EdgeProps } from '@xyflow/react';

/* ── Pipeline Edge (solid line, clickable to disconnect) ── */

function PipelineEdgeComponent({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  selected,
}: EdgeProps) {
  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  });

  return (
    <BaseEdge
      id={id}
      path={edgePath}
      style={{
        stroke: selected ? 'rgba(0,200,255,0.7)' : 'rgba(255,255,255,0.1)',
        strokeWidth: selected ? 2 : 1.5,
        transition: 'stroke 0.15s',
        cursor: 'pointer',
      }}
    />
  );
}

export const PipelineEdge = memo(PipelineEdgeComponent);

/* ── Bypass Edge (dashed line, shot → video shortcut when pipeline is broken) ── */

function BypassEdgeComponent({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  selected,
}: EdgeProps) {
  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  });

  return (
    <BaseEdge
      id={id}
      path={edgePath}
      style={{
        stroke: selected ? 'rgba(255,180,50,0.8)' : 'rgba(255,180,50,0.35)',
        strokeWidth: selected ? 2.5 : 2,
        strokeDasharray: '8 4',
        transition: 'stroke 0.15s',
        cursor: 'pointer',
      }}
    />
  );
}

export const BypassEdge = memo(BypassEdgeComponent);
