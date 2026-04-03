'use client';

import { memo } from 'react';
import { getBezierPath, type EdgeProps } from '@xyflow/react';
import { useCanvasStore } from '../../../stores/canvasStore';

/* ── Pipeline Edge (solid line + optional electricity flow animation) ── */

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
  const flowAnimation = useCanvasStore((s) => s.edgeFlowAnimation);

  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  });

  const baseColor = selected ? 'rgba(0,200,255,0.7)' : 'rgba(255,255,255,0.12)';

  return (
    <g>
      {/* Base edge line */}
      <path
        d={edgePath}
        fill="none"
        stroke={baseColor}
        strokeWidth={selected ? 2 : 1.5}
        style={{ transition: 'stroke 0.15s' }}
        className="react-flow__edge-path"
      />

      {/* Electricity flow streak with halo */}
      {flowAnimation && (
        <>
          <defs>
            {/* Outer halo glow — large soft blur */}
            <filter id={`edge-halo-${id}`} x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="6" result="blur1" />
              <feMerge>
                <feMergeNode in="blur1" />
              </feMerge>
            </filter>
            {/* Inner glow — sharper */}
            <filter id={`edge-glow-${id}`} x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="3" result="blur2" />
              <feMerge>
                <feMergeNode in="blur2" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          {/* Layer 1: Wide halo — soft ambient glow around streak */}
          <path
            d={edgePath}
            fill="none"
            stroke={selected ? 'rgba(0,180,255,0.25)' : 'rgba(0,160,255,0.15)'}
            strokeWidth={selected ? 12 : 8}
            strokeLinecap="round"
            strokeDasharray="40 190"
            filter={`url(#edge-halo-${id})`}
          >
            <animate
              attributeName="stroke-dashoffset"
              values="230;0"
              dur="2s"
              repeatCount="indefinite"
            />
          </path>
          {/* Layer 2: Core streak — bright center */}
          <path
            d={edgePath}
            fill="none"
            stroke={selected ? 'rgba(0,210,255,0.95)' : 'rgba(0,180,255,0.7)'}
            strokeWidth={selected ? 3 : 2}
            strokeLinecap="round"
            strokeDasharray="30 200"
            filter={`url(#edge-glow-${id})`}
          >
            <animate
              attributeName="stroke-dashoffset"
              values="230;0"
              dur="2s"
              repeatCount="indefinite"
            />
          </path>
          {/* Layer 3: Second streak — trailing pulse */}
          <path
            d={edgePath}
            fill="none"
            stroke={selected ? 'rgba(0,200,255,0.4)' : 'rgba(0,160,255,0.25)'}
            strokeWidth={selected ? 5 : 3}
            strokeLinecap="round"
            strokeDasharray="20 210"
            filter={`url(#edge-halo-${id})`}
          >
            <animate
              attributeName="stroke-dashoffset"
              values="230;0"
              dur="2s"
              begin="-0.8s"
              repeatCount="indefinite"
            />
          </path>
        </>
      )}
    </g>
  );
}

export const PipelineEdge = memo(PipelineEdgeComponent);

/* ── Bypass Edge (dashed line, shot → video shortcut when pipeline is broken) ── */

function BypassEdgeComponent({
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
    <path
      d={edgePath}
      fill="none"
      stroke={selected ? 'rgba(255,180,50,0.8)' : 'rgba(255,180,50,0.35)'}
      strokeWidth={selected ? 2.5 : 2}
      strokeDasharray="8 4"
      style={{ transition: 'stroke 0.15s', cursor: 'pointer' }}
      className="react-flow__edge-path"
    />
  );
}

export const BypassEdge = memo(BypassEdgeComponent);
