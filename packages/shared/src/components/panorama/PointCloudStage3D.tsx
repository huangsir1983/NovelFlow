'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import { createPortal } from 'react-dom';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import {
  type Character3D,
  CHAR_COLORS,
  createCharObject,
  disposeObject,
} from './directorStageHelpers';

export interface PointCloudStage3DProps {
  panoramaUrl: string;     // equirectangular VR panorama (color)
  depthMapUrl: string;     // equirectangular depth map (grayscale: white=near, black=far)
  isOpen: boolean;
  onClose: () => void;
  baseRadius?: number;     // base sphere radius (default 10)
  depthScale?: number;     // depth displacement amount (default 2)
  pointSize?: number;      // point size in pixels (default 2.0)
  characters?: Character3D[];
  onCharactersUpdate?: (chars: Character3D[]) => void;
}

// ── Load image as ImageData ──────────────────────────────────────

function loadImageData(url: string): Promise<{ data: Uint8ClampedArray; width: number; height: number }> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = img.width;
      canvas.height = img.height;
      const ctx = canvas.getContext('2d')!;
      ctx.drawImage(img, 0, 0);
      const imageData = ctx.getImageData(0, 0, img.width, img.height);
      resolve({ data: imageData.data, width: img.width, height: img.height });
    };
    img.onerror = () => reject(new Error(`Failed to load image: ${url}`));
    img.src = url;
  });
}

// ── Build point cloud from panorama + depth ─────────────────────

function buildPointCloud(
  colorData: { data: Uint8ClampedArray; width: number; height: number },
  depthData: { data: Uint8ClampedArray; width: number; height: number },
  baseRadius: number,
  depthScale: number,
  sampleStep: number,
): THREE.BufferGeometry {
  const { width, height } = colorData;
  const dw = depthData.width;
  const dh = depthData.height;

  // Estimate point count
  const cols = Math.ceil(width / sampleStep);
  const rows = Math.ceil(height / sampleStep);
  const maxPoints = cols * rows;

  const positions = new Float32Array(maxPoints * 3);
  const colors = new Float32Array(maxPoints * 3);
  let idx = 0;

  for (let py = 0; py < height; py += sampleStep) {
    for (let px = 0; px < width; px += sampleStep) {
      // Equirectangular UV
      const u = px / width;   // 0..1  → longitude 0..2π
      const v = py / height;  // 0..1  → latitude  π(top)..0(bottom)

      // Spherical angles (Three.js convention: Y-up)
      // u=0 → looking at -Z, u=0.5 → +X, etc.
      const theta = u * Math.PI * 2;       // longitude
      const phi = (1 - v) * Math.PI;       // latitude: v=0 → top(phi=π), v=1 → bottom(phi=0)

      // Direction vector (Y-up)
      const sinPhi = Math.sin(phi);
      const dx = sinPhi * Math.sin(theta);
      const dy = Math.cos(phi);
      const dz = -sinPhi * Math.cos(theta);

      // Sample depth (nearest neighbor, map coordinates)
      const dpx = Math.min(Math.floor(u * dw), dw - 1);
      const dpy = Math.min(Math.floor(v * dh), dh - 1);
      const dIdx = (dpy * dw + dpx) * 4;
      const depthVal = depthData.data[dIdx] / 255; // 0=far, 1=near

      // Radius: near objects (white) are closer → smaller radius
      // far objects (black) stay at baseRadius
      const r = baseRadius - depthVal * depthScale;

      positions[idx * 3] = dx * r;
      positions[idx * 3 + 1] = dy * r;
      positions[idx * 3 + 2] = dz * r;

      // Color
      const cIdx = (py * width + px) * 4;
      colors[idx * 3] = colorData.data[cIdx] / 255;
      colors[idx * 3 + 1] = colorData.data[cIdx + 1] / 255;
      colors[idx * 3 + 2] = colorData.data[cIdx + 2] / 255;

      idx++;
    }
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(positions.slice(0, idx * 3), 3));
  geo.setAttribute('color', new THREE.BufferAttribute(colors.slice(0, idx * 3), 3));
  return geo;
}

// ══════════════════════════════════════════════════════════════════

export function PointCloudStage3D({
  panoramaUrl,
  depthMapUrl,
  isOpen,
  onClose,
  baseRadius = 10,
  depthScale = 2,
  pointSize = 2.0,
  characters: initialCharacters = [],
  onCharactersUpdate,
}: PointCloudStage3DProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const pointsRef = useRef<THREE.Points | null>(null);
  const charGroupRef = useRef<THREE.Group | null>(null);
  const charObjsRef = useRef<Map<string, THREE.Group>>(new Map());
  const animIdRef = useRef(0);
  const raycasterRef = useRef(new THREE.Raycaster());
  const mouseRef = useRef(new THREE.Vector2());
  const groundPlaneRef = useRef(new THREE.Plane(new THREE.Vector3(0, 1, 0), 0));
  const dragRef = useRef<{ id: string; obj: THREE.Object3D } | null>(null);
  const isDraggingRef = useRef(false);
  const ptrDownRef = useRef({ x: 0, y: 0 });

  // Store raw image data for rebuilding point cloud when params change
  const colorDataRef = useRef<{ data: Uint8ClampedArray; width: number; height: number } | null>(null);
  const depthDataRef = useRef<{ data: Uint8ClampedArray; width: number; height: number } | null>(null);

  const charsRef = useRef(initialCharacters);
  const onCharsUpdateRef = useRef(onCharactersUpdate);
  const onCloseRef = useRef(onClose);

  const [loading, setLoading] = useState(true);
  const [chars, setChars] = useState<Character3D[]>(initialCharacters);
  const [selectedCharId, setSelectedCharId] = useState<string | null>(null);
  const [currentDepthScale, setCurrentDepthScale] = useState(depthScale);
  const [currentPointSize, setCurrentPointSize] = useState(pointSize);
  const [currentBaseRadius, setCurrentBaseRadius] = useState(baseRadius);
  const [pointCount, setPointCount] = useState(0);

  useEffect(() => { charsRef.current = chars; }, [chars]);
  useEffect(() => { onCharsUpdateRef.current = onCharactersUpdate; }, [onCharactersUpdate]);
  useEffect(() => { onCloseRef.current = onClose; }, [onClose]);

  // ── Rebuild point cloud when depth params change ──
  const rebuildPoints = useCallback((ds: number, br: number) => {
    if (!colorDataRef.current || !depthDataRef.current || !sceneRef.current) return;

    // Remove old points
    if (pointsRef.current) {
      sceneRef.current.remove(pointsRef.current);
      pointsRef.current.geometry.dispose();
      (pointsRef.current.material as THREE.PointsMaterial).dispose();
      pointsRef.current = null;
    }

    // Sample step: downsample large images to keep point count manageable
    const w = colorDataRef.current.width;
    const h = colorDataRef.current.height;
    const totalPixels = w * h;
    const maxPoints = 800_000;
    const sampleStep = Math.max(1, Math.ceil(Math.sqrt(totalPixels / maxPoints)));

    const geo = buildPointCloud(colorDataRef.current, depthDataRef.current, br, ds, sampleStep);
    setPointCount(geo.getAttribute('position').count);

    const mat = new THREE.PointsMaterial({
      size: currentPointSize,
      vertexColors: true,
      sizeAttenuation: true,
    });

    const points = new THREE.Points(geo, mat);
    sceneRef.current.add(points);
    pointsRef.current = points;
  }, [currentPointSize]);

  // ── Main scene setup ──
  useEffect(() => {
    if (!isOpen || !containerRef.current) return;
    const container = containerRef.current;
    const w = container.clientWidth;
    const h = container.clientHeight;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x08080f);
    sceneRef.current = scene;

    // Camera inside the point cloud sphere
    const camera = new THREE.PerspectiveCamera(75, w / h, 0.01, 200);
    camera.position.set(0, 0, 0);
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 0, -0.01); // look slightly forward
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.enableZoom = true;
    controls.minDistance = 0;
    controls.maxDistance = currentBaseRadius * 0.9;
    controls.rotateSpeed = -0.3; // inverted for inside-sphere feel
    controls.update();
    controlsRef.current = controls;

    // Lighting (for characters)
    scene.add(new THREE.AmbientLight(0xffffff, 1.0));

    // Character group
    const charGroup = new THREE.Group();
    scene.add(charGroup);
    charGroupRef.current = charGroup;

    // Load images
    setLoading(true);
    Promise.all([
      loadImageData(panoramaUrl),
      loadImageData(depthMapUrl),
    ]).then(([colorImg, depthImg]) => {
      colorDataRef.current = colorImg;
      depthDataRef.current = depthImg;

      // Build initial point cloud
      const totalPixels = colorImg.width * colorImg.height;
      const maxPoints = 800_000;
      const sampleStep = Math.max(1, Math.ceil(Math.sqrt(totalPixels / maxPoints)));

      const geo = buildPointCloud(colorImg, depthImg, currentBaseRadius, currentDepthScale, sampleStep);
      setPointCount(geo.getAttribute('position').count);

      const mat = new THREE.PointsMaterial({
        size: currentPointSize,
        vertexColors: true,
        sizeAttenuation: true,
      });

      const points = new THREE.Points(geo, mat);
      scene.add(points);
      pointsRef.current = points;

      setLoading(false);
    }).catch((err) => {
      console.error('Failed to load images for point cloud:', err);
      setLoading(false);
    });

    // ── Pointer events ──
    const handlePointerDown = (e: PointerEvent) => {
      ptrDownRef.current = { x: e.clientX, y: e.clientY };
      isDraggingRef.current = false;

      const rect = container.getBoundingClientRect();
      mouseRef.current.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouseRef.current.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      raycasterRef.current.setFromCamera(mouseRef.current, camera);

      if (charGroupRef.current && charGroupRef.current.children.length > 0) {
        const hits = raycasterRef.current.intersectObjects(charGroupRef.current.children, true);
        if (hits.length > 0) {
          let target: THREE.Object3D = hits[0].object;
          while (target.parent && target.parent !== charGroupRef.current) target = target.parent;
          const charId = target.userData.characterId as string | undefined;
          if (charId) {
            dragRef.current = { id: charId, obj: target };
            controls.enabled = false;
            setSelectedCharId(charId);
            return;
          }
        }
      }
    };

    const handlePointerMove = (e: PointerEvent) => {
      const dx = e.clientX - ptrDownRef.current.x;
      const dy = e.clientY - ptrDownRef.current.y;
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) isDraggingRef.current = true;

      if (dragRef.current && isDraggingRef.current) {
        const rect = container.getBoundingClientRect();
        mouseRef.current.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
        mouseRef.current.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
        raycasterRef.current.setFromCamera(mouseRef.current, camera);

        const pt = new THREE.Vector3();
        if (raycasterRef.current.ray.intersectPlane(groundPlaneRef.current, pt)) {
          const maxR = currentBaseRadius * 0.8;
          pt.x = Math.max(-maxR, Math.min(maxR, pt.x));
          pt.z = Math.max(-maxR, Math.min(maxR, pt.z));
          dragRef.current.obj.position.set(pt.x, 0, pt.z);
        }
      }
    };

    const handlePointerUp = () => {
      if (dragRef.current) {
        if (isDraggingRef.current) {
          const pos = dragRef.current.obj.position;
          const id = dragRef.current.id;
          const updated = charsRef.current.map(c =>
            c.id === id ? { ...c, x: pos.x, z: pos.z } : c,
          );
          setChars(updated);
          onCharsUpdateRef.current?.(updated);
        }
        controls.enabled = true;
        dragRef.current = null;
      } else if (!isDraggingRef.current) {
        setSelectedCharId(null);
      }
    };

    container.addEventListener('pointerdown', handlePointerDown);
    container.addEventListener('pointermove', handlePointerMove);
    container.addEventListener('pointerup', handlePointerUp);

    // ── Animation ──
    const animate = () => {
      animIdRef.current = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const handleResize = () => {
      if (!container.clientWidth || !container.clientHeight) return;
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      container.removeEventListener('pointerdown', handlePointerDown);
      container.removeEventListener('pointermove', handlePointerMove);
      container.removeEventListener('pointerup', handlePointerUp);
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animIdRef.current);
      controls.dispose();
      scene.traverse((obj: THREE.Object3D) => {
        const o = obj as any;
        if (o.geometry) o.geometry.dispose();
        if (o.material) {
          const ms = Array.isArray(o.material) ? o.material : [o.material];
          for (const m of ms) { m.map?.dispose(); m.dispose(); }
        }
      });
      renderer.dispose();
      if (container.contains(renderer.domElement)) container.removeChild(renderer.domElement);
      sceneRef.current = null;
      cameraRef.current = null;
      rendererRef.current = null;
      controlsRef.current = null;
      pointsRef.current = null;
      charGroupRef.current = null;
      charObjsRef.current.clear();
      colorDataRef.current = null;
      depthDataRef.current = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, panoramaUrl, depthMapUrl]);

  // ── Update point size live ──
  useEffect(() => {
    if (pointsRef.current) {
      (pointsRef.current.material as THREE.PointsMaterial).size = currentPointSize;
    }
  }, [currentPointSize]);

  // ── Rebuild when depth scale or base radius changes ──
  useEffect(() => {
    rebuildPoints(currentDepthScale, currentBaseRadius);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentDepthScale, currentBaseRadius]);

  // ── Sync characters ──
  useEffect(() => {
    const group = charGroupRef.current;
    if (!group) return;
    const newIds = new Set(chars.map(c => c.id));
    for (const [id, obj] of charObjsRef.current.entries()) {
      if (!newIds.has(id)) { group.remove(obj); disposeObject(obj); charObjsRef.current.delete(id); }
    }
    for (const char of chars) {
      let obj = charObjsRef.current.get(char.id);
      if (!obj) { obj = createCharObject(char); charObjsRef.current.set(char.id, obj); group.add(obj); }
      obj.position.set(char.x, 0, char.z);
    }
  }, [chars]);

  // ── Selection ring ──
  useEffect(() => {
    for (const [id, obj] of charObjsRef.current.entries()) {
      const ring = obj.children.find(c => c.userData.isSelectionRing);
      if (ring) ring.visible = (id === selectedCharId);
    }
  }, [selectedCharId]);

  // ── Keyboard ──
  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCloseRef.current();
      if ((e.key === 'Delete' || e.key === 'Backspace') && selectedCharId) {
        e.preventDefault();
        const updated = charsRef.current.filter(c => c.id !== selectedCharId);
        setChars(updated);
        setSelectedCharId(null);
        onCharsUpdateRef.current?.(updated);
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isOpen, selectedCharId]);

  // ── Callbacks ──
  const handleAddChar = useCallback(() => {
    const idx = charsRef.current.length;
    const newChar: Character3D = {
      id: `char-${Date.now().toString(36)}`,
      name: `角色${idx + 1}`,
      x: (Math.random() - 0.5) * 4,
      z: (Math.random() - 0.5) * 4,
      color: CHAR_COLORS[idx % CHAR_COLORS.length],
    };
    const updated = [...charsRef.current, newChar];
    setChars(updated);
    setSelectedCharId(newChar.id);
    onCharsUpdateRef.current?.(updated);
  }, []);

  const handleResetView = useCallback(() => {
    if (!cameraRef.current || !controlsRef.current) return;
    cameraRef.current.position.set(0, 0, 0);
    cameraRef.current.fov = 75;
    cameraRef.current.updateProjectionMatrix();
    controlsRef.current.target.set(0, 0, -0.01);
    controlsRef.current.update();
  }, []);

  if (!isOpen) return null;

  return createPortal(
    <div style={{ position: 'fixed', inset: 0, zIndex: 9999, background: '#000', display: 'flex', flexDirection: 'column' }}>
      <div ref={containerRef} style={{ flex: 1, cursor: 'grab' }} />

      {loading && (
        <div style={{
          position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(0,0,0,0.8)', zIndex: 10,
        }}>
          <div style={{ textAlign: 'center', color: 'rgba(255,255,255,0.6)' }}>
            <div style={{ fontSize: 24, marginBottom: 8 }}>&#9696;</div>
            <div style={{ fontSize: 13 }}>构建 3D 点云中...</div>
          </div>
        </div>
      )}

      {/* Controls (top-left) */}
      <div style={{
        position: 'absolute', top: 16, left: 16, zIndex: 20,
        background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(12px)',
        borderRadius: 12, padding: '12px 14px', minWidth: 210,
        border: '1px solid rgba(255,255,255,0.08)',
      }}>
        <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', letterSpacing: 1, marginBottom: 8 }}>
          点云 3D 导演台
        </div>

        {/* Depth scale */}
        <div style={{ marginBottom: 6 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.35)' }}>深度强度</span>
            <span style={{ fontSize: 9, color: 'rgba(6,182,212,0.8)' }}>{currentDepthScale.toFixed(1)}</span>
          </div>
          <input
            type="range" min={0} max={8} step={0.1}
            value={currentDepthScale}
            onChange={e => setCurrentDepthScale(parseFloat(e.target.value))}
            style={{ width: '100%', accentColor: '#06b6d4' }}
          />
        </div>

        {/* Point size */}
        <div style={{ marginBottom: 6 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.35)' }}>点大小</span>
            <span style={{ fontSize: 9, color: 'rgba(6,182,212,0.8)' }}>{currentPointSize.toFixed(1)}</span>
          </div>
          <input
            type="range" min={0.5} max={6} step={0.1}
            value={currentPointSize}
            onChange={e => setCurrentPointSize(parseFloat(e.target.value))}
            style={{ width: '100%', accentColor: '#06b6d4' }}
          />
        </div>

        {/* Base radius */}
        <div style={{ marginBottom: 6 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.35)' }}>场景半径</span>
            <span style={{ fontSize: 9, color: 'rgba(6,182,212,0.8)' }}>{currentBaseRadius.toFixed(0)}</span>
          </div>
          <input
            type="range" min={3} max={30} step={1}
            value={currentBaseRadius}
            onChange={e => setCurrentBaseRadius(parseFloat(e.target.value))}
            style={{ width: '100%', accentColor: '#06b6d4' }}
          />
        </div>

        <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.25)', lineHeight: 1.6 }}>
          点数: {pointCount.toLocaleString()}<br />
          VR 全景 + 深度图 → 3D 点云<br />
          拖拽旋转 | 滚轮缩放
        </div>
      </div>

      {/* Character panel (top-right) */}
      <div style={{
        position: 'absolute', top: 16, right: 16, zIndex: 20,
        background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(12px)',
        borderRadius: 12, padding: '10px 12px', minWidth: 160,
        border: '1px solid rgba(255,255,255,0.08)',
        maxHeight: 'calc(100vh - 120px)', overflowY: 'auto',
      }}>
        <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', letterSpacing: 1, marginBottom: 8 }}>
          角色 ({chars.length})
        </div>
        {chars.map(c => (
          <div key={c.id}
            onClick={() => setSelectedCharId(c.id === selectedCharId ? null : c.id)}
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '5px 6px', borderRadius: 6, cursor: 'pointer', marginBottom: 2,
              background: c.id === selectedCharId ? 'rgba(6,182,212,0.15)' : 'transparent',
            }}
          >
            <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: c.color || CHAR_COLORS[0] }} />
            <span style={{ fontSize: 11, color: c.id === selectedCharId ? 'rgba(6,182,212,1)' : 'rgba(255,255,255,0.7)', flex: 1 }}>{c.name}</span>
          </div>
        ))}
        <button onClick={handleAddChar} style={{
          width: '100%', marginTop: 6, padding: '6px 0', borderRadius: 6,
          background: 'rgba(6,182,212,0.12)', border: '1px solid rgba(6,182,212,0.25)',
          color: 'rgba(6,182,212,0.8)', fontSize: 11, cursor: 'pointer',
        }}>+ 添加角色</button>
        {selectedCharId && (
          <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.25)', marginTop: 6, textAlign: 'center' }}>
            拖拽移动 | Delete 删除
          </div>
        )}
      </div>

      {/* Bottom */}
      <div style={{
        position: 'absolute', bottom: 24, left: '50%', transform: 'translateX(-50%)',
        display: 'flex', gap: 8, zIndex: 20,
      }}>
        <button onClick={handleResetView} style={{
          padding: '10px 20px', borderRadius: 12,
          background: 'rgba(255,255,255,0.12)', border: '1px solid rgba(255,255,255,0.15)',
          color: 'rgba(255,255,255,0.8)', fontSize: 13, cursor: 'pointer', backdropFilter: 'blur(8px)',
        }}>重置视角</button>
        <button onClick={onClose} style={{
          padding: '10px 20px', borderRadius: 12,
          background: 'rgba(255,255,255,0.12)', border: '1px solid rgba(255,255,255,0.15)',
          color: 'rgba(255,255,255,0.8)', fontSize: 13, cursor: 'pointer', backdropFilter: 'blur(8px)',
        }}>关闭</button>
      </div>

      <div style={{ position: 'absolute', bottom: 8, right: 16, zIndex: 20, fontSize: 10, color: 'rgba(255,255,255,0.2)' }}>
        ESC 关闭 | 拖拽旋转 | 滚轮缩放
      </div>
    </div>,
    document.body,
  );
}
