import { describe, it, expect } from 'vitest';
import {
  buildGeminiPrompt,
  buildImageList,
  buildMappings,
  buildInterleavedParts,
  type CharacterMapping,
  type StageScreenshots,
} from './stageScreenshot';

// ── buildGeminiPrompt ────────────────────────────────────────────

describe('buildGeminiPrompt', () => {
  const twoChars: CharacterMapping[] = [
    {
      stageCharId: 'c1', stageCharName: '角色 1', stageCharColor: '红',
      referenceCharName: '高令宁', poseImageIndex: 2, refImageIndex: 3,
    },
    {
      stageCharId: 'c2', stageCharName: '角色 2', stageCharColor: '青',
      referenceCharName: '沈词', poseImageIndex: 4, refImageIndex: 5,
    },
  ];

  it('includes @1 base scene reference', () => {
    const prompt = buildGeminiPrompt(twoChars);
    expect(prompt).toContain('@1');
  });

  it('includes all character image indices', () => {
    const prompt = buildGeminiPrompt(twoChars);
    expect(prompt).toContain('@2');
    expect(prompt).toContain('@3');
    expect(prompt).toContain('@4');
    expect(prompt).toContain('@5');
  });

  it('includes character names', () => {
    const prompt = buildGeminiPrompt(twoChars);
    expect(prompt).toContain('高令宁');
    expect(prompt).toContain('沈词');
  });

  it('includes color descriptions', () => {
    const prompt = buildGeminiPrompt(twoChars);
    expect(prompt).toContain('红色人偶');
    expect(prompt).toContain('青色人偶');
  });

  it('includes scene description when provided', () => {
    const prompt = buildGeminiPrompt(twoChars, '中式古典大厅');
    expect(prompt).toContain('中式古典大厅');
  });

  it('omits scene description line when not provided', () => {
    const prompt = buildGeminiPrompt(twoChars);
    expect(prompt).not.toContain('场景描述');
  });

  it('includes requirements section', () => {
    const prompt = buildGeminiPrompt(twoChars);
    expect(prompt).toContain('姿态');
    expect(prompt).toContain('影视级');
  });

  it('works with single character', () => {
    const one: CharacterMapping[] = [{
      stageCharId: 'c1', stageCharName: '角色 1', stageCharColor: '红',
      referenceCharName: '高令宁', poseImageIndex: 2, refImageIndex: 3,
    }];
    const prompt = buildGeminiPrompt(one);
    expect(prompt).toContain('@2');
    expect(prompt).toContain('@3');
    expect(prompt).not.toContain('@4');
  });
});

// ── buildImageList ───────────────────────────────────────────────

describe('buildImageList', () => {
  it('puts base screenshot at index 1', () => {
    const list = buildImageList('base64_scene', []);
    expect(list).toHaveLength(1);
    expect(list[0]).toEqual({ data: 'base64_scene', index: 1 });
  });

  it('interleaves pose and reference images', () => {
    const list = buildImageList('base', [
      { poseScreenshot: 'pose1', referenceBase64: 'ref1' },
      { poseScreenshot: 'pose2', referenceBase64: 'ref2' },
    ]);
    expect(list).toHaveLength(5);
    expect(list[0]).toEqual({ data: 'base', index: 1 });
    expect(list[1]).toEqual({ data: 'pose1', index: 2 });
    expect(list[2]).toEqual({ data: 'ref1', index: 3 });
    expect(list[3]).toEqual({ data: 'pose2', index: 4 });
    expect(list[4]).toEqual({ data: 'ref2', index: 5 });
  });

  it('indices are sequential starting from 1', () => {
    const list = buildImageList('b', [
      { poseScreenshot: 'p1', referenceBase64: 'r1' },
    ]);
    const indices = list.map(i => i.index);
    expect(indices).toEqual([1, 2, 3]);
  });
});

// ── buildMappings ────────────────────────────────────────────────

describe('buildMappings', () => {
  const screenshots: StageScreenshots = {
    base: 'base64_base',
    characters: [
      { stageCharId: 'c1', stageCharName: '角色 1', color: '红', screenshot: 'ss1' },
      { stageCharId: 'c2', stageCharName: '角色 2', color: '青', screenshot: 'ss2' },
    ],
  };

  it('computes correct image indices', () => {
    const refs = [
      { stageCharId: 'c1', referenceCharName: '高令宁' },
      { stageCharId: 'c2', referenceCharName: '沈词' },
    ];
    const mappings = buildMappings(screenshots, refs);

    expect(mappings).toHaveLength(2);
    expect(mappings[0].poseImageIndex).toBe(2);
    expect(mappings[0].refImageIndex).toBe(3);
    expect(mappings[1].poseImageIndex).toBe(4);
    expect(mappings[1].refImageIndex).toBe(5);
  });

  it('carries through character metadata', () => {
    const refs = [{ stageCharId: 'c1', referenceCharName: '高令宁' }];
    const mappings = buildMappings(screenshots, refs);

    expect(mappings[0].stageCharName).toBe('角色 1');
    expect(mappings[0].stageCharColor).toBe('红');
    expect(mappings[0].referenceCharName).toBe('高令宁');
  });

  it('skips characters not found in screenshots', () => {
    const refs = [
      { stageCharId: 'c1', referenceCharName: '高令宁' },
      { stageCharId: 'c999', referenceCharName: '不存在' },
    ];
    const mappings = buildMappings(screenshots, refs);
    expect(mappings).toHaveLength(1);
    expect(mappings[0].referenceCharName).toBe('高令宁');
  });

  it('returns empty array when no matches', () => {
    const refs = [{ stageCharId: 'nope', referenceCharName: 'X' }];
    expect(buildMappings(screenshots, refs)).toEqual([]);
  });
});

// ── buildInterleavedParts ────────────────────────────────────────

describe('buildInterleavedParts', () => {
  const screenshots: StageScreenshots = {
    base: 'base64_scene',
    characters: [
      { stageCharId: 'c1', stageCharName: '角色 1', color: '#06b6d4', screenshot: 'ss1' },
      { stageCharId: 'c2', stageCharName: '角色 2', color: '#f472b6', screenshot: 'ss2' },
    ],
  };

  const charData = [
    {
      stageCharId: 'c1', referenceCharName: '高令宁', stageCharColor: '#06b6d4',
      poseScreenshot: 'pose1', referenceBase64: 'ref1',
    },
    {
      stageCharId: 'c2', referenceCharName: '沈词', stageCharColor: '#f472b6',
      poseScreenshot: 'pose2', referenceBase64: 'ref2',
    },
  ];

  it('puts all images first, then single text block', () => {
    const parts = buildInterleavedParts(screenshots, charData);
    // 5 images first, then 1 text at the end
    const imageCount = parts.filter(p => p.type === 'image').length;
    const textCount = parts.filter(p => p.type === 'text').length;
    expect(imageCount).toBe(5);
    expect(textCount).toBe(1);
    // All images come before the text
    const lastImageIdx = parts.map((p, i) => p.type === 'image' ? i : -1).filter(i => i >= 0).pop()!;
    const textIdx = parts.findIndex(p => p.type === 'text');
    expect(lastImageIdx).toBeLessThan(textIdx);
  });

  it('includes base scene as first image', () => {
    const parts = buildInterleavedParts(screenshots, charData);
    expect(parts[0].type).toBe('image');
    expect(parts[0].content).toBe('base64_scene');
  });

  it('orders images: base, pose1, ref1, pose2, ref2', () => {
    const parts = buildInterleavedParts(screenshots, charData);
    const images = parts.filter(p => p.type === 'image');
    expect(images).toHaveLength(5);
    expect(images[0].content).toBe('base64_scene');
    expect(images[1].content).toBe('pose1');
    expect(images[2].content).toBe('ref1');
    expect(images[3].content).toBe('pose2');
    expect(images[4].content).toBe('ref2');
  });

  it('uses ordinal references (图1, 图2, 图3) in text', () => {
    const parts = buildInterleavedParts(screenshots, charData);
    const text = parts.find(p => p.type === 'text')!.content;
    expect(text).toContain('图1');
    expect(text).toContain('图2');
    expect(text).toContain('图3');
    expect(text).toContain('图4');
    expect(text).toContain('图5');
  });

  it('uses Chinese color names instead of hex', () => {
    const parts = buildInterleavedParts(screenshots, charData);
    const text = parts.find(p => p.type === 'text')!.content;
    expect(text).toContain('蓝色人偶');
    expect(text).toContain('粉色人偶');
    expect(text).not.toContain('#06b6d4');
    expect(text).not.toContain('#f472b6');
  });

  it('includes character names', () => {
    const parts = buildInterleavedParts(screenshots, charData);
    const text = parts.find(p => p.type === 'text')!.content;
    expect(text).toContain('高令宁');
    expect(text).toContain('沈词');
  });

  it('links pose to reference per character', () => {
    const parts = buildInterleavedParts(screenshots, charData);
    const text = parts.find(p => p.type === 'text')!.content;
    // char1: pose=图2, ref=图3
    expect(text).toMatch(/角色1.*高令宁.*图2.*图3/s);
    // char2: pose=图4, ref=图5
    expect(text).toMatch(/角色2.*沈词.*图4.*图5/s);
  });

  it('includes scene description when provided', () => {
    const parts = buildInterleavedParts(screenshots, charData, '中式古典大厅');
    const text = parts.find(p => p.type === 'text')!.content;
    expect(text).toContain('中式古典大厅');
  });

  it('includes rules about not swapping and preserving lighting', () => {
    const parts = buildInterleavedParts(screenshots, charData);
    const text = parts.find(p => p.type === 'text')!.content;
    expect(text).toContain('姿态');
    expect(text).toContain('影视级');
    expect(text).toContain('不要互换');
    expect(text).toContain('环境光融合');
    expect(text).toContain('位置锁定');
    expect(text).toContain('大小锁定');
  });

  it('includes bbox position lock when bbox is provided', () => {
    const charDataWithBbox = [
      {
        ...charData[0],
        bbox: { left: 25.5, top: 10.2, width: 20.3, height: 60.8 },
      },
    ];
    const parts = buildInterleavedParts(screenshots, charDataWithBbox);
    const text = parts.find(p => p.type === 'text')!.content;
    expect(text).toContain('左边界25.5%');
    expect(text).toContain('上边界10.2%');
    expect(text).toContain('宽20.3%');
    expect(text).toContain('高60.8%');
    expect(text).toContain('不能偏移也不能放大缩小');
  });

  it('works with single character', () => {
    const one = [charData[0]];
    const parts = buildInterleavedParts(screenshots, one);
    const images = parts.filter(p => p.type === 'image');
    expect(images).toHaveLength(3); // base + pose + ref
    const text = parts.find(p => p.type === 'text')!.content;
    expect(text).toContain('图2');
    expect(text).toContain('图3');
    expect(text).not.toContain('图4');
  });
});
