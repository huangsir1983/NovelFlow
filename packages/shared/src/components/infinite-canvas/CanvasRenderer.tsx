'use client';

// ══════════════════════════════════════════════════════════════
// CanvasRenderer.tsx — 虚拟化节点渲染器
// ══════════════════════════════════════════════════════════════

import React, { useMemo } from 'react';
import { useInfiniteCanvasStore } from '../../../stores/infiniteCanvasStore';
import { StoryboardNode } from '../nodes/StoryboardNode';
import { ImageNode } from '../nodes/ImageNode';
import { VideoNode } from '../nodes/VideoNode';
import type { CanvasNodeData } from '../../../types/canvas';

export const CanvasRenderer: React.FC = () => {
  const getVisibleNodes = useInfiniteCanvasStore((s) => s.getVisibleNodes);
  const transform = useInfiniteCanvasStore((s) => s.view.transform);

  const visibleNodes = useMemo(() => getVisibleNodes(), [transform.offsetX, transform.offsetY, transform.scale, getVisibleNodes]);

  return (
    <>
      {visibleNodes.map((node) => (
        <NodeWrapper key={node.id} node={node} />
      ))}
    </>
  );
};

const NodeWrapper: React.FC<{ node: CanvasNodeData }> = ({ node }) => {
  const style: React.CSSProperties = {
    position: 'absolute',
    left: node.position.x,
    top: node.position.y,
    width: node.size.width,
  };

  return (
    <div style={style}>
      {node.type === 'storyboard' && <StoryboardNode node={node} />}
      {node.type === 'image' && <ImageNode node={node} />}
      {node.type === 'video' && <VideoNode node={node} />}
    </div>
  );
};
