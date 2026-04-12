/**
 * Shared helpers for 3D Director Stage components.
 * Character creation, disposal, constants, and types.
 */

import * as THREE from 'three';

// ── Types ──────────────────────────────────────────────────────────

export interface Character3D {
  id: string;
  name: string;
  imageUrl?: string;
  x: number;
  z: number;
  color?: string;
  scale?: number;
}

export interface DirectorStage3DProps {
  panoramaUrl: string;
  isOpen: boolean;
  onClose: () => void;
  sceneType?: 'indoor' | 'outdoor';
  characters?: Character3D[];
  onCharactersUpdate?: (chars: Character3D[]) => void;
}

// ── Constants ──────────────────────────────────────────────────────

export const PRESETS = {
  indoor: {
    label: '室内',
    cylinderRadius: 5,
    eyeLevel: 1.6,
    charHeight: 1.7,
    radiusRange: { min: 2, max: 12, step: 0.5 },
    cameraPos: [0, 3, 3] as const,
    cameraTarget: [0, 0, 0] as const,
  },
  outdoor: {
    label: '室外',
    cylinderRadius: 25,
    eyeLevel: 1.7,
    charHeight: 1.7,
    radiusRange: { min: 10, max: 60, step: 1 },
    cameraPos: [0, 8, 12] as const,
    cameraTarget: [0, 0, 0] as const,
  },
};

export const CHAR_COLORS = ['#06b6d4', '#f472b6', '#a78bfa', '#34d399', '#fbbf24', '#f87171', '#60a5fa'];

// ── Helpers ────────────────────────────────────────────────────────

export function createLabelSprite(text: string, color: string): THREE.Sprite {
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 64;
  const ctx = canvas.getContext('2d')!;

  ctx.fillStyle = 'rgba(0,0,0,0.55)';
  ctx.beginPath();
  ctx.roundRect(4, 4, 248, 56, 12);
  ctx.fill();

  ctx.fillStyle = color;
  ctx.font = 'bold 28px sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text.slice(0, 6), 128, 32);

  const texture = new THREE.CanvasTexture(canvas);
  const mat = new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false });
  const sprite = new THREE.Sprite(mat);
  sprite.scale.set(1.2, 0.3, 1);
  return sprite;
}

export function createCharObject(char: Character3D): THREE.Group {
  const group = new THREE.Group();
  group.userData.characterId = char.id;

  const colorHex = char.color || CHAR_COLORS[0];
  const threeColor = new THREE.Color(colorHex);

  // Body: capsule (total height = 1.3 + 0.4 = 1.7m)
  const capsuleGeo = new THREE.CapsuleGeometry(0.2, 1.3, 8, 16);
  const capsuleMat = new THREE.MeshStandardMaterial({ color: threeColor, roughness: 0.5, metalness: 0.1 });
  const capsule = new THREE.Mesh(capsuleGeo, capsuleMat);
  capsule.position.y = 0.85;
  capsule.userData.characterId = char.id;
  group.add(capsule);

  // Label above head
  const label = createLabelSprite(char.name, colorHex);
  label.position.y = 2.1;
  group.add(label);

  // Shadow circle
  const shadowGeo = new THREE.CircleGeometry(0.3, 16);
  shadowGeo.rotateX(-Math.PI / 2);
  const shadowMat = new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.25 });
  const shadow = new THREE.Mesh(shadowGeo, shadowMat);
  shadow.position.y = 0.005;
  group.add(shadow);

  // Selection ring (hidden by default)
  const ringGeo = new THREE.RingGeometry(0.35, 0.42, 32);
  ringGeo.rotateX(-Math.PI / 2);
  const ringMat = new THREE.MeshBasicMaterial({ color: 0x06b6d4, transparent: true, opacity: 0.6, side: THREE.DoubleSide });
  const ring = new THREE.Mesh(ringGeo, ringMat);
  ring.position.y = 0.01;
  ring.visible = false;
  ring.userData.isSelectionRing = true;
  group.add(ring);

  group.position.set(char.x, 0, char.z);
  return group;
}

export function disposeObject(obj: THREE.Object3D) {
  obj.traverse((child: THREE.Object3D) => {
    const c = child as any;
    if (c.geometry) c.geometry.dispose();
    if (c.material) {
      const mats = Array.isArray(c.material) ? c.material : [c.material];
      for (const m of mats) { m.map?.dispose(); m.dispose(); }
    }
  });
}
