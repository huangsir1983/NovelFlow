'use client';

import React, { useState, useCallback, useMemo, useRef } from 'react';
import { useReactFlow } from '@xyflow/react';
import { useCanvasStore } from '../../../stores/canvasStore';
import { useProjectStore } from '../../../stores';
import type { CanvasNodeStatus } from '../../../types';

/* ═══════════════════════════════════════════════════════════════
   SceneNavigatorWheel — 半圆转盘场景导航
   ───────────────────────────────────────────────────────────────
   半圆形转盘，扇形分格，每格一个场景（序号+名称）。
   中心小半圆是开关按钮：点击展开/收起扇形区域。
   收起时仅显示中心半圆（保留当前场景序号/总数）。
   滚轮逐场景转动，点击场景片聚焦到该场景第一个分镜卡片。
   ═══════════════════════════════════════════════════════════════ */

/* ── Status colors ── */
const STATUS_COLORS: Record<CanvasNodeStatus, string> = {
  success: '#22c55e',
  running: '#3b82f6',
  queued: '#f59e0b',
  error: '#ef4444',
  idle: '#4b5563',
};

/* ── Geometry ── */
const INNER_R = 44;
const OUTER_R = 190;
const SLOTS = 9;
const SECTOR_ANGLE = 180 / SLOTS;
const HALF_ARC = 90;
const TOOLBAR_OFFSET = 52;

/* ── Helpers ── */
const deg2rad = (d: number) => (d * Math.PI) / 180;

function polarToXY(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = deg2rad(angleDeg);
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function sectorPath(
  cx: number, cy: number,
  r1: number, r2: number,
  startDeg: number, endDeg: number,
): string {
  const s1 = polarToXY(cx, cy, r1, startDeg);
  const e1 = polarToXY(cx, cy, r1, endDeg);
  const s2 = polarToXY(cx, cy, r2, startDeg);
  const e2 = polarToXY(cx, cy, r2, endDeg);
  const large = Math.abs(endDeg - startDeg) > 180 ? 1 : 0;
  return [
    `M ${s2.x} ${s2.y}`,
    `A ${r2} ${r2} 0 ${large} 1 ${e2.x} ${e2.y}`,
    `L ${e1.x} ${e1.y}`,
    `A ${r1} ${r1} 0 ${large} 0 ${s1.x} ${s1.y}`,
    'Z',
  ].join(' ');
}

/** SVG path for a right-half circle (center button shape) */
function halfCirclePath(cx: number, cy: number, r: number): string {
  return [
    `M ${cx} ${cy - r}`,
    `A ${r} ${r} 0 0 1 ${cx} ${cy + r}`,
    'Z',
  ].join(' ');
}

/* ── Scene info ── */
interface SceneInfo {
  id: string;
  heading: string;
  order: number;
  shotCount: number;
  doneCount: number;
  totalCount: number;
  errorCount: number;
  processingCount: number;
  dominantStatus: CanvasNodeStatus;
}

/* ══════════════════════════════════════════════════════════════ */

export function SceneNavigatorWheel() {
  const reactFlow = useReactFlow();
  const nodes = useCanvasStore((s) => s.nodes);
  const focusedSceneId = useCanvasStore((s) => s.focusedSceneId);
  const setFocusedSceneId = useCanvasStore((s) => s.setFocusedSceneId);
  const scenes = useProjectStore((s) => s.scenes);

  const [expanded, setExpanded] = useState(false);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [centerHovered, setCenterHovered] = useState(false);
  const wheelCooldown = useRef(false);

  // ── Build scene list ──
  const sceneInfos = useMemo<SceneInfo[]>(() => {
    return [...scenes]
      .sort((a, b) => a.order - b.order)
      .map((scene) => {
        const sceneNodes = nodes.filter(
          (n) => (n.data as { sceneId?: string }).sceneId === scene.id,
        );
        const shotNodes = sceneNodes.filter(
          (n) => (n.data as { nodeType?: string }).nodeType === 'shot',
        );
        let doneCount = 0, errorCount = 0, processingCount = 0;
        for (const n of sceneNodes) {
          const s = (n.data as { status?: string }).status;
          if (s === 'success') doneCount++;
          else if (s === 'error') errorCount++;
          else if (s === 'running' || s === 'queued') processingCount++;
        }
        let dominantStatus: CanvasNodeStatus = 'idle';
        if (errorCount > 0) dominantStatus = 'error';
        else if (processingCount > 0) dominantStatus = 'running';
        else if (doneCount === sceneNodes.length && sceneNodes.length > 0) dominantStatus = 'success';

        return {
          id: scene.id,
          heading: scene.heading || `Scene ${scene.order}`,
          order: scene.order,
          shotCount: shotNodes.length,
          doneCount,
          totalCount: sceneNodes.length,
          errorCount,
          processingCount,
          dominantStatus,
        };
      });
  }, [scenes, nodes]);

  // ── Focused index ──
  const focusedIndex = useMemo(() => {
    const idx = sceneInfos.findIndex((s) => s.id === focusedSceneId);
    return idx >= 0 ? idx : 0;
  }, [sceneInfos, focusedSceneId]);

  // ── Visible slots centered on focusedIndex ──
  const slotData = useMemo(() => {
    const total = sceneInfos.length;
    if (total === 0) return [];
    const centerSlot = Math.floor(SLOTS / 2);
    const result: Array<{ scene: SceneInfo | null; slotIndex: number }> = [];
    for (let s = 0; s < SLOTS; s++) {
      const offset = s - centerSlot;
      const sceneIdx = focusedIndex + offset;
      result.push({
        scene: sceneIdx >= 0 && sceneIdx < total ? sceneInfos[sceneIdx] : null,
        slotIndex: s,
      });
    }
    return result;
  }, [sceneInfos, focusedIndex]);

  // ── Global progress (shot count, not total node count) ──
  const globalShotDone = useMemo(() => sceneInfos.reduce((s, g) => s + g.doneCount, 0), [sceneInfos]);
  const globalShotTotal = useMemo(() => sceneInfos.reduce((s, g) => s + g.shotCount, 0), [sceneInfos]);

  // ── Navigate: focus on the first SHOT node of the scene ──
  const flyToScene = useCallback(
    (sceneId: string) => {
      setFocusedSceneId(sceneId);

      // Read positions directly from store — no dependency on React Flow's internal node list
      const allNodes = useCanvasStore.getState().nodes;
      const shotNodes = allNodes
        .filter(
          (n) =>
            (n.data as { sceneId?: string }).sceneId === sceneId &&
            (n.data as { nodeType?: string }).nodeType === 'shot',
        )
        .sort((a, b) => {
          const aNum = (a.data as { shotNumber?: number }).shotNumber ?? 0;
          const bNum = (b.data as { shotNumber?: number }).shotNumber ?? 0;
          return aNum - bNum;
        });

      // Compute bounding box of the first shot row
      let targetNodes: typeof allNodes;
      if (shotNodes.length > 0) {
        const firstShotY = shotNodes[0].position.y;
        targetNodes = allNodes.filter((n) => {
          const d = n.data as { sceneId?: string };
          return d.sceneId === sceneId && Math.abs(n.position.y - firstShotY) < 50;
        });
      } else {
        const sceneNode = allNodes.find(
          (n) => (n.data as { sceneId?: string }).sceneId === sceneId &&
                 (n.data as { nodeType?: string }).nodeType === 'scene',
        );
        targetNodes = sceneNode ? [sceneNode] : [];
      }

      if (targetNodes.length === 0) return;

      // Calculate bounding box center from node positions (bypass fitView entirely)
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
      for (const n of targetNodes) {
        const w = (n.measured?.width ?? n.width ?? 280) as number;
        const h = (n.measured?.height ?? n.height ?? 200) as number;
        minX = Math.min(minX, n.position.x);
        minY = Math.min(minY, n.position.y);
        maxX = Math.max(maxX, n.position.x + w);
        maxY = Math.max(maxY, n.position.y + h);
      }

      const centerX = (minX + maxX) / 2;
      const centerY = (minY + maxY) / 2;
      const boxW = maxX - minX;
      const boxH = maxY - minY;

      // Fit zoom to show the row with padding
      const screenW = typeof window !== 'undefined' ? window.innerWidth : 1920;
      const screenH = typeof window !== 'undefined' ? window.innerHeight : 1080;
      const padding = 0.3;
      const zoomX = screenW / (boxW * (1 + padding));
      const zoomY = screenH / (boxH * (1 + padding));
      const zoom = Math.min(Math.min(zoomX, zoomY), 1.0); // cap at 1.0

      // setViewport is synchronous — no need to wait for React Flow to have the nodes
      reactFlow.setViewport(
        {
          x: screenW / 2 - centerX * zoom,
          y: screenH / 2 - centerY * zoom,
          zoom,
        },
        { duration: 400 },
      );
    },
    [reactFlow, setFocusedSceneId],
  );

  // ── Scroll wheel: advance one scene at a time ──
  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (sceneInfos.length === 0 || wheelCooldown.current) return;

      wheelCooldown.current = true;
      setTimeout(() => { wheelCooldown.current = false; }, 80);

      let next = focusedIndex;
      if (e.deltaY > 0) next = Math.min(focusedIndex + 1, sceneInfos.length - 1);
      else if (e.deltaY < 0) next = Math.max(focusedIndex - 1, 0);

      if (next !== focusedIndex) {
        flyToScene(sceneInfos[next].id);
      }
    },
    [focusedIndex, sceneInfos, flyToScene],
  );

  if (sceneInfos.length === 0) return null;

  // ── SVG coordinate system ──
  const cx = 0;
  const cy = OUTER_R;
  const svgW = OUTER_R + 2;
  const svgH = OUTER_R * 2 + 4;
  const btnR = INNER_R - 5; // center button radius

  const focusedScene = sceneInfos[focusedIndex];

  // ═══════════════════════════════════════════════════════════
  // Collapsed: only the center half-circle button
  // ═══════════════════════════════════════════════════════════
  if (!expanded) {
    const btnW = btnR + 2;
    const btnH = btnR * 2 + 4;
    return (
      <div
        onWheel={handleWheel}
        style={{
          position: 'absolute',
          left: TOOLBAR_OFFSET,
          top: '50%',
          transform: 'translateY(-50%)',
          zIndex: 45,
          width: btnW,
          height: btnH,
          pointerEvents: 'auto',
          cursor: 'pointer',
        }}
      >
        <svg width={btnW} height={btnH} viewBox={`0 0 ${btnW} ${btnH}`}>
          {/* Half-circle button */}
          <path
            d={halfCirclePath(0, btnR + 2, btnR)}
            fill={centerHovered ? 'rgba(30,38,60,0.98)' : 'rgba(17,24,39,0.95)'}
            stroke={centerHovered ? 'rgba(99,102,241,0.5)' : 'rgba(75,85,99,0.4)'}
            strokeWidth={1.5}
            onClick={() => setExpanded(true)}
            onMouseEnter={() => setCenterHovered(true)}
            onMouseLeave={() => setCenterHovered(false)}
            style={{ cursor: 'pointer', transition: 'fill 0.15s, stroke 0.15s' }}
          />
          {/* Scene number */}
          <text
            x={btnR * 0.4}
            y={btnR + 2 - 8}
            textAnchor="middle"
            dominantBaseline="central"
            style={{ fontSize: 15, fontWeight: 700, fill: '#e5e7eb', pointerEvents: 'none' }}
          >
            {focusedScene?.order ?? '—'}
          </text>
          {/* Progress: done/total */}
          <text
            x={btnR * 0.4}
            y={btnR + 2 + 8}
            textAnchor="middle"
            dominantBaseline="central"
            style={{ fontSize: 9, fill: '#6b7280', pointerEvents: 'none' }}
          >
            {globalShotDone}/{globalShotTotal}
          </text>
        </svg>
      </div>
    );
  }

  // ═══════════════════════════════════════════════════════════
  // Expanded: full half-circle fan
  // ═══════════════════════════════════════════════════════════
  return (
    <div
      onWheel={handleWheel}
      style={{
        position: 'absolute',
        left: TOOLBAR_OFFSET,
        top: '50%',
        transform: 'translateY(-50%)',
        zIndex: 45,
        width: svgW,
        height: svgH,
        pointerEvents: 'auto',
        overflow: 'visible',
      }}
    >
      <svg
        width={svgW}
        height={svgH}
        viewBox={`0 0 ${svgW} ${svgH}`}
        style={{ overflow: 'visible' }}
      >
        {/* ── Background half-circle ── */}
        <path
          d={sectorPath(cx, cy, INNER_R - 4, OUTER_R + 2, -HALF_ARC, HALF_ARC)}
          fill="rgba(17,24,39,0.88)"
          stroke="rgba(75,85,99,0.3)"
          strokeWidth={1}
        />

        {/* ── Sector slots ── */}
        {slotData.map(({ scene, slotIndex }) => {
          const startAngle = -HALF_ARC + slotIndex * SECTOR_ANGLE;
          const endAngle = startAngle + SECTOR_ANGLE;
          const midAngle = (startAngle + endAngle) / 2;

          if (!scene) {
            return (
              <path
                key={`empty-${slotIndex}`}
                d={sectorPath(cx, cy, INNER_R, OUTER_R, startAngle, endAngle)}
                fill="rgba(20,26,40,0.5)"
                stroke="rgba(75,85,99,0.15)"
                strokeWidth={0.5}
              />
            );
          }

          const isFocused = scene.id === focusedSceneId;
          const isHovered = scene.id === hoveredId;
          const statusColor = STATUS_COLORS[scene.dominantStatus];

          let fill = 'rgba(30,41,59,0.6)';
          if (isFocused) fill = 'rgba(99,102,241,0.22)';
          else if (isHovered) fill = 'rgba(55,65,81,0.7)';

          let stroke = 'rgba(75,85,99,0.25)';
          let strokeW = 0.5;
          if (isFocused) { stroke = 'rgba(99,102,241,0.6)'; strokeW = 1.5; }
          else if (isHovered) { stroke = 'rgba(99,102,241,0.3)'; strokeW = 1; }

          const textR = (INNER_R + OUTER_R) / 2;
          const textPos = polarToXY(cx, cy, textR, midAngle);
          const statusPos = polarToXY(cx, cy, OUTER_R - 12, midAngle);
          const numPos = polarToXY(cx, cy, INNER_R + 16, midAngle);

          return (
            <g
              key={scene.id}
              onClick={() => flyToScene(scene.id)}
              onMouseEnter={() => setHoveredId(scene.id)}
              onMouseLeave={() => setHoveredId(null)}
              style={{ cursor: 'pointer' }}
            >
              <path
                d={sectorPath(cx, cy, INNER_R, OUTER_R, startAngle, endAngle)}
                fill={fill}
                stroke={stroke}
                strokeWidth={strokeW}
              />
              {/* Status color bar on outer edge */}
              <path
                d={sectorPath(cx, cy, OUTER_R - 3, OUTER_R, startAngle + 0.5, endAngle - 0.5)}
                fill={statusColor}
                opacity={isFocused ? 0.8 : 0.4}
              />
              {/* Scene number */}
              <text
                x={numPos.x}
                y={numPos.y}
                textAnchor="middle"
                dominantBaseline="central"
                transform={`rotate(${midAngle}, ${numPos.x}, ${numPos.y})`}
                style={{
                  fontSize: isFocused ? 11 : 10,
                  fontWeight: 700,
                  fill: isFocused ? '#c7d2fe' : '#9ca3af',
                  pointerEvents: 'none',
                  userSelect: 'none',
                }}
              >
                S{scene.order}
              </text>
              {/* Scene heading */}
              <text
                x={textPos.x}
                y={textPos.y}
                textAnchor="middle"
                dominantBaseline="central"
                transform={`rotate(${midAngle}, ${textPos.x}, ${textPos.y})`}
                style={{
                  fontSize: isFocused ? 11 : 10,
                  fontWeight: isFocused ? 600 : 400,
                  fill: isFocused ? '#f3f4f6' : isHovered ? '#e5e7eb' : '#9ca3af',
                  pointerEvents: 'none',
                  userSelect: 'none',
                }}
              >
                {scene.heading.length > 6 ? scene.heading.slice(0, 6) + '…' : scene.heading}
              </text>
              {/* Shot count */}
              <text
                x={statusPos.x}
                y={statusPos.y}
                textAnchor="middle"
                dominantBaseline="central"
                transform={`rotate(${midAngle}, ${statusPos.x}, ${statusPos.y})`}
                style={{
                  fontSize: 8,
                  fill: '#6b7280',
                  pointerEvents: 'none',
                  userSelect: 'none',
                }}
              >
                {scene.shotCount}镜
              </text>
            </g>
          );
        })}

        {/* ── Center half-circle button (toggle) ── */}
        <path
          d={halfCirclePath(cx, cy, btnR)}
          fill={centerHovered ? 'rgba(30,38,60,0.98)' : 'rgba(17,24,39,0.95)'}
          stroke={centerHovered ? 'rgba(99,102,241,0.5)' : 'rgba(75,85,99,0.4)'}
          strokeWidth={1.5}
          onClick={() => setExpanded(false)}
          onMouseEnter={() => setCenterHovered(true)}
          onMouseLeave={() => setCenterHovered(false)}
          style={{ cursor: 'pointer', transition: 'fill 0.15s, stroke 0.15s' }}
        />
        {/* Center text: scene number */}
        <text
          x={cx + btnR * 0.38}
          y={cy - 8}
          textAnchor="middle"
          dominantBaseline="central"
          style={{ fontSize: 15, fontWeight: 700, fill: '#e5e7eb', pointerEvents: 'none' }}
        >
          {focusedScene?.order ?? '—'}
        </text>
        {/* Center text: done/total */}
        <text
          x={cx + btnR * 0.38}
          y={cy + 8}
          textAnchor="middle"
          dominantBaseline="central"
          style={{ fontSize: 9, fill: '#6b7280', pointerEvents: 'none' }}
        >
          {globalShotDone}/{globalShotTotal}
        </text>
      </svg>

      {/* ── Hover tooltip ── */}
      {hoveredId && (() => {
        const hScene = sceneInfos.find((s) => s.id === hoveredId);
        if (!hScene) return null;
        return (
          <div
            style={{
              position: 'absolute',
              left: OUTER_R + 14,
              top: '50%',
              transform: 'translateY(-50%)',
              backgroundColor: 'rgba(17,24,39,0.96)',
              border: '1px solid rgba(75,85,99,0.5)',
              borderRadius: 10,
              padding: '10px 14px',
              minWidth: 180,
              maxWidth: 260,
              zIndex: 200,
              boxShadow: '4px 4px 20px rgba(0,0,0,0.5)',
              backdropFilter: 'blur(8px)',
              pointerEvents: 'none',
            }}
          >
            <div style={{ fontSize: 13, fontWeight: 600, color: '#e5e7eb', marginBottom: 4 }}>
              S{hScene.order}. {hScene.heading}
            </div>
            <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 6 }}>
              {hScene.shotCount} 分镜 · {hScene.doneCount}/{hScene.totalCount} 完成
              {hScene.errorCount > 0 && (
                <span style={{ color: '#ef4444', marginLeft: 4 }}>{hScene.errorCount} 错误</span>
              )}
            </div>
            <div style={{
              height: 4, borderRadius: 2,
              backgroundColor: 'rgba(75,85,99,0.3)', overflow: 'hidden',
            }}>
              <div style={{
                height: '100%',
                width: `${hScene.totalCount > 0 ? (hScene.doneCount / hScene.totalCount) * 100 : 0}%`,
                backgroundColor: STATUS_COLORS[hScene.dominantStatus],
                borderRadius: 2,
              }} />
            </div>
          </div>
        );
      })()}
    </div>
  );
}

export default SceneNavigatorWheel;
