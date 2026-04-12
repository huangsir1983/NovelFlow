/**
 * Mannequin loader — loads Xbot.glb (Mixamo-rigged humanoid) via GLTFLoader.
 *
 * Key facts about the Xbot model:
 *   - Armature node has scale = (0.01, 0.01, 0.01) — bones are in cm internally
 *   - GLTFLoader strips colons from bone names: "mixamorigHips" not "mixamorig:Hips"
 *   - Two meshes: Beta_Surface (body) + Beta_Joints (joint spheres)
 *   - Rest pose is T-pose (arms horizontal)
 *   - Full Mixamo skeleton (67 bones)
 */

import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';

/* ══════════════════════════════════════════════════════════════
   Bone name mapping: our joint name → Mixamo bone name
   ══════════════════════════════════════════════════════════════ */

const BONE_NAME_MAP: Record<string, string> = {
  hips:           'mixamorigHips',
  spine:          'mixamorigSpine',
  spine1:         'mixamorigSpine1',
  chest:          'mixamorigSpine2',
  neck:           'mixamorigNeck',
  head:           'mixamorigHead',

  leftShoulder:   'mixamorigLeftShoulder',
  leftUpperArm:   'mixamorigLeftArm',
  leftLowerArm:   'mixamorigLeftForeArm',
  leftHand:       'mixamorigLeftHand',

  rightShoulder:  'mixamorigRightShoulder',
  rightUpperArm:  'mixamorigRightArm',
  rightLowerArm:  'mixamorigRightForeArm',
  rightHand:      'mixamorigRightHand',

  leftUpperLeg:   'mixamorigLeftUpLeg',
  leftLowerLeg:   'mixamorigLeftLeg',
  leftFoot:       'mixamorigLeftFoot',

  rightUpperLeg:  'mixamorigRightUpLeg',
  rightLowerLeg:  'mixamorigRightLeg',
  rightFoot:      'mixamorigRightFoot',

  // Fingers — base joint of each finger
  leftThumb:      'mixamorigLeftHandThumb1',
  leftIndex:      'mixamorigLeftHandIndex1',
  leftMiddle:     'mixamorigLeftHandMiddle1',
  leftRing:       'mixamorigLeftHandRing1',
  leftPinky:      'mixamorigLeftHandPinky1',

  rightThumb:     'mixamorigRightHandThumb1',
  rightIndex:     'mixamorigRightHandIndex1',
  rightMiddle:    'mixamorigRightHandMiddle1',
  rightRing:      'mixamorigRightHandRing1',
  rightPinky:     'mixamorigRightHandPinky1',
};

/** Names of bones the user can interactively rotate */
export const INTERACTIVE_JOINTS = [
  'hips', 'spine', 'chest', 'neck', 'head',
  'leftShoulder', 'leftUpperArm', 'leftLowerArm', 'leftHand',
  'rightShoulder', 'rightUpperArm', 'rightLowerArm', 'rightHand',
  'leftUpperLeg', 'leftLowerLeg', 'leftFoot',
  'rightUpperLeg', 'rightLowerLeg', 'rightFoot',
  'leftThumb', 'leftIndex', 'leftMiddle', 'leftRing', 'leftPinky',
  'rightThumb', 'rightIndex', 'rightMiddle', 'rightRing', 'rightPinky',
] as const;

/** Joint display labels (Chinese) */
export const JOINT_LABELS: Record<string, string> = {
  hips: '骨盆', spine: '脊柱', chest: '胸', neck: '脖子', head: '头',
  leftShoulder: '左肩', leftUpperArm: '左上臂', leftLowerArm: '左前臂', leftHand: '左手腕',
  rightShoulder: '右肩', rightUpperArm: '右上臂', rightLowerArm: '右前臂', rightHand: '右手腕',
  leftUpperLeg: '左大腿', leftLowerLeg: '左小腿', leftFoot: '左脚',
  rightUpperLeg: '右大腿', rightLowerLeg: '右小腿', rightFoot: '右脚',
  leftThumb: '左拇指', leftIndex: '左食指', leftMiddle: '左中指', leftRing: '左无名指', leftPinky: '左小指',
  rightThumb: '右拇指', rightIndex: '右食指', rightMiddle: '右中指', rightRing: '右无名指', rightPinky: '右小指',
};

/** Joint groups for UI sidebar */
export const JOINT_GROUPS: Array<{ label: string; joints: string[] }> = [
  { label: '头部', joints: ['head', 'neck'] },
  { label: '躯干', joints: ['chest', 'spine', 'hips'] },
  { label: '左臂', joints: ['leftShoulder', 'leftUpperArm', 'leftLowerArm', 'leftHand'] },
  { label: '左手', joints: ['leftThumb', 'leftIndex', 'leftMiddle', 'leftRing', 'leftPinky'] },
  { label: '右臂', joints: ['rightShoulder', 'rightUpperArm', 'rightLowerArm', 'rightHand'] },
  { label: '右手', joints: ['rightThumb', 'rightIndex', 'rightMiddle', 'rightRing', 'rightPinky'] },
  { label: '左腿', joints: ['leftUpperLeg', 'leftLowerLeg', 'leftFoot'] },
  { label: '右腿', joints: ['rightUpperLeg', 'rightLowerLeg', 'rightFoot'] },
];

/* ══════════════════════════════════════════════════════════════
   Gap fill specs
   ══════════════════════════════════════════════════════════════ */

interface GapFillSpec {
  boneName: string;
  radius: number;
  scaleY?: number;
  scaleXZ?: number;
  /** If true, this fill also copies the bone's world quaternion (for torso fills) */
  followRotation?: boolean;
}

const GAP_FILL_SPECS: GapFillSpec[] = [
  { boneName: 'spine',          radius: 0.095, scaleY: 1.6, scaleXZ: 0.85, followRotation: true },
  { boneName: 'hips',           radius: 0.10,  scaleY: 1.2, scaleXZ: 0.80, followRotation: true },
  { boneName: 'neck',           radius: 0.04,  scaleY: 1.3 },
  { boneName: 'leftShoulder',   radius: 0.045, scaleY: 0.8 },
  { boneName: 'rightShoulder',  radius: 0.045, scaleY: 0.8 },
  { boneName: 'leftUpperLeg',   radius: 0.065, scaleY: 0.7 },
  { boneName: 'rightUpperLeg',  radius: 0.065, scaleY: 0.7 },
  { boneName: 'leftLowerArm',   radius: 0.028 },
  { boneName: 'rightLowerArm',  radius: 0.028 },
  { boneName: 'leftLowerLeg',   radius: 0.04 },
  { boneName: 'rightLowerLeg',  radius: 0.04 },
];

/* ══════════════════════════════════════════════════════════════
   Result type
   ══════════════════════════════════════════════════════════════ */

export interface MannequinResult {
  model: THREE.Object3D;
  skinnedMesh: THREE.SkinnedMesh;
  skeleton: THREE.Skeleton;
  jointMarkers: Map<string, THREE.Mesh>;
  gapFills: Map<string, THREE.Mesh>;
  facialFeatures: Map<string, THREE.Mesh>;
  outlineMesh: THREE.SkinnedMesh | null;
  /** Captured on first updateAllHelpers call (rest pose) */
  headRestWorldQuat: THREE.Quaternion | null;
  boneMap: Map<string, THREE.Bone>;
}

/* ══════════════════════════════════════════════════════════════
   Loader
   ══════════════════════════════════════════════════════════════ */

export async function loadMannequin(modelUrl = '/models/Xbot.glb'): Promise<MannequinResult> {
  const loader = new GLTFLoader();

  const gltf = await new Promise<import('three/examples/jsm/loaders/GLTFLoader.js').GLTF>(
    (resolve, reject) => {
      loader.load(modelUrl, resolve, undefined, reject);
    },
  );

  const model = gltf.scene;

  let bodyMesh: THREE.SkinnedMesh | null = null;
  let jointsMesh: THREE.SkinnedMesh | null = null;

  model.traverse((child) => {
    if ((child as THREE.SkinnedMesh).isSkinnedMesh) {
      const sm = child as THREE.SkinnedMesh;
      if (sm.name === 'Beta_Surface') bodyMesh = sm;
      else if (sm.name === 'Beta_Joints') jointsMesh = sm;
    }
  });

  if (!bodyMesh) throw new Error('Xbot.glb: Beta_Surface mesh not found');
  const body = bodyMesh as THREE.SkinnedMesh;

  // Body — warm skin tone
  body.material = new THREE.MeshStandardMaterial({
    color: 0xd4b896, roughness: 0.55, metalness: 0.02, side: THREE.DoubleSide,
  });

  // Beta_Joints — same color as body, fully opaque
  if (jointsMesh) {
    const joints = jointsMesh as THREE.SkinnedMesh;
    joints.material = new THREE.MeshStandardMaterial({
      color: 0xd4b896, roughness: 0.55, metalness: 0.02,
    });
    joints.scale.set(0.33, 0.33, 0.33);
    joints.renderOrder = 1;
    joints.visible = true;
  }

  const skeleton = body.skeleton;

  // Build bone map
  const boneMap = new Map<string, THREE.Bone>();
  for (const [ourName, mixamoName] of Object.entries(BONE_NAME_MAP)) {
    let bone = skeleton.bones.find((b) => b.name === mixamoName);
    if (!bone) {
      const colonName = mixamoName.replace('mixamorig', 'mixamorig:');
      bone = skeleton.bones.find((b) => b.name === colonName);
    }
    if (bone) boneMap.set(ourName, bone);
  }

  if (boneMap.size === 0) {
    console.error('[Mannequin] boneMap is EMPTY. Skeleton bone names:', skeleton.bones.slice(0, 5).map(b => b.name));
  }

  _captureRestPose(boneMap);

  const jointMarkers = _buildJointMarkers();
  const gapFills = _buildGapFills();
  const facialFeatures = _buildFacialFeatures();

  // Outline disabled — previous attempts (clone, inflate) didn't work reliably with SkinnedMesh
  const outlineMesh: THREE.SkinnedMesh | null = null;

  return { model, skinnedMesh: body, skeleton, jointMarkers, gapFills, facialFeatures, outlineMesh, headRestWorldQuat: null, boneMap };
}

/* ══════════════════════════════════════════════════════════════
   Build markers & gap fills
   ══════════════════════════════════════════════════════════════ */

/** Finger joints get smaller markers */
const FINGER_JOINTS = new Set([
  'leftThumb', 'leftIndex', 'leftMiddle', 'leftRing', 'leftPinky',
  'rightThumb', 'rightIndex', 'rightMiddle', 'rightRing', 'rightPinky',
]);

function _buildJointMarkers(): Map<string, THREE.Mesh> {
  const markers = new Map<string, THREE.Mesh>();
  const mat = new THREE.MeshBasicMaterial({
    color: 0x4488ff, transparent: true, opacity: 0.3, depthTest: false,
  });

  for (const name of INTERACTIVE_JOINTS) {
    const r = FINGER_JOINTS.has(name) ? 0.008 : 0.018;
    const geo = new THREE.SphereGeometry(r, 10, 8);
    const mesh = new THREE.Mesh(geo, mat.clone());
    mesh.name = `joint_${name}`;
    mesh.userData.jointName = name;
    mesh.renderOrder = 999;
    markers.set(name, mesh);
  }
  return markers;
}

function _buildGapFills(): Map<string, THREE.Mesh> {
  const fills = new Map<string, THREE.Mesh>();
  // Same color as body for seamless blending, higher roughness to reduce specular
  const mat = new THREE.MeshStandardMaterial({
    color: 0xd4b896, roughness: 1.0, metalness: 0.0, side: THREE.DoubleSide,
  });

  for (const spec of GAP_FILL_SPECS) {
    const geo = new THREE.SphereGeometry(spec.radius, 12, 8);
    const mesh = new THREE.Mesh(geo, mat);
    mesh.name = `gapFill_${spec.boneName}`;
    mesh.scale.set(spec.scaleXZ ?? 1, spec.scaleY ?? 1, spec.scaleXZ ?? 1);
    fills.set(spec.boneName, mesh);
  }
  return fills;
}

/* ══════════════════════════════════════════════════════════════
   Facial features — eyes, eyebrows, nose, mouth for AI face detection
   ══════════════════════════════════════════════════════════════ */

/** Eyebrow arc — curved tube following head sphere */
function _browArcGeo(): THREE.TubeGeometry {
  const curve = new THREE.QuadraticBezierCurve3(
    new THREE.Vector3(-0.016, 0, -0.004),
    new THREE.Vector3(0, 0, 0.003),
    new THREE.Vector3(0.016, 0, -0.004),
  );
  return new THREE.TubeGeometry(curve, 8, 0.002, 4, false);
}

/** Mouth arc — curved tube following head sphere */
function _mouthArcGeo(): THREE.TubeGeometry {
  const curve = new THREE.QuadraticBezierCurve3(
    new THREE.Vector3(-0.016, 0, -0.003),
    new THREE.Vector3(0, 0, 0.002),
    new THREE.Vector3(0.016, 0, -0.003),
  );
  return new THREE.TubeGeometry(curve, 8, 0.0018, 4, false);
}

function _buildFacialFeatures(): Map<string, THREE.Mesh> {
  const features = new Map<string, THREE.Mesh>();

  // depthTest: true so features are hidden when viewed from behind
  const eyeMat = new THREE.MeshStandardMaterial({ color: 0x1a1008, roughness: 0.3, metalness: 0 });
  const browMat = new THREE.MeshStandardMaterial({ color: 0x2a1a0a, roughness: 0.8, metalness: 0 });
  const noseMat = new THREE.MeshStandardMaterial({ color: 0xc0a080, roughness: 0.6, metalness: 0 });
  const mouthMat = new THREE.MeshStandardMaterial({ color: 0xb06060, roughness: 0.5, metalness: 0 });

  // Offsets in world space: X = right, Y = up, Z = forward (face direction)
  // Rotated by head delta-quaternion (current vs rest) in updateAllHelpers
  const specs: Array<{ name: string; geo: THREE.BufferGeometry; mat: THREE.Material; offset: [number, number, number] }> = [
    // Eyes
    { name: 'leftEye',  geo: new THREE.SphereGeometry(0.008, 8, 6), mat: eyeMat,   offset: [-0.040, 0.08, 0.13] },
    { name: 'rightEye', geo: new THREE.SphereGeometry(0.008, 8, 6), mat: eyeMat,   offset: [0.040, 0.08, 0.13] },
    // Eyebrows — curved arcs following head curvature
    { name: 'leftBrow', geo: _browArcGeo(), mat: browMat,  offset: [-0.040, 0.105, 0.13] },
    { name: 'rightBrow',geo: _browArcGeo(), mat: browMat,  offset: [0.040, 0.105, 0.13] },
    // Nose — protrudes forward
    { name: 'nose',     geo: new THREE.SphereGeometry(0.007, 8, 6), mat: noseMat,  offset: [0, 0.035, 0.14] },
    // Mouth — curved arc following head curvature
    { name: 'mouth',    geo: _mouthArcGeo(), mat: mouthMat, offset: [0, -0.005, 0.13] },
  ];

  for (const spec of specs) {
    const mesh = new THREE.Mesh(spec.geo, spec.mat);
    mesh.name = `face_${spec.name}`;
    mesh.userData.localOffset = new THREE.Vector3(spec.offset[0], spec.offset[1], spec.offset[2]);
    mesh.renderOrder = 998;
    features.set(spec.name, mesh);
  }

  return features;
}

/* ══════════════════════════════════════════════════════════════
   Per-frame update
   ══════════════════════════════════════════════════════════════ */

const _wp = new THREE.Vector3();
const _wq = new THREE.Quaternion();

/** Lookup which gap fills follow bone rotation */
const _rotatingFills = new Set(GAP_FILL_SPECS.filter(s => s.followRotation).map(s => s.boneName));

export function updateAllHelpers(mannequin: MannequinResult) {
  const { boneMap, jointMarkers, gapFills, model } = mannequin;
  model.updateMatrixWorld(true);

  for (const [name, marker] of jointMarkers) {
    const bone = boneMap.get(name);
    if (bone) { bone.getWorldPosition(_wp); marker.position.copy(_wp); }
  }
  for (const [boneName, fill] of gapFills) {
    const bone = boneMap.get(boneName);
    if (bone) {
      bone.getWorldPosition(_wp);
      fill.position.copy(_wp);
      if (_rotatingFills.has(boneName)) {
        bone.getWorldQuaternion(_wq);
        fill.quaternion.copy(_wq);
      }
    }
  }

  // Position facial features relative to head bone using delta rotation from rest pose
  const headBone = boneMap.get('head');
  if (headBone && mannequin.facialFeatures.size > 0) {
    headBone.getWorldPosition(_wp);
    headBone.getWorldQuaternion(_wq);

    // Capture rest-pose world quaternion on first call
    if (!mannequin.headRestWorldQuat) {
      mannequin.headRestWorldQuat = _wq.clone();
    }

    // Delta = how much the head has rotated from rest pose
    const restInv = mannequin.headRestWorldQuat.clone().invert();
    const delta = _wq.clone().multiply(restInv);

    const headPos = _wp.clone();
    for (const [, mesh] of mannequin.facialFeatures) {
      // localOffset is in world space (X=right, Y=up, Z=forward in rest pose)
      const offset = (mesh.userData.localOffset as THREE.Vector3).clone().applyQuaternion(delta);
      mesh.position.copy(headPos).add(offset);
      mesh.quaternion.copy(delta);
    }
  }
}

export const updateJointMarkers = (boneMap: Map<string, THREE.Bone>, jointMarkers: Map<string, THREE.Mesh>) => {
  for (const [name, marker] of jointMarkers) {
    const bone = boneMap.get(name);
    if (bone) { bone.getWorldPosition(_wp); marker.position.copy(_wp); }
  }
};

/* ══════════════════════════════════════════════════════════════
   Highlight
   ══════════════════════════════════════════════════════════════ */

export function highlightJoint(jointMarkers: Map<string, THREE.Mesh>, selectedName: string | null) {
  for (const [name, mesh] of jointMarkers) {
    const mat = mesh.material as THREE.MeshBasicMaterial;
    if (name === selectedName) {
      mat.color.setHex(0xffb432);
      mat.opacity = 0.7;
      mesh.scale.set(2.2, 2.2, 2.2);
    } else {
      mat.color.setHex(0x4488ff);
      mat.opacity = 0.3;
      mesh.scale.set(1, 1, 1);
    }
  }
}

/* ══════════════════════════════════════════════════════════════
   Rest pose
   ══════════════════════════════════════════════════════════════ */

const _restQuats = new Map<string, THREE.Quaternion>();

function _captureRestPose(boneMap: Map<string, THREE.Bone>) {
  _restQuats.clear();
  for (const [name, bone] of boneMap) {
    _restQuats.set(name, bone.quaternion.clone());
  }
}

/* ══════════════════════════════════════════════════════════════
   Pose presets

   IMPORTANT: Xbot rest pose is T-pose (arms perfectly horizontal).
   All angle values are DELTA on top of rest pose.
   To bring arms down to sides: leftUpperArm z ≈ -65, rightUpperArm z ≈ +65
   ══════════════════════════════════════════════════════════════ */

type PoseAngles = Record<string, { x: number; y: number; z: number }>;

export const POSE_PRESETS: Record<string, { label: string; angles: PoseAngles }> = {

  standing: {
    label: '站立',
    angles: {
      leftUpperArm:  { x: 0, y: 0, z: -65 },
      rightUpperArm: { x: 0, y: 0, z: 65 },
      leftLowerArm:  { x: 0, y: 0, z: -3 },
      rightLowerArm: { x: 0, y: 0, z: 3 },
    },
  },

  sitting: {
    label: '坐姿',
    angles: {
      leftUpperLeg:  { x: -90, y: 0, z: 0 },
      rightUpperLeg: { x: -90, y: 0, z: 0 },
      leftLowerLeg:  { x: 90, y: 0, z: 0 },
      rightLowerLeg: { x: 90, y: 0, z: 0 },
      leftUpperArm:  { x: 0, y: 0, z: -60 },
      rightUpperArm: { x: 0, y: 0, z: 60 },
      leftLowerArm:  { x: 0, y: 0, z: -5 },
      rightLowerArm: { x: 0, y: 0, z: 5 },
    },
  },

  walking: {
    label: '行走',
    angles: {
      // Legs — mid-stride
      leftUpperLeg:  { x: -25, y: 0, z: 0 },
      rightUpperLeg: { x: 20, y: 0, z: 0 },
      leftLowerLeg:  { x: 15, y: 0, z: 0 },
      rightLowerLeg: { x: -25, y: 0, z: 0 },
      // Arms — swinging opposite to legs, hanging at sides
      leftUpperArm:  { x: 20, y: 0, z: -55 },
      rightUpperArm: { x: -25, y: 0, z: 55 },
      leftLowerArm:  { x: -20, y: 0, z: -8 },
      rightLowerArm: { x: -15, y: 0, z: 8 },
    },
  },

  running: {
    label: '奔跑',
    angles: {
      // Legs — larger stride
      leftUpperLeg:  { x: -40, y: 0, z: 0 },
      rightUpperLeg: { x: 30, y: 0, z: 0 },
      leftLowerLeg:  { x: 25, y: 0, z: 0 },
      rightLowerLeg: { x: 50, y: 0, z: 0 },
      // Arms — bigger swing, elbows bent
      leftUpperArm:  { x: 35, y: 0, z: -50 },
      rightUpperArm: { x: -40, y: 0, z: 50 },
      leftLowerArm:  { x: -70, y: 0, z: -5 },
      rightLowerArm: { x: -60, y: 0, z: 5 },
      // Slight forward lean
      spine: { x: 10, y: 0, z: 0 },
    },
  },

  fighting: {
    label: '格斗',
    angles: {
      // Boxing guard — fists up protecting face
      leftUpperArm:  { x: -70, y: 30, z: -20 },
      rightUpperArm: { x: -70, y: -30, z: 20 },
      leftLowerArm:  { x: -100, y: 20, z: 0 },
      rightLowerArm: { x: -100, y: -20, z: 0 },
      // Staggered stance
      leftUpperLeg:  { x: -20, y: 15, z: 0 },
      rightUpperLeg: { x: -10, y: -15, z: 0 },
      leftLowerLeg:  { x: 25, y: 0, z: 0 },
      rightLowerLeg: { x: 15, y: 0, z: 0 },
      // Slight crouch and twist
      spine: { x: 8, y: -12, z: 0 },
      chest: { x: 5, y: -8, z: 0 },
    },
  },

  crouching: {
    label: '蹲下',
    angles: {
      leftUpperLeg:  { x: -120, y: 0, z: 15 },
      rightUpperLeg: { x: -120, y: 0, z: -15 },
      leftLowerLeg:  { x: 130, y: 0, z: 0 },
      rightLowerLeg: { x: 130, y: 0, z: 0 },
      leftUpperArm:  { x: -10, y: 0, z: -50 },
      rightUpperArm: { x: -10, y: 0, z: 50 },
      leftLowerArm:  { x: -20, y: 0, z: -10 },
      rightLowerArm: { x: -20, y: 0, z: 10 },
      spine: { x: 15, y: 0, z: 0 },
    },
  },

  thinking: {
    label: '思考',
    angles: {
      // Right hand on chin
      leftUpperArm:  { x: 0, y: 0, z: -65 },
      rightUpperArm: { x: -80, y: -30, z: 30 },
      leftLowerArm:  { x: 0, y: 0, z: -3 },
      rightLowerArm: { x: -110, y: 0, z: 0 },
      rightHand:     { x: 10, y: 0, z: 0 },
      // Left arm crosses body supporting right elbow
      head: { x: -8, y: 5, z: 0 },
      neck: { x: -5, y: 3, z: 0 },
    },
  },

  tpose: {
    label: 'T-Pose',
    angles: {},
  },

  hugging: {
    label: '搂',
    angles: {
      leftUpperArm:  { x: -60, y: 0, z: -20 },
      rightUpperArm: { x: -60, y: 0, z: 20 },
      leftLowerArm:  { x: 0, y: 50, z: -60 },
      rightLowerArm: { x: 0, y: -50, z: 60 },
      spine: { x: 10, y: 0, z: 0 },
      chest: { x: 5, y: 0, z: 0 },
    },
  },

  prone: {
    label: '趴',
    angles: {
      hips: { x: 90, y: 0, z: 0 },
      leftUpperArm:  { x: 0, y: 0, z: -65 },
      rightUpperArm: { x: 0, y: 0, z: 65 },
      leftLowerArm:  { x: 0, y: 40, z: -20 },
      rightLowerArm: { x: 0, y: -40, z: 20 },
      head: { x: -20, y: 0, z: 0 },
    },
  },

  lying: {
    label: '躺',
    angles: {
      hips: { x: -90, y: 0, z: 0 },
      leftUpperArm:  { x: 0, y: 0, z: -65 },
      rightUpperArm: { x: 0, y: 0, z: 65 },
      leftLowerArm:  { x: 0, y: 0, z: -5 },
      rightLowerArm: { x: 0, y: 0, z: 5 },
    },
  },
};

/* ══════════════════════════════════════════════════════════════
   Hand presets — applied independently to left or right hand.
   Keys use generic names (thumb/index/...) which get prefixed
   with "left" or "right" when applied.
   ══════════════════════════════════════════════════════════════ */

type HandAngles = Record<string, { x: number; y: number; z: number }>;

export const HAND_PRESETS: Record<string, { label: string; angles: HandAngles }> = {
  open: {
    label: '张开',
    angles: {},
  },
  fist: {
    label: '握拳',
    angles: {
      Thumb:  { x: 0, y: 0, z: -60 },
      Index:  { x: 0, y: 0, z: -90 },
      Middle: { x: 0, y: 0, z: -90 },
      Ring:   { x: 0, y: 0, z: -90 },
      Pinky:  { x: 0, y: 0, z: -90 },
    },
  },
  point: {
    label: '指向',
    angles: {
      Thumb:  { x: 0, y: 0, z: -50 },
      Index:  { x: 0, y: 0, z: 0 },
      Middle: { x: 0, y: 0, z: -90 },
      Ring:   { x: 0, y: 0, z: -90 },
      Pinky:  { x: 0, y: 0, z: -90 },
    },
  },
  relaxed: {
    label: '自然弯曲',
    angles: {
      Thumb:  { x: 0, y: 0, z: -20 },
      Index:  { x: 0, y: 0, z: -30 },
      Middle: { x: 0, y: 0, z: -35 },
      Ring:   { x: 0, y: 0, z: -40 },
      Pinky:  { x: 0, y: 0, z: -45 },
    },
  },
  spread: {
    label: '张开五指',
    angles: {
      Thumb:  { x: 0, y: 0, z: 15 },
      Index:  { x: 0, y: 8, z: 0 },
      Middle: { x: 0, y: 0, z: 0 },
      Ring:   { x: 0, y: -8, z: 0 },
      Pinky:  { x: 0, y: -15, z: 0 },
    },
  },
};

/**
 * Apply a hand preset to left or right hand.
 * @param side 'left' or 'right'
 */
export function applyHandPreset(
  boneMap: Map<string, THREE.Bone>,
  side: 'left' | 'right',
  presetKey: string,
) {
  const preset = HAND_PRESETS[presetKey];
  if (!preset) return;

  // Reset all fingers on this side to rest pose first
  const fingerNames = side === 'left'
    ? ['leftThumb', 'leftIndex', 'leftMiddle', 'leftRing', 'leftPinky']
    : ['rightThumb', 'rightIndex', 'rightMiddle', 'rightRing', 'rightPinky'];

  for (const fn of fingerNames) {
    const bone = boneMap.get(fn);
    const rest = _restQuats.get(fn);
    if (bone && rest) bone.quaternion.copy(rest);
  }

  // Apply preset angles (mirror Z for right hand — bones are mirrored)
  const dq = new THREE.Quaternion();
  const de = new THREE.Euler();
  const zSign = side === 'right' ? -1 : 1;
  for (const [genericName, euler] of Object.entries(preset.angles)) {
    const jointName = side + genericName; // e.g. "left" + "Thumb" = "leftThumb"
    const bone = boneMap.get(jointName);
    const rest = _restQuats.get(jointName);
    if (bone && rest) {
      de.set(euler.x * DEG2RAD, euler.y * DEG2RAD, euler.z * zSign * DEG2RAD);
      dq.setFromEuler(de);
      bone.quaternion.copy(rest).multiply(dq);
    }
  }
}

const DEG2RAD = Math.PI / 180;

export function applyPose(boneMap: Map<string, THREE.Bone>, angles: PoseAngles) {
  for (const name of INTERACTIVE_JOINTS) {
    const bone = boneMap.get(name);
    const rest = _restQuats.get(name);
    if (bone && rest) bone.quaternion.copy(rest);
  }
  const dq = new THREE.Quaternion();
  const de = new THREE.Euler();
  for (const [name, euler] of Object.entries(angles)) {
    const bone = boneMap.get(name);
    const rest = _restQuats.get(name);
    if (bone && rest) {
      de.set(euler.x * DEG2RAD, euler.y * DEG2RAD, euler.z * DEG2RAD);
      dq.setFromEuler(de);
      bone.quaternion.copy(rest).multiply(dq);
    }
  }
}

export function readPose(boneMap: Map<string, THREE.Bone>): PoseAngles {
  const result: PoseAngles = {};
  const R2D = 180 / Math.PI;
  const ri = new THREE.Quaternion();
  const dq = new THREE.Quaternion();
  const de = new THREE.Euler();

  for (const name of INTERACTIVE_JOINTS) {
    const bone = boneMap.get(name);
    const rest = _restQuats.get(name);
    if (!bone || !rest) continue;
    ri.copy(rest).invert();
    dq.copy(ri).multiply(bone.quaternion);
    de.setFromQuaternion(dq);
    const rx = de.x * R2D, ry = de.y * R2D, rz = de.z * R2D;
    if (Math.abs(rx) > 0.1 || Math.abs(ry) > 0.1 || Math.abs(rz) > 0.1) {
      result[name] = {
        x: Math.round(rx * 10) / 10,
        y: Math.round(ry * 10) / 10,
        z: Math.round(rz * 10) / 10,
      };
    }
  }
  return result;
}
