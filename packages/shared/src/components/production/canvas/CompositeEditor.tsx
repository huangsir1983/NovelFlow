'use client';

import { memo, useRef, useEffect, useState, useCallback } from 'react';
import { createPortal } from 'react-dom';
import type { CompositeLayerItem } from '../../../types/canvas';

interface CompositeEditorProps {
  layers: CompositeLayerItem[];
  canvasWidth: number;
  canvasHeight: number;
  onSave: (imageDataUrl: string, updatedLayers: CompositeLayerItem[]) => void;
  onClose: () => void;
}

type InteractionMode = 'idle' | 'dragging' | 'resizing' | 'rotating' | 'panning';
type HandleId = 'nw' | 'n' | 'ne' | 'e' | 'se' | 's' | 'sw' | 'w';

interface DragState {
  mode: InteractionMode;
  handle?: HandleId;
  layerId: string;
  startClientX: number;
  startClientY: number;
  startLayerX: number;
  startLayerY: number;
  startLayerW: number;
  startLayerH: number;
  startLayerRot: number;
  startAngle?: number; // for rotation
}

const HANDLE_SIZE = 8;
const HANDLE_HIT = 12; // hit area
const ROTATE_DISTANCE = 25; // px from corner to rotation anchor
const CHECKERBOARD = 'repeating-conic-gradient(#222 0% 25%, #2a2a2a 0% 50%) 0 0 / 20px 20px';

const HANDLE_CURSORS: Record<HandleId, string> = {
  nw: 'nwse-resize', n: 'ns-resize', ne: 'nesw-resize', e: 'ew-resize',
  se: 'nwse-resize', s: 'ns-resize', sw: 'nesw-resize', w: 'ew-resize',
};

/** Rotate a point around an origin */
function rotatePoint(px: number, py: number, cx: number, cy: number, angleDeg: number) {
  const rad = (angleDeg * Math.PI) / 180;
  const cos = Math.cos(rad);
  const sin = Math.sin(rad);
  const dx = px - cx;
  const dy = py - cy;
  return { x: cx + dx * cos - dy * sin, y: cy + dx * sin + dy * cos };
}

/** Get the 4 corners of a rotated rect in canvas coords */
function getRotatedCorners(layer: CompositeLayerItem) {
  const cx = layer.x + layer.width / 2;
  const cy = layer.y + layer.height / 2;
  const hw = layer.width / 2;
  const hh = layer.height / 2;
  return {
    nw: rotatePoint(cx - hw, cy - hh, cx, cy, layer.rotation),
    ne: rotatePoint(cx + hw, cy - hh, cx, cy, layer.rotation),
    se: rotatePoint(cx + hw, cy + hh, cx, cy, layer.rotation),
    sw: rotatePoint(cx - hw, cy + hh, cx, cy, layer.rotation),
  };
}

/** Get all 8 handle positions */
function getHandlePositions(layer: CompositeLayerItem) {
  const cx = layer.x + layer.width / 2;
  const cy = layer.y + layer.height / 2;
  const hw = layer.width / 2;
  const hh = layer.height / 2;
  const r = layer.rotation;
  return {
    nw: rotatePoint(cx - hw, cy - hh, cx, cy, r),
    n:  rotatePoint(cx,      cy - hh, cx, cy, r),
    ne: rotatePoint(cx + hw, cy - hh, cx, cy, r),
    e:  rotatePoint(cx + hw, cy,      cx, cy, r),
    se: rotatePoint(cx + hw, cy + hh, cx, cy, r),
    s:  rotatePoint(cx,      cy + hh, cx, cy, r),
    sw: rotatePoint(cx - hw, cy + hh, cx, cy, r),
    w:  rotatePoint(cx - hw, cy,      cx, cy, r),
  };
}

/** Check if point is near a handle */
function hitTestHandle(
  px: number, py: number, layer: CompositeLayerItem, zoom: number,
): { type: 'handle'; handle: HandleId } | { type: 'rotate' } | { type: 'body' } | null {
  const handles = getHandlePositions(layer);
  const hitR = HANDLE_HIT / zoom;
  const rotR = (HANDLE_HIT + ROTATE_DISTANCE) / zoom;

  // Check rotation zones (corners, slightly outside)
  const corners: HandleId[] = ['nw', 'ne', 'se', 'sw'];
  for (const c of corners) {
    const h = handles[c];
    const dist = Math.hypot(px - h.x, py - h.y);
    if (dist > hitR && dist < rotR) return { type: 'rotate' };
  }

  // Check resize handles
  for (const [id, pos] of Object.entries(handles)) {
    if (Math.hypot(px - pos.x, py - pos.y) < hitR) {
      return { type: 'handle', handle: id as HandleId };
    }
  }

  // Check body (rotated AABB hit test)
  const cx = layer.x + layer.width / 2;
  const cy = layer.y + layer.height / 2;
  const local = rotatePoint(px, py, cx, cy, -layer.rotation);
  if (
    local.x >= layer.x && local.x <= layer.x + layer.width &&
    local.y >= layer.y && local.y <= layer.y + layer.height
  ) {
    return { type: 'body' };
  }

  return null;
}

function CompositeEditorComponent({ layers: initialLayers, canvasWidth, canvasHeight, onSave, onClose }: CompositeEditorProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [layers, setLayers] = useState<CompositeLayerItem[]>(initialLayers);
  const [selectedLayerId, setSelectedLayerId] = useState<string | null>(null);
  const [interaction, setInteraction] = useState<DragState | null>(null);
  const [zoom, setZoom] = useState(0);
  const [panOffset, setPanOffset] = useState({ x: 0, y: 0 });
  const [loadedImages, setLoadedImages] = useState<Record<string, HTMLImageElement>>({});
  const [history, setHistory] = useState<CompositeLayerItem[][]>([initialLayers]);
  const [historyIdx, setHistoryIdx] = useState(0);
  const [dragOverIdx, setDragOverIdx] = useState<number | null>(null);
  const [panStart, setPanStart] = useState<{ x: number; y: number; ox: number; oy: number } | null>(null);

  // Compute fit zoom
  const fitZoom = typeof window !== 'undefined'
    ? Math.min((window.innerWidth - 380) / canvasWidth, (window.innerHeight - 100) / canvasHeight, 1)
    : 0.5;
  const effectiveZoom = zoom || fitZoom;

  // Push history
  const pushHistory = useCallback((newLayers: CompositeLayerItem[]) => {
    setHistory(prev => {
      const trimmed = prev.slice(0, historyIdx + 1);
      const next = [...trimmed, newLayers].slice(-50);
      return next;
    });
    setHistoryIdx(prev => Math.min(prev + 1, 49));
  }, [historyIdx]);

  const undo = useCallback(() => {
    if (historyIdx > 0) {
      const newIdx = historyIdx - 1;
      setHistoryIdx(newIdx);
      setLayers(history[newIdx]);
    }
  }, [historyIdx, history]);

  const redo = useCallback(() => {
    if (historyIdx < history.length - 1) {
      const newIdx = historyIdx + 1;
      setHistoryIdx(newIdx);
      setLayers(history[newIdx]);
    }
  }, [historyIdx, history]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'z') {
        e.preventDefault();
        if (e.shiftKey) redo(); else undo();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [undo, redo]);

  // Load images and auto-correct layer dimensions
  useEffect(() => {
    const imgs: Record<string, HTMLImageElement> = {};
    let mounted = true;
    const promises = layers
      .filter((l) => l.imageUrl)
      .map((l) => new Promise<{ id: string; img: HTMLImageElement } | null>((resolve) => {
        const img = new Image();
        img.crossOrigin = 'anonymous';
        img.onload = () => {
          if (mounted) imgs[l.id] = img;
          resolve({ id: l.id, img });
        };
        img.onerror = () => resolve(null);
        img.src = l.imageUrl!;
      }));
    Promise.all(promises).then((results) => {
      if (!mounted) return;
      setLoadedImages(imgs);

      // Auto-correct layer dimensions based on actual image aspect ratio
      setLayers(prev => {
        let changed = false;
        const updated = prev.map(layer => {
          const result = results.find(r => r && r.id === layer.id);
          if (!result) return layer;
          const { img } = result;
          const imgAspect = img.naturalWidth / img.naturalHeight;
          const layerAspect = layer.width / layer.height;

          // Only auto-correct if aspect ratio is significantly off (>10% difference)
          if (Math.abs(imgAspect - layerAspect) / imgAspect > 0.1) {
            changed = true;
            if (layer.type === 'background') {
              // Background: cover canvas
              return { ...layer, width: canvasWidth, height: canvasHeight };
            } else {
              // Character/prop: fit within canvas maintaining aspect ratio
              const targetHeight = Math.min(canvasHeight * 0.85, img.naturalHeight);
              const targetWidth = targetHeight * imgAspect;
              // Center horizontally
              const newX = (canvasWidth - targetWidth) / 2;
              const newY = (canvasHeight - targetHeight) / 2;
              return { ...layer, width: Math.round(targetWidth), height: Math.round(targetHeight), x: Math.round(newX), y: Math.round(newY) };
            }
          }
          return layer;
        });
        return changed ? updated : prev;
      });
    });
    return () => { mounted = false; };
  }, [layers.map(l => l.imageUrl).join(','), canvasWidth, canvasHeight]);

  // Render main canvas (images only)
  const renderCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, canvasWidth, canvasHeight);
    const sorted = [...layers].filter((l) => l.visible).sort((a, b) => a.zIndex - b.zIndex);
    for (const layer of sorted) {
      const img = loadedImages[layer.id];
      if (!img) continue;

      ctx.save();
      ctx.globalAlpha = layer.opacity;
      const cx = layer.x + layer.width / 2;
      const cy = layer.y + layer.height / 2;
      ctx.translate(cx, cy);
      ctx.rotate((layer.rotation * Math.PI) / 180);
      if (layer.flipX) ctx.scale(-1, 1);
      ctx.drawImage(img, -layer.width / 2, -layer.height / 2, layer.width, layer.height);
      ctx.restore();
    }
  }, [layers, loadedImages, canvasWidth, canvasHeight]);

  // Render overlay (selection handles)
  const renderOverlay = useCallback(() => {
    const canvas = overlayRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, canvasWidth, canvasHeight);

    if (!selectedLayerId) return;
    const layer = layers.find(l => l.id === selectedLayerId);
    if (!layer) return;

    const corners = getRotatedCorners(layer);
    const handles = getHandlePositions(layer);

    // Draw selection border (dashed blue)
    ctx.save();
    ctx.strokeStyle = 'rgba(59, 130, 246, 0.8)';
    ctx.lineWidth = 1.5 / effectiveZoom;
    ctx.setLineDash([6 / effectiveZoom, 4 / effectiveZoom]);
    ctx.beginPath();
    ctx.moveTo(corners.nw.x, corners.nw.y);
    ctx.lineTo(corners.ne.x, corners.ne.y);
    ctx.lineTo(corners.se.x, corners.se.y);
    ctx.lineTo(corners.sw.x, corners.sw.y);
    ctx.closePath();
    ctx.stroke();
    ctx.restore();

    // Draw handles
    const hs = HANDLE_SIZE / effectiveZoom;
    for (const [, pos] of Object.entries(handles)) {
      ctx.save();
      ctx.fillStyle = '#fff';
      ctx.strokeStyle = 'rgba(59, 130, 246, 0.8)';
      ctx.lineWidth = 1.5 / effectiveZoom;
      ctx.fillRect(pos.x - hs / 2, pos.y - hs / 2, hs, hs);
      ctx.strokeRect(pos.x - hs / 2, pos.y - hs / 2, hs, hs);
      ctx.restore();
    }

    // Draw rotation indicators at corners (small circles)
    const cornerKeys: HandleId[] = ['nw', 'ne', 'se', 'sw'];
    const rotDist = ROTATE_DISTANCE / effectiveZoom;
    const cx = layer.x + layer.width / 2;
    const cy = layer.y + layer.height / 2;
    for (const key of cornerKeys) {
      const h = handles[key];
      // Direction from center to corner, extend outward
      const dx = h.x - cx;
      const dy = h.y - cy;
      const len = Math.hypot(dx, dy);
      if (len === 0) continue;
      const rx = h.x + (dx / len) * rotDist;
      const ry = h.y + (dy / len) * rotDist;
      ctx.save();
      ctx.beginPath();
      ctx.arc(rx, ry, 4 / effectiveZoom, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(59, 130, 246, 0.4)';
      ctx.fill();
      ctx.restore();
    }
  }, [layers, selectedLayerId, effectiveZoom, canvasWidth, canvasHeight]);

  useEffect(() => { renderCanvas(); renderOverlay(); }, [renderCanvas, renderOverlay]);

  // Convert client coords to canvas coords
  const clientToCanvas = useCallback((clientX: number, clientY: number) => {
    const container = containerRef.current;
    if (!container) return { x: 0, y: 0 };
    const rect = container.getBoundingClientRect();
    return {
      x: (clientX - rect.left - panOffset.x) / effectiveZoom,
      y: (clientY - rect.top - panOffset.y) / effectiveZoom,
    };
  }, [effectiveZoom, panOffset]);

  // Mouse down on canvas
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    // Middle button = pan
    if (e.button === 1) {
      setPanStart({ x: e.clientX, y: e.clientY, ox: panOffset.x, oy: panOffset.y });
      return;
    }
    if (e.button !== 0) return;

    const { x, y } = clientToCanvas(e.clientX, e.clientY);

    // First check if we hit a handle on selected layer
    if (selectedLayerId) {
      const selLayer = layers.find(l => l.id === selectedLayerId);
      if (selLayer) {
        const hit = hitTestHandle(x, y, selLayer, effectiveZoom);
        if (hit) {
          if (hit.type === 'handle') {
            setInteraction({
              mode: 'resizing', handle: hit.handle, layerId: selLayer.id,
              startClientX: e.clientX, startClientY: e.clientY,
              startLayerX: selLayer.x, startLayerY: selLayer.y,
              startLayerW: selLayer.width, startLayerH: selLayer.height,
              startLayerRot: selLayer.rotation,
            });
            return;
          }
          if (hit.type === 'rotate') {
            const cx = selLayer.x + selLayer.width / 2;
            const cy = selLayer.y + selLayer.height / 2;
            const startAngle = Math.atan2(y - cy, x - cx) * 180 / Math.PI;
            setInteraction({
              mode: 'rotating', layerId: selLayer.id,
              startClientX: e.clientX, startClientY: e.clientY,
              startLayerX: selLayer.x, startLayerY: selLayer.y,
              startLayerW: selLayer.width, startLayerH: selLayer.height,
              startLayerRot: selLayer.rotation,
              startAngle,
            });
            return;
          }
          if (hit.type === 'body') {
            setInteraction({
              mode: 'dragging', layerId: selLayer.id,
              startClientX: e.clientX, startClientY: e.clientY,
              startLayerX: selLayer.x, startLayerY: selLayer.y,
              startLayerW: selLayer.width, startLayerH: selLayer.height,
              startLayerRot: selLayer.rotation,
            });
            return;
          }
        }
      }
    }

    // Hit test all layers (topmost first)
    const sorted = [...layers].filter(l => l.visible).sort((a, b) => b.zIndex - a.zIndex);
    for (const layer of sorted) {
      const hit = hitTestHandle(x, y, layer, effectiveZoom);
      if (hit && (hit.type === 'body' || hit.type === 'handle')) {
        setSelectedLayerId(layer.id);
        if (hit.type === 'handle') {
          setInteraction({
            mode: 'resizing', handle: (hit as any).handle, layerId: layer.id,
            startClientX: e.clientX, startClientY: e.clientY,
            startLayerX: layer.x, startLayerY: layer.y,
            startLayerW: layer.width, startLayerH: layer.height,
            startLayerRot: layer.rotation,
          });
        } else {
          setInteraction({
            mode: 'dragging', layerId: layer.id,
            startClientX: e.clientX, startClientY: e.clientY,
            startLayerX: layer.x, startLayerY: layer.y,
            startLayerW: layer.width, startLayerH: layer.height,
            startLayerRot: layer.rotation,
          });
        }
        return;
      }
    }

    // Clicked empty area
    setSelectedLayerId(null);
  }, [layers, selectedLayerId, clientToCanvas, effectiveZoom, panOffset]);

  // Mouse move
  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    // Pan with middle mouse
    if (panStart) {
      setPanOffset({
        x: panStart.ox + (e.clientX - panStart.x),
        y: panStart.oy + (e.clientY - panStart.y),
      });
      return;
    }

    if (!interaction) {
      // Update cursor based on hover
      const { x, y } = clientToCanvas(e.clientX, e.clientY);
      const canvas = overlayRef.current;
      if (!canvas) return;

      if (selectedLayerId) {
        const selLayer = layers.find(l => l.id === selectedLayerId);
        if (selLayer) {
          const hit = hitTestHandle(x, y, selLayer, effectiveZoom);
          if (hit?.type === 'handle') {
            canvas.style.cursor = HANDLE_CURSORS[(hit as any).handle];
            return;
          }
          if (hit?.type === 'rotate') {
            canvas.style.cursor = 'crosshair';
            return;
          }
          if (hit?.type === 'body') {
            canvas.style.cursor = 'move';
            return;
          }
        }
      }

      // Check hover on any layer
      const sorted = [...layers].filter(l => l.visible).sort((a, b) => b.zIndex - a.zIndex);
      for (const layer of sorted) {
        const hit = hitTestHandle(x, y, layer, effectiveZoom);
        if (hit?.type === 'body') {
          canvas.style.cursor = 'move';
          return;
        }
      }
      canvas.style.cursor = 'default';
      return;
    }

    const { x: canvasX, y: canvasY } = clientToCanvas(e.clientX, e.clientY);
    const dx = (e.clientX - interaction.startClientX) / effectiveZoom;
    const dy = (e.clientY - interaction.startClientY) / effectiveZoom;

    if (interaction.mode === 'dragging') {
      setLayers(prev => prev.map(l =>
        l.id === interaction.layerId
          ? { ...l, x: interaction.startLayerX + dx, y: interaction.startLayerY + dy }
          : l,
      ));
    } else if (interaction.mode === 'resizing' && interaction.handle) {
      const h = interaction.handle;
      const isCorner = ['nw', 'ne', 'se', 'sw'].includes(h);

      // For simplicity, compute resize in unrotated space
      const cx = interaction.startLayerX + interaction.startLayerW / 2;
      const cy = interaction.startLayerY + interaction.startLayerH / 2;
      const rot = interaction.startLayerRot;

      // Rotate mouse delta into local space
      const rad = (-rot * Math.PI) / 180;
      const localDx = dx * Math.cos(rad) - dy * Math.sin(rad);
      const localDy = dx * Math.sin(rad) + dy * Math.cos(rad);

      let newW = interaction.startLayerW;
      let newH = interaction.startLayerH;
      let newX = interaction.startLayerX;
      let newY = interaction.startLayerY;

      if (h.includes('e')) { newW += localDx; }
      if (h.includes('w')) { newW -= localDx; newX += localDx; }
      if (h.includes('s')) { newH += localDy; }
      if (h.includes('n')) { newH -= localDy; newY += localDy; }

      // Lock aspect ratio for corners
      if (isCorner) {
        const aspect = interaction.startLayerW / interaction.startLayerH;
        if (Math.abs(localDx) > Math.abs(localDy)) {
          newH = newW / aspect;
          if (h.includes('n')) {
            newY = interaction.startLayerY + (interaction.startLayerH - newH);
          }
        } else {
          newW = newH * aspect;
          if (h.includes('w')) {
            newX = interaction.startLayerX + (interaction.startLayerW - newW);
          }
        }
      }

      // Minimum size
      newW = Math.max(20, newW);
      newH = Math.max(20, newH);

      setLayers(prev => prev.map(l =>
        l.id === interaction.layerId
          ? { ...l, x: newX, y: newY, width: Math.round(newW), height: Math.round(newH) }
          : l,
      ));
    } else if (interaction.mode === 'rotating') {
      const layer = layers.find(l => l.id === interaction.layerId);
      if (!layer) return;
      const lcx = interaction.startLayerX + interaction.startLayerW / 2;
      const lcy = interaction.startLayerY + interaction.startLayerH / 2;
      const currentAngle = Math.atan2(canvasY - lcy, canvasX - lcx) * 180 / Math.PI;
      const delta = currentAngle - (interaction.startAngle ?? 0);
      let newRot = interaction.startLayerRot + delta;
      // Snap to 0/90/180/270 if close
      for (const snap of [0, 90, 180, 270, -90, -180, -270]) {
        if (Math.abs(newRot - snap) < 3) { newRot = snap; break; }
      }
      setLayers(prev => prev.map(l =>
        l.id === interaction.layerId ? { ...l, rotation: newRot } : l,
      ));
    }
  }, [interaction, panStart, layers, selectedLayerId, clientToCanvas, effectiveZoom]);

  // Mouse up
  const handleMouseUp = useCallback(() => {
    if (panStart) { setPanStart(null); return; }
    if (interaction) {
      // Commit to history
      pushHistory(layers);
      setInteraction(null);
    }
  }, [interaction, panStart, layers, pushHistory]);

  // Wheel zoom
  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setZoom(prev => Math.max(0.05, Math.min(4, (prev || fitZoom) * delta)));
  }, [fitZoom]);

  // Export
  const handleExport = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    renderCanvas();
    const dataUrl = canvas.toDataURL('image/png');
    onSave(dataUrl, layers);
  }, [renderCanvas, layers, onSave]);

  // Mirror selected layer
  const flipSelected = useCallback(() => {
    if (!selectedLayerId) return;
    setLayers(prev => {
      const next = prev.map(l => l.id === selectedLayerId ? { ...l, flipX: !l.flipX } : l);
      pushHistory(next);
      return next;
    });
  }, [selectedLayerId, pushHistory]);

  // Reset zoom to fit
  const resetZoom = useCallback(() => {
    setZoom(fitZoom);
    setPanOffset({ x: 0, y: 0 });
  }, [fitZoom]);

  // Layer reorder via drag-and-drop in panel
  const handleLayerDragStart = useCallback((e: React.DragEvent, idx: number) => {
    e.dataTransfer.setData('text/plain', String(idx));
    e.dataTransfer.effectAllowed = 'move';
  }, []);

  const handleLayerDragOver = useCallback((e: React.DragEvent, idx: number) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDragOverIdx(idx);
  }, []);

  const handleLayerDrop = useCallback((e: React.DragEvent, dropIdx: number) => {
    e.preventDefault();
    setDragOverIdx(null);
    const fromIdx = parseInt(e.dataTransfer.getData('text/plain'), 10);
    if (isNaN(fromIdx) || fromIdx === dropIdx) return;

    setLayers(prev => {
      // Sorted by zIndex descending for display
      const sorted = [...prev].sort((a, b) => b.zIndex - a.zIndex);
      const [moved] = sorted.splice(fromIdx, 1);
      sorted.splice(dropIdx, 0, moved);
      // Reassign zIndex (descending: top = highest)
      const next = sorted.map((l, i) => ({ ...l, zIndex: sorted.length - 1 - i }));
      pushHistory(next);
      return next;
    });
  }, [pushHistory]);

  // Update layer property
  const updateLayerProp = useCallback((layerId: string, prop: string, value: number | boolean) => {
    setLayers(prev => {
      const next = prev.map(l => l.id === layerId ? { ...l, [prop]: value } : l);
      pushHistory(next);
      return next;
    });
  }, [pushHistory]);

  // Toggle visibility
  const toggleVisibility = useCallback((layerId: string) => {
    setLayers(prev => {
      const next = prev.map(l => l.id === layerId ? { ...l, visible: !l.visible } : l);
      pushHistory(next);
      return next;
    });
  }, [pushHistory]);

  const selectedLayer = layers.find(l => l.id === selectedLayerId);

  return createPortal(
    <div
      style={{ position: 'fixed', inset: 0, zIndex: 9999, backgroundColor: 'rgba(0,0,0,0.92)', display: 'flex' }}
      onMouseUp={handleMouseUp}
    >
      {/* Canvas area */}
      <div
        style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', position: 'relative' }}
        onWheel={handleWheel}
      >
        {/* Floating toolbar */}
        <div style={{
          position: 'absolute', top: 16, left: 16, zIndex: 10,
          display: 'flex', gap: 4, padding: '6px 8px',
          backgroundColor: 'rgba(20,20,30,0.85)', borderRadius: 10,
          border: '1px solid rgba(255,255,255,0.08)',
        }}>
          <button onClick={flipSelected} disabled={!selectedLayerId} title="水平镜像 (Flip)"
            style={{ ...toolBtnStyle, opacity: selectedLayerId ? 1 : 0.3 }}>⟷</button>
          <button onClick={resetZoom} title="适应画布"
            style={toolBtnStyle}>⊞</button>
          <div style={{ width: 1, backgroundColor: 'rgba(255,255,255,0.1)', margin: '0 4px' }} />
          <button onClick={undo} disabled={historyIdx <= 0} title="撤销 (Ctrl+Z)"
            style={{ ...toolBtnStyle, opacity: historyIdx > 0 ? 1 : 0.3 }}>↩</button>
          <button onClick={redo} disabled={historyIdx >= history.length - 1} title="重做 (Ctrl+Shift+Z)"
            style={{ ...toolBtnStyle, opacity: historyIdx < history.length - 1 ? 1 : 0.3 }}>↪</button>
        </div>

        {/* Canvas container with zoom & pan */}
        <div
          ref={containerRef}
          style={{
            position: 'relative',
            background: CHECKERBOARD,
            borderRadius: 8,
            overflow: 'hidden',
            transform: `translate(${panOffset.x}px, ${panOffset.y}px)`,
          }}
        >
          <canvas
            ref={canvasRef}
            width={canvasWidth}
            height={canvasHeight}
            style={{ width: canvasWidth * effectiveZoom, height: canvasHeight * effectiveZoom, display: 'block' }}
          />
          <canvas
            ref={overlayRef}
            width={canvasWidth}
            height={canvasHeight}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            style={{
              position: 'absolute', inset: 0,
              width: canvasWidth * effectiveZoom,
              height: canvasHeight * effectiveZoom,
              cursor: interaction?.mode === 'dragging' ? 'grabbing'
                : interaction?.mode === 'rotating' ? 'crosshair'
                : 'default',
            }}
          />
        </div>

        {/* Zoom indicator */}
        <div style={{
          position: 'absolute', bottom: 16, left: 16, fontSize: 11,
          color: 'rgba(255,255,255,0.35)', backgroundColor: 'rgba(0,0,0,0.4)',
          padding: '4px 10px', borderRadius: 6,
        }}>
          {Math.round(effectiveZoom * 100)}%
        </div>
      </div>

      {/* Right panel — layers */}
      <div style={{
        width: 320, backgroundColor: '#1a1c24', borderLeft: '1px solid rgba(255,255,255,0.08)',
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{ padding: '16px 20px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: 'rgba(255,255,255,0.8)' }}>图层</span>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={handleExport} style={{ fontSize: 12, padding: '6px 14px', borderRadius: 8, border: 'none', backgroundColor: 'rgba(129,140,248,0.2)', color: 'rgba(129,140,248,0.9)', cursor: 'pointer', fontWeight: 500 }}>
              导出
            </button>
            <button onClick={onClose} style={{ fontSize: 12, padding: '6px 14px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.1)', backgroundColor: 'transparent', color: 'rgba(255,255,255,0.5)', cursor: 'pointer' }}>
              关闭
            </button>
          </div>
        </div>

        {/* Zoom control */}
        <div style={{ padding: '8px 20px', display: 'flex', alignItems: 'center', gap: 8, borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
          <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)' }}>缩放</span>
          <input type="range" min={0.05} max={4} step={0.05} value={effectiveZoom}
            onChange={(e) => setZoom(parseFloat(e.target.value))}
            style={{ flex: 1, accentColor: '#818cf8' }} />
          <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', minWidth: 36, textAlign: 'right' }}>
            {Math.round(effectiveZoom * 100)}%
          </span>
        </div>

        {/* Layer list — drag & drop reorder */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '4px 0' }}>
          {[...layers].sort((a, b) => b.zIndex - a.zIndex).map((layer, idx) => (
            <div
              key={layer.id}
              draggable
              onDragStart={(e) => handleLayerDragStart(e, idx)}
              onDragOver={(e) => handleLayerDragOver(e, idx)}
              onDragLeave={() => setDragOverIdx(null)}
              onDrop={(e) => handleLayerDrop(e, idx)}
              onClick={() => setSelectedLayerId(layer.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 8, padding: '6px 16px',
                backgroundColor: selectedLayerId === layer.id ? 'rgba(129,140,248,0.08)' : 'transparent',
                cursor: 'grab',
                borderLeft: selectedLayerId === layer.id ? '2px solid rgba(129,140,248,0.6)' : '2px solid transparent',
                borderTop: dragOverIdx === idx ? '2px solid rgba(129,140,248,0.5)' : '2px solid transparent',
                transition: 'background-color 0.1s',
              }}
            >
              {/* Drag handle */}
              <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.15)', cursor: 'grab', userSelect: 'none' }}>⠿</span>

              {/* Thumbnail */}
              <div style={{ width: 36, height: 36, borderRadius: 6, backgroundColor: 'rgba(255,255,255,0.04)', overflow: 'hidden', flexShrink: 0 }}>
                {layer.imageUrl && <img src={layer.imageUrl} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />}
              </div>

              {/* Info */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12, color: layer.visible ? 'rgba(255,255,255,0.7)' : 'rgba(255,255,255,0.25)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {layer.type === 'background' ? '背景' : layer.type === 'character' ? '角色' : '道具'}
                </div>
                {/* Inline opacity slider */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 2 }}>
                  <input
                    type="range" min={0} max={1} step={0.01}
                    value={layer.opacity}
                    onClick={(e) => e.stopPropagation()}
                    onChange={(e) => {
                      e.stopPropagation();
                      const val = parseFloat(e.target.value);
                      setLayers(prev => prev.map(l => l.id === layer.id ? { ...l, opacity: val } : l));
                    }}
                    onMouseUp={() => pushHistory(layers)}
                    style={{ width: 60, height: 3, accentColor: '#818cf8' }}
                  />
                  <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.25)', minWidth: 24 }}>
                    {Math.round(layer.opacity * 100)}%
                  </span>
                </div>
              </div>

              {/* Controls */}
              <div style={{ display: 'flex', gap: 2, flexShrink: 0 }}>
                <button onClick={(e) => { e.stopPropagation(); toggleVisibility(layer.id); }}
                  style={iconBtnStyle}>
                  <span style={{ color: layer.visible ? 'rgba(255,255,255,0.4)' : 'rgba(255,255,255,0.15)', fontSize: 11 }}>
                    {layer.visible ? '👁' : '⊘'}
                  </span>
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Selected layer properties */}
        {selectedLayer && (
          <div style={{ padding: '12px 16px', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)' }}>属性</span>
              <button onClick={flipSelected} title="水平镜像"
                style={{
                  fontSize: 11, padding: '3px 10px', borderRadius: 6,
                  border: selectedLayer.flipX ? '1px solid rgba(129,140,248,0.4)' : '1px solid rgba(255,255,255,0.1)',
                  backgroundColor: selectedLayer.flipX ? 'rgba(129,140,248,0.15)' : 'transparent',
                  color: selectedLayer.flipX ? 'rgba(129,140,248,0.9)' : 'rgba(255,255,255,0.4)',
                  cursor: 'pointer',
                }}>
                ⟷ 镜像
              </button>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px 8px' }}>
              {([
                ['x', 'X'],
                ['y', 'Y'],
                ['rotation', '旋转'],
                ['width', 'W'],
                ['height', 'H'],
                ['opacity', '透明'],
              ] as const).map(([prop, label]) => (
                <label key={prop} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.2)' }}>{label}</span>
                  <input
                    type="number"
                    value={Math.round(selectedLayer[prop] * (prop === 'opacity' ? 100 : 1))}
                    onChange={(e) => {
                      const val = parseFloat(e.target.value) / (prop === 'opacity' ? 100 : 1);
                      updateLayerProp(selectedLayer.id, prop, val);
                    }}
                    style={{
                      width: '100%', padding: '3px 5px', borderRadius: 4,
                      border: '1px solid rgba(255,255,255,0.08)',
                      backgroundColor: 'rgba(255,255,255,0.03)',
                      color: 'rgba(255,255,255,0.6)', fontSize: 11,
                    }}
                  />
                </label>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}

const toolBtnStyle: React.CSSProperties = {
  width: 32, height: 28, border: 'none', borderRadius: 6,
  backgroundColor: 'transparent', color: 'rgba(255,255,255,0.6)',
  cursor: 'pointer', fontSize: 16, display: 'flex', alignItems: 'center', justifyContent: 'center',
};

const iconBtnStyle: React.CSSProperties = {
  width: 24, height: 24, border: 'none', backgroundColor: 'transparent', cursor: 'pointer',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
};

export const CompositeEditor = memo(CompositeEditorComponent);
