/**
 * TDD tests for cardDisplayHelpers — pure display-url + badge functions
 * for DirectorStage3D, GeminiComposite, FinalHD, VideoGeneration cards.
 */
import { describe, it, expect } from 'vitest';
import {
  getDirectorStage3DDisplayUrl,
  getGeminiCompositeDisplayUrl,
  getFinalHDDisplayUrl,
  getVideoDisplayMedia,
  buildDirectorStage3DBadges,
  buildGeminiCompositeBadges,
  buildFinalHDBadges,
  buildVideoGenerationBadges,
} from './cardDisplayHelpers';

// ── Display URL functions ──

describe('getDirectorStage3DDisplayUrl', () => {
  it('returns base64 data URL when screenshotBase64 present', () => {
    const url = getDirectorStage3DDisplayUrl({ screenshotBase64: 'abc123' });
    expect(url).toBe('data:image/jpeg;base64,abc123');
  });

  it('returns storage URL when screenshotStorageKey present and no base64', () => {
    const url = getDirectorStage3DDisplayUrl({ screenshotStorageKey: 'assets/images/shot.jpg' });
    expect(url).toContain('/uploads/assets/images/shot.jpg');
  });

  it('prefers base64 over storageKey', () => {
    const url = getDirectorStage3DDisplayUrl({
      screenshotBase64: 'abc123',
      screenshotStorageKey: 'assets/images/shot.jpg',
    });
    expect(url).toBe('data:image/jpeg;base64,abc123');
  });

  it('returns empty string when no screenshot data', () => {
    expect(getDirectorStage3DDisplayUrl({})).toBe('');
  });
});

describe('getGeminiCompositeDisplayUrl', () => {
  it('returns outputImageUrl when available', () => {
    const url = getGeminiCompositeDisplayUrl({ outputImageUrl: 'http://example.com/img.jpg' });
    expect(url).toBe('http://example.com/img.jpg');
  });

  it('returns base64 data URL from outputImageBase64 when no outputImageUrl', () => {
    const url = getGeminiCompositeDisplayUrl({ outputImageBase64: 'xyz' });
    expect(url).toBe('data:image/jpeg;base64,xyz');
  });

  it('falls back to sceneScreenshotBase64', () => {
    const url = getGeminiCompositeDisplayUrl({ sceneScreenshotBase64: 'scene64' });
    expect(url).toBe('data:image/jpeg;base64,scene64');
  });

  it('falls back to sceneScreenshotStorageKey', () => {
    const url = getGeminiCompositeDisplayUrl({ sceneScreenshotStorageKey: 'assets/scene.jpg' });
    expect(url).toContain('/uploads/assets/scene.jpg');
  });

  it('returns empty string when nothing available', () => {
    expect(getGeminiCompositeDisplayUrl({})).toBe('');
  });

  it('follows priority: outputUrl > outputBase64 > sceneBase64 > sceneStorageKey', () => {
    const all = {
      outputImageUrl: 'http://example.com/out.jpg',
      outputImageBase64: 'out64',
      sceneScreenshotBase64: 'scene64',
      sceneScreenshotStorageKey: 'assets/scene.jpg',
    };
    expect(getGeminiCompositeDisplayUrl(all)).toBe('http://example.com/out.jpg');
    expect(getGeminiCompositeDisplayUrl({ ...all, outputImageUrl: undefined })).toBe('data:image/jpeg;base64,out64');
  });
});

describe('getFinalHDDisplayUrl', () => {
  it('returns outputImageUrl when available', () => {
    expect(getFinalHDDisplayUrl({ outputImageUrl: 'http://out.jpg' })).toBe('http://out.jpg');
  });

  it('falls back to inputImageUrl', () => {
    expect(getFinalHDDisplayUrl({ inputImageUrl: 'http://in.jpg' })).toBe('http://in.jpg');
  });

  it('returns empty string when nothing available', () => {
    expect(getFinalHDDisplayUrl({})).toBe('');
  });
});

describe('getVideoDisplayMedia', () => {
  it('returns video type with videoUrl when available', () => {
    const result = getVideoDisplayMedia({ videoUrl: 'http://vid.mp4' });
    expect(result).toEqual({ type: 'video', url: 'http://vid.mp4' });
  });

  it('returns image type with inputImageUrl when no video', () => {
    const result = getVideoDisplayMedia({ inputImageUrl: 'http://img.jpg' });
    expect(result).toEqual({ type: 'image', url: 'http://img.jpg' });
  });

  it('returns none type when nothing available', () => {
    const result = getVideoDisplayMedia({});
    expect(result).toEqual({ type: 'none', url: '' });
  });

  it('prefers video over image', () => {
    const result = getVideoDisplayMedia({ videoUrl: 'http://vid.mp4', inputImageUrl: 'http://img.jpg' });
    expect(result.type).toBe('video');
  });
});

// ── Badge builder functions ──

const GREEN_BADGE_COLOR = 'rgba(52,211,153,0.7)';
const GREEN_BADGE_BG = 'rgba(52,211,153,0.15)';

describe('buildDirectorStage3DBadges', () => {
  it('returns VR badge when hasPanorama', () => {
    const badges = buildDirectorStage3DBadges({ hasPanorama: true });
    expect(badges.some(b => b.text === 'VR')).toBe(true);
  });

  it('returns 深度图 badge when hasDepthMap', () => {
    const badges = buildDirectorStage3DBadges({ hasDepthMap: true });
    expect(badges.some(b => b.text === '深度图')).toBe(true);
  });

  it('returns character count badge', () => {
    const badges = buildDirectorStage3DBadges({ characterCount: 3 });
    expect(badges.some(b => b.text === '3角色')).toBe(true);
  });

  it('does not return character badge when count is 0', () => {
    const badges = buildDirectorStage3DBadges({ characterCount: 0 });
    expect(badges.some(b => b.text.includes('角色'))).toBe(false);
  });

  it('returns 已截图 badge in green when hasScreenshot', () => {
    const badges = buildDirectorStage3DBadges({ hasScreenshot: true });
    const badge = badges.find(b => b.text === '已截图');
    expect(badge).toBeDefined();
    expect(badge!.textColor).toBe(GREEN_BADGE_COLOR);
    expect(badge!.bgColor).toBe(GREEN_BADGE_BG);
  });

  it('returns empty array when all flags are false/0', () => {
    const badges = buildDirectorStage3DBadges({});
    expect(badges).toEqual([]);
  });

  it('uses cyan theme colors for non-completion badges', () => {
    const badges = buildDirectorStage3DBadges({ hasPanorama: true });
    const vr = badges.find(b => b.text === 'VR')!;
    expect(vr.textColor).toContain('6,182,212');
    expect(vr.bgColor).toContain('6,182,212');
  });
});

describe('buildGeminiCompositeBadges', () => {
  it('returns character count badge from characterMappings', () => {
    const badges = buildGeminiCompositeBadges({
      characterMappings: [{ stageCharName: 'A' }, { stageCharName: 'B' }] as never[],
    });
    expect(badges.some(b => b.text === '2角色')).toBe(true);
  });

  it('returns 已合成 badge in green when output exists', () => {
    const badges = buildGeminiCompositeBadges({ outputImageUrl: 'http://out.jpg' });
    const badge = badges.find(b => b.text === '已合成');
    expect(badge).toBeDefined();
    expect(badge!.textColor).toBe(GREEN_BADGE_COLOR);
  });

  it('returns 等待截图 badge when no input', () => {
    const badges = buildGeminiCompositeBadges({});
    expect(badges.some(b => b.text === '等待截图')).toBe(true);
  });

  it('does not return 等待截图 when input exists', () => {
    const badges = buildGeminiCompositeBadges({ sceneScreenshotBase64: 'abc' });
    expect(badges.some(b => b.text === '等待截图')).toBe(false);
  });

  it('uses purple theme colors', () => {
    const badges = buildGeminiCompositeBadges({
      characterMappings: [{ stageCharName: 'A' }] as never[],
    });
    const charBadge = badges.find(b => b.text.includes('角色'))!;
    expect(charBadge.textColor).toContain('168,85,247');
  });
});

describe('buildFinalHDBadges', () => {
  it('returns scale factor badge 2x', () => {
    const badges = buildFinalHDBadges({ scaleFactor: 2 });
    expect(badges.some(b => b.text === '2x 放大')).toBe(true);
  });

  it('returns scale factor badge 4x', () => {
    const badges = buildFinalHDBadges({ scaleFactor: 4 });
    expect(badges.some(b => b.text === '4x 放大')).toBe(true);
  });

  it('returns 完成 badge in green when output exists', () => {
    const badges = buildFinalHDBadges({ outputImageUrl: 'http://out.jpg' });
    const badge = badges.find(b => b.text === '完成');
    expect(badge).toBeDefined();
    expect(badge!.textColor).toBe(GREEN_BADGE_COLOR);
  });

  it('uses green theme colors for scale badge', () => {
    const badges = buildFinalHDBadges({ scaleFactor: 2 });
    const scaleBadge = badges.find(b => b.text.includes('放大'))!;
    expect(scaleBadge.textColor).toContain('52,211,153');
  });
});

describe('buildVideoGenerationBadges', () => {
  it('returns mode badge T2V', () => {
    const badges = buildVideoGenerationBadges({ mode: 'text_to_video' });
    expect(badges.some(b => b.text === 'T2V')).toBe(true);
  });

  it('returns mode badge I2V', () => {
    const badges = buildVideoGenerationBadges({ mode: 'image_to_video' });
    expect(badges.some(b => b.text === 'I2V')).toBe(true);
  });

  it('returns mode badge SC2V', () => {
    const badges = buildVideoGenerationBadges({ mode: 'scene_character_to_video' });
    expect(badges.some(b => b.text === 'SC2V')).toBe(true);
  });

  it('returns duration badge', () => {
    const badges = buildVideoGenerationBadges({ durationSeconds: 8 });
    expect(badges.some(b => b.text === '8s')).toBe(true);
  });

  it('omits duration badge when durationSeconds is 0 or undefined', () => {
    expect(buildVideoGenerationBadges({ durationSeconds: 0 }).some(b => b.text.endsWith('s'))).toBe(false);
    expect(buildVideoGenerationBadges({}).some(b => b.text.endsWith('s') && !b.text.includes('V'))).toBe(false);
  });

  it('returns 完成 badge when videoUrl exists', () => {
    const badges = buildVideoGenerationBadges({ videoUrl: 'http://vid.mp4' });
    const badge = badges.find(b => b.text === '完成');
    expect(badge).toBeDefined();
    expect(badge!.textColor).toBe(GREEN_BADGE_COLOR);
  });

  it('uses fuchsia theme colors for mode badge', () => {
    const badges = buildVideoGenerationBadges({ mode: 'text_to_video' });
    const modeBadge = badges.find(b => b.text === 'T2V')!;
    expect(modeBadge.textColor).toContain('232,121,249');
  });
});
