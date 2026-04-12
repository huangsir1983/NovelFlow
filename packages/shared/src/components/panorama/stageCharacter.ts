/**
 * Stage character state management — pure functions for managing
 * 3D mannequin characters in the director stage.
 *
 * All functions are immutable: they return new objects without mutating inputs.
 */

import { POSE_PRESETS } from '../../lib/mannequinGeometry';

// ── Types ────────────────────────────────────────────────────────

export interface StageCharacter {
  id: string;
  name: string;
  x: number;
  y: number;
  z: number;
  rotationY: number;  // degrees
  color: string;
  scale: number;
  jointAngles: Record<string, { x: number; y: number; z: number }>;
  presetName: string;
}

/** A 2D sprite prop placed in the 3D stage. */
export interface StageProp {
  id: string;
  name: string;
  imageUrl: string;     // URL or base64 data-URI of prop image
  x: number;
  y: number;
  z: number;
  scale: number;
  rotationY: number;    // degrees
}

// ── Constants ────────────────────────────────────────────────────

export const STAGE_CHAR_COLORS = [
  '#06b6d4', '#f472b6', '#a78bfa', '#34d399',
  '#fbbf24', '#f87171', '#60a5fa',
];

const MIN_SCALE = 0.1;
const MAX_SCALE = 5.0;
const MIN_Y = -2;
const MAX_Y = 2;

// ── Factory ──────────────────────────────────────────────────────

let _idCounter = 0;

export function createStageCharacter(index: number): StageCharacter {
  _idCounter++;
  const preset = POSE_PRESETS['standing'];
  return {
    id: `sc-${Date.now().toString(36)}-${_idCounter}`,
    name: `角色${index + 1}`,
    x: (Math.random() - 0.5) * 3,
    y: 0,
    z: (Math.random() - 0.5) * 3,
    rotationY: 0,
    color: STAGE_CHAR_COLORS[index % STAGE_CHAR_COLORS.length],
    scale: 1.0,
    jointAngles: preset ? { ...preset.angles } : {},
    presetName: 'standing',
  };
}

// ── Preset application ───────────────────────────────────────────

export function applyBodyPreset(char: StageCharacter, presetKey: string): StageCharacter {
  if (presetKey === '') {
    return { ...char, jointAngles: {}, presetName: '' };
  }
  const preset = POSE_PRESETS[presetKey];
  if (!preset) return char;
  return {
    ...char,
    jointAngles: { ...preset.angles },
    presetName: presetKey,
  };
}

// ── Transform updates ────────────────────────────────────────────

export function updateTransform(char: StageCharacter, x: number, z: number): StageCharacter {
  return { ...char, x, z };
}

export function updateScale(char: StageCharacter, scale: number): StageCharacter {
  return { ...char, scale: Math.max(MIN_SCALE, Math.min(MAX_SCALE, scale)) };
}

// ── Rotation & Y offset ─────────────────────────────────────

export function updateRotation(char: StageCharacter, rotationY: number): StageCharacter {
  return { ...char, rotationY };
}

export function updateY(char: StageCharacter, y: number): StageCharacter {
  return { ...char, y: Math.max(MIN_Y, Math.min(MAX_Y, y)) };
}

// ── Joint angle updates ──────────────────────────────────────────

export function updateJointAngles(
  char: StageCharacter,
  angles: Record<string, { x: number; y: number; z: number }>,
): StageCharacter {
  return {
    ...char,
    jointAngles: { ...char.jointAngles, ...angles },
  };
}
