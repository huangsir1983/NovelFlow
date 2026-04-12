'use client';

import { useEffect, useRef, useCallback, useState, memo } from 'react';
import { createPortal } from 'react-dom';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { TransformControls } from 'three/examples/jsm/controls/TransformControls.js';
import {
  loadMannequin,
  updateAllHelpers,
  highlightJoint,
  applyPose,
  applyHandPreset,
  readPose,
  POSE_PRESETS,
  HAND_PRESETS,
  JOINT_GROUPS,
  JOINT_LABELS,
  type MannequinResult,
} from '../../../lib/mannequinGeometry';

function setTransformVisible(tc: TransformControls, v: boolean) {
  (tc as unknown as { visible: boolean }).visible = v;
}

interface Pose3DEditorProps {
  isOpen: boolean;
  onClose: () => void;
  onScreenshot?: (base64: string) => void;
  initialJointAngles?: Record<string, { x: number; y: number; z: number }>;
  onPoseChange?: (angles: Record<string, { x: number; y: number; z: number }>) => void;
}

function Pose3DEditorComponent({ isOpen, onClose, onScreenshot, initialJointAngles, onPoseChange }: Pose3DEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const orbitRef = useRef<OrbitControls | null>(null);
  const transformRef = useRef<TransformControls | null>(null);
  const mannequinRef = useRef<MannequinResult | null>(null);
  const animIdRef = useRef(0);
  const raycasterRef = useRef(new THREE.Raycaster());
  const mouseRef = useRef(new THREE.Vector2());
  const gridRef = useRef<THREE.GridHelper | null>(null);

  const [selectedJoint, setSelectedJoint] = useState<string | null>(null);
  const [presetName, setPresetName] = useState<string | null>(null);
  const [leftHandPreset, setLeftHandPreset] = useState<string | null>(null);
  const [rightHandPreset, setRightHandPreset] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !containerRef.current) return;

    const container = containerRef.current;
    const w = container.clientWidth;
    const h = container.clientHeight;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xffffff);
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(45, w / h, 0.01, 100);
    camera.position.set(0, 1.0, 3.5);
    camera.lookAt(0, 0.85, 0);
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Lights
    scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const dir = new THREE.DirectionalLight(0xffffff, 0.8);
    dir.position.set(3, 5, 4);
    scene.add(dir);
    const fill = new THREE.DirectionalLight(0x8888ff, 0.3);
    fill.position.set(-3, 2, -2);
    scene.add(fill);

    // Ground grid
    const gridHelper = new THREE.GridHelper(4, 20, 0xcccccc, 0xdddddd);
    scene.add(gridHelper);
    gridRef.current = gridHelper;

    // Controls
    const orbit = new OrbitControls(camera, renderer.domElement);
    orbit.target.set(0, 0.85, 0);
    orbit.enableDamping = true;
    orbit.dampingFactor = 0.1;
    orbit.minDistance = 1;
    orbit.maxDistance = 10;
    orbit.update();
    orbitRef.current = orbit;

    const transform = new TransformControls(camera, renderer.domElement);
    transform.setMode('rotate');
    transform.setSize(0.6);
    setTransformVisible(transform, false);
    scene.add(transform.getHelper());
    transformRef.current = transform;

    transform.addEventListener('dragging-changed', (event) => {
      orbit.enabled = !(event as unknown as { value: boolean }).value;
    });
    transform.addEventListener('objectChange', () => {
      if (onPoseChange && mannequinRef.current) {
        onPoseChange(readPose(mannequinRef.current.boneMap));
      }
    });

    // Animation loop — render first, then update helpers (so matrixWorld is fresh)
    const animate = () => {
      animIdRef.current = requestAnimationFrame(animate);
      orbit.update();
      if (mannequinRef.current) {
        mannequinRef.current.skeleton.update();
      }
      renderer.render(scene, camera);
      // Update helper positions AFTER render (matrixWorld is now current)
      if (mannequinRef.current) {
        updateAllHelpers(mannequinRef.current);
      }
    };
    animate();

    // Load model
    let cancelled = false;
    setLoading(true);
    setLoadError(null);

    loadMannequin('/models/Xbot.glb').then((mannequin) => {
      if (cancelled) return;

      // Add model to scene
      scene.add(mannequin.model);

      // Add joint markers to scene (separate from model so they don't get skinned)
      for (const marker of mannequin.jointMarkers.values()) {
        scene.add(marker);
      }

      // Add gap fills to scene
      for (const fill of mannequin.gapFills.values()) {
        scene.add(fill);
      }

      // Add facial features to scene
      for (const feat of mannequin.facialFeatures.values()) {
        scene.add(feat);
      }

      mannequinRef.current = mannequin;

      // Force a matrix world update so helpers get correct initial positions
      scene.updateMatrixWorld(true);
      updateAllHelpers(mannequin);

      // Apply initial pose
      if (initialJointAngles && Object.keys(initialJointAngles).length > 0) {
        applyPose(mannequin.boneMap, initialJointAngles);
      }

      setLoading(false);
    }).catch((err) => {
      if (!cancelled) {
        console.error('Failed to load mannequin:', err);
        setLoadError(String(err));
        setLoading(false);
      }
    });

    const onResize = () => {
      const nw = container.clientWidth, nh = container.clientHeight;
      camera.aspect = nw / nh;
      camera.updateProjectionMatrix();
      renderer.setSize(nw, nh);
    };
    window.addEventListener('resize', onResize);

    return () => {
      cancelled = true;
      window.removeEventListener('resize', onResize);
      cancelAnimationFrame(animIdRef.current);
      transform.dispose();
      orbit.dispose();
      renderer.dispose();
      renderer.domElement.parentNode?.removeChild(renderer.domElement);
      const m = mannequinRef.current;
      if (m) {
        m.skinnedMesh.geometry.dispose();
        const mat = m.skinnedMesh.material;
        if (Array.isArray(mat)) mat.forEach((mm) => mm.dispose());
        else (mat as THREE.Material).dispose();
        for (const marker of m.jointMarkers.values()) {
          marker.geometry.dispose();
          (marker.material as THREE.Material).dispose();
        }
        for (const fill of m.gapFills.values()) {
          fill.geometry.dispose();
        }
        for (const feat of m.facialFeatures.values()) {
          feat.geometry.dispose();
          (feat.material as THREE.Material).dispose();
        }
        if (m.outlineMesh) {
          (m.outlineMesh.material as THREE.Material).dispose();
        }
      }
      mannequinRef.current = null;
      sceneRef.current = null;
      cameraRef.current = null;
      rendererRef.current = null;
      orbitRef.current = null;
      transformRef.current = null;
      gridRef.current = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  const handleCanvasClick = useCallback((e: React.MouseEvent) => {
    if (!rendererRef.current || !cameraRef.current || !mannequinRef.current) return;
    const rect = rendererRef.current.domElement.getBoundingClientRect();
    mouseRef.current.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    mouseRef.current.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
    raycasterRef.current.setFromCamera(mouseRef.current, cameraRef.current);

    const markers: THREE.Object3D[] = Array.from(mannequinRef.current.jointMarkers.values());
    const hits = raycasterRef.current.intersectObjects(markers, false);
    selectJoint(hits.length > 0 ? (hits[0].object.userData.jointName as string) : null);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectJoint = useCallback((name: string | null) => {
    setSelectedJoint(name);
    if (!mannequinRef.current || !transformRef.current) return;
    highlightJoint(mannequinRef.current.jointMarkers, name);
    if (name) {
      const bone = mannequinRef.current.boneMap.get(name);
      if (bone) {
        transformRef.current.attach(bone);
        setTransformVisible(transformRef.current, true);
      }
    } else {
      transformRef.current.detach();
      setTransformVisible(transformRef.current, false);
    }
  }, []);

  const handlePreset = useCallback((key: string) => {
    if (!mannequinRef.current) return;
    const preset = POSE_PRESETS[key];
    if (!preset) return;
    applyPose(mannequinRef.current.boneMap, preset.angles);
    setPresetName(key);
    setSelectedJoint(null);
    if (transformRef.current) { transformRef.current.detach(); setTransformVisible(transformRef.current, false); }
    highlightJoint(mannequinRef.current.jointMarkers, null);
    if (onPoseChange) onPoseChange(preset.angles);
  }, [onPoseChange]);

  const handleScreenshot = useCallback(() => {
    if (!rendererRef.current || !sceneRef.current || !cameraRef.current) return;
    const renderer = rendererRef.current;
    const camera = cameraRef.current;
    const scene = sceneRef.current;
    const mannequin = mannequinRef.current;

    // Hide grid, Beta_Joints, and joint markers for clean screenshot — keep gap fills + facial features visible
    const hiddenForShot: THREE.Object3D[] = [];
    if (mannequin) {
      // Hide Beta_Joints (the model's built-in joint spheres)
      mannequin.model.traverse((child) => {
        if (child.name === 'Beta_Joints' && child.visible) {
          child.visible = false;
          hiddenForShot.push(child);
        }
      });
      // Hide interactive joint markers (blue spheres — UI only)
      for (const marker of mannequin.jointMarkers.values()) {
        if (marker.visible) { marker.visible = false; hiddenForShot.push(marker); }
      }
    }
    // Hide grid
    if (gridRef.current) { gridRef.current.visible = false; hiddenForShot.push(gridRef.current); }
    if (transformRef.current) setTransformVisible(transformRef.current, false);

    const origW = renderer.domElement.width, origH = renderer.domElement.height;
    renderer.setSize(1920, 1080);
    camera.aspect = 1920 / 1080;
    camera.updateProjectionMatrix();
    // Ensure gap fills + facial features are positioned correctly before screenshot
    if (mannequin) updateAllHelpers(mannequin);
    renderer.render(scene, camera);

    const base64 = renderer.domElement.toDataURL('image/jpeg', 0.92).split(',')[1];

    renderer.setSize(origW, origH);
    camera.aspect = origW / origH;
    camera.updateProjectionMatrix();
    // Restore visibility
    for (const obj of hiddenForShot) obj.visible = true;
    if (transformRef.current && selectedJoint) setTransformVisible(transformRef.current, true);

    if (onScreenshot) onScreenshot(base64);
  }, [onScreenshot, selectedJoint]);

  const handleReset = useCallback(() => {
    if (!mannequinRef.current) return;
    applyPose(mannequinRef.current.boneMap, {});
    setPresetName(null);
    setLeftHandPreset(null);
    setRightHandPreset(null);
    setSelectedJoint(null);
    if (transformRef.current) { transformRef.current.detach(); setTransformVisible(transformRef.current, false); }
    highlightJoint(mannequinRef.current.jointMarkers, null);
    if (onPoseChange) onPoseChange({});
  }, [onPoseChange]);

  const handleHandPreset = useCallback((side: 'left' | 'right', key: string) => {
    if (!mannequinRef.current) return;
    applyHandPreset(mannequinRef.current.boneMap, side, key);
    if (side === 'left') setLeftHandPreset(key);
    else setRightHandPreset(key);
    if (onPoseChange) onPoseChange(readPose(mannequinRef.current.boneMap));
  }, [onPoseChange]);

  if (!isOpen) return null;

  const overlay = (
    <div style={{ position: 'fixed', inset: 0, zIndex: 9999, display: 'flex', backgroundColor: 'rgba(0,0,0,0.95)' }}>
      {/* Left sidebar */}
      <div style={{
        width: 200, padding: '16px 12px', overflowY: 'auto',
        backgroundColor: 'rgba(15,17,22,0.95)',
        borderRight: '1px solid rgba(255,255,255,0.06)',
        display: 'flex', flexDirection: 'column', gap: 4,
      }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'rgba(168,85,247,0.9)', marginBottom: 8 }}>关节列表</div>
        {JOINT_GROUPS.map((group: { label: string; joints: string[] }) => (
          <div key={group.label}>
            <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', padding: '6px 0 3px', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              {group.label}
            </div>
            {group.joints.map((name: string) => (
              <button
                key={name}
                onClick={() => selectJoint(name)}
                style={{
                  display: 'block', width: '100%', textAlign: 'left',
                  padding: '5px 8px', borderRadius: 6, border: 'none',
                  fontSize: 11, cursor: 'pointer', marginBottom: 1,
                  backgroundColor: selectedJoint === name ? 'rgba(168,85,247,0.2)' : 'transparent',
                  color: selectedJoint === name ? 'rgba(168,85,247,0.9)' : 'rgba(255,255,255,0.5)',
                  transition: 'all 0.15s',
                }}
                onMouseEnter={e => { if (selectedJoint !== name) (e.target as HTMLElement).style.backgroundColor = 'rgba(255,255,255,0.05)'; }}
                onMouseLeave={e => { if (selectedJoint !== name) (e.target as HTMLElement).style.backgroundColor = 'transparent'; }}
              >
                {JOINT_LABELS[name] || name}
              </button>
            ))}
          </div>
        ))}
      </div>

      {/* 3D viewport */}
      <div style={{ flex: 1, position: 'relative' }}>
        <div ref={containerRef} onClick={handleCanvasClick} style={{ width: '100%', height: '100%' }} />

        {/* Loading / error */}
        {loading && (
          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(26,26,46,0.8)' }}>
            <div style={{ padding: '12px 24px', borderRadius: 10, backgroundColor: 'rgba(168,85,247,0.15)', border: '1px solid rgba(168,85,247,0.3)', color: 'rgba(168,85,247,0.9)', fontSize: 14 }}>
              {loadError ? `加载失败: ${loadError}` : '加载模型中...'}
            </div>
          </div>
        )}

        {selectedJoint && (
          <div style={{
            position: 'absolute', top: 16, left: '50%', transform: 'translateX(-50%)',
            padding: '6px 16px', borderRadius: 8,
            backgroundColor: 'rgba(168,85,247,0.15)', border: '1px solid rgba(168,85,247,0.3)',
            color: 'rgba(168,85,247,0.9)', fontSize: 12, fontWeight: 500,
          }}>
            {JOINT_LABELS[selectedJoint] || selectedJoint}
          </div>
        )}

      </div>

      {/* Right sidebar — presets & actions */}
      <div style={{
        width: 200, padding: '16px 12px', overflowY: 'auto',
        backgroundColor: 'rgba(15,17,22,0.95)',
        borderLeft: '1px solid rgba(255,255,255,0.06)',
        display: 'flex', flexDirection: 'column', gap: 12,
      }}>
        {/* Body presets */}
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'rgba(168,85,247,0.9)', marginBottom: 6 }}>身体预设</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {(Object.entries(POSE_PRESETS) as [string, { label: string; angles: Record<string, { x: number; y: number; z: number }> }][]).map(([key, preset]) => (
              <button key={key} onClick={() => handlePreset(key)} style={{
                padding: '4px 8px', borderRadius: 5, border: 'none', fontSize: 10, cursor: 'pointer',
                backgroundColor: presetName === key ? 'rgba(168,85,247,0.25)' : 'rgba(255,255,255,0.06)',
                color: presetName === key ? 'rgba(168,85,247,0.9)' : 'rgba(255,255,255,0.5)',
              }}>
                {preset.label}
              </button>
            ))}
          </div>
        </div>

        {/* Left hand presets */}
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'rgba(96,165,250,0.9)', marginBottom: 6 }}>左手</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {(Object.entries(HAND_PRESETS) as [string, { label: string }][]).map(([key, hp]) => (
              <button key={`L${key}`} onClick={() => handleHandPreset('left', key)} style={{
                padding: '3px 8px', borderRadius: 5, border: 'none', fontSize: 10, cursor: 'pointer',
                backgroundColor: leftHandPreset === key ? 'rgba(59,130,246,0.25)' : 'rgba(255,255,255,0.05)',
                color: leftHandPreset === key ? 'rgba(96,165,250,0.9)' : 'rgba(255,255,255,0.4)',
              }}>
                {hp.label}
              </button>
            ))}
          </div>
        </div>

        {/* Right hand presets */}
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'rgba(96,165,250,0.9)', marginBottom: 6 }}>右手</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {(Object.entries(HAND_PRESETS) as [string, { label: string }][]).map(([key, hp]) => (
              <button key={`R${key}`} onClick={() => handleHandPreset('right', key)} style={{
                padding: '3px 8px', borderRadius: 5, border: 'none', fontSize: 10, cursor: 'pointer',
                backgroundColor: rightHandPreset === key ? 'rgba(59,130,246,0.25)' : 'rgba(255,255,255,0.05)',
                color: rightHandPreset === key ? 'rgba(96,165,250,0.9)' : 'rgba(255,255,255,0.4)',
              }}>
                {hp.label}
              </button>
            ))}
          </div>
        </div>

        {/* Divider */}
        <div style={{ height: 1, backgroundColor: 'rgba(255,255,255,0.06)' }} />

        {/* Actions */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <button onClick={handleReset} style={{ width: '100%', padding: '6px 0', borderRadius: 6, border: 'none', fontSize: 11, cursor: 'pointer', backgroundColor: 'rgba(255,255,255,0.06)', color: 'rgba(255,255,255,0.5)' }}>
            重置
          </button>
          <button onClick={handleScreenshot} style={{ width: '100%', padding: '6px 0', borderRadius: 6, border: 'none', fontSize: 11, cursor: 'pointer', fontWeight: 500, backgroundColor: 'rgba(52,211,153,0.2)', color: 'rgba(52,211,153,0.9)' }}>
            截图
          </button>
          <button onClick={onClose} style={{ width: '100%', padding: '6px 0', borderRadius: 6, border: 'none', fontSize: 11, cursor: 'pointer', backgroundColor: 'rgba(255,255,255,0.06)', color: 'rgba(255,255,255,0.5)' }}>
            关闭
          </button>
        </div>
      </div>

      <button onClick={onClose} style={{
        position: 'absolute', top: 16, right: 16, width: 32, height: 32, borderRadius: 8, border: 'none',
        backgroundColor: 'rgba(255,255,255,0.06)', color: 'rgba(255,255,255,0.4)',
        fontSize: 16, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>×</button>
    </div>
  );

  return createPortal(overlay, document.body);
}

export const Pose3DEditor = memo(Pose3DEditorComponent);
