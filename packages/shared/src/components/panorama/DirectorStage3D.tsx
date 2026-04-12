'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import { createPortal } from 'react-dom';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import {
  cylinderVertexShader,
  cylinderFragmentShader,
  groundVertexShader,
  groundFragmentShader,
} from './cylindricalShader';
import {
  type Character3D,
  type DirectorStage3DProps,
  PRESETS,
  CHAR_COLORS,
  createCharObject,
  disposeObject,
} from './directorStageHelpers';

export type { Character3D, DirectorStage3DProps };

// ══════════════════════════════════════════════════════════════════
// Main Component
// ══════════════════════════════════════════════════════════════════

export function DirectorStage3D({
  panoramaUrl,
  isOpen,
  onClose,
  sceneType: initialSceneType = 'indoor',
  characters: initialCharacters = [],
  onCharactersUpdate,
}: DirectorStage3DProps) {
  // ── Refs ──
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const cylinderRef = useRef<THREE.Mesh | null>(null);
  const cylinderMatRef = useRef<THREE.ShaderMaterial | null>(null);
  const groundRef = useRef<THREE.Mesh | null>(null);
  const groundMatRef = useRef<THREE.ShaderMaterial | null>(null);
  const gridRef = useRef<THREE.GridHelper | null>(null);
  const boundaryRef = useRef<THREE.Mesh | null>(null);
  const charGroupRef = useRef<THREE.Group | null>(null);
  const charObjsRef = useRef<Map<string, THREE.Group>>(new Map());
  const textureRef = useRef<THREE.Texture | null>(null);
  const animIdRef = useRef(0);
  const raycasterRef = useRef(new THREE.Raycaster());
  const mouseRef = useRef(new THREE.Vector2());
  const groundPlaneRef = useRef(new THREE.Plane(new THREE.Vector3(0, 1, 0), 0));
  const dragRef = useRef<{ id: string; obj: THREE.Object3D } | null>(null);
  const isDraggingRef = useRef(false);
  const ptrDownRef = useRef({ x: 0, y: 0 });

  // Stable-ref wrappers for values used inside event handlers
  const charsRef = useRef(initialCharacters);
  const radiusRef = useRef(PRESETS[initialSceneType].cylinderRadius);
  const onCharsUpdateRef = useRef(onCharactersUpdate);
  const onCloseRef = useRef(onClose);

  // ── State ──
  const [loading, setLoading] = useState(true);
  const [sceneType, setSceneType] = useState<'indoor' | 'outdoor'>(initialSceneType);
  const [radius, setRadius] = useState(PRESETS[initialSceneType].cylinderRadius);
  const [chars, setChars] = useState<Character3D[]>(initialCharacters);
  const [selectedCharId, setSelectedCharId] = useState<string | null>(null);

  // ── Sync refs ──
  useEffect(() => { charsRef.current = chars; }, [chars]);
  useEffect(() => { radiusRef.current = radius; }, [radius]);
  useEffect(() => { onCharsUpdateRef.current = onCharactersUpdate; }, [onCharactersUpdate]);
  useEffect(() => { onCloseRef.current = onClose; }, [onClose]);

  const preset = PRESETS[sceneType];

  // ══════════════════════════════════════════════════════════════
  // Main scene setup (renderer, camera, controls, lights, texture)
  // ══════════════════════════════════════════════════════════════
  useEffect(() => {
    if (!isOpen || !containerRef.current) return;
    const container = containerRef.current;
    const w = container.clientWidth;
    const h = container.clientHeight;

    // Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x08080f);
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(50, w / h, 0.01, 2000);
    const cp = PRESETS[initialSceneType].cameraPos;
    camera.position.set(cp[0], cp[1], cp[2]);
    cameraRef.current = camera;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    const ct = PRESETS[initialSceneType].cameraTarget;
    controls.target.set(ct[0], ct[1], ct[2]);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.maxDistance = 200;
    controls.minDistance = 0.3;
    controls.update();
    controlsRef.current = controls;

    // Lighting
    scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const dl = new THREE.DirectionalLight(0xffffff, 0.4);
    dl.position.set(5, 10, 5);
    scene.add(dl);

    // Character group
    const charGroup = new THREE.Group();
    scene.add(charGroup);
    charGroupRef.current = charGroup;

    // Load panorama texture
    setLoading(true);
    const applyTexture = (tex: THREE.Texture) => {
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.wrapS = THREE.RepeatWrapping;
      tex.minFilter = THREE.LinearFilter;
      tex.magFilter = THREE.LinearFilter;
      textureRef.current = tex;
      if (cylinderMatRef.current) {
        cylinderMatRef.current.uniforms.uPanorama.value = tex;
        cylinderMatRef.current.needsUpdate = true;
      }
      if (groundMatRef.current) {
        groundMatRef.current.uniforms.uPanorama.value = tex;
        groundMatRef.current.needsUpdate = true;
      }
      setLoading(false);
    };
    const loader = new THREE.TextureLoader();
    loader.load(panoramaUrl, applyTexture, undefined, () => {
      // Fallback via Image element
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
    });

    // ── Pointer events for character dragging ──
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
          const maxR = radiusRef.current * 0.9;
          const dist = Math.sqrt(pt.x * pt.x + pt.z * pt.z);
          if (dist > maxR) { pt.x *= maxR / dist; pt.z *= maxR / dist; }
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

    // ── Animation loop ──
    const animate = () => {
      animIdRef.current = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    // ── Resize ──
    const handleResize = () => {
      if (!container.clientWidth || !container.clientHeight) return;
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    };
    window.addEventListener('resize', handleResize);

    // ── Cleanup ──
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
      textureRef.current?.dispose();
      textureRef.current = null;
      sceneRef.current = null;
      cameraRef.current = null;
      rendererRef.current = null;
      controlsRef.current = null;
      cylinderRef.current = null;
      cylinderMatRef.current = null;
      groundRef.current = null;
      groundMatRef.current = null;
      gridRef.current = null;
      boundaryRef.current = null;
      charGroupRef.current = null;
      charObjsRef.current.clear();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, panoramaUrl]);

  // ══════════════════════════════════════════════════════════════
  // Rebuild cylinder / ground / grid when radius or sceneType changes
  // ══════════════════════════════════════════════════════════════
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;

    const R = radius;
    const eyeLevel = preset.eyeLevel;

    // ── Cylinder ──
    if (cylinderRef.current) {
      scene.remove(cylinderRef.current);
      cylinderRef.current.geometry.dispose();
      (cylinderRef.current.material as THREE.Material).dispose();
    }

    const cylH = R * 3;
    const cylGeo = new THREE.CylinderGeometry(R, R, cylH, 128, 1, true);
    const cylMat = new THREE.ShaderMaterial({
      uniforms: {
        uPanorama: { value: textureRef.current },
        uCylinderRadius: { value: R },
        uEyeLevel: { value: eyeLevel },
      },
      vertexShader: cylinderVertexShader,
      fragmentShader: cylinderFragmentShader,
      side: THREE.BackSide,
    });
    const cylinder = new THREE.Mesh(cylGeo, cylMat);
    cylinder.position.y = eyeLevel;
    scene.add(cylinder);
    cylinderRef.current = cylinder;
    cylinderMatRef.current = cylMat;

    // ── Ground plane (panorama nadir projection) ──
    if (groundRef.current) {
      scene.remove(groundRef.current);
      groundRef.current.geometry.dispose();
      (groundRef.current.material as THREE.Material).dispose();
    }
    const gndGeo = new THREE.CircleGeometry(R * 0.99, 128);
    gndGeo.rotateX(-Math.PI / 2);
    const gndMat = new THREE.ShaderMaterial({
      uniforms: {
        uPanorama: { value: textureRef.current },
        uEyeLevel: { value: eyeLevel },
        uGroundRadius: { value: R * 0.99 },
      },
      vertexShader: groundVertexShader,
      fragmentShader: groundFragmentShader,
      side: THREE.DoubleSide,
    });
    const ground = new THREE.Mesh(gndGeo, gndMat);
    ground.position.y = 0.001;
    scene.add(ground);
    groundRef.current = ground;
    groundMatRef.current = gndMat;

    // ── Grid ──
    if (gridRef.current) {
      scene.remove(gridRef.current);
      const gm = gridRef.current.material;
      const gms = Array.isArray(gm) ? gm : [gm];
      gms.forEach(m => m.dispose());
      gridRef.current.geometry.dispose();
    }
    const divisions = Math.min(Math.ceil(R * 2), 40);
    const grid = new THREE.GridHelper(R * 2, divisions, 0x333355, 0x1e1e33);
    grid.position.y = 0.003;
    const gridMats = Array.isArray(grid.material) ? grid.material : [grid.material];
    gridMats.forEach(m => { m.transparent = true; m.opacity = 0.12; });
    scene.add(grid);
    gridRef.current = grid;

    // ── Boundary ring ──
    if (boundaryRef.current) {
      scene.remove(boundaryRef.current);
      boundaryRef.current.geometry.dispose();
      (boundaryRef.current.material as THREE.Material).dispose();
    }
    const bndGeo = new THREE.RingGeometry(R * 0.95, R * 0.97, 64);
    bndGeo.rotateX(-Math.PI / 2);
    const bndMat = new THREE.MeshBasicMaterial({ color: 0x06b6d4, transparent: true, opacity: 0.1, side: THREE.DoubleSide });
    const boundary = new THREE.Mesh(bndGeo, bndMat);
    boundary.position.y = 0.006;
    scene.add(boundary);
    boundaryRef.current = boundary;

    // ── Camera limits ──
    if (cameraRef.current) {
      cameraRef.current.far = Math.max(R * 20, 100);
      cameraRef.current.updateProjectionMatrix();
    }
    if (controlsRef.current) {
      controlsRef.current.maxDistance = Math.max(R * 4, 20);
    }
  }, [radius, sceneType, preset.eyeLevel]);

  // ══════════════════════════════════════════════════════════════
  // Sync characters state → Three.js objects
  // ══════════════════════════════════════════════════════════════
  useEffect(() => {
    const group = charGroupRef.current;
    if (!group) return;

    const newIds = new Set(chars.map(c => c.id));

    // Remove deleted
    for (const [id, obj] of charObjsRef.current.entries()) {
      if (!newIds.has(id)) {
        group.remove(obj);
        disposeObject(obj);
        charObjsRef.current.delete(id);
      }
    }

    // Add new / update position
    for (const char of chars) {
      let obj = charObjsRef.current.get(char.id);
      if (!obj) {
        obj = createCharObject(char);
        charObjsRef.current.set(char.id, obj);
        group.add(obj);
      }
      obj.position.set(char.x, 0, char.z);
    }
  }, [chars]);

  // ── Selection ring toggle ──
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

  // ══════════════════════════════════════════════════════════════
  // Callbacks
  // ══════════════════════════════════════════════════════════════

  const handleSceneTypeChange = useCallback((type: 'indoor' | 'outdoor') => {
    setSceneType(type);
    const p = PRESETS[type];
    setRadius(p.cylinderRadius);
    if (cameraRef.current && controlsRef.current) {
      cameraRef.current.position.set(p.cameraPos[0], p.cameraPos[1], p.cameraPos[2]);
      controlsRef.current.target.set(p.cameraTarget[0], p.cameraTarget[1], p.cameraTarget[2]);
      controlsRef.current.update();
    }
  }, []);

  const handleAddChar = useCallback(() => {
    const idx = charsRef.current.length;
    const R = radiusRef.current;
    const newChar: Character3D = {
      id: `char-${Date.now().toString(36)}`,
      name: `角色${idx + 1}`,
      x: (Math.random() - 0.5) * R * 0.4,
      z: (Math.random() - 0.5) * R * 0.4,
      color: CHAR_COLORS[idx % CHAR_COLORS.length],
    };
    const updated = [...charsRef.current, newChar];
    setChars(updated);
    setSelectedCharId(newChar.id);
    onCharsUpdateRef.current?.(updated);
  }, []);

  const handleResetView = useCallback(() => {
    if (!cameraRef.current || !controlsRef.current) return;
    const p = PRESETS[sceneType];
    cameraRef.current.position.set(p.cameraPos[0], p.cameraPos[1], p.cameraPos[2]);
    cameraRef.current.fov = 50;
    cameraRef.current.updateProjectionMatrix();
    controlsRef.current.target.set(p.cameraTarget[0], p.cameraTarget[1], p.cameraTarget[2]);
    controlsRef.current.update();
  }, [sceneType]);

  // ══════════════════════════════════════════════════════════════
  // Render
  // ══════════════════════════════════════════════════════════════

  if (!isOpen) return null;

  const rRange = preset.radiusRange;

  return createPortal(
    <div style={{ position: 'fixed', inset: 0, zIndex: 9999, background: '#000', display: 'flex', flexDirection: 'column' }}>
      {/* Three.js viewport */}
      <div ref={containerRef} style={{ flex: 1, cursor: 'grab' }} />

      {/* Loading overlay */}
      {loading && (
        <div style={{
          position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(0,0,0,0.8)', zIndex: 10,
        }}>
          <div style={{ textAlign: 'center', color: 'rgba(255,255,255,0.6)' }}>
            <div style={{ fontSize: 24, marginBottom: 8 }}>&#9696;</div>
            <div style={{ fontSize: 13 }}>加载全景中...</div>
          </div>
        </div>
      )}

      {/* ── Scene controls (top-left) ── */}
      <div style={{
        position: 'absolute', top: 16, left: 16, zIndex: 20,
        background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(12px)',
        borderRadius: 12, padding: '12px 14px', minWidth: 200,
        border: '1px solid rgba(255,255,255,0.08)',
      }}>
        <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', letterSpacing: 1, marginBottom: 8 }}>
          3D 导演台
        </div>

        {/* Scene type toggle */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 10 }}>
          {(['indoor', 'outdoor'] as const).map(type => (
            <button
              key={type}
              onClick={() => handleSceneTypeChange(type)}
              style={{
                flex: 1, padding: '5px 0', borderRadius: 6, fontSize: 11, fontWeight: 500,
                border: sceneType === type ? '1px solid rgba(6,182,212,0.5)' : '1px solid rgba(255,255,255,0.1)',
                background: sceneType === type ? 'rgba(6,182,212,0.2)' : 'rgba(255,255,255,0.04)',
                color: sceneType === type ? 'rgba(6,182,212,1)' : 'rgba(255,255,255,0.5)',
                cursor: 'pointer', transition: 'all 0.15s',
              }}
            >
              {PRESETS[type].label}
            </button>
          ))}
        </div>

        {/* Radius slider */}
        <div style={{ marginBottom: 6 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.35)' }}>半径</span>
            <span style={{ fontSize: 9, color: 'rgba(6,182,212,0.8)' }}>{radius.toFixed(1)}m</span>
          </div>
          <input
            type="range"
            min={rRange.min}
            max={rRange.max}
            step={rRange.step}
            value={radius}
            onChange={e => setRadius(parseFloat(e.target.value))}
            style={{ width: '100%', accentColor: '#06b6d4' }}
          />
        </div>

        {/* Info */}
        <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.25)', lineHeight: 1.6 }}>
          直径 {(radius * 2).toFixed(1)}m&ensp;|&ensp;可行走 {(radius * 0.9 * 2).toFixed(1)}m
          <br />
          角色 {preset.charHeight}m&ensp;|&ensp;视线高 {preset.eyeLevel}m
        </div>
      </div>

      {/* ── Character panel (top-right) ── */}
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
          <div
            key={c.id}
            onClick={() => setSelectedCharId(c.id === selectedCharId ? null : c.id)}
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '5px 6px', borderRadius: 6, cursor: 'pointer', marginBottom: 2,
              background: c.id === selectedCharId ? 'rgba(6,182,212,0.15)' : 'transparent',
              transition: 'background 0.15s',
            }}
            onMouseEnter={e => { if (c.id !== selectedCharId) e.currentTarget.style.background = 'rgba(255,255,255,0.04)'; }}
            onMouseLeave={e => { if (c.id !== selectedCharId) e.currentTarget.style.background = 'transparent'; }}
          >
            <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: c.color || CHAR_COLORS[0], flexShrink: 0 }} />
            <span style={{ fontSize: 11, color: c.id === selectedCharId ? 'rgba(6,182,212,1)' : 'rgba(255,255,255,0.7)', flex: 1 }}>
              {c.name}
            </span>
            <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.25)' }}>
              ({c.x.toFixed(1)}, {c.z.toFixed(1)})
            </span>
          </div>
        ))}

        <button
          onClick={handleAddChar}
          style={{
            width: '100%', marginTop: 6, padding: '6px 0', borderRadius: 6,
            background: 'rgba(6,182,212,0.12)', border: '1px solid rgba(6,182,212,0.25)',
            color: 'rgba(6,182,212,0.8)', fontSize: 11, cursor: 'pointer',
            transition: 'background 0.15s',
          }}
          onMouseEnter={e => { e.currentTarget.style.background = 'rgba(6,182,212,0.25)'; }}
          onMouseLeave={e => { e.currentTarget.style.background = 'rgba(6,182,212,0.12)'; }}
        >
          + 添加角色
        </button>

        {selectedCharId && (
          <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.25)', marginTop: 6, textAlign: 'center' }}>
            拖拽移动 | Delete 删除
          </div>
        )}
      </div>

      {/* ── Bottom controls ── */}
      <div style={{
        position: 'absolute', bottom: 24, left: '50%', transform: 'translateX(-50%)',
        display: 'flex', gap: 8, zIndex: 20,
      }}>
        <button
          onClick={handleResetView}
          style={{
            padding: '10px 20px', borderRadius: 12,
            background: 'rgba(255,255,255,0.12)', border: '1px solid rgba(255,255,255,0.15)',
            color: 'rgba(255,255,255,0.8)', fontSize: 13, cursor: 'pointer',
            backdropFilter: 'blur(8px)', transition: 'background 0.15s',
          }}
          onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.2)'; }}
          onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.12)'; }}
        >
          重置视角
        </button>
        <button
          onClick={onClose}
          style={{
            padding: '10px 20px', borderRadius: 12,
            background: 'rgba(255,255,255,0.12)', border: '1px solid rgba(255,255,255,0.15)',
            color: 'rgba(255,255,255,0.8)', fontSize: 13, cursor: 'pointer',
            backdropFilter: 'blur(8px)', transition: 'background 0.15s',
          }}
          onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.2)'; }}
          onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.12)'; }}
        >
          关闭
        </button>
      </div>

      {/* ESC hint */}
      <div style={{ position: 'absolute', bottom: 8, right: 16, zIndex: 20, fontSize: 10, color: 'rgba(255,255,255,0.2)' }}>
        ESC 关闭 | 拖拽旋转 | 滚轮缩放 | 拖拽角色移动
      </div>
    </div>,
    document.body,
  );
}
