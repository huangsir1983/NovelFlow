'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import { createPortal } from 'react-dom';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import type { ViewPoint } from '../../types/canvas';
import {
  sphericalToCartesian,
  cartesianToSpherical,
  cameraTargetFromAngles,
} from './panoramaHelpers';
import { panoramaVertexShader, panoramaFragmentShader } from './panoramaShader';

interface PanoramaViewerProps {
  panoramaUrl: string;
  isOpen: boolean;
  onClose: () => void;
  onScreenshot?: (base64: string, viewAngle: { yaw: number; pitch: number; fov: number }) => void;
  viewpoints?: ViewPoint[];
  activeViewpointId?: string;
  onViewpointChange?: (vpId: string) => void;
  onViewpointsUpdate?: (vps: ViewPoint[]) => void;
  editMode?: boolean;
}

// ── Hotspot sprite texture cache ──
const _spriteCanvasCache = new Map<string, HTMLCanvasElement>();
function _makeHotspotTexture(label: string, isActive: boolean): HTMLCanvasElement {
  const key = `${label}:${isActive}`;
  const cached = _spriteCanvasCache.get(key);
  if (cached) return cached;

  const canvas = document.createElement('canvas');
  canvas.width = 512;
  canvas.height = 160;
  const ctx = canvas.getContext('2d')!;

  ctx.fillStyle = isActive ? 'rgba(6,182,212,0.85)' : 'rgba(255,255,255,0.22)';
  ctx.beginPath();
  ctx.roundRect(8, 8, 496, 144, 28);
  ctx.fill();

  ctx.strokeStyle = isActive ? 'rgba(6,182,212,1)' : 'rgba(255,255,255,0.5)';
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.roundRect(8, 8, 496, 144, 28);
  ctx.stroke();

  ctx.fillStyle = isActive ? '#fff' : 'rgba(6,182,212,0.9)';
  ctx.beginPath();
  ctx.arc(60, 80, 14, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = isActive ? '#fff' : 'rgba(255,255,255,0.9)';
  ctx.font = 'bold 48px sans-serif';
  ctx.textBaseline = 'middle';
  ctx.fillText(label.slice(0, 8), 90, 84);

  _spriteCanvasCache.set(key, canvas);
  return canvas;
}

// ── Auto-correction: factor in distance + zoom + view direction ──
// Three factors combined:
//   1. distanceFactor: how far camera is from sphere center (0–1)
//   2. fovScale: narrower FOV → distortion more visible → more correction
//   3. dirFactor: looking toward near wall (offset direction) → more distortion
function computeAutoCorrection(
  posX: number, posZ: number, fov: number,
  viewDirX?: number, viewDirZ?: number,
): number {
  const distance = Math.sqrt(posX * posX + posZ * posZ);
  if (distance < 1) return 0; // at center, no correction needed

  const distanceFactor = Math.pow(distance / POS_RANGE, 0.6); // exponential: kicks in harder at moderate distances
  const fovScale = 75 / fov; // neutral at default FOV=75; zoomed in → >1

  // Direction factor: dot(viewDir, offsetDir)
  //   near-wall (dot>0): tunnel compression → strong penalty (0.7), correction worsens it
  //   perpendicular (dot≈0): curvature → full correction
  //   far-wall (dot<0): convex-mirror bulge → lighter penalty (0.45), needs more correction
  let dirFactor = 1;
  if (viewDirX !== undefined && viewDirZ !== undefined) {
    const viewLen = Math.sqrt(viewDirX * viewDirX + viewDirZ * viewDirZ);
    if (viewLen > 0.001) {
      const dot = (viewDirX / viewLen) * (posX / distance) + (viewDirZ / viewLen) * (posZ / distance);
      dirFactor = dot > 0
        ? 1.0 - 0.7 * dot      // near-wall: same as before
        : 1.0 + 0.45 * dot;    // far-wall: gentler penalty (dot is negative)
    }
  }

  const rawCorr = Math.min(Math.max(distanceFactor * fovScale * dirFactor, 0), 1);

  // Cap correction at extreme distances to limit tunnel/barrel distortion.
  const distRatio = distance / POS_RANGE;
  const maxCorr = 1.0 - 0.50 * Math.pow(distRatio, 1.5);

  return Math.round(Math.min(rawCorr, maxCorr) * 100) / 100;
}
// Pre-allocated vectors for animation loop (avoid GC)
let _viewDirVec: THREE.Vector3 | null = null;
let _centerVertexVec: THREE.Vector3 | null = null;
let _rayDirVec: THREE.Vector3 | null = null;
let _effectiveDirVec: THREE.Vector3 | null = null;

// ── Panorama sphere constants ──
// Change SPHERE_RADIUS to resize; all derived values update automatically.
const SPHERE_RADIUS = 500;
const HOTSPOT_RADIUS = SPHERE_RADIUS - 10;   // hotspot labels sit just inside the sphere
const POS_RANGE = SPHERE_RADIUS * 0.8;       // camera offset range (80% of radius)

// ── Minimap polar projection helper ──
const MINIMAP_SIZE = 180;
const MINIMAP_RADIUS = MINIMAP_SIZE / 2 - 4; // leave border

function generateMinimapBackground(img: HTMLImageElement): ImageData {
  const size = MINIMAP_SIZE;
  const cx = size / 2;
  const cy = size / 2;
  const r = MINIMAP_RADIUS;

  // Sample equirectangular image via offscreen canvas
  const srcCanvas = document.createElement('canvas');
  const sw = Math.min(img.naturalWidth, 512);
  const sh = Math.min(img.naturalHeight, 256);
  srcCanvas.width = sw;
  srcCanvas.height = sh;
  const srcCtx = srcCanvas.getContext('2d')!;
  srcCtx.drawImage(img, 0, 0, sw, sh);
  const srcData = srcCtx.getImageData(0, 0, sw, sh);

  const out = new ImageData(size, size);
  for (let py = 0; py < size; py++) {
    for (let px = 0; px < size; px++) {
      // Mirror both axes: negate so minimap top=south, left=east (matches actual panorama orientation)
      const dx = cx - px;
      const dy = cy - py;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist > r) continue;

      // Polar → equirectangular
      const theta = Math.atan2(dy, dx); // azimuth on canvas (0=right, π/2=down)
      const phi = (dist / r) * (Math.PI / 2); // 0=nadir, π/2=horizon

      // Offset 0.75 so minimap UP=forward(-Z), RIGHT=right(+X) — matches viewpoint dots & FOV wedge
      const eqU = ((theta / (2 * Math.PI) + 0.75) % 1.0);
      const eqV = 0.5 + phi / Math.PI; // bottom half of equirect

      const sx = Math.floor(eqU * (sw - 1));
      const sy = Math.floor(Math.min(eqV, 0.999) * (sh - 1));
      const si = (sy * sw + sx) * 4;
      const di = (py * size + px) * 4;

      out.data[di] = srcData.data[si];
      out.data[di + 1] = srcData.data[si + 1];
      out.data[di + 2] = srcData.data[si + 2];
      out.data[di + 3] = Math.round(srcData.data[si + 3] * 0.5); // semi-transparent
    }
  }
  return out;
}

// ── Minimap sub-component ──
const ORIGIN_ID = '__origin__';

function Minimap({
  viewpoints,
  activeId,
  backgroundData,
  cameraYaw,
  cameraFov,
  originPos,
  originSelected,
  onPositionChange,
  onOriginChange,
  onOriginSelect,
}: {
  viewpoints: ViewPoint[];
  activeId: string | undefined;
  backgroundData: ImageData | null;
  cameraYaw: number;
  cameraFov: number;
  originPos: { posX: number; posZ: number };
  originSelected: boolean;
  onPositionChange: (vpId: string, posX: number, posZ: number) => void;
  onOriginChange: (posX: number, posZ: number) => void;
  onOriginSelect: () => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const draggingRef = useRef<string | null>(null);

  // Draw minimap
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d')!;
    const cx = MINIMAP_SIZE / 2;
    const cy = MINIMAP_SIZE / 2;
    const r = MINIMAP_RADIUS;

    ctx.clearRect(0, 0, MINIMAP_SIZE, MINIMAP_SIZE);

    // Background circle
    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.clip();

    // Draw polar projection background
    if (backgroundData) {
      ctx.putImageData(backgroundData, 0, 0);
    }

    // Dark overlay for contrast
    ctx.fillStyle = 'rgba(0,0,0,0.4)';
    ctx.fillRect(0, 0, MINIMAP_SIZE, MINIMAP_SIZE);
    ctx.restore();

    // Circle border
    ctx.strokeStyle = 'rgba(255,255,255,0.15)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.stroke();

    // Center crosshair
    ctx.strokeStyle = 'rgba(255,255,255,0.12)';
    ctx.lineWidth = 0.5;
    ctx.beginPath();
    ctx.moveTo(cx - 8, cy); ctx.lineTo(cx + 8, cy);
    ctx.moveTo(cx, cy - 8); ctx.lineTo(cx, cy + 8);
    ctx.stroke();

    // Grid rings
    for (const frac of [0.33, 0.66]) {
      ctx.strokeStyle = 'rgba(255,255,255,0.06)';
      ctx.beginPath();
      ctx.arc(cx, cy, r * frac, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Origin point — draggable & selectable
    const ox = cx - (originPos.posX / POS_RANGE) * r;
    const oy = cy - (originPos.posZ / POS_RANGE) * r;
    ctx.fillStyle = originSelected ? 'rgba(251,191,36,1)' : 'rgba(251,191,36,0.6)';
    ctx.beginPath();
    ctx.arc(ox, oy, originSelected ? 5 : 3.5, 0, Math.PI * 2);
    ctx.fill();
    if (originSelected) {
      ctx.strokeStyle = 'rgba(251,191,36,0.5)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(ox, oy, 8, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.fillStyle = originSelected ? 'rgba(251,191,36,0.9)' : 'rgba(251,191,36,0.5)';
    ctx.font = '8px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('初始', ox, oy - 9);

    // Draw viewpoint dots (linear: POS_RANGE=400 maps to edge, mirrored)
    for (const vp of viewpoints) {
      const isActive = vp.id === activeId;
      const x = cx - ((vp.posX ?? 0) / POS_RANGE) * r;
      const y = cy - ((vp.posZ ?? 0) / POS_RANGE) * r;

      // Dot
      ctx.fillStyle = isActive ? 'rgba(6,182,212,1)' : 'rgba(255,255,255,0.6)';
      ctx.beginPath();
      ctx.arc(x, y, isActive ? 5 : 3, 0, Math.PI * 2);
      ctx.fill();

      // Label
      ctx.fillStyle = isActive ? 'rgba(6,182,212,0.9)' : 'rgba(255,255,255,0.5)';
      ctx.font = '9px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(vp.label.slice(0, 4), x, y - 8);
    }

    // Draw FOV direction wedge from active viewpoint position (linear, mirrored)
    const activeVp = viewpoints.find(v => v.id === activeId);
    if (activeVp) {
      const ax = cx - ((activeVp.posX ?? 0) / POS_RANGE) * r;
      const ay = cy - ((activeVp.posZ ?? 0) / POS_RANGE) * r;
      // Convert yaw to canvas angle: yaw 0°=-Z(up), 90°=+X(right) → canvas 0=right
      const centerAngle = cameraYaw * Math.PI / 180 - Math.PI / 2;
      const halfFov = (cameraFov * Math.PI / 180) / 2;

      ctx.save();
      ctx.fillStyle = 'rgba(6,182,212,0.18)';
      ctx.strokeStyle = 'rgba(6,182,212,0.6)';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(ax, ay);
      ctx.arc(ax, ay, r * 0.85, centerAngle - halfFov, centerAngle + halfFov);
      ctx.lineTo(ax, ay);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      ctx.restore();
    }
  }, [viewpoints, activeId, backgroundData, cameraYaw, cameraFov, originPos, originSelected]);

  // Mouse interaction (linear: POS_RANGE=400 at edge, mirrored)
  const getMapPos = useCallback((e: React.MouseEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;
    const dx = px - MINIMAP_SIZE / 2;
    const dy = py - MINIMAP_SIZE / 2;
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist > MINIMAP_RADIUS) return null;
    const posX = -(dx / MINIMAP_RADIUS) * POS_RANGE;
    const posZ = -(dy / MINIMAP_RADIUS) * POS_RANGE;
    return { posX: Math.round(posX), posZ: Math.round(posZ), px, py };
  }, []);

  const findNearPoint = useCallback((px: number, py: number) => {
    const cx = MINIMAP_SIZE / 2;
    const cy = MINIMAP_SIZE / 2;
    // Check origin point
    const originPx = cx - (originPos.posX / POS_RANGE) * MINIMAP_RADIUS;
    const originPy = cy - (originPos.posZ / POS_RANGE) * MINIMAP_RADIUS;
    if (Math.abs(px - originPx) < 10 && Math.abs(py - originPy) < 10) return ORIGIN_ID;
    for (const vp of viewpoints) {
      const vpx = cx - ((vp.posX ?? 0) / POS_RANGE) * MINIMAP_RADIUS;
      const vpy = cy - ((vp.posZ ?? 0) / POS_RANGE) * MINIMAP_RADIUS;
      if (Math.abs(px - vpx) < 10 && Math.abs(py - vpy) < 10) return vp.id;
    }
    return null;
  }, [viewpoints, originPos]);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    const pos = getMapPos(e);
    if (!pos) return;
    const nearId = findNearPoint(pos.px, pos.py);
    if (nearId === ORIGIN_ID) {
      draggingRef.current = ORIGIN_ID;
      onOriginSelect();
    } else if (nearId) {
      draggingRef.current = nearId;
    } else if (activeId) {
      onPositionChange(activeId, pos.posX, pos.posZ);
    }
  }, [getMapPos, findNearPoint, activeId, onPositionChange, onOriginSelect]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!draggingRef.current) return;
    const pos = getMapPos(e);
    if (pos) {
      if (draggingRef.current === ORIGIN_ID) {
        onOriginChange(pos.posX, pos.posZ);
      } else {
        onPositionChange(draggingRef.current, pos.posX, pos.posZ);
      }
    }
  }, [getMapPos, onPositionChange, onOriginChange]);

  const handleMouseUp = useCallback(() => {
    draggingRef.current = null;
  }, []);

  return (
    <canvas
      ref={canvasRef}
      width={MINIMAP_SIZE}
      height={MINIMAP_SIZE}
      style={{
        width: MINIMAP_SIZE, height: MINIMAP_SIZE,
        borderRadius: '50%', cursor: 'crosshair',
        border: '1px solid rgba(255,255,255,0.1)',
      }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    />
  );
}



// ══════════════════════════════════════════════════════════════════
// Main Component
// ══════════════════════════════════════════════════════════════════

export function PanoramaViewer({
  panoramaUrl,
  isOpen,
  onClose,
  onScreenshot,
  viewpoints = [],
  activeViewpointId,
  onViewpointChange,
  onViewpointsUpdate,
  editMode = false,
}: PanoramaViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const materialRef = useRef<THREE.ShaderMaterial | null>(null);
  const animationIdRef = useRef<number>(0);
  const hotspotsGroupRef = useRef<THREE.Group | null>(null);
  const raycasterRef = useRef<THREE.Raycaster>(new THREE.Raycaster());
  const mouseRef = useRef<THREE.Vector2>(new THREE.Vector2());
  const isDraggingRef = useRef(false);
  const pointerDownPosRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const editModeRef = useRef(editMode);
  const navigateRef = useRef<(vpId: string) => void>(() => {});
  const localViewpointsRef = useRef<ViewPoint[]>(viewpoints);
  const activeIdRef = useRef<string | undefined>(activeViewpointId);
  const onViewpointsUpdateRef = useRef(onViewpointsUpdate);
  // Camera offset stored independently — OrbitControls manages camera.position for rotation,
  // this ref holds the desired offset for the shader's parallax calculation.
  const cameraOffsetRef = useRef<{ x: number; y: number; z: number }>({ x: 0, y: 0, z: 0 });

  const [loading, setLoading] = useState(true);
  const [activeId, setActiveId] = useState<string | undefined>(activeViewpointId);
  const [localViewpoints, setLocalViewpoints] = useState<ViewPoint[]>(viewpoints);
  const [labelInput, setLabelInput] = useState<{ show: boolean; yaw: number; pitch: number; value: string }>({
    show: false, yaw: 0, pitch: 0, value: '',
  });
  const [minimapBg, setMinimapBg] = useState<ImageData | null>(null);
  const [liveCorrection, setLiveCorrection] = useState(0);
  const [liveCameraYaw, setLiveCameraYaw] = useState(0);
  const [liveCameraFov, setLiveCameraFov] = useState(75);
  const [originPos, setOriginPos] = useState<{ posX: number; posZ: number }>({ posX: 0, posZ: 0 });
  const [originSelected, setOriginSelected] = useState(false);

  // Sync from props
  useEffect(() => { editModeRef.current = editMode; }, [editMode]);
  useEffect(() => { setLocalViewpoints(viewpoints); }, [viewpoints]);
  useEffect(() => { setActiveId(activeViewpointId); }, [activeViewpointId]);
  useEffect(() => { localViewpointsRef.current = localViewpoints; }, [localViewpoints]);
  useEffect(() => { activeIdRef.current = activeId; }, [activeId]);
  useEffect(() => { onViewpointsUpdateRef.current = onViewpointsUpdate; }, [onViewpointsUpdate]);

  // Auto-select first viewpoint if none active + sync offset ref
  useEffect(() => {
    if (!activeId && localViewpoints.length > 0) {
      const defaultVp = localViewpoints.find(v => v.isDefault) ?? localViewpoints[0];
      setActiveId(defaultVp.id);
      cameraOffsetRef.current = { x: defaultVp.posX ?? 0, y: defaultVp.posY ?? 0, z: defaultVp.posZ ?? 0 };
    } else if (activeId) {
      const vp = localViewpoints.find(v => v.id === activeId);
      if (vp) cameraOffsetRef.current = { x: vp.posX ?? 0, y: vp.posY ?? 0, z: vp.posZ ?? 0 };
    }
  }, [activeId, localViewpoints]);

  // Persist default viewpoints on first open (they come from canvasLayout, not yet saved to backend)
  const defaultsPersisted = useRef(false);
  useEffect(() => {
    if (isOpen && !defaultsPersisted.current && localViewpoints.length > 0 && localViewpoints[0].id.startsWith('vp-default-')) {
      defaultsPersisted.current = true;
      onViewpointsUpdate?.(localViewpoints);
    }
  }, [isOpen, localViewpoints, onViewpointsUpdate]);

  // Initialize Three.js scene with custom shader
  useEffect(() => {
    if (!isOpen || !containerRef.current) return;

    const container = containerRef.current;

    const scene = new THREE.Scene();
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 1000);
    camera.position.set(0, 0, 0.1);
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Panorama sphere with custom ShaderMaterial (no geometry.scale inversion, use BackSide)
    const geometry = new THREE.SphereGeometry(SPHERE_RADIUS, 60, 40);
    const material = new THREE.ShaderMaterial({
      uniforms: {
        uPanorama: { value: null },
        uCameraOffset: { value: new THREE.Vector3(0, 0, 0) },
        uCorrectionStrength: { value: 0.5 },
      },
      vertexShader: panoramaVertexShader,
      fragmentShader: panoramaFragmentShader,
      side: THREE.BackSide,
    });
    const sphere = new THREE.Mesh(geometry, material);
    scene.add(sphere);
    materialRef.current = material;

    // Hotspots group
    const hotspotsGroup = new THREE.Group();
    scene.add(hotspotsGroup);
    hotspotsGroupRef.current = hotspotsGroup;

    // Load panorama texture
    setLoading(true);
    const applyTexture = (texture: THREE.Texture) => {
      texture.colorSpace = THREE.SRGBColorSpace;
      texture.minFilter = THREE.LinearFilter;
      texture.magFilter = THREE.LinearFilter;
      material.uniforms.uPanorama.value = texture;
      material.needsUpdate = true;
      setLoading(false);
    };

    const loader = new THREE.TextureLoader();
    loader.load(
      panoramaUrl,
      (texture) => applyTexture(texture),
      undefined,
      () => {
        if (!panoramaUrl.startsWith('data:')) {
          const img = new Image();
          img.crossOrigin = 'anonymous';
          img.onload = () => {
            const tex = new THREE.Texture(img);
            tex.needsUpdate = true;
            applyTexture(tex);
          };
          img.onerror = () => setLoading(false);
          img.src = panoramaUrl;
        } else {
          setLoading(false);
        }
      },
    );

    // Generate minimap background
    const bgImg = new Image();
    bgImg.crossOrigin = 'anonymous';
    bgImg.onload = () => {
      const data = generateMinimapBackground(bgImg);
      setMinimapBg(data);
    };
    bgImg.src = panoramaUrl;

    // Orbit controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableZoom = false;
    controls.enablePan = false;
    controls.rotateSpeed = 0.5;
    controlsRef.current = controls;

    // FOV-based zoom (shader correction handled by animation loop)
    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();
      camera.fov = Math.max(20, Math.min(100, camera.fov + e.deltaY * 0.05));
      camera.updateProjectionMatrix();
    };
    container.addEventListener('wheel', handleWheel, { passive: false });

    // Drag vs click tracking
    const handlePointerDown = (e: PointerEvent) => {
      isDraggingRef.current = false;
      pointerDownPosRef.current = { x: e.clientX, y: e.clientY };
    };
    const handlePointerMove = (e: PointerEvent) => {
      const dx = e.clientX - pointerDownPosRef.current.x;
      const dy = e.clientY - pointerDownPosRef.current.y;
      if (Math.abs(dx) > 5 || Math.abs(dy) > 5) isDraggingRef.current = true;
    };
    const handlePointerUp = (e: PointerEvent) => {
      if (isDraggingRef.current) return;

      const rect = container.getBoundingClientRect();
      mouseRef.current.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouseRef.current.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      raycasterRef.current.setFromCamera(mouseRef.current, camera);

      // Check hotspot clicks
      if (hotspotsGroupRef.current && hotspotsGroupRef.current.children.length > 0) {
        const intersects = raycasterRef.current.intersectObjects(hotspotsGroupRef.current.children);
        if (intersects.length > 0) {
          const vpId = intersects[0].object.userData.viewpointId as string;
          if (vpId) { navigateRef.current(vpId); return; }
        }
      }

      // Edit mode: click on sphere to place new viewpoint
      if (editModeRef.current) {
        const dir = raycasterRef.current.ray.direction;
        const { yaw, pitch } = cartesianToSpherical(dir.x * SPHERE_RADIUS, dir.y * SPHERE_RADIUS, dir.z * SPHERE_RADIUS);
        setLabelInput({ show: true, yaw, pitch, value: '' });
      }
    };
    container.addEventListener('pointerdown', handlePointerDown);
    container.addEventListener('pointermove', handlePointerMove);
    container.addEventListener('pointerup', handlePointerUp);

    // Animation loop — live auto-correction every frame
    if (!_viewDirVec) _viewDirVec = new THREE.Vector3();
    if (!_centerVertexVec) _centerVertexVec = new THREE.Vector3();
    if (!_rayDirVec) _rayDirVec = new THREE.Vector3();
    if (!_effectiveDirVec) _effectiveDirVec = new THREE.Vector3();
    let _lastCorrDisplay = -1;
    let _corrFrameCount = 0;
    const animate = () => {
      animationIdRef.current = requestAnimationFrame(animate);
      controls.update();

      // Auto-correct distortion using stored offset (NOT camera.position, which OrbitControls resets)
      const mat = materialRef.current;
      if (mat) {
        const off = cameraOffsetRef.current;
        mat.uniforms.uCameraOffset.value.set(off.x, off.y, off.z);

        // View direction = where camera actually looks (NOT controls.target which stays at origin)
        camera.getWorldDirection(_viewDirVec!);
        const autoCorr = computeAutoCorrection(
          off.x, off.z,
          camera.fov,
          _viewDirVec!.x, _viewDirVec!.z,
        );
        mat.uniforms.uCorrectionStrength.value = autoCorr;

        // Throttle React state updates for display (~10 fps)
        _corrFrameCount++;
        if (_corrFrameCount >= 6) {
          _corrFrameCount = 0;
          if (autoCorr !== _lastCorrDisplay) {
            _lastCorrDisplay = autoCorr;
            setLiveCorrection(autoCorr);
          }
          // Compute effective viewing direction for minimap FOV wedge.
          // The shader remaps via mix(sphereDir, rayDir, correction), so the effective
          // center-of-screen direction differs from camera.forward when offset is large.
          // Center vertex on sphere ≈ SPHERE_RADIUS × camera.forward
          _centerVertexVec!.copy(_viewDirVec!).multiplyScalar(SPHERE_RADIUS);
          // rayDir = normalize(centerVertex - offset)
          _rayDirVec!.set(
            _centerVertexVec!.x - off.x,
            _centerVertexVec!.y - off.y,
            _centerVertexVec!.z - off.z,
          ).normalize();
          // effectiveDir = normalize(mix(sphereDir, rayDir, correction))
          const c = autoCorr;
          _effectiveDirVec!.set(
            _viewDirVec!.x * (1 - c) + _rayDirVec!.x * c,
            _viewDirVec!.y * (1 - c) + _rayDirVec!.y * c,
            _viewDirVec!.z * (1 - c) + _rayDirVec!.z * c,
          ).normalize();
          // Direct canvas angle: atan2(z, x) maps XZ plane → minimap (right=+X, down=+Z)
          setLiveCameraYaw(Math.atan2(_effectiveDirVec!.z, _effectiveDirVec!.x) * 180 / Math.PI + 90);
          setLiveCameraFov(Math.round(camera.fov));
        }
      }

      renderer.render(scene, camera);
    };
    animate();

    const handleResize = () => {
      if (!container) return;
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      container.removeEventListener('wheel', handleWheel);
      container.removeEventListener('pointerdown', handlePointerDown);
      container.removeEventListener('pointermove', handlePointerMove);
      container.removeEventListener('pointerup', handlePointerUp);
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationIdRef.current);
      controls.dispose();
      renderer.dispose();
      geometry.dispose();
      material.dispose();
      if (material.uniforms.uPanorama.value) material.uniforms.uPanorama.value.dispose();
      hotspotsGroup.children.forEach(child => {
        if (child instanceof THREE.Sprite) {
          child.material.map?.dispose();
          child.material.dispose();
        }
      });
      if (container.contains(renderer.domElement)) container.removeChild(renderer.domElement);
      sceneRef.current = null;
      cameraRef.current = null;
      rendererRef.current = null;
      controlsRef.current = null;
      materialRef.current = null;
      hotspotsGroupRef.current = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, panoramaUrl]);

  // Update hotspot sprites
  useEffect(() => {
    const group = hotspotsGroupRef.current;
    if (!group) return;
    while (group.children.length > 0) {
      const child = group.children[0];
      if (child instanceof THREE.Sprite) { child.material.map?.dispose(); child.material.dispose(); }
      group.remove(child);
    }
    for (const vp of localViewpoints) {
      const isActive = vp.id === activeId;
      const canvasTex = _makeHotspotTexture(vp.label, isActive);
      const texture = new THREE.CanvasTexture(canvasTex);
      const spriteMat = new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false });
      const sprite = new THREE.Sprite(spriteMat);
      const pos = sphericalToCartesian(vp.yaw, vp.pitch, HOTSPOT_RADIUS);
      sprite.position.set(pos.x, pos.y, pos.z);
      sprite.scale.set(70, 22, 1);
      sprite.userData.viewpointId = vp.id;
      group.add(sprite);
    }
  }, [localViewpoints, activeId, isOpen]);

  // Navigate to viewpoint (animation loop handles auto-correction)
  const _navigateToViewpoint = useCallback((vpId: string) => {
    const vp = localViewpoints.find(v => v.id === vpId);
    if (!vp || !cameraRef.current || !controlsRef.current) return;

    const camera = cameraRef.current;
    const controls = controlsRef.current;

    const target = cameraTargetFromAngles(vp.yaw, vp.pitch);
    const startFov = camera.fov;
    const endFov = vp.fov;
    const startTarget = controls.target.clone();
    const endTarget = new THREE.Vector3(target.x, target.y, target.z);
    const startOff = { ...cameraOffsetRef.current };
    const endOff = { x: vp.posX ?? 0, y: vp.posY ?? 0, z: vp.posZ ?? 0 };

    const duration = 300;
    const startTime = performance.now();

    const animateTransition = (now: number) => {
      const t = Math.min((now - startTime) / duration, 1);
      const ease = t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;

      controls.target.lerpVectors(startTarget, endTarget, ease);
      camera.fov = startFov + (endFov - startFov) * ease;
      // Animate offset ref (NOT camera.position — OrbitControls owns that)
      cameraOffsetRef.current = {
        x: startOff.x + (endOff.x - startOff.x) * ease,
        y: startOff.y + (endOff.y - startOff.y) * ease,
        z: startOff.z + (endOff.z - startOff.z) * ease,
      };
      camera.updateProjectionMatrix();
      controls.update();

      if (t < 1) requestAnimationFrame(animateTransition);
    };
    requestAnimationFrame(animateTransition);

    setActiveId(vpId);
    setOriginSelected(false);
    onViewpointChange?.(vpId);
  }, [localViewpoints, onViewpointChange]);
  navigateRef.current = _navigateToViewpoint;

  // Get current camera state
  const _getCurrentState = useCallback(() => {
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    const mat = materialRef.current;
    const off = cameraOffsetRef.current;
    if (!camera || !controls) return { yaw: 0, pitch: 0, fov: 75, posX: 0, posY: 0, posZ: 0, correctionStrength: 0.5 };
    const dir = camera.getWorldDirection(new THREE.Vector3());
    const { yaw, pitch } = cartesianToSpherical(dir.x, dir.y, dir.z);
    return {
      yaw: Math.round(yaw * 10) / 10,
      pitch: Math.round(pitch * 10) / 10,
      fov: Math.round(camera.fov * 10) / 10,
      posX: Math.round(off.x),
      posY: Math.round(off.y),
      posZ: Math.round(off.z),
      correctionStrength: mat ? Math.round((mat.uniforms.uCorrectionStrength.value as number) * 100) / 100 : 0.5,
    };
  }, []);

  // Screenshot
  const handleScreenshot = useCallback(() => {
    const renderer = rendererRef.current;
    const scene = sceneRef.current;
    const camera = cameraRef.current;
    const container = containerRef.current;
    const hotspotsGroup = hotspotsGroupRef.current;
    if (!renderer || !scene || !camera || !container) return;

    const origW = container.clientWidth;
    const origH = container.clientHeight;

    if (hotspotsGroup) hotspotsGroup.visible = false;

    renderer.setSize(1920, 1080);
    camera.aspect = 1920 / 1080;
    camera.updateProjectionMatrix();
    renderer.render(scene, camera);

    const dataUrl = renderer.domElement.toDataURL('image/jpeg', 0.95);

    if (hotspotsGroup) hotspotsGroup.visible = true;
    renderer.setSize(origW, origH);
    camera.aspect = origW / origH;
    camera.updateProjectionMatrix();

    const base64 = dataUrl.split(',')[1] || dataUrl;
    const state = _getCurrentState();
    onScreenshot?.(base64, { yaw: state.yaw, pitch: state.pitch, fov: state.fov });
  }, [onScreenshot, _getCurrentState]);

  // Reset view
  const handleRecenter = useCallback(() => {
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!camera || !controls) return;
    camera.fov = 75;
    camera.updateProjectionMatrix();
    controls.target.set(0, 0, 0);
    controls.update();
    cameraOffsetRef.current = { x: 0, y: 0, z: 0 };
  }, []);

  // Save current view as new viewpoint
  const handleSaveCurrentView = useCallback(() => {
    const state = _getCurrentState();
    setLabelInput({ show: true, yaw: state.yaw, pitch: state.pitch, value: '' });
  }, [_getCurrentState]);

  // Confirm new viewpoint label
  const handleConfirmLabel = useCallback(() => {
    if (!labelInput.value.trim()) {
      setLabelInput(prev => ({ ...prev, show: false }));
      return;
    }
    const state = _getCurrentState();
    const newVp: ViewPoint = {
      id: `vp-${Date.now().toString(36)}`,
      label: labelInput.value.trim(),
      yaw: state.yaw,
      pitch: state.pitch,
      fov: state.fov,
      posX: state.posX,
      posY: state.posY,
      posZ: state.posZ,
      correctionStrength: state.correctionStrength,
      isDefault: localViewpoints.length === 0,
    };
    const updated = [...localViewpoints, newVp];
    setLocalViewpoints(updated);
    setActiveId(newVp.id);
    setLabelInput({ show: false, yaw: 0, pitch: 0, value: '' });
    onViewpointsUpdate?.(updated);
    onViewpointChange?.(newVp.id);
  }, [labelInput, localViewpoints, onViewpointsUpdate, onViewpointChange, _getCurrentState]);

  // Delete viewpoint
  const handleDeleteViewpoint = useCallback((vpId: string) => {
    const updated = localViewpoints.filter(v => v.id !== vpId);
    setLocalViewpoints(updated);
    if (activeId === vpId) setActiveId(updated[0]?.id);
    onViewpointsUpdate?.(updated);
  }, [localViewpoints, activeId, onViewpointsUpdate]);

  // Minimap position change → update offset ref (shader handled by animation loop)
  const handleMinimapPositionChange = useCallback((vpId: string, posX: number, posZ: number) => {
    const updated = localViewpoints.map(vp =>
      vp.id === vpId ? { ...vp, posX, posZ } : vp,
    );
    setLocalViewpoints(updated);

    // Update offset ref — animation loop reads this for shader uniforms
    if (vpId === activeId) {
      cameraOffsetRef.current = { ...cameraOffsetRef.current, x: posX, z: posZ };
    }

    onViewpointsUpdate?.(updated);
  }, [localViewpoints, activeId, onViewpointsUpdate]);

  // Origin point handlers
  const handleOriginSelect = useCallback(() => {
    setOriginSelected(true);
    cameraOffsetRef.current = { ...cameraOffsetRef.current, x: originPos.posX, z: originPos.posZ };
  }, [originPos]);

  const handleOriginChange = useCallback((posX: number, posZ: number) => {
    setOriginPos({ posX, posZ });
    if (originSelected) {
      cameraOffsetRef.current = { ...cameraOffsetRef.current, x: posX, z: posZ };
    }
  }, [originSelected]);


  if (!isOpen) return null;

  const activeVp = localViewpoints.find(v => v.id === activeId);

  return createPortal(
    <div style={{ position: 'fixed', inset: 0, zIndex: 9999, background: '#000', display: 'flex', flexDirection: 'column' }}>
      {/* Three.js container */}
      <div ref={containerRef} style={{ flex: 1, cursor: 'grab' }} />

      {/* Loading overlay */}
      {loading && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.8)', zIndex: 10 }}>
          <div style={{ textAlign: 'center', color: 'rgba(255,255,255,0.6)' }}>
            <div style={{ fontSize: 24, marginBottom: 8 }}>&#9696;</div>
            <div style={{ fontSize: 13 }}>Loading panorama...</div>
          </div>
        </div>
      )}

      {/* Viewpoint panel (top-left) */}
      {(localViewpoints.length > 0 || editMode) && (
        <div
          data-testid="viewpoint-panel"
          style={{
            position: 'absolute', top: 16, left: 16, zIndex: 20,
            background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(12px)',
            borderRadius: 12, padding: '10px 6px', minWidth: 200, maxWidth: 260,
            border: '1px solid rgba(255,255,255,0.08)',
            maxHeight: 'calc(100vh - 120px)', overflowY: 'auto',
          }}
        >
          <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', padding: '0 8px 6px', letterSpacing: 1 }}>
            VIEWPOINTS
          </div>
          {editMode && (
            <div
              onClick={() => { setOriginSelected(true); cameraOffsetRef.current = { ...cameraOffsetRef.current, x: originPos.posX, z: originPos.posZ }; }}
              style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '6px 8px', borderRadius: 8, cursor: 'pointer',
                background: originSelected ? 'rgba(251,191,36,0.2)' : 'transparent',
                transition: 'background 0.15s',
              }}
              onMouseEnter={e => { if (!originSelected) e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; }}
              onMouseLeave={e => { if (!originSelected) e.currentTarget.style.background = 'transparent'; }}
            >
              <div style={{
                width: 6, height: 6, borderRadius: '50%',
                backgroundColor: originSelected ? 'rgba(251,191,36,1)' : 'rgba(251,191,36,0.5)',
              }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 12, color: originSelected ? 'rgba(251,191,36,1)' : 'rgba(251,191,36,0.7)' }}>
                  初始点
                </div>
                <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.3)' }}>
                  X: {originPos.posX.toFixed(0)} / Z: {originPos.posZ.toFixed(0)}
                </div>
              </div>
            </div>
          )}
          {localViewpoints.map(vp => (
            <div key={vp.id}>
              <div
                data-testid={`vp-item-${vp.id}`}
                onClick={() => _navigateToViewpoint(vp.id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '6px 8px', borderRadius: 8, cursor: 'pointer',
                  background: vp.id === activeId ? 'rgba(6,182,212,0.2)' : 'transparent',
                  transition: 'background 0.15s',
                }}
                onMouseEnter={e => { if (vp.id !== activeId) e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; }}
                onMouseLeave={e => { if (vp.id !== activeId) e.currentTarget.style.background = 'transparent'; }}
              >
                <div style={{
                  width: 6, height: 6, borderRadius: '50%',
                  backgroundColor: vp.id === activeId ? 'rgba(6,182,212,1)' : 'rgba(255,255,255,0.25)',
                }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12, color: vp.id === activeId ? 'rgba(6,182,212,1)' : 'rgba(255,255,255,0.8)' }}>
                    {vp.label}
                  </div>
                  <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.3)' }}>
                    {vp.yaw.toFixed(0)}° / {vp.pitch.toFixed(0)}° / FOV {vp.fov.toFixed(0)}°
                  </div>
                </div>
                {editMode && (
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDeleteViewpoint(vp.id); }}
                    style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.3)', cursor: 'pointer', fontSize: 14, padding: '0 2px' }}
                  >×</button>
                )}
              </div>

              {/* Edit controls: minimap + correction slider for active viewpoint */}
              {editMode && vp.id === activeId && (
                <div style={{ padding: '8px 8px 8px 14px', borderLeft: '2px solid rgba(6,182,212,0.3)', marginLeft: 14 }}>
                  <div style={{ fontSize: 9, color: 'rgba(6,182,212,0.6)', marginBottom: 6, letterSpacing: 0.5 }}>
                    机位 (俯视图点击/拖拽)
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 8 }}>
                    <Minimap
                      viewpoints={localViewpoints}
                      activeId={activeId}
                      backgroundData={minimapBg}
                      cameraYaw={liveCameraYaw}
                      cameraFov={liveCameraFov}
                      originPos={originPos}
                      originSelected={originSelected}
                      onPositionChange={handleMinimapPositionChange}
                      onOriginChange={handleOriginChange}
                      onOriginSelect={handleOriginSelect}
                    />
                  </div>
                  <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.3)', textAlign: 'center', marginBottom: 4 }}>
                    X: {(vp.posX ?? 0).toFixed(0)} &nbsp; Z: {(vp.posZ ?? 0).toFixed(0)}
                  </div>
                  <div style={{ fontSize: 9, color: 'rgba(251,191,36,0.5)', textAlign: 'center', marginBottom: 8 }}>
                    初始点 X: {originPos.posX.toFixed(0)} &nbsp; Z: {originPos.posZ.toFixed(0)}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ fontSize: 9, color: 'rgba(6,182,212,0.6)', letterSpacing: 0.5 }}>
                      畸变矫正
                    </span>
                    <span style={{ fontSize: 9, color: 'rgba(52,211,153,0.7)', padding: '1px 5px', borderRadius: 3, backgroundColor: 'rgba(52,211,153,0.1)' }}>
                      自动
                    </span>
                    <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.5)', marginLeft: 'auto' }}>
                      {Math.round(liveCorrection * 100)}%
                    </span>
                  </div>
                </div>
              )}
            </div>
          ))}
          {editMode && (
            <button
              onClick={handleSaveCurrentView}
              style={{
                width: '100%', marginTop: 6, padding: '6px 8px',
                background: 'rgba(6,182,212,0.15)', border: '1px solid rgba(6,182,212,0.3)',
                borderRadius: 8, color: 'rgba(6,182,212,0.9)', fontSize: 11,
                cursor: 'pointer', transition: 'background 0.15s',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'rgba(6,182,212,0.25)'; }}
              onMouseLeave={e => { e.currentTarget.style.background = 'rgba(6,182,212,0.15)'; }}
            >
              + 保存当前视角
            </button>
          )}
        </div>
      )}

      {/* Label input dialog */}
      {labelInput.show && (
        <div style={{
          position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
          zIndex: 30, background: 'rgba(15,17,22,0.95)', backdropFilter: 'blur(20px)',
          borderRadius: 16, padding: 24, minWidth: 280, border: '1px solid rgba(255,255,255,0.1)',
        }}>
          <div style={{ fontSize: 13, color: 'rgba(255,255,255,0.6)', marginBottom: 12 }}>
            新建机位 ({Math.round(labelInput.yaw)}°, {Math.round(labelInput.pitch)}°)
          </div>
          <input
            autoFocus
            value={labelInput.value}
            onChange={e => setLabelInput(prev => ({ ...prev, value: e.target.value }))}
            onKeyDown={e => { if (e.key === 'Enter') handleConfirmLabel(); if (e.key === 'Escape') setLabelInput(prev => ({ ...prev, show: false })); }}
            placeholder="输入机位名称..."
            style={{
              width: '100%', padding: '8px 12px', borderRadius: 8,
              background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.12)',
              color: '#fff', fontSize: 13, outline: 'none',
            }}
          />
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button onClick={handleConfirmLabel}
              style={{ flex: 1, padding: '8px 16px', borderRadius: 8, background: 'rgba(6,182,212,0.8)', border: 'none', color: '#fff', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>
              确认
            </button>
            <button onClick={() => setLabelInput(prev => ({ ...prev, show: false }))}
              style={{ flex: 1, padding: '8px 16px', borderRadius: 8, background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.12)', color: 'rgba(255,255,255,0.7)', fontSize: 12, cursor: 'pointer' }}>
              取消
            </button>
          </div>
        </div>
      )}

      {/* Bottom controls */}
      <div style={{ position: 'absolute', bottom: 24, left: '50%', transform: 'translateX(-50%)', display: 'flex', gap: 8, zIndex: 20 }}>
        {onScreenshot && (
          <button onClick={handleScreenshot}
            style={{ padding: '10px 20px', borderRadius: 12, background: 'rgba(59,130,246,0.8)', border: 'none', color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer', backdropFilter: 'blur(8px)', transition: 'background 0.15s' }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(59,130,246,1)'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'rgba(59,130,246,0.8)'; }}>
            截图
          </button>
        )}
        {editMode && (
          <button onClick={handleSaveCurrentView}
            style={{ padding: '10px 20px', borderRadius: 12, background: 'rgba(6,182,212,0.7)', border: 'none', color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer', backdropFilter: 'blur(8px)', transition: 'background 0.15s' }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(6,182,212,0.9)'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'rgba(6,182,212,0.7)'; }}>
            + 保存机位
          </button>
        )}
        <button onClick={handleRecenter}
          style={{ padding: '10px 20px', borderRadius: 12, background: 'rgba(255,255,255,0.12)', border: '1px solid rgba(255,255,255,0.15)', color: 'rgba(255,255,255,0.8)', fontSize: 13, cursor: 'pointer', backdropFilter: 'blur(8px)', transition: 'background 0.15s' }}
          onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.2)'; }}
          onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.12)'; }}>
          重置视角
        </button>
        <button onClick={onClose}
          style={{ padding: '10px 20px', borderRadius: 12, background: 'rgba(255,255,255,0.12)', border: '1px solid rgba(255,255,255,0.15)', color: 'rgba(255,255,255,0.8)', fontSize: 13, cursor: 'pointer', backdropFilter: 'blur(8px)', transition: 'background 0.15s' }}
          onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.2)'; }}
          onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.12)'; }}>
          关闭
        </button>
      </div>

      {/* ESC hint */}
      <div style={{ position: 'absolute', top: 16, right: 16, zIndex: 20, fontSize: 11, color: 'rgba(255,255,255,0.3)' }}>
        ESC 关闭 | 拖拽旋转 | 滚轮缩放{editMode ? ' | 点击空白处添加机位' : ''}
      </div>
    </div>,
    document.body,
  );
}
