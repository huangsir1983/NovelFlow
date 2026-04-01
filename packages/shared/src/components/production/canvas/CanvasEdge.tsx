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
    <>
      {/* Glow layer */}
      <BaseEdge
        id={`${id}-glow`}
        path={edgePath}
        style={{
          stroke: 'rgba(0,200,255,0.1)',
          strokeWidth: 8,
          filter: 'blur(4px)',
        }}
      />
      {/* Main line */}
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          stroke: selected ? 'rgba(0,200,255,0.8)' : 'rgba(0,200,255,0.3)',
          strokeWidth: 2,
          transition: 'stroke 0.2s',
        }}
      />
      {/* Animated dot */}
      <circle r="3" fill="rgba(0,200,255,0.8)">
        <animateMotion dur="3s" repeatCount="indefinite" path={edgePath} />
      </circle>
    </>
  );
}

export const PipelineEdge = memo(PipelineEdgeComponent);
