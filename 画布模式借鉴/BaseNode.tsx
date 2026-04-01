// ============================================================
// BaseNode.tsx - 节点基础样式与交互
// ============================================================
import React, { useRef, useCallback } from 'react';
import { useCanvasStore } from '../../store/canvasStore';
import { NodeData, NodeStatus, ModuleType } from '../../types';

const STATUS_CONFIG: Record<NodeStatus, { color: string; bg: string; label: string }> = {
  idle:       { color: '#888780', bg: 'rgba(136,135,128,0.1)', label: '未开始' },
  ready:      { color: '#378ADD', bg: 'rgba(55,138,221,0.1)',  label: '就绪' },
  processing: { color: '#BA7517', bg: 'rgba(186,117,23,0.1)',  label: '处理中' },
  done:       { color: '#1D9E75', bg: 'rgba(29,158,117,0.1)',  label: '完成' },
  error:      { color: '#E24B4A', bg: 'rgba(226,75,74,0.1)',   label: '失败' },
  outdated:   { color: '#D85A30', bg: 'rgba(216,90,48,0.1)',   label: '需更新' },
};

const MODULE_COLORS: Record<ModuleType, string> = {
  dialogue:  '#378ADD',
  action:    '#D85A30',
  suspense:  '#534AB7',
  landscape: '#1D9E75',
  emotion:   '#D4537E',
};

interface BaseNodeProps {
  node: NodeData;
  headerColor: string;
  icon: string;
  children: React.ReactNode;
}

export const BaseNode: React.FC<BaseNodeProps> = ({ node, headerColor, icon, children }) => {
  const { selectNode, moveNode, view, selectedNodeIds, hoveredNodeId, setHoveredNode } = useCanvasStore();
  const { transform } = view;
  const dragRef = useRef<{ startX: number; startY: number; nodeX: number; nodeY: number } | null>(null);
  const isSelected = selectedNodeIds.has(node.id);
  const isHovered = hoveredNodeId === node.id;
  const sc = STATUS_CONFIG[node.status];

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    selectNode(node.id, e.shiftKey);
    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      nodeX: node.position.x,
      nodeY: node.position.y,
    };

    const onMove = (me: MouseEvent) => {
      if (!dragRef.current) return;
      const dx = (me.clientX - dragRef.current.startX) / transform.scale;
      const dy = (me.clientY - dragRef.current.startY) / transform.scale;
      moveNode(node.id, {
        x: dragRef.current.nodeX + dx,
        y: dragRef.current.nodeY + dy,
      });
    };
    const onUp = () => {
      dragRef.current = null;
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [node.id, node.position, transform.scale, selectNode, moveNode]);

  return (
    <div
      onMouseDown={onMouseDown}
      onMouseEnter={() => setHoveredNode(node.id)}
      onMouseLeave={() => setHoveredNode(null)}
      style={{
        background: 'var(--color-background-primary)',
        border: `${isSelected ? 1.5 : 0.5}px solid ${isSelected ? '#378ADD' : isHovered ? 'var(--color-border-primary)' : 'var(--color-border-secondary)'}`,
        borderRadius: 10,
        cursor: 'pointer',
        transition: 'border-color 0.12s',
        position: 'relative',
        overflow: 'visible',
      }}
    >
      {/* 节点头部 */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: '7px 10px 6px',
        borderBottom: '0.5px solid var(--color-border-tertiary)',
        background: headerColor + '18',
        borderRadius: '10px 10px 0 0',
      }}>
        <div style={{
          width: 18,
          height: 18,
          borderRadius: 4,
          background: headerColor + '33',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 10,
          flexShrink: 0,
        }}>
          {icon}
        </div>
        <span style={{ fontSize: 11, fontWeight: 500, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {node.label}
        </span>
        {/* 状态指示点 */}
        <div style={{ width: 6, height: 6, borderRadius: '50%', background: sc.color, flexShrink: 0 }} title={sc.label} />
      </div>

      {/* 节点体 */}
      <div style={{ padding: '8px 10px' }}>
        {children}

        {/* 底部标签行 */}
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 6 }}>
          <StatusPill status={node.status} />
          {node.moduleType && (
            <span style={{
              fontSize: 10,
              padding: '2px 6px',
              borderRadius: 4,
              background: MODULE_COLORS[node.moduleType] + '18',
              color: MODULE_COLORS[node.moduleType],
            }}>
              {node.agentAssigned && '🤖 '}{node.moduleType}
            </span>
          )}
        </div>
      </div>

      {/* Agent 分配徽章 */}
      {node.agentAssigned && (
        <div style={{
          position: 'absolute',
          top: -7,
          right: -7,
          width: 16,
          height: 16,
          borderRadius: '50%',
          background: '#1D9E75',
          border: '2px solid var(--color-background-primary)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 8,
          color: '#fff',
          fontWeight: 700,
        }}>A</div>
      )}
    </div>
  );
};

export const StatusPill: React.FC<{ status: NodeStatus }> = ({ status }) => {
  const sc = STATUS_CONFIG[status];
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 3,
      fontSize: 10,
      padding: '2px 7px',
      borderRadius: 99,
      background: sc.bg,
      color: sc.color,
      fontWeight: 500,
    }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: sc.color }} />
      {sc.label}
    </span>
  );
};


// ============================================================
// StoryboardNode.tsx - 分镜文本节点
// ============================================================
import React from 'react';
import { BaseNode } from './BaseNode';
import { NodeData, StoryboardContent } from '../../types';

export const StoryboardNode: React.FC<{ node: NodeData }> = ({ node }) => {
  const content = node.content as StoryboardContent;

  return (
    <BaseNode node={node} headerColor="#378ADD" icon="📄">
      {/* 分镜原文摘要 */}
      <div style={{
        fontSize: 11,
        color: 'var(--color-text-secondary)',
        lineHeight: 1.5,
        marginBottom: 6,
        display: '-webkit-box',
        WebkitLineClamp: 2,
        WebkitBoxOrient: 'vertical',
        overflow: 'hidden',
      }}>
        {content.rawText || '暂无分镜内容'}
      </div>

      {/* 镜头类型 & 情感 */}
      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 4 }}>
        {content.shotType && (
          <Tag color="#378ADD">{SHOT_LABELS[content.shotType] || content.shotType}</Tag>
        )}
        {content.emotion && (
          <Tag color="#534AB7">{content.emotion}</Tag>
        )}
        {content.duration > 0 && (
          <Tag color="#888780">{content.duration}s</Tag>
        )}
      </div>

      {/* 角色 */}
      {content.characterIds.length > 0 && (
        <div style={{ fontSize: 10, color: 'var(--color-text-tertiary)' }}>
          角色: {content.characterIds.length}
        </div>
      )}

      {/* 提示词状态 */}
      <div style={{ marginTop: 6, display: 'flex', gap: 4 }}>
        <PromptDot label="图" filled={!!content.imagePrompt} />
        <PromptDot label="视" filled={!!content.videoPrompt} />
      </div>
    </BaseNode>
  );
};

const SHOT_LABELS: Record<string, string> = {
  'close-up': '特写',
  'medium': '中景',
  'wide': '远景',
  'overhead': '俯视',
  'low-angle': '仰视',
  'pov': '主观',
  'over-shoulder': '过肩',
};

const Tag: React.FC<{ children: React.ReactNode; color: string }> = ({ children, color }) => (
  <span style={{
    fontSize: 10,
    padding: '1px 5px',
    borderRadius: 4,
    background: color + '15',
    color,
  }}>{children}</span>
);

const PromptDot: React.FC<{ label: string; filled: boolean }> = ({ label, filled }) => (
  <span style={{
    fontSize: 9,
    padding: '1px 5px',
    borderRadius: 3,
    background: filled ? '#1D9E7520' : 'var(--color-background-secondary)',
    color: filled ? '#1D9E75' : 'var(--color-text-tertiary)',
    border: `0.5px solid ${filled ? '#1D9E7540' : 'var(--color-border-tertiary)'}`,
  }}>
    {label}提示词{filled ? '✓' : '?'}
  </span>
);


// ============================================================
// ImageNode.tsx - 图片合成节点
// ============================================================
import React from 'react';
import { BaseNode, StatusPill } from './BaseNode';
import { NodeData, ImageContent } from '../../types';

export const ImageNode: React.FC<{ node: NodeData }> = ({ node }) => {
  const content = node.content as ImageContent;
  const doneSteps = content.workflowSteps.filter(s => s.status === 'done').length;
  const totalSteps = content.workflowSteps.length;
  const progress = totalSteps > 0 ? doneSteps / totalSteps : 0;

  return (
    <BaseNode node={node} headerColor="#1D9E75" icon="🖼">
      {/* 图片预览或占位 */}
      <div style={{
        width: '100%',
        height: 72,
        borderRadius: 6,
        background: content.resultImageUrl ? undefined : 'var(--color-background-secondary)',
        border: '0.5px solid var(--color-border-tertiary)',
        marginBottom: 6,
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        position: 'relative',
      }}>
        {content.resultImageUrl ? (
          <img
            src={content.resultImageUrl}
            alt=""
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
            loading="lazy"
          />
        ) : (
          <span style={{ fontSize: 22, opacity: 0.4 }}>🖼</span>
        )}
        {/* 进度条 */}
        <div style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          height: 3,
          background: 'rgba(0,0,0,0.1)',
        }}>
          <div style={{
            width: `${progress * 100}%`,
            height: '100%',
            background: '#1D9E75',
            transition: 'width 0.4s ease',
          }} />
        </div>
      </div>

      {/* 步骤进度 */}
      <div style={{ fontSize: 10, color: 'var(--color-text-secondary)', marginBottom: 4 }}>
        合成步骤 {doneSteps}/{totalSteps}
      </div>

      {/* 步骤列表 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {content.workflowSteps.slice(0, 3).map(step => (
          <WorkflowStepRow key={step.id} name={step.name} status={step.status} />
        ))}
        {content.workflowSteps.length > 3 && (
          <div style={{ fontSize: 10, color: 'var(--color-text-tertiary)' }}>
            +{content.workflowSteps.length - 3} 步骤
          </div>
        )}
      </div>
    </BaseNode>
  );
};

const WorkflowStepRow: React.FC<{ name: string; status: string }> = ({ name, status }) => {
  const colors: Record<string, string> = {
    done: '#1D9E75', processing: '#BA7517', pending: '#888780', error: '#E24B4A'
  };
  const icons: Record<string, string> = {
    done: '✓', processing: '⟳', pending: '○', error: '✗'
  };
  const color = colors[status] || '#888780';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10 }}>
      <span style={{ color, width: 12, textAlign: 'center' }}>{icons[status] || '○'}</span>
      <span style={{ color: 'var(--color-text-secondary)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {name}
      </span>
    </div>
  );
};


// ============================================================
// VideoNode.tsx - 视频生成节点
// ============================================================
import React from 'react';
import { BaseNode } from './BaseNode';
import { NodeData, VideoContent } from '../../types';

const PROVIDER_LABELS: Record<string, string> = {
  jimeng: '即梦',
  kling: '可灵',
  runway: 'Runway',
  pika: 'Pika',
};

export const VideoNode: React.FC<{ node: NodeData }> = ({ node }) => {
  const content = node.content as VideoContent;

  return (
    <BaseNode node={node} headerColor="#639922" icon="🎬">
      {/* 视频预览 */}
      <div style={{
        width: '100%',
        height: 64,
        borderRadius: 6,
        background: content.thumbnailUrl ? undefined : '#EAF3DE',
        border: '0.5px solid var(--color-border-tertiary)',
        marginBottom: 6,
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        position: 'relative',
      }}>
        {content.thumbnailUrl ? (
          <>
            <img src={content.thumbnailUrl} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} loading="lazy" />
            <div style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'rgba(0,0,0,0.15)',
            }}>
              <div style={{
                width: 24,
                height: 24,
                borderRadius: '50%',
                background: 'rgba(255,255,255,0.9)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 10,
              }}>▶</div>
            </div>
          </>
        ) : (
          <span style={{ fontSize: 20, opacity: 0.4 }}>🎬</span>
        )}
      </div>

      {/* 信息行 */}
      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 4 }}>
        <Tag color="#639922">{PROVIDER_LABELS[content.provider] || content.provider}</Tag>
        <Tag color="#888780">{content.duration}s</Tag>
        <Tag color="#888780">{content.resolution}</Tag>
      </div>

      {/* 任务ID（如有） */}
      {content.jobId && (
        <div style={{ fontSize: 10, color: 'var(--color-text-tertiary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          任务: {content.jobId}
        </div>
      )}
    </BaseNode>
  );
};


// ============================================================
// NodeInspector.tsx - 右侧节点详情面板
// ============================================================
import React from 'react';
import { useCanvasStore } from '../../store/canvasStore';
import { StoryboardContent, ImageContent, VideoContent } from '../../types';
import { useWorkflow } from '../../hooks/useWorkflow';

export const NodeInspector: React.FC<{ nodeId: string }> = ({ nodeId }) => {
  const node = useCanvasStore(s => s.nodes.get(nodeId));
  const { runNode, editPrompt, viewChain } = useWorkflow();

  if (!node) return null;

  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ fontSize: 11, color: 'var(--color-text-secondary)', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
        选中节点
      </div>

      <div style={{
        background: 'var(--color-background-secondary)',
        borderRadius: 8,
        padding: 10,
        marginBottom: 8,
      }}>
        <div style={{ fontWeight: 500, fontSize: 13, marginBottom: 4 }}>{node.label}</div>
        {node.type === 'storyboard' && (
          <div style={{ fontSize: 11, color: 'var(--color-text-secondary)', lineHeight: 1.5 }}>
            {(node.content as StoryboardContent).rawText?.slice(0, 80)}...
          </div>
        )}
        <div style={{ marginTop: 6, display: 'flex', gap: 4 }}>
          <ChainBtn onClick={() => runNode(nodeId)}>执行</ChainBtn>
          <ChainBtn onClick={() => editPrompt(nodeId)}>编辑提示词</ChainBtn>
        </div>
        <ChainBtn style={{ marginTop: 6, width: '100%' }} onClick={() => viewChain(nodeId)}>
          查看完整分镜链 →
        </ChainBtn>
      </div>
    </div>
  );
};

const ChainBtn: React.FC<{
  children: React.ReactNode;
  onClick?: () => void;
  style?: React.CSSProperties;
}> = ({ children, onClick, style }) => (
  <button
    onClick={onClick}
    style={{
      fontSize: 11,
      padding: '5px 10px',
      border: '0.5px solid var(--color-border-tertiary)',
      borderRadius: 6,
      background: 'transparent',
      color: 'var(--color-text-primary)',
      cursor: 'pointer',
      flex: 1,
      ...style,
    }}
  >
    {children}
  </button>
);
