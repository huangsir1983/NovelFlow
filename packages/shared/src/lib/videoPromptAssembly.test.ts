import { describe, it, expect } from 'vitest';
import { assembleVideoPrompt, buildImageRefsFromNodeData } from './videoPromptAssembly';
import type { VideoGenerationNodeData } from '../types/canvas';

/** Helper: partial VideoGenerationNodeData for testing */
function makeData(overrides: Partial<VideoGenerationNodeData> = {}): Partial<VideoGenerationNodeData> {
  return {
    nodeType: 'videoGeneration',
    shotDescription: '苏阳坐在桌前翻看课本，室友从门外走进来',
    shotFraming: '中景',
    shotCameraAngle: '侧面平视',
    shotCameraMovement: '缓慢跟随转动',
    shotDialogue: '苏阳：你怎么才回来？',
    shotEmotionTarget: '好奇',
    shotCharactersInFrame: ['苏阳', '室友1'],
    shotCharacterActions: {
      '苏阳': { expression: '好奇', action: '翻书', position: '桌前' },
      '室友1': { expression: '疲惫', action: '走进来', position: '门口' },
    },
    sceneLocation: '学生宿舍内部',
    sceneTimeOfDay: '白天',
    sceneDescription: '一间普通的大学宿舍',
    durationSeconds: 5,
    characterRefs: [
      { name: '苏阳', visualRefUrl: 'http://example.com/suyang.jpg' },
      { name: '室友1', visualRefUrl: 'http://example.com/roommate1.jpg' },
    ],
    inputImageUrl: 'http://example.com/firstframe.jpg',
    ...overrides,
  };
}

describe('assembleVideoPrompt', () => {
  it('generates structured prompt with all sections', () => {
    const prompt = assembleVideoPrompt(makeData());

    // 角色行
    expect(prompt).toContain('角色：');
    expect(prompt).toContain('苏阳');
    expect(prompt).toContain('室友1');

    // 首帧图行
    expect(prompt).toContain('首帧图：');

    // 时长
    expect(prompt).toContain('此组分镜预计时长5秒');

    // 场景
    expect(prompt).toContain('场景：学生宿舍内部');
    expect(prompt).toContain('时间：白天');

    // 前置提示词
    expect(prompt).toContain('前置提示词：');
    expect(prompt).toContain('保持人物一致性');

    // 镜头行
    expect(prompt).toContain('镜头1：');
    expect(prompt).toContain('中景');
    expect(prompt).toContain('侧面平视');
    expect(prompt).toContain('缓慢跟随转动');
  });

  it('includes image index references (图片N) for characters', () => {
    const prompt = assembleVideoPrompt(makeData());

    // 首帧图 = 图片1, 苏阳 = 图片2, 室友1 = 图片3
    expect(prompt).toMatch(/图片1.*首帧图|首帧图.*图片1/);
    expect(prompt).toMatch(/图片2.*苏阳|苏阳.*图片2/);  // 图片2是苏阳 or similar
    expect(prompt).toMatch(/图片3.*室友1|室友1.*图片3/);
  });

  it('includes shot description in 镜头 line', () => {
    const prompt = assembleVideoPrompt(makeData());
    expect(prompt).toContain('苏阳坐在桌前翻看课本');
  });

  it('handles missing optional fields gracefully', () => {
    const prompt = assembleVideoPrompt(makeData({
      shotDialogue: undefined,
      shotEmotionTarget: undefined,
      shotCameraMovement: undefined,
      shotCharacterActions: undefined,
      sceneTimeOfDay: undefined,
      characterRefs: [],
      inputImageUrl: undefined,
    }));

    // Should not throw, should still have scene and shot info
    expect(prompt).toContain('场景：学生宿舍内部');
    expect(prompt).toContain('镜头1：');
    expect(prompt).not.toContain('角色：'); // no characters
    expect(prompt).not.toContain('首帧图：'); // no first frame
    expect(prompt).not.toContain('时间：'); // no time of day
  });

  it('handles zero duration', () => {
    const prompt = assembleVideoPrompt(makeData({ durationSeconds: 0 }));
    expect(prompt).not.toContain('此组分镜预计时长');
  });

  it('includes dialogue when present', () => {
    const prompt = assembleVideoPrompt(makeData());
    expect(prompt).toContain('你怎么才回来');
  });

  it('works with single character and no first frame', () => {
    const prompt = assembleVideoPrompt(makeData({
      shotCharactersInFrame: ['苏阳'],
      characterRefs: [{ name: '苏阳', visualRefUrl: 'http://example.com/suyang.jpg' }],
      inputImageUrl: undefined,
    }));
    // 苏阳 should be 图片1 (no first frame, so characters start at 1)
    expect(prompt).toContain('角色：');
    expect(prompt).toMatch(/图片1.*苏阳|苏阳.*图片1/);
    expect(prompt).not.toContain('首帧图：');
  });
});

describe('buildImageRefsFromNodeData', () => {
  it('builds refs with firstFrame at index 0 and characters after', () => {
    const refs = buildImageRefsFromNodeData(makeData());

    expect(refs).toHaveLength(3);
    expect(refs[0].type).toBe('firstFrame');
    expect(refs[0].label).toBe('首帧图');
    expect(refs[0].url).toBe('http://example.com/firstframe.jpg');
    expect(refs[1].type).toBe('character');
    expect(refs[1].label).toBe('苏阳');
    expect(refs[1].characterName).toBe('苏阳');
    expect(refs[2].type).toBe('character');
    expect(refs[2].label).toBe('室友1');
  });

  it('omits firstFrame when no inputImageUrl', () => {
    const refs = buildImageRefsFromNodeData(makeData({ inputImageUrl: undefined }));
    expect(refs).toHaveLength(2);
    expect(refs[0].type).toBe('character');
  });

  it('omits characters without visualRefUrl', () => {
    const refs = buildImageRefsFromNodeData(makeData({
      characterRefs: [
        { name: '苏阳', visualRefUrl: 'http://example.com/suyang.jpg' },
        { name: '室友1' }, // no URL
      ],
    }));
    expect(refs).toHaveLength(2); // firstFrame + 苏阳
    expect(refs.find(r => r.label === '室友1')).toBeUndefined();
  });

  it('returns empty array when no data', () => {
    const refs = buildImageRefsFromNodeData({});
    expect(refs).toEqual([]);
  });

  it('assigns unique ids', () => {
    const refs = buildImageRefsFromNodeData(makeData());
    const ids = refs.map(r => r.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('includes storageKey when available', () => {
    const refs = buildImageRefsFromNodeData(makeData({
      inputStorageKey: 'uploads/firstframe.jpg',
      characterRefs: [
        { name: '苏阳', visualRefUrl: 'http://example.com/suyang.jpg', visualRefStorageKey: 'refs/suyang.jpg' },
      ],
    }));
    expect(refs[0].storageKey).toBe('uploads/firstframe.jpg');
    expect(refs[1].storageKey).toBe('refs/suyang.jpg');
  });
});
