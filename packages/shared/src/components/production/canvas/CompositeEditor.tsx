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

const CHECKERBOARD = 'repeating-conic-gradient(#222 0% 25%, #2a2a2a 0% 50%) 0 0 / 20px 20px';

function CompositeEditorComponent({ layers: initialLayers, canvasWidth, canvasHeight, onSave, onClose }: CompositeEditorProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [layers, setLayers] = useState<CompositeLayerItem[]>(initialLayers);
  const [selectedLayerId, setSelectedLayerId] = useState<string | null>(null);
  const [dragging, setDragging] = useState<{ layerId: string; startX: number; startY: number; layerX: number; layerY: number } | null>(null);
  const [zoom, setZoom] = useState(1);
  const [loadedImages, setLoadedImages] = useState<Record<string, HTMLImageElement>>({});

  // Load images
  useEffect(() => {
    const imgs: Record<string, HTMLImageElement> = {};
    let mounted = true;
    const promises = layers
      .filter((l) => l.imageUrl && l.visible)
      .map((l) => new Promise<void>((resolve) => {
        const img = new Image();
        img.crossOrigin = 'anonymous';
        img.onload = () => { if (mounted) imgs[l.id] = img; resolve(); };
        img.onerror = () => resolve();
        img.src = l.imageUrl!;
      }));
    Promise.all(promises).then(() => { if (mounted) setLoadedImages(imgs); });
    return () => { mounted = false; };
  }, [layers]);

  // Render canvas
  const renderCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, canvasWidth, canvasHeight);

    // Sort layers by zIndex
    const sorted = [...layers].filter((l) => l.visible).sort((a, b) => a.zIndex - b.zIndex);
    for (const layer of sorted) {
      const img = loadedImages[layer.id];
      if (!img) continue;

      ctx.save();
      ctx.globalAlpha = layer.opacity;
      ctx.translate(layer.x + layer.width / 2, layer.y + layer.height / 2);
      ctx.rotate((layer.rotation * Math.PI) / 180);
      ctx.drawImage(img, -layer.width / 2, -layer.height / 2, layer.width, layer.height);
      ctx.restore();
    }
  }, [layers, loadedImages, canvasWidth, canvasHeight]);

  useEffect(() => { renderCanvas(); }, [renderCanvas]);

  // Mouse drag
  const handleMouseDown = (e: React.MouseEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / zoom;
    const y = (e.clientY - rect.top) / zoom;

    // Find topmost layer at click point
    const sorted = [...layers].filter((l) => l.visible).sort((a, b) => b.zIndex - a.zIndex);
    for (const layer of sorted) {
      if (x >= layer.x && x <= layer.x + layer.width && y >= layer.y && y <= layer.y + layer.height) {
        setSelectedLayerId(layer.id);
        setDragging({ layerId: layer.id, startX: e.clientX, startY: e.clientY, layerX: layer.x, layerY: layer.y });
        return;
      }
    }
    setSelectedLayerId(null);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!dragging) return;
    const dx = (e.clientX - dragging.startX) / zoom;
    const dy = (e.clientY - dragging.startY) / zoom;
    setLayers((prev) =>
      prev.map((l) => l.id === dragging.layerId ? { ...l, x: dragging.layerX + dx, y: dragging.layerY + dy } : l),
    );
  };

  const handleMouseUp = () => setDragging(null);

  const handleExport = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    renderCanvas();
    const dataUrl = canvas.toDataURL('image/png');
    onSave(dataUrl, layers);
  };

  const moveLayer = (layerId: string, direction: 'up' | 'down') => {
    setLayers((prev) => {
      const idx = prev.findIndex((l) => l.id === layerId);
      if (idx < 0) return prev;
      const newLayers = [...prev];
      if (direction === 'up' && idx > 0) {
        [newLayers[idx - 1], newLayers[idx]] = [newLayers[idx], newLayers[idx - 1]];
      } else if (direction === 'down' && idx < newLayers.length - 1) {
        [newLayers[idx], newLayers[idx + 1]] = [newLayers[idx + 1], newLayers[idx]];
      }
      return newLayers.map((l, i) => ({ ...l, zIndex: i }));
    });
  };

  const toggleVisibility = (layerId: string) => {
    setLayers((prev) => prev.map((l) => l.id === layerId ? { ...l, visible: !l.visible } : l));
  };

  const fitZoom = Math.min(
    (window.innerWidth - 360) / canvasWidth,
    (window.innerHeight - 120) / canvasHeight,
    1,
  );

  return createPortal(
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      backgroundColor: 'rgba(0,0,0,0.85)', display: 'flex',
    }}>
      {/* Canvas area */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'auto' }}
        onMouseMove={handleMouseMove} onMouseUp={handleMouseUp}>
        <div style={{ background: CHECKERBOARD, borderRadius: 8, overflow: 'hidden' }}>
          <canvas
            ref={canvasRef}
            width={canvasWidth}
            height={canvasHeight}
            style={{ width: canvasWidth * (zoom || fitZoom), height: canvasHeight * (zoom || fitZoom), cursor: dragging ? 'grabbing' : 'default' }}
            onMouseDown={handleMouseDown}
          />
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
          <input type="range" min={0.1} max={2} step={0.05} value={zoom || fitZoom}
            onChange={(e) => setZoom(parseFloat(e.target.value))}
            style={{ flex: 1, accentColor: '#818cf8' }} />
          <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', minWidth: 36, textAlign: 'right' }}>{Math.round((zoom || fitZoom) * 100)}%</span>
        </div>

        {/* Layer list */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
          {[...layers].sort((a, b) => b.zIndex - a.zIndex).map((layer) => (
            <div
              key={layer.id}
              onClick={() => setSelectedLayerId(layer.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 10, padding: '8px 20px',
                backgroundColor: selectedLayerId === layer.id ? 'rgba(129,140,248,0.08)' : 'transparent',
                cursor: 'pointer', borderLeft: selectedLayerId === layer.id ? '2px solid rgba(129,140,248,0.6)' : '2px solid transparent',
              }}>
              {/* Thumbnail */}
              <div style={{ width: 36, height: 36, borderRadius: 6, backgroundColor: 'rgba(255,255,255,0.04)', overflow: 'hidden', flexShrink: 0 }}>
                {layer.imageUrl && <img src={layer.imageUrl} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />}
              </div>
              {/* Info */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12, color: layer.visible ? 'rgba(255,255,255,0.7)' : 'rgba(255,255,255,0.25)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {layer.type === 'background' ? '背景' : layer.type === 'character' ? '角色' : '道具'}
                </div>
                <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.2)' }}>
                  {Math.round(layer.x)}, {Math.round(layer.y)} | {layer.width}x{layer.height}
                </div>
              </div>
              {/* Controls */}
              <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
                <button onClick={(e) => { e.stopPropagation(); toggleVisibility(layer.id); }}
                  style={{ width: 24, height: 24, border: 'none', backgroundColor: 'transparent', cursor: 'pointer', fontSize: 12, color: layer.visible ? 'rgba(255,255,255,0.4)' : 'rgba(255,255,255,0.15)' }}>
                  {layer.visible ? '👁' : '⊘'}
                </button>
                <button onClick={(e) => { e.stopPropagation(); moveLayer(layer.id, 'up'); }}
                  style={{ width: 24, height: 24, border: 'none', backgroundColor: 'transparent', cursor: 'pointer', fontSize: 10, color: 'rgba(255,255,255,0.3)' }}>
                  ▲
                </button>
                <button onClick={(e) => { e.stopPropagation(); moveLayer(layer.id, 'down'); }}
                  style={{ width: 24, height: 24, border: 'none', backgroundColor: 'transparent', cursor: 'pointer', fontSize: 10, color: 'rgba(255,255,255,0.3)' }}>
                  ▼
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Selected layer properties */}
        {selectedLayerId && (() => {
          const layer = layers.find((l) => l.id === selectedLayerId);
          if (!layer) return null;
          return (
            <div style={{ padding: '12px 20px', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', marginBottom: 8 }}>属性</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 12px' }}>
                {(['x', 'y', 'width', 'height', 'rotation', 'opacity'] as const).map((prop) => (
                  <label key={prop} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)' }}>{prop}</span>
                    <input
                      type="number"
                      value={Math.round(layer[prop] * (prop === 'opacity' ? 100 : 1))}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value) / (prop === 'opacity' ? 100 : 1);
                        setLayers((prev) => prev.map((l) => l.id === selectedLayerId ? { ...l, [prop]: val } : l));
                      }}
                      style={{
                        width: '100%', padding: '4px 6px', borderRadius: 4, border: '1px solid rgba(255,255,255,0.08)',
                        backgroundColor: 'rgba(255,255,255,0.03)', color: 'rgba(255,255,255,0.6)', fontSize: 11,
                      }}
                    />
                  </label>
                ))}
              </div>
            </div>
          );
        })()}
      </div>
    </div>,
    document.body,
  );
}

export const CompositeEditor = memo(CompositeEditorComponent);
