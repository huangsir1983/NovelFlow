'use client';

import { memo } from 'react';
import { BaseEdge, getBezierPath, type EdgeProps } from '@xyflow/react';

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
      }}
    />
  );
}

export const PipelineEdge = memo(PipelineEdgeComponent);
