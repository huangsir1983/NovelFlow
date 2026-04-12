/**
 * Mannequin instance manager for the 3D director stage.
 *
 * - Singleton loader: loads Xbot.glb once, clones for each character
 * - Uses SkeletonUtils.clone() to share geometry, independent skeletons
 * - Manages joint markers + gap fills per instance (only visible on selection)
 * - Exposes apply/read pose, scale, and disposal
 */

import * as THREE from 'three';
import * as SkeletonUtils from 'three/examples/jsm/utils/SkeletonUtils.js';
import {
  loadMannequin,
  highlightJoint,
  applyPose,
  applyHandPreset,
  readPose,
  type MannequinResult,
} from '../../lib/mannequinGeometry';
import type { StageCharacter } from './stageCharacter';

// ── Types ────────────────────────────────────────────────────────

export interface MannequinInstance {
  characterId: string;
  model: THREE.Object3D;       // cloned scene root
  skinnedMesh: THREE.SkinnedMesh;
  skeleton: THREE.Skeleton;
  boneMap: Map<string, THREE.Bone>;
  jointMarkers: Map<string, THREE.Mesh>;
  gapFills: Map<string, THREE.Mesh>;
  facialFeatures: Map<string, THREE.Mesh>;
  /** Captured on first positionFacialFeatures call (rest pose head orientation) */
  headRestWorldQuat: THREE.Quaternion | null;
  /** Root group that holds model + helpers, added to scene */
  root: THREE.Group;
  /** Separate group for facial features — added to scene (NOT root) for world-space positioning */
  faceGroup: THREE.Group;
}

// ── Singleton source model ───────────────────────────────────────

let _sourcePromise: Promise<MannequinResult> | null = null;

export function preloadMannequin(modelUrl = '/models/Xbot.glb'): Promise<MannequinResult> {
  if (!_sourcePromise) {
    _sourcePromise = loadMannequin(modelUrl).then((result) => {
      // Hide the source model (it's only used for cloning)
      result.model.visible = false;
      return result;
    });
  }
  return _sourcePromise;
}

// ── Clone a mannequin for a character ────────────────────────────

export function cloneMannequin(source: MannequinResult, char: StageCharacter): MannequinInstance {
  const root = new THREE.Group();
  root.name = `mannequin_${char.id}`;
  root.userData.characterId = char.id;

  // Clone the model (shares geometry, creates independent skeleton)
  const clonedModel = SkeletonUtils.clone(source.model);
  clonedModel.visible = true;

  // Find the skinned mesh and skeleton in the clone
  let skinnedMesh: THREE.SkinnedMesh | null = null;
  clonedModel.traverse((child) => {
    if ((child as THREE.SkinnedMesh).isSkinnedMesh) {
      const sm = child as THREE.SkinnedMesh;
      if (sm.name === 'Beta_Surface') skinnedMesh = sm;
    }
  });

  if (!skinnedMesh) throw new Error('Cloned model missing Beta_Surface');
  const skeleton = (skinnedMesh as THREE.SkinnedMesh).skeleton;

  // Build bone map for the clone
  const boneMap = new Map<string, THREE.Bone>();
  const BONE_NAME_MAP: Record<string, string> = {
    hips: 'mixamorigHips', spine: 'mixamorigSpine', spine1: 'mixamorigSpine1',
    chest: 'mixamorigSpine2', neck: 'mixamorigNeck', head: 'mixamorigHead',
    leftShoulder: 'mixamorigLeftShoulder', leftUpperArm: 'mixamorigLeftArm',
    leftLowerArm: 'mixamorigLeftForeArm', leftHand: 'mixamorigLeftHand',
    rightShoulder: 'mixamorigRightShoulder', rightUpperArm: 'mixamorigRightArm',
    rightLowerArm: 'mixamorigRightForeArm', rightHand: 'mixamorigRightHand',
    leftUpperLeg: 'mixamorigLeftUpLeg', leftLowerLeg: 'mixamorigLeftLeg',
    leftFoot: 'mixamorigLeftFoot',
    rightUpperLeg: 'mixamorigRightUpLeg', rightLowerLeg: 'mixamorigRightLeg',
    rightFoot: 'mixamorigRightFoot',
    leftThumb: 'mixamorigLeftHandThumb1', leftIndex: 'mixamorigLeftHandIndex1',
    leftMiddle: 'mixamorigLeftHandMiddle1', leftRing: 'mixamorigLeftHandRing1',
    leftPinky: 'mixamorigLeftHandPinky1',
    rightThumb: 'mixamorigRightHandThumb1', rightIndex: 'mixamorigRightHandIndex1',
    rightMiddle: 'mixamorigRightHandMiddle1', rightRing: 'mixamorigRightHandRing1',
    rightPinky: 'mixamorigRightHandPinky1',
  };

  for (const [ourName, mixamoName] of Object.entries(BONE_NAME_MAP)) {
    let bone = skeleton.bones.find((b) => b.name === mixamoName);
    if (!bone) {
      const colonName = mixamoName.replace('mixamorig', 'mixamorig:');
      bone = skeleton.bones.find((b) => b.name === colonName);
    }
    if (bone) boneMap.set(ourName, bone);
  }

  // Tint model with character color for visual differentiation
  clonedModel.traverse((child) => {
    const mesh = child as THREE.Mesh;
    if (mesh.isMesh && mesh.material) {
      const mat = (mesh.material as THREE.Material).clone();
      if ((mat as any).color) {
        (mat as any).color.set(char.color);
      }
      mesh.material = mat;
    }
  });

  root.add(clonedModel);

  // Apply initial state
  root.position.set(char.x, char.y || 0, char.z);
  root.rotation.y = ((char.rotationY || 0) * Math.PI) / 180;
  root.scale.setScalar(char.scale);

  // Apply pose if provided
  if (char.jointAngles && Object.keys(char.jointAngles).length > 0) {
    applyPose(boneMap, char.jointAngles);
  }

  // Create facial features as children of root (positioned like joint markers via worldToLocal).
  const facialFeatures = new Map<string, THREE.Mesh>();
  const faceGroup = new THREE.Group(); // unused placeholder for interface compat
  {
    const makeFaceMat = (color: number, _roughness?: number): THREE.MeshBasicMaterial => {
      // MeshBasicMaterial — unaffected by lights, always visible.
      // depthTest off: renders on top of head mesh. depthWrite off: doesn't occlude others.
      return new THREE.MeshBasicMaterial({ color, depthTest: false, depthWrite: false });
    };
    const eyeMat = makeFaceMat(0x1a1008, 0.3);
    const browMat = makeFaceMat(0x2a1a0a, 0.8);
    const noseMat = makeFaceMat(0xc0a080, 0.6);
    const mouthMat = makeFaceMat(0xb06060, 0.5);

    const browCurve = new THREE.QuadraticBezierCurve3(
      new THREE.Vector3(-0.016, 0, -0.004),
      new THREE.Vector3(0, 0, 0.003),
      new THREE.Vector3(0.016, 0, -0.004),
    );
    const mouthCurve = new THREE.QuadraticBezierCurve3(
      new THREE.Vector3(-0.016, 0, -0.003),
      new THREE.Vector3(0, 0, 0.002),
      new THREE.Vector3(0.016, 0, -0.003),
    );

    // Offsets in headBone local space (X=right, Y=up, Z=forward)
    const faceSpecs: Array<{ name: string; geo: THREE.BufferGeometry; mat: THREE.Material; offset: [number, number, number] }> = [
      { name: 'leftEye',   geo: new THREE.SphereGeometry(0.012, 8, 6), mat: eyeMat,         offset: [-0.040, 0.08, 0.13] },
      { name: 'rightEye',  geo: new THREE.SphereGeometry(0.012, 8, 6), mat: eyeMat.clone(),  offset: [0.040, 0.08, 0.13] },
      { name: 'leftBrow',  geo: new THREE.TubeGeometry(browCurve, 8, 0.003, 4, false),  mat: browMat,         offset: [-0.040, 0.105, 0.13] },
      { name: 'rightBrow', geo: new THREE.TubeGeometry(browCurve, 8, 0.003, 4, false),  mat: browMat.clone(),  offset: [0.040, 0.105, 0.13] },
      { name: 'nose',      geo: new THREE.SphereGeometry(0.010, 8, 6), mat: noseMat,        offset: [0, 0.040, 0.14] },
      { name: 'mouth',     geo: new THREE.TubeGeometry(mouthCurve, 8, 0.003, 4, false), mat: mouthMat,       offset: [0, -0.005, 0.13] },
    ];

    // Debug: log head bone status
    const hb = boneMap.get('head');
    console.log('[FACE] headBone found:', !!hb, 'boneMap keys:', [...boneMap.keys()].join(','));

    for (const spec of faceSpecs) {
      const mesh = new THREE.Mesh(spec.geo, spec.mat);
      mesh.name = `face_${spec.name}`;
      mesh.userData.localOffset = new THREE.Vector3(spec.offset[0], spec.offset[1], spec.offset[2]);
      mesh.renderOrder = 998;
      root.add(mesh);
      facialFeatures.set(spec.name, mesh);
    }
  }

  // Create lightweight joint markers (invisible by default, shown on selection)
  // We create simple small spheres — not using the full mannequinGeometry markers
  // to keep them lightweight for multiple characters
  const jointMarkers = new Map<string, THREE.Mesh>();
  const markerMat = new THREE.MeshBasicMaterial({
    color: 0x44aaff, transparent: true, opacity: 0.6, depthTest: false,
  });
  const FINGER_JOINTS = new Set([
    'leftThumb', 'leftIndex', 'leftMiddle', 'leftRing', 'leftPinky',
    'rightThumb', 'rightIndex', 'rightMiddle', 'rightRing', 'rightPinky',
  ]);
  for (const [name] of boneMap.entries()) {
    const r = FINGER_JOINTS.has(name) ? 0.02 : 0.05;
    const geo = new THREE.SphereGeometry(r, 8, 6);
    const mesh = new THREE.Mesh(geo, markerMat.clone());
    mesh.name = `joint_${name}`;
    mesh.userData.jointName = name;
    mesh.userData.characterId = char.id;
    mesh.renderOrder = 999;
    mesh.visible = false; // hidden until selected
    root.add(mesh);
    jointMarkers.set(name, mesh);
  }

  // Minimal gap fills (just the key ones for visual quality)
  const gapFills = new Map<string, THREE.Mesh>();

  return {
    characterId: char.id,
    model: clonedModel,
    skinnedMesh: skinnedMesh as THREE.SkinnedMesh,
    skeleton,
    boneMap,
    jointMarkers,
    gapFills,
    facialFeatures,
    headRestWorldQuat: null,
    root,
    faceGroup,
  };
}

// ── Update instance from character state ─────────────────────────

export function syncInstanceToCharacter(inst: MannequinInstance, char: StageCharacter): void {
  inst.root.position.set(char.x, char.y || 0, char.z);
  inst.root.rotation.y = ((char.rotationY || 0) * Math.PI) / 180;
  inst.root.scale.setScalar(char.scale);
  if (char.jointAngles) {
    applyPose(inst.boneMap, char.jointAngles);
  }
  positionFacialFeatures(inst);
}

// ── Selection: show/hide joint markers ───────────────────────────

export function setInstanceSelected(inst: MannequinInstance, selected: boolean): void {
  for (const marker of inst.jointMarkers.values()) {
    marker.visible = selected;
  }
}

export function updateJointMarkerPositions(inst: MannequinInstance): void {
  // Ensure world matrices are up-to-date before reading bone positions
  inst.root.updateMatrixWorld(true);
  const worldPos = new THREE.Vector3();
  for (const [name, marker] of inst.jointMarkers.entries()) {
    const bone = inst.boneMap.get(name);
    if (bone) {
      // Get bone world position, then convert to root-local space
      // (markers are children of root, so their position is root-local)
      bone.getWorldPosition(worldPos);
      inst.root.worldToLocal(worldPos);
      marker.position.copy(worldPos);
    }
  }
}

// ── Position facial features (same pattern as joint markers) ─────

const _fwp = new THREE.Vector3();

/**
 * Position facial features using headBone.localToWorld → root.worldToLocal.
 * Same proven approach as updateJointMarkerPositions.
 * Features are children of root, offsets are in headBone local space.
 */
const _headWorldQuat = new THREE.Quaternion();
const _rootQuat = new THREE.Quaternion();
const _delta = new THREE.Quaternion();
const _faceDir = new THREE.Vector3();
const _toCamera = new THREE.Vector3();

/**
 * Position facial features using skeleton boneInverses for actual head position,
 * and full bone-chain world quaternion for rotation tracking.
 *
 * Xbot model has bones at origin in Object3D hierarchy; real positions
 * are encoded in skeleton.boneInverses (bind matrices).
 */
export function positionFacialFeatures(inst: MannequinInstance, camera?: THREE.Camera): void {
  const headBone = inst.boneMap.get('head');
  if (!headBone || inst.facialFeatures.size === 0) return;

  const headIdx = inst.skeleton.bones.indexOf(headBone);
  if (headIdx < 0) return;

  inst.root.updateMatrixWorld(true);

  // 1. Head bind-pose position & orientation (model-local / root-local space)
  const bindMat = inst.skeleton.boneInverses[headIdx].clone().invert();
  const bindPos = _fwp.setFromMatrixPosition(bindMat);
  const bindQuat = _delta.setFromRotationMatrix(bindMat); // reuse _delta temporarily

  // 2. Head current world quaternion (full bone chain: root → hips → … → head)
  headBone.getWorldQuaternion(_headWorldQuat);

  // 3. Root world quaternion
  inst.root.getWorldQuaternion(_rootQuat);

  // 4. Delta rotation in root-local space:
  //    headInRootLocal = rootQuat⁻¹ * headWorldQuat
  //    delta = headInRootLocal * bindQuat⁻¹
  const bindQuatClone = bindQuat.clone();          // save before _delta is reused
  const bindPosClone = new THREE.Vector3().copy(bindPos); // save before _fwp is reused
  _delta.copy(_rootQuat).invert().multiply(_headWorldQuat).multiply(bindQuatClone.invert());

  // 5. Back-face visibility: hide features when head faces away from camera
  let faceVisible = true;
  if (camera) {
    // Face forward in world space = rootQuat * delta * (0,0,1)
    _faceDir.set(0, 0, 1).applyQuaternion(_delta).applyQuaternion(_rootQuat);
    // Head world position for dot product
    const headWorldPos = bindPosClone.clone();
    inst.root.localToWorld(headWorldPos);
    camera.getWorldPosition(_toCamera);
    _toCamera.sub(headWorldPos).normalize();
    faceVisible = _faceDir.dot(_toCamera) > -0.1;
  }

  // 6. Position each feature in root-local space
  for (const [, mesh] of inst.facialFeatures) {
    mesh.visible = faceVisible;
    if (!faceVisible) continue;
    const offset = (mesh.userData.localOffset as THREE.Vector3).clone();
    offset.applyQuaternion(_delta);
    mesh.position.copy(bindPosClone).add(offset);
  }
}

// ── Disposal ─────────────────────────────────────────────────────

export function disposeInstance(inst: MannequinInstance): void {
  inst.root.traverse((child) => {
    const c = child as any;
    if (c.geometry) c.geometry.dispose();
    if (c.material) {
      const mats = Array.isArray(c.material) ? c.material : [c.material];
      for (const m of mats) { m.map?.dispose(); m.dispose(); }
    }
  });
  inst.faceGroup.removeFromParent();
}

// Re-export pose functions for convenience
export { applyPose, applyHandPreset, readPose, highlightJoint };
