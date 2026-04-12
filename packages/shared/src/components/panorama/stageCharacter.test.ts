import { describe, it, expect } from 'vitest';
import {
  createStageCharacter,
  applyBodyPreset,
  updateTransform,
  updateScale,
  updateJointAngles,
  updateRotation,
  updateY,
  STAGE_CHAR_COLORS,
  type StageCharacter,
} from './stageCharacter';

describe('stageCharacter', () => {
  // ── createStageCharacter ──

  it('creates a character with valid defaults', () => {
    const char = createStageCharacter(0);
    expect(char.id).toBeTruthy();
    expect(char.name).toBe('角色1');
    expect(char.scale).toBe(1.0);
    expect(Object.keys(char.jointAngles).length).toBeGreaterThan(0); // standing preset has angles
    expect(char.presetName).toBe('standing');
    expect(char.color).toBe(STAGE_CHAR_COLORS[0]);
    expect(typeof char.x).toBe('number');
    expect(typeof char.z).toBe('number');
    expect(char.rotationY).toBe(0);
    expect(char.y).toBe(0);
  });

  it('increments name and cycles colors', () => {
    const c0 = createStageCharacter(0);
    const c3 = createStageCharacter(3);
    expect(c0.name).toBe('角色1');
    expect(c3.name).toBe('角色4');
    expect(c3.color).toBe(STAGE_CHAR_COLORS[3 % STAGE_CHAR_COLORS.length]);
  });

  it('generates unique IDs', () => {
    const a = createStageCharacter(0);
    const b = createStageCharacter(1);
    expect(a.id).not.toBe(b.id);
  });

  // ── applyBodyPreset ──

  it('applies a body preset and stores preset name + angles', () => {
    const char = createStageCharacter(0);
    const updated = applyBodyPreset(char, 'sitting');
    expect(updated.presetName).toBe('sitting');
    expect(updated.jointAngles).toBeDefined();
    expect(Object.keys(updated.jointAngles).length).toBeGreaterThan(0);
    // Original not mutated
    expect(char.presetName).toBe('standing');
  });

  it('returns same character for unknown preset', () => {
    const char = createStageCharacter(0);
    const updated = applyBodyPreset(char, 'nonexistent_xyz');
    expect(updated).toBe(char);
  });

  it('reset (empty string) clears angles', () => {
    const char = applyBodyPreset(createStageCharacter(0), 'sitting');
    const reset = applyBodyPreset(char, '');
    expect(reset.jointAngles).toEqual({});
    expect(reset.presetName).toBe('');
  });

  // ── updateTransform ──

  it('updates x and z, preserves other fields', () => {
    const char = applyBodyPreset(createStageCharacter(0), 'walking');
    const moved = updateTransform(char, 3.5, -2.0);
    expect(moved.x).toBe(3.5);
    expect(moved.z).toBe(-2.0);
    expect(moved.presetName).toBe('walking');
    expect(moved.jointAngles).toEqual(char.jointAngles);
    // Original not mutated
    expect(char.x).not.toBe(3.5);
  });

  // ── updateScale ──

  it('updates scale and clamps to valid range', () => {
    const char = createStageCharacter(0);
    expect(updateScale(char, 1.5).scale).toBe(1.5);
    expect(updateScale(char, 0.05).scale).toBe(0.1); // min clamp
    expect(updateScale(char, 10).scale).toBe(5.0);    // max clamp
    // Original not mutated
    expect(char.scale).toBe(1.0);
  });

  // ── updateJointAngles ──

  it('merges joint angles into existing state', () => {
    const char = applyBodyPreset(createStageCharacter(0), 'standing');
    const updated = updateJointAngles(char, { head: { x: 15, y: 0, z: 0 } });
    expect(updated.jointAngles.head).toEqual({ x: 15, y: 0, z: 0 });
    // Other joints from the preset still exist
    if (char.jointAngles.leftUpperArm) {
      expect(updated.jointAngles.leftUpperArm).toEqual(char.jointAngles.leftUpperArm);
    }
    // Original not mutated
    expect(char.jointAngles.head).not.toEqual({ x: 15, y: 0, z: 0 });
  });

  // ── updateRotation ──

  it('updates rotationY and preserves other fields', () => {
    const char = applyBodyPreset(createStageCharacter(0), 'walking');
    const rotated = updateRotation(char, 90);
    expect(rotated.rotationY).toBe(90);
    expect(rotated.presetName).toBe('walking');
    expect(rotated.scale).toBe(1.0);
    // Original not mutated
    expect(char.rotationY).toBe(0);
  });

  it('accepts negative and large rotation values', () => {
    const char = createStageCharacter(0);
    expect(updateRotation(char, -45).rotationY).toBe(-45);
    expect(updateRotation(char, 720).rotationY).toBe(720);
  });

  // ── updateY ──

  it('updates y offset and preserves other fields', () => {
    const char = applyBodyPreset(createStageCharacter(0), 'sitting');
    const moved = updateY(char, 0.5);
    expect(moved.y).toBe(0.5);
    expect(moved.presetName).toBe('sitting');
    // Original not mutated
    expect(char.y).toBe(0);
  });

  it('clamps y to valid range', () => {
    const char = createStageCharacter(0);
    expect(updateY(char, -10).y).toBe(-2);  // min clamp
    expect(updateY(char, 10).y).toBe(2);    // max clamp
    expect(updateY(char, 0.8).y).toBe(0.8); // within range
  });

  it('single-axis joint update preserves other axes (slider pattern)', () => {
    const char = applyBodyPreset(createStageCharacter(0), 'standing');
    const withHead = updateJointAngles(char, { head: { x: 10, y: 20, z: 30 } });
    // Simulate slider changing only x: spread prev + override one axis
    const prev = withHead.jointAngles.head;
    const updated = updateJointAngles(withHead, { head: { ...prev, x: 45 } });
    expect(updated.jointAngles.head).toEqual({ x: 45, y: 20, z: 30 });
    // Other joints from preset untouched
    expect(updated.jointAngles.leftUpperArm).toEqual(withHead.jointAngles.leftUpperArm);
  });

  it('updateTransform preserves rotationY and y', () => {
    let char = createStageCharacter(0);
    char = updateRotation(char, 45);
    char = updateY(char, 0.5);
    const moved = updateTransform(char, 5, -3);
    expect(moved.x).toBe(5);
    expect(moved.z).toBe(-3);
    expect(moved.rotationY).toBe(45);
    expect(moved.y).toBe(0.5);
  });

  // ── New body presets (leaning, kneeling, pointing, bowing) ──

  it('applies leaning preset', () => {
    const char = createStageCharacter(0);
    const updated = applyBodyPreset(char, 'leaning');
    expect(updated.presetName).toBe('leaning');
    expect(updated.jointAngles.hips).toBeDefined();
    expect(updated.jointAngles.rightUpperArm).toBeDefined();
  });

  it('applies kneeling preset with bent knees', () => {
    const char = createStageCharacter(0);
    const updated = applyBodyPreset(char, 'kneeling');
    expect(updated.presetName).toBe('kneeling');
    expect(updated.jointAngles.leftUpperLeg).toBeDefined();
    expect(updated.jointAngles.leftUpperLeg!.x).toBe(-90);
    expect(updated.jointAngles.leftLowerLeg).toBeDefined();
    expect(updated.jointAngles.leftLowerLeg!.x).toBe(160);
  });

  it('applies pointing preset with extended arm', () => {
    const char = createStageCharacter(0);
    const updated = applyBodyPreset(char, 'pointing');
    expect(updated.presetName).toBe('pointing');
    expect(updated.jointAngles.rightUpperArm).toBeDefined();
    expect(updated.jointAngles.rightUpperArm!.x).toBe(-80);
  });

  it('applies bowing preset with forward lean', () => {
    const char = createStageCharacter(0);
    const updated = applyBodyPreset(char, 'bowing');
    expect(updated.presetName).toBe('bowing');
    expect(updated.jointAngles.spine).toBeDefined();
    expect(updated.jointAngles.spine!.x).toBe(20);
    expect(updated.jointAngles.chest).toBeDefined();
    expect(updated.jointAngles.chest!.x).toBe(15);
  });
});
