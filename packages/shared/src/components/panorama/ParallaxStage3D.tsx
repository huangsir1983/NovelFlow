'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import { createPortal } from 'react-dom';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { TransformControls } from 'three/examples/jsm/controls/TransformControls.js';
import { createLabelSprite } from './directorStageHelpers';
import {
  type StageCharacter,
  type StageProp,
  createStageCharacter,
  applyBodyPreset,
  updateTransform,
  updateScale,
  updateRotation,
  updateY,
  updateJointAngles,
} from './stageCharacter';
import {
  type MannequinInstance,
  preloadMannequin,
  cloneMannequin,
  syncInstanceToCharacter,
  setInstanceSelected,
  updateJointMarkerPositions,
  positionFacialFeatures,
  disposeInstance,
  readPose,
  applyHandPreset,
} from './stageMannequinManager';
import { HAND_PRESETS } from '../../lib/mannequinGeometry';
import type { StageScreenshots } from './stageScreenshot';

function setTransformVisible(tc: TransformControls, v: boolean) {
  (tc as unknown as { visible: boolean }).visible = v;
}

// ── Body preset labels ──────────────────────────────────────────
const BODY_PRESETS: { key: string; label: string }[] = [
  { key: 'standing', label: '站立' }, { key: 'sitting', label: '坐下' },
  { key: 'walking', label: '行走' }, { key: 'running', label: '跑步' },
  { key: 'fighting', label: '格斗' }, { key: 'crouching', label: '蹲下' },
  { key: 'thinking', label: '思考' }, { key: 'tpose', label: 'T-Pose' },
  { key: 'hugging', label: '拥抱' }, { key: 'prone', label: '趴下' },
  { key: 'lying', label: '躺下' },
  { key: 'leaning', label: '倚靠' }, { key: 'kneeling', label: '跪' },
  { key: 'pointing', label: '指向' }, { key: 'bowing', label: '鞠躬' },
];

export interface ParallaxStage3DProps {
  panoramaUrl: string;     // equirectangular VR panorama (color)
  depthMapUrl: string;     // equirectangular depth map (grayscale: white=near, black=far)
  isOpen: boolean;
  onClose: () => void;
  sphereRadius?: number;
  parallaxScale?: number;  // strength of parallax effect (default 0.3)
  characters?: StageCharacter[];
  onCharactersUpdate?: (chars: StageCharacter[]) => void;
  onScreenshots?: (screenshots: StageScreenshots) => void;
  props?: StageProp[];     // 2D sprite props placed in the 3D scene
  /** Called when camera state changes (on close / screenshot) for persistence */
  onCameraStateChange?: (state: { position: { x: number; y: number; z: number }; fov: number; target: { x: number; y: number; z: number } }) => void;
  /** Restore camera to this state on open */
  initialCameraState?: { position: { x: number; y: number; z: number }; fov: number; target: { x: number; y: number; z: number } };
}

// ── Parallax Occlusion Mapping shader for sphere interior ────────

const pomVertexShader = /* glsl */ `
  varying vec3 vWorldPos;

  void main() {
    vWorldPos = (modelMatrix * vec4(position, 1.0)).xyz;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const pomFragmentShader = /* glsl */ `
  precision highp float;

  uniform sampler2D uPanorama;
  uniform sampler2D uDepthMap;
  uniform float uParallaxScale;
  uniform vec3 uCameraPos;

  varying vec3 vWorldPos;

  #define PI  3.14159265359
  #define TWO_PI 6.28318530718
  #define NUM_LINEAR_STEPS 32
  #define NUM_BINARY_STEPS 6

  vec2 dirToUV(vec3 dir) {
    float theta = atan(dir.x, -dir.z);
    float phi   = asin(clamp(dir.y, -1.0, 1.0));
    return vec2(0.5 + theta / TWO_PI, 0.5 + phi / PI);
  }

  void main() {
    vec3 surfDir = normalize(vWorldPos);
    vec3 viewDir = normalize(vWorldPos - uCameraPos);

    // ── Tangent frame on sphere ──
    vec3 upRef = abs(surfDir.y) < 0.99 ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0);
    vec3 T = normalize(cross(upRef, surfDir));   // tangent (longitude / u)
    vec3 B = cross(surfDir, T);                  // bitangent (latitude / v)

    // View direction projected into tangent space
    float vT = dot(viewDir, T);
    float vB = dot(viewDir, B);
    float vN = dot(viewDir, -surfDir);  // inward normal component

    // Clamp normal factor to avoid extreme offsets at grazing angles
    float nFactor = max(abs(vN), 0.2);

    // Maximum UV offset — converts tangent-space view direction to equirectangular UV
    vec2 maxOffset = vec2(
      vT / TWO_PI,
      -vB / PI
    ) * uParallaxScale / nFactor;

    // ── Steep Parallax Mapping ──
    float layerStep = 1.0 / float(NUM_LINEAR_STEPS);
    vec2 uvStep = maxOffset * layerStep;

    vec2 currentUV = dirToUV(surfDir);
    float currentLayer = 0.0;

    // Depth map: white=1=near(raised), black=0=far(base)
    // POM convention: layer goes from 0 (viewer) to 1 (surface)
    // We look for: layer >= (1 - depthSample) i.e. the recessed depth
    float currentMapH = texture2D(uDepthMap, currentUV).r;

    // March until we go below the surface
    for (int i = 0; i < NUM_LINEAR_STEPS; i++) {
      if (currentLayer >= (1.0 - currentMapH)) break;
      currentUV += uvStep;
      currentLayer += layerStep;
      currentMapH = texture2D(uDepthMap, currentUV).r;
    }

    // ── Binary refinement ──
    vec2 prevUV = currentUV - uvStep;
    float prevLayer = currentLayer - layerStep;

    for (int j = 0; j < NUM_BINARY_STEPS; j++) {
      vec2 midUV = (prevUV + currentUV) * 0.5;
      float midLayer = (prevLayer + currentLayer) * 0.5;
      float midH = texture2D(uDepthMap, midUV).r;

      if (midLayer < (1.0 - midH)) {
        prevUV = midUV;
        prevLayer = midLayer;
      } else {
        currentUV = midUV;
        currentLayer = midLayer;
      }
    }

    // ── Sample color ──
    vec4 color = texture2D(uPanorama, currentUV);
    // Three.js decodes sRGB to linear; re-encode for display
    color.rgb = pow(color.rgb, vec3(1.0 / 2.2));

    gl_FragColor = color;
  }
`;

// ══════════════════════════════════════════════════════════════════

export function ParallaxStage3D({
  panoramaUrl,
  depthMapUrl,
  isOpen,
  onClose,
  sphereRadius = 10,
  parallaxScale = 0.3,
  characters: initialCharacters = [],
  onCharactersUpdate,
  onScreenshots,
  props: stageProps = [],
  onCameraStateChange,
  initialCameraState,
}: ParallaxStage3DProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const transformRef = useRef<TransformControls | null>(null);
  const sphereMeshRef = useRef<THREE.Mesh | null>(null);
  const charGroupRef = useRef<THREE.Group | null>(null);
  const charObjsRef = useRef<Map<string, MannequinInstance>>(new Map());
  const propGroupRef = useRef<THREE.Group | null>(null);
  const propMeshesRef = useRef<Map<string, THREE.Mesh>>(new Map());
  const mannequinSourceRef = useRef<any>(null);
  const selectedCharIdRef = useRef<string | null>(null);
  const animIdRef = useRef(0);
  const raycasterRef = useRef(new THREE.Raycaster());
  const mouseRef = useRef(new THREE.Vector2());
  const groundPlaneRef = useRef(new THREE.Plane(new THREE.Vector3(0, 1, 0), 1.6)); // y = -1.6 (eye level)
  const dragRef = useRef<{ id: string; obj: THREE.Object3D } | null>(null);
  const isDraggingRef = useRef(false);
  const pointerDownOnCharRef = useRef(false);
  const transformDraggingRef = useRef(false);
  const ptrDownRef = useRef({ x: 0, y: 0 });

  const charsRef = useRef(initialCharacters);
  const onCharsUpdateRef = useRef(onCharactersUpdate);
  const onCloseRef = useRef(onClose);

  const [loading, setLoading] = useState(true);
  const [chars, setChars] = useState<StageCharacter[]>(initialCharacters);
  const [selectedCharId, setSelectedCharId] = useState<string | null>(null);
  const [currentParallax, setCurrentParallax] = useState(parallaxScale);
  const [mannequinReady, setMannequinReady] = useState(false);
  const [selectedJoint, setSelectedJoint] = useState<string | null>(null);
  const [leftHandPreset, setLeftHandPreset] = useState<string | null>(null);
  const [rightHandPreset, setRightHandPreset] = useState<string | null>(null);
  const [shutterPhase, setShutterPhase] = useState<'idle' | 'flash' | 'fade'>('idle');

  useEffect(() => { charsRef.current = chars; }, [chars]);

  // Sync characters from parent props (may update after mount)
  useEffect(() => {
    if (initialCharacters && initialCharacters.length > 0) {
      setChars(prev => {
        const prevIds = prev.map(c => c.id).sort().join(',');
        const newIds = initialCharacters.map(c => c.id).sort().join(',');
        return prevIds === newIds ? prev : initialCharacters;
      });
    }
  }, [initialCharacters]);

  const onScreenshotsRef = useRef(onScreenshots);
  const onCameraStateChangeRef = useRef(onCameraStateChange);
  useEffect(() => { onCharsUpdateRef.current = onCharactersUpdate; }, [onCharactersUpdate]);
  useEffect(() => { onScreenshotsRef.current = onScreenshots; }, [onScreenshots]);
  useEffect(() => { onCloseRef.current = onClose; }, [onClose]);
  useEffect(() => { onCameraStateChangeRef.current = onCameraStateChange; }, [onCameraStateChange]);
  useEffect(() => { selectedCharIdRef.current = selectedCharId; }, [selectedCharId]);

  /** Emit current camera state for persistence */
  const emitCameraState = useCallback(() => {
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!camera || !controls || !onCameraStateChangeRef.current) return;
    onCameraStateChangeRef.current({
      position: { x: camera.position.x, y: camera.position.y, z: camera.position.z },
      fov: camera.fov,
      target: { x: controls.target.x, y: controls.target.y, z: controls.target.z },
    });
  }, []);

  // ── Main scene setup ──
  useEffect(() => {
    if (!isOpen || !containerRef.current) return;
    const container = containerRef.current;
    const w = container.clientWidth;
    const h = container.clientHeight;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x08080f);
    sceneRef.current = scene;

    const eyeLevel = 1.6; // standard human eye height

    const camera = new THREE.PerspectiveCamera(75, w / h, 0.01, 200);
    camera.position.set(0, 0, 0.01);
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 0, -0.01); // look forward
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.enableZoom = false;   // we handle zoom via FOV
    controls.enablePan = false;    // we handle pan manually
    controls.rotateSpeed = -0.3;   // inverted for inside-sphere feel
    controlsRef.current = controls;

    // Restore camera state if available (from copy/paste or previous session)
    if (initialCameraState) {
      camera.position.set(initialCameraState.position.x, initialCameraState.position.y, initialCameraState.position.z);
      camera.fov = initialCameraState.fov;
      camera.updateProjectionMatrix();
      controls.target.set(initialCameraState.target.x, initialCameraState.target.y, initialCameraState.target.z);
      // Force immediate sync — damping would otherwise interpolate and drift
      controls.enableDamping = false;
      controls.update();
      controls.enableDamping = true;
    }
    controls.mouseButtons = { LEFT: THREE.MOUSE.ROTATE, MIDDLE: undefined as any, RIGHT: THREE.MOUSE.ROTATE };
    controls.update();
    controlsRef.current = controls;

    // TransformControls — rotation gizmo for joint manipulation
    const transform = new TransformControls(camera, renderer.domElement);
    transform.setMode('rotate');
    transform.setSize(0.6);
    setTransformVisible(transform, false);
    scene.add(transform.getHelper());
    transformRef.current = transform;

    transform.addEventListener('dragging-changed', (event) => {
      const dragging = (event as unknown as { value: boolean }).value;
      controls.enabled = !dragging;
      transformDraggingRef.current = dragging;
    });
    transform.addEventListener('objectChange', () => {
      const selId = selectedCharIdRef.current;
      if (!selId) return;
      const inst = charObjsRef.current.get(selId);
      if (!inst) return;
      // Read current pose from skeleton and update state
      const newAngles = readPose(inst.boneMap);
      const updated = charsRef.current.map(c =>
        c.id === selId ? { ...c, jointAngles: newAngles, presetName: '' } : c,
      );
      setChars(updated);
      onCharsUpdateRef.current?.(updated);
    });

    // FOV zoom via mouse wheel
    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();
      camera.fov = Math.max(30, Math.min(110, camera.fov + e.deltaY * 0.05));
      camera.updateProjectionMatrix();
    };
    container.addEventListener('wheel', handleWheel, { passive: false });

    // Manual middle-mouse pan
    let isPanning = false;
    let panStart = { x: 0, y: 0 };
    const panSensitivity = 0.01;

    const handlePanDown = (e: PointerEvent) => {
      if (e.button === 1) { // middle mouse
        e.preventDefault();
        isPanning = true;
        panStart = { x: e.clientX, y: e.clientY };
      }
    };
    const handlePanMove = (e: PointerEvent) => {
      if (!isPanning) return;
      const dx = (e.clientX - panStart.x) * panSensitivity;
      const dy = (e.clientY - panStart.y) * panSensitivity;
      panStart = { x: e.clientX, y: e.clientY };

      // Move camera in its local right/up directions
      const right = new THREE.Vector3();
      const up = new THREE.Vector3();
      camera.getWorldDirection(new THREE.Vector3());
      right.setFromMatrixColumn(camera.matrixWorld, 0); // camera right
      up.setFromMatrixColumn(camera.matrixWorld, 1);     // camera up

      const offset = right.multiplyScalar(-dx).add(up.multiplyScalar(dy));
      camera.position.add(offset);
      controls.target.add(offset);
    };
    const handlePanUp = (e: PointerEvent) => {
      if (e.button === 1) isPanning = false;
    };

    container.addEventListener('pointerdown', handlePanDown);
    container.addEventListener('pointermove', handlePanMove);
    container.addEventListener('pointerup', handlePanUp);

    // Lighting (for mannequin materials)
    scene.add(new THREE.AmbientLight(0xffffff, 0.8));
    const dirLight = new THREE.DirectionalLight(0xffffff, 0.6);
    dirLight.position.set(2, 4, 3);
    scene.add(dirLight);

    // Preload mannequin model (singleton, shared across clones)
    preloadMannequin().then((source) => {
      mannequinSourceRef.current = source;
      setMannequinReady(true);
    });

    // Character group — positioned at ground level (below eye level)
    const charGroup = new THREE.Group();
    charGroup.position.y = -eyeLevel;
    scene.add(charGroup);
    charGroupRef.current = charGroup;

    // Prop group — same ground level as characters
    const propGroup = new THREE.Group();
    propGroup.position.y = -eyeLevel;
    scene.add(propGroup);
    propGroupRef.current = propGroup;

    // Load textures
    setLoading(true);
    const loader = new THREE.TextureLoader();
    let panoTex: THREE.Texture | null = null;
    let depthTex: THREE.Texture | null = null;
    let loaded = 0;

    const checkReady = () => {
      loaded++;
      if (loaded < 2 || !panoTex || !depthTex) return;

      const R = sphereRadius;
      const geo = new THREE.SphereGeometry(R, 128, 64);

      const mat = new THREE.ShaderMaterial({
        uniforms: {
          uPanorama: { value: panoTex },
          uDepthMap: { value: depthTex },
          uParallaxScale: { value: currentParallax },
          uCameraPos: { value: camera.position.clone() },
        },
        vertexShader: pomVertexShader,
        fragmentShader: pomFragmentShader,
        side: THREE.BackSide,
      });

      const mesh = new THREE.Mesh(geo, mat);
      scene.add(mesh);
      sphereMeshRef.current = mesh;

      setLoading(false);
    };

    const loadTex = (url: string, cb: (t: THREE.Texture) => void) => {
      loader.load(url, (tex) => {
        tex.colorSpace = THREE.SRGBColorSpace;
        tex.minFilter = THREE.LinearFilter;
        tex.magFilter = THREE.LinearFilter;
        tex.wrapS = THREE.RepeatWrapping;
        tex.wrapT = THREE.ClampToEdgeWrapping;
        cb(tex);
        checkReady();
      }, undefined, () => {
        const img = new Image();
        img.crossOrigin = 'anonymous';
        img.onload = () => {
          const tex = new THREE.Texture(img);
          tex.colorSpace = THREE.SRGBColorSpace;
          tex.wrapS = THREE.RepeatWrapping;
          tex.wrapT = THREE.ClampToEdgeWrapping;
          tex.needsUpdate = true;
          cb(tex);
          checkReady();
        };
        img.onerror = () => { console.warn('[ParallaxStage3D] Texture load failed:', url); loaded++; setLoading(false); };
        img.src = url;
      });
    };

    loadTex(panoramaUrl, (t) => { panoTex = t; });
    if (depthMapUrl) {
      console.log('[ParallaxStage3D] Loading depth map:', depthMapUrl);
      loadTex(depthMapUrl, (t) => {
        t.colorSpace = THREE.LinearSRGBColorSpace;
        depthTex = t;
        console.log('[ParallaxStage3D] Depth map loaded successfully');
      });
    } else {
      console.log('[ParallaxStage3D] No depth map URL, using flat fallback');
      // No depth map — create a flat white texture (no parallax effect)
      const canvas = document.createElement('canvas');
      canvas.width = 4;
      canvas.height = 2;
      const ctx = canvas.getContext('2d')!;
      ctx.fillStyle = '#808080'; // mid-gray = no displacement
      ctx.fillRect(0, 0, 4, 2);
      depthTex = new THREE.CanvasTexture(canvas);
      depthTex.wrapS = THREE.RepeatWrapping;
      depthTex.wrapT = THREE.ClampToEdgeWrapping;
      loaded++;
      checkReady();
    }

    // ── Pointer events ──
    const handlePointerDown = (e: PointerEvent) => {
      // Skip all custom handling while TransformControls gizmo is being dragged
      if (transformDraggingRef.current) return;

      ptrDownRef.current = { x: e.clientX, y: e.clientY };
      isDraggingRef.current = false;
      pointerDownOnCharRef.current = false;

      const rect = container.getBoundingClientRect();
      mouseRef.current.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouseRef.current.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      raycasterRef.current.setFromCamera(mouseRef.current, camera);

      if (charGroupRef.current && charGroupRef.current.children.length > 0) {
        const hits = raycasterRef.current.intersectObjects(charGroupRef.current.children, true);
        if (hits.length > 0) {
          // Scan all hits — prioritize joint markers (they may be behind the mesh surface)
          let jointHitObj: THREE.Object3D | null = null;
          for (const hit of hits) {
            if (hit.object.userData?.jointName) { jointHitObj = hit.object; break; }
          }
          const hitObj = jointHitObj || hits[0].object;
          const jointName = hitObj.userData?.jointName as string | undefined;

          let target: THREE.Object3D = hitObj;
          while (target.parent && target.parent !== charGroupRef.current) target = target.parent;
          const charId = target.userData.characterId as string | undefined;
          if (charId) {
            pointerDownOnCharRef.current = true;
            setSelectedCharId(charId);
            if (jointName) {
              // Joint marker clicked — attach rotation gizmo to bone
              setSelectedJoint(jointName);
              const inst = charObjsRef.current.get(charId);
              if (inst && transformRef.current) {
                const bone = inst.boneMap.get(jointName);
                if (bone) {
                  transformRef.current.attach(bone);
                  setTransformVisible(transformRef.current, true);
                }
              }
            } else if (transformRef.current && (transformRef.current as unknown as { visible: boolean }).visible) {
              // Gizmo is active — body click just deselects joint, don't start drag
              setSelectedJoint(null);
              transformRef.current.detach();
              setTransformVisible(transformRef.current, false);
            } else {
              // No gizmo active — start drag
              setSelectedJoint(null);
              dragRef.current = { id: charId, obj: target };
              controls.enabled = false;
            }
            return;
          }
        }
      }
    };

    const handlePointerMove = (e: PointerEvent) => {
      if (transformDraggingRef.current) return;
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
          const maxR = sphereRadius * 0.8;
          pt.x = Math.max(-maxR, Math.min(maxR, pt.x));
          pt.z = Math.max(-maxR, Math.min(maxR, pt.z));
          const currentY = dragRef.current.obj.position.y;
          dragRef.current.obj.position.set(pt.x, currentY, pt.z);
        }
      }
    };

    const handlePointerUp = () => {
      if (transformDraggingRef.current) return;
      if (dragRef.current) {
        if (isDraggingRef.current) {
          const pos = dragRef.current.obj.position;
          const id = dragRef.current.id;
          const updated = charsRef.current.map(c =>
            c.id === id ? updateTransform(c, pos.x, pos.z) : c,
          );
          setChars(updated);
          onCharsUpdateRef.current?.(updated);
        }
        controls.enabled = true;
        dragRef.current = null;
      } else if (!isDraggingRef.current && !pointerDownOnCharRef.current) {
        // Click on empty space — deselect everything
        setSelectedCharId(null);
        setSelectedJoint(null);
        if (transformRef.current) {
          transformRef.current.detach();
          setTransformVisible(transformRef.current, false);
        }
      }
    };

    container.addEventListener('pointerdown', handlePointerDown);
    container.addEventListener('pointermove', handlePointerMove);
    container.addEventListener('pointerup', handlePointerUp);

    // ── Animation ──
    const animate = () => {
      animIdRef.current = requestAnimationFrame(animate);
      controls.update();

      // Clamp camera inside sphere after pan
      const maxMove = sphereRadius * 0.25;
      camera.position.x = Math.max(-maxMove, Math.min(maxMove, camera.position.x));
      camera.position.y = Math.max(-maxMove, Math.min(maxMove, camera.position.y));
      camera.position.z = Math.max(-maxMove, Math.min(maxMove, camera.position.z));

      // Update camera position uniform for POM.
      // POM requires camera offset from sphere center to produce parallax.
      // When camera is at center (the default), viewDir ≈ surfaceNormal everywhere,
      // so tangential components are ~0 and no UV displacement occurs.
      // Fix: offset virtual camera backward along view direction so that edge-of-view
      // fragments have meaningful tangential view components, creating visible depth.
      if (sphereMeshRef.current) {
        const mat = sphereMeshRef.current.material as THREE.ShaderMaterial;
        const dir = new THREE.Vector3();
        camera.getWorldDirection(dir);

        // Read the user-set base parallax scale (from slider / prop)
        // We store it separately to avoid feedback loops with attenuation
        const basePScale = mat.uniforms.uParallaxScale.value as number;

        // Attenuate POM strength when camera is off-center to reduce distortion.
        // Camera displacement causes asymmetric tangent-space view directions on the sphere,
        // producing visible warping. Reducing parallax scale at larger offsets mitigates this.
        const camOffset = camera.position.length();
        const offsetRatio = Math.min(camOffset / maxMove, 1.0);
        const attenuation = 1.0 - offsetRatio * 0.8; // 80% reduction at max offset

        // Virtual camera position: always offset from ORIGIN (not from displaced camera)
        // along the view direction. This keeps POM sampling symmetric regardless of pan.
        const virtualOffset = basePScale * attenuation * sphereRadius;
        const virtualPos = dir.clone().multiplyScalar(-virtualOffset);
        mat.uniforms.uCameraPos.value.copy(virtualPos);
      }

      // Update joint markers and facial features for all mannequins
      for (const inst of charObjsRef.current.values()) {
        inst.skeleton.update();
        positionFacialFeatures(inst, camera);
      }
      const selId = selectedCharIdRef.current;
      if (selId) {
        const inst = charObjsRef.current.get(selId);
        if (inst) updateJointMarkerPositions(inst);
      }

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
      container.removeEventListener('pointerdown', handlePanDown);
      container.removeEventListener('pointermove', handlePanMove);
      container.removeEventListener('pointerup', handlePanUp);
      container.removeEventListener('wheel', handleWheel);
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animIdRef.current);
      transform.dispose();
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
      transformRef.current = null;
      sphereMeshRef.current = null;
      charGroupRef.current = null;
      for (const inst of charObjsRef.current.values()) disposeInstance(inst);
      charObjsRef.current.clear();
      // Dispose prop meshes
      for (const mesh of propMeshesRef.current.values()) {
        mesh.geometry.dispose();
        const mat = mesh.material as THREE.MeshBasicMaterial;
        mat.map?.dispose();
        mat.dispose();
      }
      propMeshesRef.current.clear();
      propGroupRef.current = null;
      mannequinSourceRef.current = null;
      setMannequinReady(false);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, panoramaUrl, depthMapUrl, sphereRadius]);

  // ── Update parallax scale live ──
  useEffect(() => {
    if (sphereMeshRef.current) {
      const mat = sphereMeshRef.current.material as THREE.ShaderMaterial;
      mat.uniforms.uParallaxScale.value = currentParallax;
    }
  }, [currentParallax]);

  // ── Sync characters (mannequin instances) ──
  useEffect(() => {
    const group = charGroupRef.current;
    const source = mannequinSourceRef.current;
    if (!group || !source) return;

    const newIds = new Set(chars.map(c => c.id));

    // Remove deleted characters
    for (const [id, inst] of charObjsRef.current.entries()) {
      if (!newIds.has(id)) {
        group.remove(inst.root);
        disposeInstance(inst);
        charObjsRef.current.delete(id);
      }
    }

    // Create or sync existing characters
    for (const char of chars) {
      let inst = charObjsRef.current.get(char.id);
      if (!inst) {
        inst = cloneMannequin(source, char);
        // Label above head
        const label = createLabelSprite(char.name, char.color);
        label.position.y = 2.1;
        inst.root.add(label);
        // Shadow blob on ground (dark, radial fade — won't confuse Gemini)
        const shadowCanvas = document.createElement('canvas');
        shadowCanvas.width = 128;
        shadowCanvas.height = 128;
        const ctx = shadowCanvas.getContext('2d')!;
        const grad = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
        grad.addColorStop(0, 'rgba(0,0,0,0.75)');
        grad.addColorStop(0.5, 'rgba(0,0,0,0.4)');
        grad.addColorStop(0.8, 'rgba(0,0,0,0.15)');
        grad.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, 128, 128);
        const shadowTex = new THREE.CanvasTexture(shadowCanvas);
        const shadowGeo = new THREE.PlaneGeometry(0.8, 0.8);
        shadowGeo.rotateX(-Math.PI / 2);
        const shadowMat = new THREE.MeshBasicMaterial({
          map: shadowTex, transparent: true, depthWrite: false,
        });
        const shadow = new THREE.Mesh(shadowGeo, shadowMat);
        shadow.position.y = 0.005;
        shadow.renderOrder = -1;
        inst.root.add(shadow);
        // Color ring around shadow — editor-only, hidden during screenshot
        const ringGeo = new THREE.RingGeometry(0.42, 0.46, 48);
        ringGeo.rotateX(-Math.PI / 2);
        const ringMat = new THREE.MeshBasicMaterial({
          color: new THREE.Color(char.color), transparent: true, opacity: 0.7,
          depthWrite: false,
        });
        const ring = new THREE.Mesh(ringGeo, ringMat);
        ring.position.y = 0.006;
        ring.userData.editorOnly = true; // tag for screenshot hiding
        inst.root.add(ring);
        charObjsRef.current.set(char.id, inst);
        group.add(inst.root);
      } else {
        syncInstanceToCharacter(inst, char);
      }
    }
  }, [chars, mannequinReady]);

  // ── Sync 2D sprite props into scene ──
  useEffect(() => {
    const group = propGroupRef.current;
    if (!group) return;

    const newIds = new Set(stageProps.map(p => p.id));

    // Remove deleted props
    for (const [id, mesh] of propMeshesRef.current.entries()) {
      if (!newIds.has(id)) {
        group.remove(mesh);
        mesh.geometry.dispose();
        const mat = mesh.material as THREE.MeshBasicMaterial;
        mat.map?.dispose();
        mat.dispose();
        propMeshesRef.current.delete(id);
      }
    }

    // Create or update props
    for (const prop of stageProps) {
      let mesh = propMeshesRef.current.get(prop.id);
      if (!mesh) {
        // Create a textured plane for the prop
        const tex = new THREE.TextureLoader().load(prop.imageUrl);
        tex.colorSpace = THREE.SRGBColorSpace;
        const geo = new THREE.PlaneGeometry(1, 1);
        const mat = new THREE.MeshBasicMaterial({
          map: tex,
          transparent: true,
          side: THREE.DoubleSide,
          depthWrite: false,
        });
        mesh = new THREE.Mesh(geo, mat);
        mesh.userData.propId = prop.id;
        mesh.userData.propName = prop.name;
        propMeshesRef.current.set(prop.id, mesh);
        group.add(mesh);

        // Add a label sprite above the prop
        const label = createLabelSprite(prop.name, '#f59e0b');
        label.position.y = 0.7;
        mesh.add(label);
      }

      // Update transform
      mesh.position.set(prop.x, prop.y, prop.z);
      mesh.scale.setScalar(prop.scale);
      mesh.rotation.y = THREE.MathUtils.degToRad(prop.rotationY);
    }
  }, [stageProps]);

  // ── Selection: show/hide joint markers ──
  useEffect(() => {
    for (const [id, inst] of charObjsRef.current.entries()) {
      const selected = id === selectedCharId;
      setInstanceSelected(inst, selected);
      if (selected) updateJointMarkerPositions(inst);
    }
  }, [selectedCharId]);

  // ── Highlight selected joint ──
  useEffect(() => {
    if (!selectedCharId) return;
    const inst = charObjsRef.current.get(selectedCharId);
    if (!inst) return;
    for (const [name, marker] of inst.jointMarkers.entries()) {
      const mat = marker.material as THREE.MeshBasicMaterial;
      if (name === selectedJoint) {
        mat.color.set(0xff8800);
        mat.opacity = 0.9;
        marker.scale.setScalar(1.5);
      } else {
        mat.color.set(0x44aaff);
        mat.opacity = 0.6;
        marker.scale.setScalar(1.0);
      }
    }
  }, [selectedJoint, selectedCharId]);

  // ── Keyboard ──
  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { emitCameraState(); onCloseRef.current(); }
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
    const newChar = createStageCharacter(idx);
    const updated = [...charsRef.current, newChar];
    setChars(updated);
    setSelectedCharId(newChar.id);
    onCharsUpdateRef.current?.(updated);
  }, []);

  const handlePresetChange = useCallback((presetKey: string) => {
    if (!selectedCharId) return;
    const updated = charsRef.current.map(c =>
      c.id === selectedCharId ? applyBodyPreset(c, presetKey) : c,
    );
    setChars(updated);
    onCharsUpdateRef.current?.(updated);
    // Detach gizmo on preset change (bone positions change)
    setSelectedJoint(null);
    if (transformRef.current) {
      transformRef.current.detach();
      setTransformVisible(transformRef.current, false);
    }
  }, [selectedCharId]);

  const handleScaleChange = useCallback((scale: number) => {
    if (!selectedCharId) return;
    const updated = charsRef.current.map(c =>
      c.id === selectedCharId ? updateScale(c, scale) : c,
    );
    setChars(updated);
    onCharsUpdateRef.current?.(updated);
  }, [selectedCharId]);

  const handleRotationChange = useCallback((deg: number) => {
    if (!selectedCharId) return;
    const updated = charsRef.current.map(c =>
      c.id === selectedCharId ? updateRotation(c, deg) : c,
    );
    setChars(updated);
    onCharsUpdateRef.current?.(updated);
  }, [selectedCharId]);

  const handleYChange = useCallback((y: number) => {
    if (!selectedCharId) return;
    const updated = charsRef.current.map(c =>
      c.id === selectedCharId ? updateY(c, y) : c,
    );
    setChars(updated);
    onCharsUpdateRef.current?.(updated);
  }, [selectedCharId]);

  const handleJointAngleChange = useCallback((joint: string, axis: 'x' | 'y' | 'z', value: number) => {
    if (!selectedCharId) return;
    const updated = charsRef.current.map(c => {
      if (c.id !== selectedCharId) return c;
      const prev = c.jointAngles[joint] || { x: 0, y: 0, z: 0 };
      return updateJointAngles(c, { [joint]: { ...prev, [axis]: value } });
    });
    setChars(updated);
    onCharsUpdateRef.current?.(updated);
  }, [selectedCharId]);

  const handleHandPreset = useCallback((side: 'left' | 'right', key: string) => {
    if (!selectedCharId) return;
    const inst = charObjsRef.current.get(selectedCharId);
    if (!inst) return;
    applyHandPreset(inst.boneMap, side, key);
    if (side === 'left') setLeftHandPreset(key);
    else setRightHandPreset(key);
    // Read back full pose and update state
    const newAngles = readPose(inst.boneMap);
    const updated = charsRef.current.map(c =>
      c.id === selectedCharId ? { ...c, jointAngles: newAngles } : c,
    );
    setChars(updated);
    onCharsUpdateRef.current?.(updated);
  }, [selectedCharId]);

  // ── Screenshot ──
  const handleScreenshot = useCallback(() => {
    const renderer = rendererRef.current;
    const scene = sceneRef.current;
    const camera = cameraRef.current;
    const group = charGroupRef.current;
    if (!renderer || !scene || !camera || !group) return;

    // Hide editor-only elements (color rings, labels, joint markers, gizmo)
    const hidden: THREE.Object3D[] = [];
    const hideObj = (obj: THREE.Object3D) => {
      if (obj.visible) { obj.visible = false; hidden.push(obj); }
    };
    group.traverse((child) => {
      if (child.userData.editorOnly) hideObj(child);
      if (child.userData.jointName) hideObj(child);
      if ((child as any).isSprite) hideObj(child); // labels
    });
    // Keep Beta_Joints visible — they define the human form for Gemini
    if (transformRef.current) setTransformVisible(transformRef.current, false);

    // Save original size
    const origW = renderer.domElement.width;
    const origH = renderer.domElement.height;
    renderer.setSize(1920, 1080);
    camera.aspect = 1920 / 1080;
    camera.updateProjectionMatrix();

    // Update positions before screenshot
    for (const inst of charObjsRef.current.values()) {
      inst.skeleton.update();
      positionFacialFeatures(inst, camera);
    }

    // 1. Base scene screenshot (all characters visible)
    renderer.render(scene, camera);
    const base = renderer.domElement.toDataURL('image/jpeg', 0.6).split(',')[1];

    // 2. Per-character isolated screenshots
    const charScreenshots: StageScreenshots['characters'] = [];
    const allRoots = new Map<string, boolean>(); // charId → original visibility
    for (const [id, inst] of charObjsRef.current.entries()) {
      allRoots.set(id, inst.root.visible);
    }

    for (const char of charsRef.current) {
      // Hide all other characters
      for (const [id, inst] of charObjsRef.current.entries()) {
        inst.root.visible = (id === char.id);
      }
      renderer.render(scene, camera);

      // Crop to character bounding box with padding
      const inst = charObjsRef.current.get(char.id);
      let croppedB64 = renderer.domElement.toDataURL('image/jpeg', 0.6).split(',')[1];
      let charBbox: { left: number; top: number; width: number; height: number } | undefined;
      if (inst) {
        const box = new THREE.Box3().setFromObject(inst.root);
        const corners = [
          new THREE.Vector3(box.min.x, box.min.y, box.min.z),
          new THREE.Vector3(box.max.x, box.min.y, box.min.z),
          new THREE.Vector3(box.min.x, box.max.y, box.min.z),
          new THREE.Vector3(box.max.x, box.max.y, box.min.z),
          new THREE.Vector3(box.min.x, box.min.y, box.max.z),
          new THREE.Vector3(box.max.x, box.min.y, box.max.z),
          new THREE.Vector3(box.min.x, box.max.y, box.max.z),
          new THREE.Vector3(box.max.x, box.max.y, box.max.z),
        ];
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        for (const c of corners) {
          c.project(camera);
          const sx = (c.x * 0.5 + 0.5) * 1920;
          const sy = (1 - (c.y * 0.5 + 0.5)) * 1080;
          if (sx < minX) minX = sx;
          if (sy < minY) minY = sy;
          if (sx > maxX) maxX = sx;
          if (sy > maxY) maxY = sy;
        }
        // Add padding (15% of character size)
        const padX = (maxX - minX) * 0.15;
        const padY = (maxY - minY) * 0.15;
        const cx = Math.max(0, Math.floor(minX - padX));
        const cy = Math.max(0, Math.floor(minY - padY));
        const cw = Math.min(1920 - cx, Math.ceil(maxX - minX + padX * 2));
        const ch = Math.min(1080 - cy, Math.ceil(maxY - minY + padY * 2));
        if (cw > 10 && ch > 10) {
          const cropCanvas = document.createElement('canvas');
          cropCanvas.width = cw;
          cropCanvas.height = ch;
          const cropCtx = cropCanvas.getContext('2d')!;
          cropCtx.drawImage(renderer.domElement, cx, cy, cw, ch, 0, 0, cw, ch);
          croppedB64 = cropCanvas.toDataURL('image/jpeg', 0.6).split(',')[1];
          // Compute bounding box as percentage of frame (1 decimal for precision)
          charBbox = {
            left: Math.round((cx / 1920) * 1000) / 10,
            top: Math.round((cy / 1080) * 1000) / 10,
            width: Math.round((cw / 1920) * 1000) / 10,
            height: Math.round((ch / 1080) * 1000) / 10,
          };
        }
      }

      charScreenshots.push({
        stageCharId: char.id,
        stageCharName: char.name,
        color: char.color,
        screenshot: croppedB64,
        bbox: charBbox,
      });
    }

    // Restore all characters visibility
    for (const [id, inst] of charObjsRef.current.entries()) {
      inst.root.visible = allRoots.get(id) ?? true;
    }

    // Restore size
    renderer.setSize(origW, origH);
    camera.aspect = origW / origH;
    camera.updateProjectionMatrix();

    // Restore hidden elements
    for (const obj of hidden) obj.visible = true;
    if (transformRef.current && selectedCharIdRef.current) {
      setTransformVisible(transformRef.current, true);
    }

    const result: StageScreenshots = { base, characters: charScreenshots };
    onScreenshotsRef.current?.(result);

    // Persist camera state alongside screenshots
    emitCameraState();

    // Freeze controls so damping doesn't drift during shutter animation
    if (controlsRef.current) controlsRef.current.enabled = false;

    // Trigger shutter animation → auto-close
    setShutterPhase('flash');
  }, []);

  const handleResetView = useCallback(() => {
    if (!cameraRef.current || !controlsRef.current) return;
    cameraRef.current.position.set(0, 0, 0.01);
    cameraRef.current.fov = 75;
    cameraRef.current.updateProjectionMatrix();
    controlsRef.current.target.set(0, 0, -0.01);
    controlsRef.current.update();
  }, []);

  const selectedChar = chars.find(c => c.id === selectedCharId);

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
            <div style={{ fontSize: 13 }}>加载场景中...</div>
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
          视差 3D 导演台
        </div>

        <div style={{ marginBottom: 6 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.35)' }}>视差强度</span>
            <span style={{ fontSize: 9, color: 'rgba(6,182,212,0.8)' }}>{currentParallax.toFixed(2)}</span>
          </div>
          <input
            type="range" min={0} max={1.0} step={0.01}
            value={currentParallax}
            onChange={e => setCurrentParallax(parseFloat(e.target.value))}
            style={{ width: '100%', accentColor: '#06b6d4' }}
          />
        </div>

        <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.25)', lineHeight: 1.6 }}>
          VR 全景 + 深度图 → 视差遮挡映射<br />
          纹理保持原始画质，shader 制造 3D 错觉<br />
          拖拽旋转 | 滚轮前移 | 中键平移
        </div>
      </div>

      {/* Character panel (top-right) */}
      <div style={{
        position: 'absolute', top: 16, right: 16, zIndex: 20,
        background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(12px)',
        borderRadius: 12, padding: '10px 12px', minWidth: 180,
        border: '1px solid rgba(255,255,255,0.08)',
        maxHeight: 'calc(100vh - 120px)', overflowY: 'auto',
      }}>
        <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', letterSpacing: 1, marginBottom: 8 }}>
          角色 ({chars.length})
        </div>
        {chars.map(c => (
          <div key={c.id}
            onClick={() => {
              setSelectedCharId(c.id === selectedCharId ? null : c.id);
              setSelectedJoint(null);
              if (transformRef.current) { transformRef.current.detach(); setTransformVisible(transformRef.current, false); }
            }}
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '5px 6px', borderRadius: 6, cursor: 'pointer', marginBottom: 2,
              background: c.id === selectedCharId ? 'rgba(6,182,212,0.15)' : 'transparent',
            }}
          >
            <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: c.color }} />
            <span style={{ fontSize: 11, color: c.id === selectedCharId ? 'rgba(6,182,212,1)' : 'rgba(255,255,255,0.7)', flex: 1 }}>{c.name}</span>
          </div>
        ))}
        <button onClick={handleAddChar} style={{
          width: '100%', marginTop: 6, padding: '6px 0', borderRadius: 6,
          background: 'rgba(6,182,212,0.12)', border: '1px solid rgba(6,182,212,0.25)',
          color: 'rgba(6,182,212,0.8)', fontSize: 11, cursor: 'pointer',
        }}>+ 添加角色</button>

        {/* ── Selected character controls ── */}
        {selectedChar && (
          <>
            {/* Body presets */}
            <div style={{ marginTop: 10, borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 8 }}>
              <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.35)', marginBottom: 6 }}>身体预设</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                {BODY_PRESETS.map(p => (
                  <button key={p.key} onClick={() => handlePresetChange(p.key)} style={{
                    padding: '3px 7px', borderRadius: 4, fontSize: 9, cursor: 'pointer',
                    background: selectedChar.presetName === p.key ? 'rgba(6,182,212,0.2)' : 'rgba(255,255,255,0.04)',
                    border: selectedChar.presetName === p.key ? '1px solid rgba(6,182,212,0.4)' : '1px solid rgba(255,255,255,0.08)',
                    color: selectedChar.presetName === p.key ? 'rgba(6,182,212,1)' : 'rgba(255,255,255,0.5)',
                  }}>{p.label}</button>
                ))}
              </div>
            </div>
            {/* Hand presets */}
            <div style={{ marginTop: 8, borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 8 }}>
              <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.35)', marginBottom: 4 }}>左手</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3, marginBottom: 6 }}>
                {(Object.entries(HAND_PRESETS) as [string, { label: string }][]).map(([key, hp]) => (
                  <button key={`L${key}`} onClick={() => handleHandPreset('left', key)} style={{
                    padding: '3px 7px', borderRadius: 4, fontSize: 9, cursor: 'pointer',
                    background: leftHandPreset === key ? 'rgba(96,165,250,0.2)' : 'rgba(255,255,255,0.04)',
                    border: leftHandPreset === key ? '1px solid rgba(96,165,250,0.4)' : '1px solid rgba(255,255,255,0.08)',
                    color: leftHandPreset === key ? 'rgba(96,165,250,1)' : 'rgba(255,255,255,0.5)',
                  }}>{hp.label}</button>
                ))}
              </div>
              <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.35)', marginBottom: 4 }}>右手</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                {(Object.entries(HAND_PRESETS) as [string, { label: string }][]).map(([key, hp]) => (
                  <button key={`R${key}`} onClick={() => handleHandPreset('right', key)} style={{
                    padding: '3px 7px', borderRadius: 4, fontSize: 9, cursor: 'pointer',
                    background: rightHandPreset === key ? 'rgba(96,165,250,0.2)' : 'rgba(255,255,255,0.04)',
                    border: rightHandPreset === key ? '1px solid rgba(96,165,250,0.4)' : '1px solid rgba(255,255,255,0.08)',
                    color: rightHandPreset === key ? 'rgba(96,165,250,1)' : 'rgba(255,255,255,0.5)',
                  }}>{hp.label}</button>
                ))}
              </div>
            </div>
            {/* Scale slider */}
            <div style={{ marginTop: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.35)' }}>大小</span>
                <span style={{ fontSize: 9, color: 'rgba(6,182,212,0.8)' }}>{selectedChar.scale.toFixed(1)}</span>
              </div>
              <input type="range" min={0.3} max={3.0} step={0.1} value={selectedChar.scale}
                onChange={e => handleScaleChange(parseFloat(e.target.value))}
                style={{ width: '100%', accentColor: '#06b6d4' }}
              />
            </div>
            {/* Rotation slider */}
            <div style={{ marginTop: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.35)' }}>旋转</span>
                <span style={{ fontSize: 9, color: 'rgba(6,182,212,0.8)' }}>{selectedChar.rotationY}°</span>
              </div>
              <input type="range" min={-180} max={180} step={5} value={selectedChar.rotationY}
                onChange={e => handleRotationChange(parseFloat(e.target.value))}
                style={{ width: '100%', accentColor: '#06b6d4' }}
              />
            </div>
            {/* Y offset slider */}
            <div style={{ marginTop: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.35)' }}>上下</span>
                <span style={{ fontSize: 9, color: 'rgba(6,182,212,0.8)' }}>{selectedChar.y.toFixed(1)}m</span>
              </div>
              <input type="range" min={-2} max={2} step={0.1} value={selectedChar.y}
                onChange={e => handleYChange(parseFloat(e.target.value))}
                style={{ width: '100%', accentColor: '#06b6d4' }}
              />
            </div>
            {/* Joint angle controls */}
            {selectedJoint && (
              <div style={{ marginTop: 8, borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.35)' }}>关节: {selectedJoint}</span>
                  <button onClick={() => setSelectedJoint(null)} style={{
                    padding: '1px 6px', borderRadius: 3, fontSize: 8, cursor: 'pointer',
                    background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.12)',
                    color: 'rgba(255,255,255,0.4)',
                  }}>×</button>
                </div>
                {(['x', 'y', 'z'] as const).map(axis => {
                  const angles = selectedChar.jointAngles[selectedJoint] || { x: 0, y: 0, z: 0 };
                  return (
                    <div key={axis} style={{ marginBottom: 4 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                        <span style={{ fontSize: 8, color: 'rgba(255,255,255,0.3)' }}>{axis.toUpperCase()}</span>
                        <span style={{ fontSize: 8, color: 'rgba(6,182,212,0.7)' }}>{angles[axis]}°</span>
                      </div>
                      <input type="range" min={-180} max={180} step={5} value={angles[axis]}
                        onChange={e => handleJointAngleChange(selectedJoint, axis, parseFloat(e.target.value))}
                        style={{ width: '100%', accentColor: '#06b6d4' }}
                      />
                    </div>
                  );
                })}
              </div>
            )}
            <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.25)', marginTop: 6, textAlign: 'center' }}>
              拖拽移动 | Delete 删除 | 点击关节调整
            </div>
          </>
        )}
      </div>

      {/* Bottom */}
      <div style={{
        position: 'absolute', bottom: 24, left: '50%', transform: 'translateX(-50%)',
        display: 'flex', gap: 8, zIndex: 20,
      }}>
        <button onClick={handleScreenshot} disabled={shutterPhase !== 'idle'} style={{
          padding: '10px 20px', borderRadius: 12,
          background: 'rgba(52,211,153,0.2)', border: '1px solid rgba(52,211,153,0.4)',
          color: 'rgba(52,211,153,0.9)', fontSize: 13, fontWeight: 500, cursor: shutterPhase !== 'idle' ? 'not-allowed' : 'pointer', backdropFilter: 'blur(8px)',
          opacity: shutterPhase !== 'idle' ? 0.4 : 1,
        }}>截图</button>
        <button onClick={handleResetView} style={{
          padding: '10px 20px', borderRadius: 12,
          background: 'rgba(255,255,255,0.12)', border: '1px solid rgba(255,255,255,0.15)',
          color: 'rgba(255,255,255,0.8)', fontSize: 13, cursor: 'pointer', backdropFilter: 'blur(8px)',
        }}>重置视角</button>
        <button onClick={() => { emitCameraState(); onClose(); }} style={{
          padding: '10px 20px', borderRadius: 12,
          background: 'rgba(255,255,255,0.12)', border: '1px solid rgba(255,255,255,0.15)',
          color: 'rgba(255,255,255,0.8)', fontSize: 13, cursor: 'pointer', backdropFilter: 'blur(8px)',
        }}>关闭</button>
      </div>

      <div style={{ position: 'absolute', bottom: 8, right: 16, zIndex: 20, fontSize: 10, color: 'rgba(255,255,255,0.2)' }}>
        ESC 关闭 | 拖拽旋转 | 滚轮缩放 | 中键平移
      </div>

      {/* Shutter animation overlay */}
      {shutterPhase === 'flash' && (
        <div
          style={{
            position: 'absolute', inset: 0, zIndex: 100,
            background: '#fff',
            animation: 'shutterFlash 200ms ease-out forwards',
            pointerEvents: 'none',
          }}
          onAnimationEnd={() => setShutterPhase('fade')}
        />
      )}
      {shutterPhase === 'fade' && (
        <div
          style={{
            position: 'absolute', inset: 0, zIndex: 100,
            background: '#000',
            animation: 'shutterFade 400ms ease-in forwards',
            pointerEvents: 'none',
          }}
          onAnimationEnd={() => { setShutterPhase('idle'); emitCameraState(); onCloseRef.current?.(); }}
        />
      )}
      <style>{`
        @keyframes shutterFlash {
          0% { opacity: 0.85; }
          100% { opacity: 0; }
        }
        @keyframes shutterFade {
          0% { opacity: 0; }
          100% { opacity: 1; }
        }
      `}</style>
    </div>,
    document.body,
  );
}

export default ParallaxStage3D;
