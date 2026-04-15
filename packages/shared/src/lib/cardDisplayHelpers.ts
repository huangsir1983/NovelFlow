/**
 * Pure display helpers for the 4 Tapnow-style canvas cards:
 * DirectorStage3D, GeminiComposite, FinalHD, VideoGeneration.
 *
 * Zero React dependencies — data-in, data-out.
 */

import { API_BASE_URL } from './api';

// ── Types ──

export interface CardBadge {
  text: string;
  bgColor: string;
  textColor: string;
}

// Theme color tuples: [R, G, B]
const CYAN: [number, number, number] = [6, 182, 212];
const PURPLE: [number, number, number] = [168, 85, 247];
const GREEN: [number, number, number] = [52, 211, 153];
const FUCHSIA: [number, number, number] = [232, 121, 249];

function badge(text: string, rgb: [number, number, number], textAlpha = 0.9, bgAlpha = 0.2): CardBadge {
  return {
    text,
    textColor: `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${textAlpha})`,
    bgColor: `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${bgAlpha})`,
  };
}

function completionBadge(text: string): CardBadge {
  return badge(text, GREEN, 0.7, 0.15);
}

function dimBadge(text: string): CardBadge {
  return { text, textColor: 'rgba(255,255,255,0.3)', bgColor: 'rgba(255,255,255,0.06)' };
}

// ── Display URL functions ──

export function getDirectorStage3DDisplayUrl(data: {
  screenshotBase64?: string;
  screenshotStorageKey?: string;
}): string {
  if (data.screenshotBase64) return `data:image/jpeg;base64,${data.screenshotBase64}`;
  if (data.screenshotStorageKey) return `${API_BASE_URL}/uploads/${data.screenshotStorageKey}`;
  return '';
}

export function getGeminiCompositeDisplayUrl(data: {
  outputImageUrl?: string;
  outputImageBase64?: string;
  sceneScreenshotBase64?: string;
  sceneScreenshotStorageKey?: string;
}): string {
  if (data.outputImageUrl) return data.outputImageUrl;
  if (data.outputImageBase64) return `data:image/jpeg;base64,${data.outputImageBase64}`;
  if (data.sceneScreenshotBase64) return `data:image/jpeg;base64,${data.sceneScreenshotBase64}`;
  if (data.sceneScreenshotStorageKey) return `${API_BASE_URL}/uploads/${data.sceneScreenshotStorageKey}`;
  return '';
}

export function getFinalHDDisplayUrl(data: {
  outputImageUrl?: string;
  inputImageUrl?: string;
}): string {
  return data.outputImageUrl || data.inputImageUrl || '';
}

export function getVideoDisplayMedia(data: {
  videoUrl?: string;
  inputImageUrl?: string;
}): { type: 'video' | 'image' | 'none'; url: string } {
  if (data.videoUrl) return { type: 'video', url: data.videoUrl };
  if (data.inputImageUrl) return { type: 'image', url: data.inputImageUrl };
  return { type: 'none', url: '' };
}

// ── Badge builder functions ──

export function buildDirectorStage3DBadges(data: {
  hasPanorama?: boolean;
  hasDepthMap?: boolean;
  characterCount?: number;
  hasScreenshot?: boolean;
}): CardBadge[] {
  const badges: CardBadge[] = [];
  if (data.hasPanorama) badges.push(badge('VR', CYAN));
  if (data.hasDepthMap) badges.push(badge('深度图', CYAN, 0.7, 0.15));
  if (data.characterCount && data.characterCount > 0) badges.push(badge(`${data.characterCount}角色`, CYAN));
  if (data.hasScreenshot) badges.push(completionBadge('已截图'));
  return badges;
}

export function buildGeminiCompositeBadges(data: {
  characterMappings?: Array<{ stageCharName: string }>;
  outputImageUrl?: string;
  outputImageBase64?: string;
  sceneScreenshotBase64?: string;
  sceneScreenshotStorageKey?: string;
}): CardBadge[] {
  const badges: CardBadge[] = [];
  const charCount = data.characterMappings?.length || 0;
  if (charCount > 0) badges.push(badge(`${charCount}角色`, PURPLE));
  if (data.outputImageUrl || data.outputImageBase64) {
    badges.push(completionBadge('已合成'));
  }
  const hasInput = !!(data.sceneScreenshotBase64 || data.sceneScreenshotStorageKey);
  if (!hasInput && !data.outputImageUrl && !data.outputImageBase64) {
    badges.push(dimBadge('等待截图'));
  }
  return badges;
}

export function buildFinalHDBadges(data: {
  scaleFactor?: number;
  outputImageUrl?: string;
}): CardBadge[] {
  const badges: CardBadge[] = [];
  if (data.scaleFactor) badges.push(badge(`${data.scaleFactor}x 放大`, GREEN));
  if (data.outputImageUrl) badges.push(completionBadge('完成'));
  return badges;
}

const MODE_LABEL: Record<string, string> = {
  text_to_video: 'T2V',
  image_to_video: 'I2V',
  scene_character_to_video: 'SC2V',
};

export function buildVideoGenerationBadges(data: {
  mode?: string;
  durationSeconds?: number;
  videoUrl?: string;
}): CardBadge[] {
  const badges: CardBadge[] = [];
  if (data.mode && MODE_LABEL[data.mode]) badges.push(badge(MODE_LABEL[data.mode], FUCHSIA));
  if (data.durationSeconds && data.durationSeconds > 0) badges.push(dimBadge(`${data.durationSeconds}s`));
  if (data.videoUrl) badges.push(completionBadge('完成'));
  return badges;
}
