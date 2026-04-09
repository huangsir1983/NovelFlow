// ============================================================
// SceneNavigatorWheel.tsx
// 左侧半圆形场景导航盘
// 功能：
//   - 按剧情场景分组显示所有分镜
//   - 鼠标滚轮滚动场景列表
//   - 点击场景胶囊 → 画布飞行动画定位
//   - 每个场景显示进度环（完成/总数）
//   - 悬停展开子分镜列表
//   - 支持状态筛选（全部/未开始/进行中/完成）
// ============================================================

import React, { useState, useRef, useCallback, useEffect } from 'react';
import { useCanvasStore } from '../../store/canvasStore';
import { useProjectStore } from '../../store/projectStore';
import { NodeData, Scene } from '../../types';

// ── 类型 ─────────────────────────────────────────────────────
type FilterMode = 'all' | 'idle' | 'processing' | 'done' | 'error';

interface SceneGroup {
  scene: Scene;
  nodes: NodeData[];
  done: number;
  total: number;
  centerX: number; // 该场景在画布中的中心X
  centerY: number; // 该场景在画布中的中心Y
}

// ── 常量 ─────────────────────────────────────────────────────
const WHEEL_WIDTH = 52;          // 收起时的宽度
const WHEEL_EXPANDED = 240;      // 展开时的宽度
const ITEM_HEIGHT = 52;          // 每个场景胶囊高度
const VISIBLE_ITEMS = 9;         // 可见胶囊数量
const PANEL_HEIGHT = ITEM_HEIGHT * VISIBLE_ITEMS + 80; // 面板总高

const STATUS_COLORS: Record<string, string> = {
  done:       '#1D9E75',
  processing: '#BA7517',
  idle:       '#888780',
  ready:      '#378ADD',
  error:      '#E24B4A',
  outdated:   '#D85A30',
};

// ── 组件 ─────────────────────────────────────────────────────
export const SceneNavigatorWheel: React.FC = () => {
  const [expanded, setExpanded] = useState(true);
  const [scrollIndex, setScrollIndex] = useState(0);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [filterMode, setFilterMode] = useState<FilterMode>('all');
  const [activeSceneId, setActiveSceneId] = useState<string | null>(null);

  const { nodes, view, setTransform } = useCanvasStore();
  const { scenes, chapters } = useProjectStore();
  const wheelRef = useRef<HTMLDivElement>(null);

  // 构建场景组（scene → 其下所有节点）
  const sceneGroups: SceneGroup[] = React.useMemo(() => {
    const allNodes = Array.from(nodes.values());
    return Array.from(scenes.values()).map(scene => {
      const sceneNodes = allNodes.filter(n => n.sceneId === scene.id);

      // 计算该场景节点的画布中心
      const sbNodes = sceneNodes.filter(n => n.type === 'storyboard');
      const centerX = sbNodes.length > 0
        ? sbNodes.reduce((s, n) => s + n.position.x, 0) / sbNodes.length
        : 0;
      const centerY = sbNodes.length > 0
        ? sbNodes.reduce((s, n) => s + n.position.y, 0) / sbNodes.length
        : 0;

      return {
        scene,
        nodes: sceneNodes,
        done: sceneNodes.filter(n => n.status === 'done').length,
        total: sceneNodes.length,
        centerX,
        centerY,
      };
    }).sort((a, b) => a.scene.order - b.scene.order);
  }, [nodes, scenes]);

  // 按筛选条件过滤
  const filteredGroups = React.useMemo(() => {
    if (filterMode === 'all') return sceneGroups;
    return sceneGroups.filter(g => {
      if (filterMode === 'done') return g.done === g.total && g.total > 0;
      if (filterMode === 'idle') return g.done === 0;
      if (filterMode === 'processing') return g.done > 0 && g.done < g.total;
      if (filterMode === 'error') return g.nodes.some(n => n.status === 'error');
      return true;
    });
  }, [sceneGroups, filterMode]);

  // 可见场景
  const visibleGroups = filteredGroups.slice(scrollIndex, scrollIndex + VISIBLE_ITEMS);

  // 滚轮滚动
  const onWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 1 : -1;
    setScrollIndex(prev =>
      Math.max(0, Math.min(filteredGroups.length - VISIBLE_ITEMS, prev + delta))
    );
  }, [filteredGroups.length]);

  // 点击场景 → 画布飞行定位
  const flyToScene = useCallback((group: SceneGroup) => {
    setActiveSceneId(group.scene.id);
    const { visibleRect } = view;
    const targetScale = 0.85;
    const targetOffsetX = visibleRect.width / 2 - group.centerX * targetScale;
    const targetOffsetY = visibleRect.height / 2 - group.centerY * targetScale;

    // 平滑动画飞行
    const startOX = view.transform.offsetX;
    const startOY = view.transform.offsetY;
    const startScale = view.transform.scale;
    const duration = 400;
    const start = performance.now();

    const animate = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const ease = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
      setTransform({
        scale: startScale + (targetScale - startScale) * ease,
        offsetX: startOX + (targetOffsetX - startOX) * ease,
        offsetY: startOY + (targetOffsetY - startOY) * ease,
      });
      if (t < 1) requestAnimationFrame(animate);
    };
    requestAnimationFrame(animate);
  }, [view, setTransform]);

  // 总体进度
  const totalDone = sceneGroups.reduce((s, g) => s + g.done, 0);
  const totalNodes = sceneGroups.reduce((s, g) => s + g.total, 0);
  const overallPct = totalNodes > 0 ? totalDone / totalNodes : 0;

  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        top: '50%',
        transform: 'translateY(-50%)',
        zIndex: 80,
        display: 'flex',
        alignItems: 'stretch',
      }}
    >
      {/* 主面板 */}
      <div
        ref={wheelRef}
        onWheel={onWheel}
        style={{
          width: expanded ? WHEEL_EXPANDED : WHEEL_WIDTH,
          height: PANEL_HEIGHT,
          background: 'var(--color-background-primary)',
          borderRadius: '0 16px 16px 0',
          border: '0.5px solid var(--color-border-tertiary)',
          borderLeft: 'none',
          overflow: 'hidden',
          transition: 'width 0.22s ease',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '2px 0 8px rgba(0,0,0,0.06)',
        }}
      >
        {/* 顶部：总进度 + 切换按钮 */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          padding: '10px 10px 6px',
          borderBottom: '0.5px solid var(--color-border-tertiary)',
          gap: 8,
          flexShrink: 0,
        }}>
          {/* 总进度环 */}
          <ProgressRing pct={overallPct} size={30} color="#1D9E75" />
          {expanded && (
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--color-text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {totalDone}/{totalNodes} 完成
              </div>
              <div style={{ fontSize: 10, color: 'var(--color-text-secondary)' }}>
                {sceneGroups.length} 个场景
              </div>
            </div>
          )}
          {/* 收起/展开 */}
          <button
            onClick={() => setExpanded(e => !e)}
            style={{
              width: 22,
              height: 22,
              borderRadius: '50%',
              border: '0.5px solid var(--color-border-tertiary)',
              background: 'transparent',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 10,
              color: 'var(--color-text-secondary)',
              flexShrink: 0,
            }}
          >
            {expanded ? '‹' : '›'}
          </button>
        </div>

        {/* 筛选栏（仅展开时显示） */}
        {expanded && (
          <div style={{ display: 'flex', gap: 4, padding: '6px 10px', flexShrink: 0 }}>
            {(['all', 'idle', 'processing', 'done', 'error'] as FilterMode[]).map(f => (
              <button
                key={f}
                onClick={() => { setFilterMode(f); setScrollIndex(0); }}
                style={{
                  fontSize: 9,
                  padding: '2px 5px',
                  borderRadius: 4,
                  border: '0.5px solid var(--color-border-tertiary)',
                  background: filterMode === f ? 'var(--color-background-secondary)' : 'transparent',
                  color: filterMode === f ? 'var(--color-text-primary)' : 'var(--color-text-tertiary)',
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                }}
              >
                {f === 'all' ? '全部' : f === 'idle' ? '未开始' : f === 'processing' ? '进行中' : f === 'done' ? '已完成' : '有错误'}
              </button>
            ))}
          </div>
        )}

        {/* 场景列表 */}
        <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
          {/* 顶部渐隐（可滚动提示） */}
          {scrollIndex > 0 && (
            <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 20, background: 'linear-gradient(to bottom, var(--color-background-primary), transparent)', zIndex: 2, pointerEvents: 'none' }} />
          )}

          {visibleGroups.map((group, idx) => (
            <SceneCapsule
              key={group.scene.id}
              group={group}
              expanded={expanded}
              isActive={activeSceneId === group.scene.id}
              isHovered={hoveredId === group.scene.id}
              onHover={setHoveredId}
              onClick={flyToScene}
            />
          ))}

          {visibleGroups.length === 0 && (
            <div style={{ padding: 16, fontSize: 11, color: 'var(--color-text-tertiary)', textAlign: 'center' }}>
              无匹配场景
            </div>
          )}

          {/* 底部渐隐 */}
          {scrollIndex + VISIBLE_ITEMS < filteredGroups.length && (
            <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 20, background: 'linear-gradient(to top, var(--color-background-primary), transparent)', zIndex: 2, pointerEvents: 'none' }} />
          )}
        </div>

        {/* 底部滚动指示器 */}
        {expanded && filteredGroups.length > VISIBLE_ITEMS && (
          <div style={{ padding: '4px 10px 6px', display: 'flex', justifyContent: 'center', gap: 3, flexShrink: 0 }}>
            {Array.from({ length: Math.ceil(filteredGroups.length / VISIBLE_ITEMS) }).map((_, i) => (
              <div
                key={i}
                onClick={() => setScrollIndex(i * VISIBLE_ITEMS)}
                style={{
                  width: i === Math.floor(scrollIndex / VISIBLE_ITEMS) ? 14 : 4,
                  height: 4,
                  borderRadius: 2,
                  background: i === Math.floor(scrollIndex / VISIBLE_ITEMS) ? '#378ADD' : 'var(--color-border-secondary)',
                  cursor: 'pointer',
                  transition: 'width 0.2s',
                }}
              />
            ))}
          </div>
        )}
      </div>

      {/* 右侧竖条：悬停子分镜预览 */}
      {hoveredId && (() => {
        const group = sceneGroups.find(g => g.scene.id === hoveredId);
        if (!group) return null;
        return (
          <SubStoryboardPreview group={group} />
        );
      })()}
    </div>
  );
};

// ── 场景胶囊 ──────────────────────────────────────────────────
const SceneCapsule: React.FC<{
  group: SceneGroup;
  expanded: boolean;
  isActive: boolean;
  isHovered: boolean;
  onHover: (id: string | null) => void;
  onClick: (group: SceneGroup) => void;
}> = ({ group, expanded, isActive, isHovered, onHover, onClick }) => {
  const pct = group.total > 0 ? group.done / group.total : 0;
  const statusColor = pct === 1 ? '#1D9E75' : pct > 0 ? '#BA7517' : '#888780';

  return (
    <div
      onMouseEnter={() => onHover(group.scene.id)}
      onMouseLeave={() => onHover(null)}
      onClick={() => onClick(group)}
      style={{
        height: ITEM_HEIGHT,
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '0 10px',
        cursor: 'pointer',
        background: isActive
          ? 'var(--color-background-info)'
          : isHovered
            ? 'var(--color-background-secondary)'
            : 'transparent',
        borderLeft: `3px solid ${isActive ? '#378ADD' : 'transparent'}`,
        transition: 'background 0.12s',
      }}
    >
      {/* 进度环 */}
      <ProgressRing pct={pct} size={28} color={statusColor} label={`${group.done}/${group.total}`} />

      {expanded && (
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: 12,
            fontWeight: 500,
            color: 'var(--color-text-primary)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}>
            {group.scene.title}
          </div>
          <div style={{ display: 'flex', gap: 4, marginTop: 2, alignItems: 'center' }}>
            <div style={{ fontSize: 10, color: 'var(--color-text-tertiary)' }}>
              {group.nodes.filter(n => n.type === 'storyboard').length} 分镜
            </div>
            {/* 微型状态条 */}
            <MiniStatusBar nodes={group.nodes} />
          </div>
        </div>
      )}
    </div>
  );
};

// ── 进度环 ────────────────────────────────────────────────────
const ProgressRing: React.FC<{
  pct: number;
  size: number;
  color: string;
  label?: string;
}> = ({ pct, size, color, label }) => {
  const r = (size - 4) / 2;
  const circ = 2 * Math.PI * r;
  const dash = circ * pct;
  const cx = size / 2;

  return (
    <svg width={size} height={size} style={{ flexShrink: 0 }}>
      <circle cx={cx} cy={cx} r={r} fill="none" stroke="var(--color-border-tertiary)" strokeWidth={2} />
      <circle
        cx={cx} cy={cx} r={r}
        fill="none"
        stroke={color}
        strokeWidth={2}
        strokeDasharray={`${dash} ${circ - dash}`}
        strokeDashoffset={circ / 4}
        strokeLinecap="round"
      />
      {label && (
        <text x={cx} y={cx} textAnchor="middle" dominantBaseline="central" fontSize={size < 30 ? 7 : 9} fill="var(--color-text-secondary)">
          {label}
        </text>
      )}
    </svg>
  );
};

// ── 微型状态条 ────────────────────────────────────────────────
const MiniStatusBar: React.FC<{ nodes: NodeData[] }> = ({ nodes }) => {
  const total = nodes.length;
  if (total === 0) return null;
  const counts = {
    done: nodes.filter(n => n.status === 'done').length,
    processing: nodes.filter(n => n.status === 'processing').length,
    error: nodes.filter(n => n.status === 'error').length,
  };
  return (
    <div style={{ display: 'flex', height: 4, borderRadius: 2, overflow: 'hidden', width: 60, background: 'var(--color-border-tertiary)' }}>
      <div style={{ width: `${(counts.done / total) * 100}%`, background: '#1D9E75' }} />
      <div style={{ width: `${(counts.processing / total) * 100}%`, background: '#BA7517' }} />
      <div style={{ width: `${(counts.error / total) * 100}%`, background: '#E24B4A' }} />
    </div>
  );
};

// ── 子分镜悬停预览面板 ────────────────────────────────────────
const SubStoryboardPreview: React.FC<{ group: SceneGroup }> = ({ group }) => {
  const sbNodes = group.nodes.filter(n => n.type === 'storyboard').slice(0, 12);

  return (
    <div style={{
      marginLeft: 6,
      background: 'var(--color-background-primary)',
      border: '0.5px solid var(--color-border-tertiary)',
      borderRadius: 10,
      padding: '10px 12px',
      minWidth: 180,
      maxWidth: 220,
      boxShadow: '2px 2px 8px rgba(0,0,0,0.06)',
      alignSelf: 'center',
    }}>
      <div style={{ fontSize: 11, fontWeight: 500, marginBottom: 8, color: 'var(--color-text-primary)' }}>
        {group.scene.title}
      </div>
      {sbNodes.map((node, i) => (
        <div key={node.id} style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '3px 0',
          borderBottom: i < sbNodes.length - 1 ? '0.5px solid var(--color-border-tertiary)' : 'none',
        }}>
          <div style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: STATUS_COLORS[node.status] || '#888',
            flexShrink: 0,
          }} />
          <div style={{ fontSize: 10, color: 'var(--color-text-secondary)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {node.label}
          </div>
        </div>
      ))}
      {group.nodes.filter(n => n.type === 'storyboard').length > 12 && (
        <div style={{ fontSize: 10, color: 'var(--color-text-tertiary)', marginTop: 4 }}>
          +{group.nodes.filter(n => n.type === 'storyboard').length - 12} 更多分镜
        </div>
      )}
    </div>
  );
};
