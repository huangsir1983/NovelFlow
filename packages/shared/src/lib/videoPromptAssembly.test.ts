import { describe, it, expect } from 'vitest';
import { assembleVideoPrompt, buildImageRefsFromNodeData, assembleSegmentPrompt, buildSegmentImageRefs, assembleMergedPromptFromNodes } from './videoPromptAssembly';
import type { VideoGenerationNodeData, VideoSegmentNodeData, VideoSegmentShotInfo } from '../types/canvas';

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

/* ══════════════════════════════════════════════════════════════
   assembleSegmentPrompt — multi-shot merged prompt
   ══════════════════════════════════════════════════════════════ */

function makeShot(overrides: Partial<VideoSegmentShotInfo> = {}): VideoSegmentShotInfo {
  return {
    shotId: 'shot-1',
    description: '苏阳坐在桌前翻看课本',
    framing: '中景',
    cameraAngle: '侧面平视',
    cameraMovement: '缓慢跟随转动',
    durationSeconds: 4,
    ...overrides,
  };
}

function makeSegmentData(overrides: Partial<VideoSegmentNodeData> = {}): Partial<VideoSegmentNodeData> {
  return {
    nodeType: 'videoSegment',
    shotGroupId: 'g1',
    shotIds: ['shot-1', 'shot-2'],
    totalDurationSeconds: 7,
    progress: 0,
    mode: 'image_to_video',
    driftRisk: 'low',
    recommendedProvider: 'jimeng',
    inputImageUrl: 'http://example.com/firstframe.jpg',
    sceneLocation: '学生宿舍内部',
    sceneTimeOfDay: '白天',
    characterRefs: [
      { name: '苏阳', visualRefUrl: 'http://example.com/suyang.jpg' },
      { name: '室友1', visualRefUrl: 'http://example.com/roommate1.jpg' },
    ],
    shots: [
      makeShot({ shotId: 'shot-1', durationSeconds: 4, description: '苏阳坐在桌前翻看课本' }),
      makeShot({
        shotId: 'shot-2', durationSeconds: 3, description: '室友推门走进来',
        framing: '近景', cameraAngle: '正面平视', cameraMovement: '静止',
        dialogue: '你怎么才回来？',
      }),
    ],
    ...overrides,
  };
}

describe('assembleSegmentPrompt', () => {
  it('generates multi-shot prompt with all sections', () => {
    const prompt = assembleSegmentPrompt(makeSegmentData());

    expect(prompt).toContain('角色：');
    expect(prompt).toContain('苏阳');
    expect(prompt).toContain('室友1');
    expect(prompt).toContain('首帧图：');
    expect(prompt).toContain('此组分镜预计时长7秒');
    expect(prompt).toContain('场景：学生宿舍内部');
    expect(prompt).toContain('时间：白天');
    expect(prompt).toContain('前置提示词：');
    expect(prompt).toContain('镜头1：');
    expect(prompt).toContain('镜头2：');
  });

  it('includes per-shot framing/camera details', () => {
    const prompt = assembleSegmentPrompt(makeSegmentData());

    // Shot 1
    expect(prompt).toMatch(/镜头1：.*4秒/);
    expect(prompt).toMatch(/镜头1：.*中景/);
    expect(prompt).toMatch(/镜头1：.*侧面平视/);
    expect(prompt).toMatch(/镜头1：.*缓慢跟随转动/);

    // Shot 2
    expect(prompt).toMatch(/镜头2：.*3秒/);
    expect(prompt).toMatch(/镜头2：.*近景/);
    expect(prompt).toMatch(/镜头2：.*正面平视/);
  });

  it('includes shot descriptions in 画面承接', () => {
    const prompt = assembleSegmentPrompt(makeSegmentData());
    expect(prompt).toContain('苏阳坐在桌前翻看课本');
    expect(prompt).toContain('室友推门走进来');
  });

  it('includes dialogue in shot lines', () => {
    const prompt = assembleSegmentPrompt(makeSegmentData());
    expect(prompt).toContain('你怎么才回来');
  });

  it('adds transition hints for shots after the first', () => {
    const prompt = assembleSegmentPrompt(makeSegmentData());
    // First shot should NOT have transition
    const lines = prompt.split('\n');
    const shot1Line = lines.find(l => l.startsWith('镜头1：'));
    const shot2Line = lines.find(l => l.startsWith('镜头2：'));
    expect(shot1Line).not.toContain('过渡');
    expect(shot2Line).toContain('过渡');
  });

  it('degenerates to single-shot format for 1-shot segment', () => {
    const prompt = assembleSegmentPrompt(makeSegmentData({
      shotIds: ['shot-1'],
      totalDurationSeconds: 4,
      shots: [makeShot({ shotId: 'shot-1', durationSeconds: 4 })],
    }));

    expect(prompt).toContain('镜头1：');
    expect(prompt).not.toContain('镜头2：');
    expect(prompt).toContain('此组分镜预计时长4秒');
  });

  it('handles three shots with character deduplication', () => {
    const prompt = assembleSegmentPrompt(makeSegmentData({
      shotIds: ['shot-1', 'shot-2', 'shot-3'],
      totalDurationSeconds: 10,
      shots: [
        makeShot({ shotId: 'shot-1', durationSeconds: 4 }),
        makeShot({ shotId: 'shot-2', durationSeconds: 3, framing: '近景' }),
        makeShot({ shotId: 'shot-3', durationSeconds: 3, framing: '全景', description: '两人一起走出宿舍' }),
      ],
    }));

    expect(prompt).toContain('镜头1：');
    expect(prompt).toContain('镜头2：');
    expect(prompt).toContain('镜头3：');
    expect(prompt).toContain('此组分镜预计时长10秒');
    // Character refs should appear only once in 角色 line
    const charLine = prompt.split('\n').find(l => l.startsWith('角色：'));
    expect(charLine).toBeDefined();
    const suyangMatches = charLine!.match(/苏阳/g);
    expect(suyangMatches).toHaveLength(1);
  });

  it('handles missing optional fields', () => {
    const prompt = assembleSegmentPrompt(makeSegmentData({
      inputImageUrl: undefined,
      sceneTimeOfDay: undefined,
      characterRefs: [],
      shots: [makeShot({ cameraMovement: undefined, dialogue: undefined })],
    }));

    expect(prompt).not.toContain('角色：');
    expect(prompt).not.toContain('首帧图：');
    expect(prompt).not.toContain('时间：');
    expect(prompt).toContain('镜头1：');
  });

  it('computes total duration from shots array', () => {
    const data = makeSegmentData({
      totalDurationSeconds: 0, // intentionally wrong — function should sum from shots
    });
    const prompt = assembleSegmentPrompt(data);
    // Should use the actual sum: 4 + 3 = 7
    expect(prompt).toContain('此组分镜预计时长7秒');
  });
});

describe('buildSegmentImageRefs', () => {
  it('builds refs with firstFrame + deduplicated characters', () => {
    const refs = buildSegmentImageRefs(makeSegmentData());
    expect(refs).toHaveLength(3); // firstFrame + 苏阳 + 室友1
    expect(refs[0].type).toBe('firstFrame');
    expect(refs[1].type).toBe('character');
    expect(refs[1].label).toBe('苏阳');
    expect(refs[2].type).toBe('character');
    expect(refs[2].label).toBe('室友1');
  });

  it('omits firstFrame when no inputImageUrl', () => {
    const refs = buildSegmentImageRefs(makeSegmentData({ inputImageUrl: undefined }));
    expect(refs).toHaveLength(2);
    expect(refs[0].type).toBe('character');
  });

  it('deduplicates characters across shots', () => {
    const refs = buildSegmentImageRefs(makeSegmentData({
      characterRefs: [
        { name: '苏阳', visualRefUrl: 'http://example.com/suyang.jpg' },
        { name: '苏阳', visualRefUrl: 'http://example.com/suyang.jpg' }, // duplicate
        { name: '室友1', visualRefUrl: 'http://example.com/roommate1.jpg' },
      ],
    }));
    const charRefs = refs.filter(r => r.type === 'character');
    expect(charRefs).toHaveLength(2); // 苏阳 only once
  });
});

/* ══════════════════════════════════════════════════════════════
   assembleMergedPromptFromNodes — 磁吸合并多节点 prompt
   ══════════════════════════════════════════════════════════════ */

function makeMergedNode(overrides: Partial<VideoGenerationNodeData> = {}): { data: Partial<VideoGenerationNodeData> } {
  return { data: makeData(overrides) };
}

describe('assembleMergedPromptFromNodes', () => {
  it('generates structured prompt with multiple shots', () => {
    const nodes = [
      makeMergedNode({ shotDescription: '苏阳坐在桌前', durationSeconds: 4, inputImageUrl: 'http://ex.com/frame1.jpg' }),
      makeMergedNode({ shotDescription: '室友走进来', durationSeconds: 3, shotFraming: '近景', inputImageUrl: 'http://ex.com/frame2.jpg' }),
    ];
    const prompt = assembleMergedPromptFromNodes(nodes);

    expect(prompt).toContain('镜头1：');
    expect(prompt).toContain('镜头2：');
    expect(prompt).toContain('4秒');
    expect(prompt).toContain('3秒');
    expect(prompt).toContain('近景');
  });

  it('each shot references its own first frame', () => {
    const nodes = [
      makeMergedNode({ inputImageUrl: 'http://ex.com/frame1.jpg' }),
      makeMergedNode({ inputImageUrl: 'http://ex.com/frame2.jpg' }),
    ];
    const prompt = assembleMergedPromptFromNodes(nodes);

    // 图片1=镜头1首帧, 图片2=镜头2首帧
    expect(prompt).toContain('镜头1首帧：图片1');
    expect(prompt).toContain('镜头2首帧：图片2');
  });

  it('deduplicates characters across nodes', () => {
    const nodes = [
      makeMergedNode({
        characterRefs: [
          { name: '苏阳', visualRefUrl: 'http://ex.com/suyang.jpg' },
          { name: '室友1', visualRefUrl: 'http://ex.com/rm1.jpg' },
        ],
      }),
      makeMergedNode({
        characterRefs: [
          { name: '苏阳', visualRefUrl: 'http://ex.com/suyang.jpg' }, // duplicate
          { name: '室友2', visualRefUrl: 'http://ex.com/rm2.jpg' },
        ],
      }),
    ];
    const prompt = assembleMergedPromptFromNodes(nodes);

    // 角色行应包含 3 个角色（苏阳去重）
    const charLine = prompt.split('\n').find(l => l.startsWith('角色：'));
    expect(charLine).toBeDefined();
    expect(charLine).toContain('苏阳');
    expect(charLine).toContain('室友1');
    expect(charLine).toContain('室友2');
    // 苏阳只出现一次
    const matches = charLine!.match(/苏阳/g);
    expect(matches).toHaveLength(1);
  });

  it('includes scene, time, and fixed prefix', () => {
    const nodes = [makeMergedNode()];
    const prompt = assembleMergedPromptFromNodes(nodes);

    expect(prompt).toContain('场景：学生宿舍内部');
    expect(prompt).toContain('时间：白天');
    expect(prompt).toContain('前置提示词：');
    expect(prompt).toContain('保持人物一致性');
  });

  it('computes total duration from all nodes', () => {
    const nodes = [
      makeMergedNode({ durationSeconds: 4 }),
      makeMergedNode({ durationSeconds: 3 }),
      makeMergedNode({ durationSeconds: 5 }),
    ];
    const prompt = assembleMergedPromptFromNodes(nodes);
    expect(prompt).toContain('此组分镜预计时长12秒');
  });

  it('returns empty string for empty nodes array', () => {
    expect(assembleMergedPromptFromNodes([])).toBe('');
  });

  it('adds transition hint for shots after the first', () => {
    const nodes = [
      makeMergedNode({ durationSeconds: 4 }),
      makeMergedNode({ durationSeconds: 3 }),
    ];
    const prompt = assembleMergedPromptFromNodes(nodes);
    const lines = prompt.split('\n');
    const shot2Line = lines.find(l => l.startsWith('镜头2：'));
    expect(shot2Line).toContain('过渡（自然衔接）');
  });
});
