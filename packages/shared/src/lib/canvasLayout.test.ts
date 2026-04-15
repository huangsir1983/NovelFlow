import { describe, it, expect } from 'vitest';
import { buildCanvasGraph } from './canvasLayout';
import type { ViewPoint } from '../types/canvas';

const scene = {
  id: 's1',
  heading: 'Scene 1',
  location: 'Grand Hall',
  timeOfDay: 'day',
  description: '',
  characterNames: ['Alice'],
  order: 0,
  coreEvent: '',
  emotionalPeak: '',
  narrativeMode: '',
};

const shot = {
  id: 'shot1',
  sceneId: 's1',
  shotNumber: 1,
  framing: 'medium',
  cameraAngle: 'eye-level',
  cameraMovement: '',
  description: 'Test shot',
  thumbnailUrl: undefined,
  visualPrompt: '',
  charactersInFrame: ['Alice'],
  durationEstimate: '3s',
};

const defaultCharMap = {
  Alice: {
    name: 'Alice',
    appearance: {},
    costume: {},
    visualRefUrl: undefined,
    visualRefStorageKey: undefined,
  },
};

describe('buildCanvasGraph with viewpoints', () => {
  it('passes viewpoints into SceneBGNode data', () => {
    const viewpoints: ViewPoint[] = [
      { id: 'vp1', label: '大厅中央', yaw: 0, pitch: 0, fov: 75, isDefault: true },
      { id: 'vp2', label: '阳台', yaw: 90, pitch: -10, fov: 60 },
    ];

    const { nodes } = buildCanvasGraph([scene], [shot], {
      locationPanoramaMap: {
        'Grand Hall': {
          panoramaUrl: 'http://test/panorama.jpg',
          panoramaStorageKey: 'assets/panoramas/test.jpg',
          viewpoints,
        },
      },
      characterMap: defaultCharMap,
    });

    const sceneBGNode = nodes.find(n => n.type === 'sceneBG');
    expect(sceneBGNode).toBeDefined();

    const data = sceneBGNode!.data as Record<string, unknown>;
    expect(data.viewpoints).toHaveLength(2);
    expect(data.activeViewpointId).toBe('vp1');
    expect((data.viewAngle as Record<string, number>).fov).toBe(75);
  });

  it('works without viewpoints (backward compat)', () => {
    const { nodes } = buildCanvasGraph([scene], [shot], {
      locationPanoramaMap: {
        'Grand Hall': {
          panoramaUrl: 'http://test/panorama.jpg',
        },
      },
      characterMap: defaultCharMap,
    });

    const sceneBGNode = nodes.find(n => n.type === 'sceneBG');
    expect(sceneBGNode).toBeDefined();

    const data = sceneBGNode!.data as Record<string, unknown>;
    expect((data.viewpoints as unknown[]).length).toBeGreaterThan(0);
    expect(data.activeViewpointId).toBe('vp-default-up');
    expect(data.panoramaUrl).toBe('http://test/panorama.jpg');
  });
});

// ═══════════════════════════════════════════════════════════
// New pipeline topology tests (DirectorStage3D + GeminiComposite)
// ═══════════════════════════════════════════════════════════

describe('New pipeline: removed nodes', () => {
  const opts = { characterMap: defaultCharMap };

  it('should NOT contain any Pose3D node', () => {
    const { nodes } = buildCanvasGraph([scene], [shot], opts);
    const pose3dNodes = nodes.filter(n => n.type === 'pose3D');
    expect(pose3dNodes).toHaveLength(0);
  });

  it('should NOT contain any per-character Expression node', () => {
    const { nodes } = buildCanvasGraph([scene], [shot], opts);
    const charExprNodes = nodes.filter(
      n => n.id.startsWith('imgproc-expression-shot1-') && !n.id.endsWith('-scene'),
    );
    expect(charExprNodes).toHaveLength(0);
  });

  it('should NOT contain any Matting node', () => {
    const { nodes } = buildCanvasGraph([scene], [shot], opts);
    const mattingNodes = nodes.filter(
      n => (n.data as Record<string, unknown>).processType === 'matting',
    );
    expect(mattingNodes).toHaveLength(0);
  });

  it('should NOT contain any HDUpscale-BG node', () => {
    const { nodes } = buildCanvasGraph([scene], [shot], opts);
    const hdBgNodes = nodes.filter(
      n => n.id.includes('hdUpscale') && n.id.endsWith('-bg'),
    );
    expect(hdBgNodes).toHaveLength(0);
  });

  it('should NOT contain old Composite node', () => {
    const { nodes } = buildCanvasGraph([scene], [shot], opts);
    const compositeNodes = nodes.filter(n => n.type === 'composite');
    expect(compositeNodes).toHaveLength(0);
  });

  it('should NOT have any Pose3D edges', () => {
    const { edges } = buildCanvasGraph([scene], [shot], opts);
    const p3dEdges = edges.filter(
      e => e.source.includes('pose3d') || e.target.includes('pose3d'),
    );
    expect(p3dEdges).toHaveLength(0);
  });

  it('should NOT have any Matting edges', () => {
    const { edges } = buildCanvasGraph([scene], [shot], opts);
    const mattingEdges = edges.filter(
      e => e.source.includes('matting') || e.target.includes('matting'),
    );
    expect(mattingEdges).toHaveLength(0);
  });
});

describe('New pipeline: DirectorStage3D node', () => {
  const opts = { characterMap: defaultCharMap };

  it('should create a DirectorStage3D node per shot', () => {
    const { nodes } = buildCanvasGraph([scene], [shot], opts);
    const dsNode = nodes.find(n => n.type === 'directorStage3D');
    expect(dsNode).toBeDefined();
    expect(dsNode!.id).toBe('dirstage-shot1');
    const data = dsNode!.data as Record<string, unknown>;
    expect(data.nodeType).toBe('directorStage3D');
  });

  it('should have SceneBG → DirectorStage3D edge', () => {
    const { edges } = buildCanvasGraph([scene], [shot], opts);
    const edge = edges.find(
      e => e.source === 'scenebg-shot1' && e.target === 'dirstage-shot1',
    );
    expect(edge).toBeDefined();
    expect(edge!.type).toBe('pipeline');
  });

  it('should have CharacterProcess → DirectorStage3D edge', () => {
    const { edges } = buildCanvasGraph([scene], [shot], opts);
    const edge = edges.find(
      e => e.source === 'charproc-shot1-Alice' && e.target === 'dirstage-shot1',
    );
    expect(edge).toBeDefined();
    expect(edge!.type).toBe('pipeline');
  });

  it('should pass depthMap info when available', () => {
    const { nodes } = buildCanvasGraph([scene], [shot], {
      characterMap: defaultCharMap,
      locationPanoramaMap: {
        'Grand Hall': {
          panoramaUrl: 'http://test/vr.jpg',
          depthMapUrl: 'http://test/depth.png',
          depthMapStorageKey: 'assets/depth/001.png',
        },
      },
    });

    const bgNode = nodes.find(n => n.type === 'sceneBG');
    expect(bgNode).toBeDefined();
    const bgData = bgNode!.data as Record<string, unknown>;
    expect(bgData.depthMapUrl).toBe('http://test/depth.png');
    expect(bgData.depthMapStorageKey).toBe('assets/depth/001.png');
  });
});

describe('New pipeline: GeminiComposite node', () => {
  const opts = { characterMap: defaultCharMap };

  it('should create a GeminiComposite node per shot', () => {
    const { nodes } = buildCanvasGraph([scene], [shot], opts);
    const gcNode = nodes.find(n => n.type === 'geminiComposite');
    expect(gcNode).toBeDefined();
    expect(gcNode!.id).toBe('geminicomp-shot1');
    const data = gcNode!.data as Record<string, unknown>;
    expect(data.nodeType).toBe('geminiComposite');
  });

  it('should have DirectorStage3D → GeminiComposite edge', () => {
    const { edges } = buildCanvasGraph([scene], [shot], opts);
    const edge = edges.find(
      e => e.source === 'dirstage-shot1' && e.target === 'geminicomp-shot1',
    );
    expect(edge).toBeDefined();
    expect(edge!.type).toBe('pipeline');
  });

  it('should have GeminiComposite → PostExpression edge', () => {
    const { edges } = buildCanvasGraph([scene], [shot], opts);
    const edge = edges.find(
      e => e.source === 'geminicomp-shot1' && e.target === 'imgproc-expression-shot1-scene',
    );
    expect(edge).toBeDefined();
    expect(edge!.type).toBe('pipeline');
  });
});

describe('New pipeline: PostExpression still exists', () => {
  const opts = { characterMap: defaultCharMap };

  it('should contain a post-composite expression imageProcess node', () => {
    const { nodes } = buildCanvasGraph([scene], [shot], opts);
    const peNode = nodes.find(n => n.id === 'imgproc-expression-shot1-scene');
    expect(peNode).toBeDefined();
    expect(peNode!.type).toBe('imageProcess');
    const data = peNode!.data as Record<string, unknown>;
    expect(data.processType).toBe('expression');
  });

  it('should have PostExpression → FinalHD pipeline edge', () => {
    const { edges } = buildCanvasGraph([scene], [shot], opts);
    const edge = edges.find(
      e => e.source === 'imgproc-expression-shot1-scene' && e.target === 'finalhd-shot1',
    );
    expect(edge).toBeDefined();
    expect(edge!.type).toBe('pipeline');
  });

  it('should NOT have any blendrefine edges', () => {
    const { edges } = buildCanvasGraph([scene], [shot], opts);
    const brEdges = edges.filter(
      e => e.source.includes('blendrefine') || e.target.includes('blendrefine'),
    );
    expect(brEdges).toHaveLength(0);
  });

  it('should NOT contain any Lighting node', () => {
    const { nodes } = buildCanvasGraph([scene], [shot], opts);
    const lightingNodes = nodes.filter(n => n.type === 'lighting');
    expect(lightingNodes).toHaveLength(0);
  });
});

describe('New pipeline: multi-character shot', () => {
  const twoCharScene = { ...scene, characterNames: ['Alice', 'Bob'] };
  const twoCharShot = { ...shot, charactersInFrame: ['Alice', 'Bob'] };
  const twoCharMap = {
    Alice: { name: 'Alice', appearance: {}, costume: {}, visualRefUrl: 'http://alice.jpg' },
    Bob: { name: 'Bob', appearance: {}, costume: {}, visualRefUrl: 'http://bob.jpg' },
  };

  it('creates CharacterProcess for each character', () => {
    const { nodes } = buildCanvasGraph([twoCharScene], [twoCharShot], { characterMap: twoCharMap });
    const charNodes = nodes.filter(n => n.type === 'characterProcess');
    expect(charNodes).toHaveLength(2);
  });

  it('all CharProcess nodes connect to same DirectorStage3D', () => {
    const { edges } = buildCanvasGraph([twoCharScene], [twoCharShot], { characterMap: twoCharMap });
    const edgesToDS = edges.filter(e => e.target === 'dirstage-shot1' && e.source.startsWith('charproc-'));
    expect(edgesToDS).toHaveLength(2);
  });

  it('only one DirectorStage3D per shot', () => {
    const { nodes } = buildCanvasGraph([twoCharScene], [twoCharShot], { characterMap: twoCharMap });
    const dsNodes = nodes.filter(n => n.type === 'directorStage3D');
    expect(dsNodes).toHaveLength(1);
  });

  it('only one GeminiComposite per shot', () => {
    const { nodes } = buildCanvasGraph([twoCharScene], [twoCharShot], { characterMap: twoCharMap });
    const gcNodes = nodes.filter(n => n.type === 'geminiComposite');
    expect(gcNodes).toHaveLength(1);
  });
});

// ═══════════════════════════════════════════════════════════
// characterActions passthrough to DirectorStage3D
// ═══════════════════════════════════════════════════════════

describe('characterActions passthrough', () => {
  const sceneWithScript = {
    ...scene,
    characterNames: ['Alice', 'Bob'],
    scriptJson: {
      beats: [{
        beat_id: 'b1',
        timestamp: '00:00',
        type: 'action',
        shots: [{
          shot_type: 'medium',
          camera_move: 'static',
          angle: 'eye-level',
          subject: 'Alice and Bob',
          action: 'Alice sits while Bob runs',
          dialogue: null,
          characters: [
            { name: 'Alice', expression: '平静', action: '坐在椅子上', position: '画面左侧' },
            { name: 'Bob', expression: '紧张', action: '奔跑', position: '画面右侧' },
          ],
        }],
      }],
    },
  };

  const charMap = {
    Alice: { name: 'Alice', appearance: {}, costume: {}, visualRefUrl: 'http://alice.jpg' },
    Bob: { name: 'Bob', appearance: {}, costume: {}, visualRefUrl: 'http://bob.jpg' },
  };

  it('passes characterActions from scriptJson shots to DirectorStage3D node data', () => {
    const { nodes } = buildCanvasGraph([sceneWithScript], [], { characterMap: charMap });
    const dsNode = nodes.find(n => n.type === 'directorStage3D');
    expect(dsNode).toBeDefined();

    const data = dsNode!.data as Record<string, unknown>;
    const actions = data.characterActions as Record<string, { expression?: string; action?: string; position?: string }>;
    expect(actions).toBeDefined();
    expect(actions['Alice']).toEqual({ expression: '平静', action: '坐在椅子上', position: '画面左侧' });
    expect(actions['Bob']).toEqual({ expression: '紧张', action: '奔跑', position: '画面右侧' });
  });

  it('passes characterActions from explicit shot input', () => {
    const shotWithActions = {
      ...shot,
      charactersInFrame: ['Alice'],
      characterActions: {
        Alice: { expression: '微笑', action: '走近窗边', position: '画面中央' },
      },
    };
    const { nodes } = buildCanvasGraph([scene], [shotWithActions], { characterMap: defaultCharMap });
    const dsNode = nodes.find(n => n.type === 'directorStage3D');
    expect(dsNode).toBeDefined();

    const data = dsNode!.data as Record<string, unknown>;
    const actions = data.characterActions as Record<string, { expression?: string; action?: string; position?: string }>;
    expect(actions).toBeDefined();
    expect(actions['Alice'].action).toBe('走近窗边');
  });

  it('DirectorStage3D has undefined characterActions when shot has none', () => {
    const { nodes } = buildCanvasGraph([scene], [shot], { characterMap: defaultCharMap });
    const dsNode = nodes.find(n => n.type === 'directorStage3D');
    expect(dsNode).toBeDefined();

    const data = dsNode!.data as Record<string, unknown>;
    expect(data.characterActions).toBeUndefined();
  });
});


// ═══════════════════════════════════════════════════════════
// VideoGeneration node upstream metadata population
// ═══════════════════════════════════════════════════════════

describe('VideoGeneration node data population', () => {
  const charMap = {
    Alice: { name: 'Alice', appearance: {}, costume: {}, visualRefUrl: 'http://alice.jpg', visualRefStorageKey: 'refs/alice.jpg' },
    Bob: { name: 'Bob', appearance: {}, costume: {}, visualRefUrl: 'http://bob.jpg' },
  };

  const shotFull = {
    ...shot,
    framing: 'close-up',
    cameraAngle: 'low-angle',
    cameraMovement: 'dolly-in',
    description: 'Alice approaches Bob',
    dialogueText: 'Hello Bob',
    emotionTarget: 'surprise',
    charactersInFrame: ['Alice', 'Bob'],
    durationEstimate: '5s',
    characterActions: {
      Alice: { expression: '微笑', action: '走近', position: '画面左' },
    },
  };

  it('populates shot metadata on VideoGeneration node', () => {
    const { nodes } = buildCanvasGraph([scene], [shotFull], { characterMap: charMap });
    const vNode = nodes.find(n => n.type === 'videoGeneration');
    expect(vNode).toBeDefined();

    const d = vNode!.data as Record<string, unknown>;
    expect(d.shotDescription).toBe('Alice approaches Bob');
    expect(d.shotFraming).toBe('close-up');
    expect(d.shotCameraAngle).toBe('low-angle');
    expect(d.shotCameraMovement).toBe('dolly-in');
    expect(d.shotDialogue).toBe('Hello Bob');
    expect(d.shotEmotionTarget).toBe('surprise');
  });

  it('populates scene metadata on VideoGeneration node', () => {
    const { nodes } = buildCanvasGraph([scene], [shotFull], { characterMap: charMap });
    const d = nodes.find(n => n.type === 'videoGeneration')!.data as Record<string, unknown>;
    expect(d.sceneLocation).toBe('Grand Hall');
    expect(d.sceneTimeOfDay).toBe('day');
  });

  it('populates characterRefs with visualRefUrl and storageKey', () => {
    const { nodes } = buildCanvasGraph([scene], [shotFull], { characterMap: charMap });
    const d = nodes.find(n => n.type === 'videoGeneration')!.data as Record<string, unknown>;
    const cRefs = d.characterRefs as Array<{ name: string; visualRefUrl?: string; visualRefStorageKey?: string }>;
    expect(cRefs).toHaveLength(2);
    expect(cRefs[0].name).toBe('Alice');
    expect(cRefs[0].visualRefUrl).toBe('http://alice.jpg');
    expect(cRefs[0].visualRefStorageKey).toBe('refs/alice.jpg');
    expect(cRefs[1].name).toBe('Bob');
    expect(cRefs[1].visualRefUrl).toBe('http://bob.jpg');
  });

  it('populates durationSeconds and ratio', () => {
    const { nodes } = buildCanvasGraph([scene], [shotFull], { characterMap: charMap });
    const d = nodes.find(n => n.type === 'videoGeneration')!.data as Record<string, unknown>;
    expect(d.durationSeconds).toBe(5);
    expect(d.ratio).toBe('16:9');
  });

  it('populates shotCharactersInFrame and shotCharacterActions', () => {
    const { nodes } = buildCanvasGraph([scene], [shotFull], { characterMap: charMap });
    const d = nodes.find(n => n.type === 'videoGeneration')!.data as Record<string, unknown>;
    expect(d.shotCharactersInFrame).toEqual(['Alice', 'Bob']);
    const actions = d.shotCharacterActions as Record<string, unknown>;
    expect(actions).toBeDefined();
    expect(actions['Alice']).toEqual({ expression: '微笑', action: '走近', position: '画面左' });
  });
});

// ── NODE_WIDTHS: 4种卡片统一为 260px ──

describe('NODE_WIDTHS: pipeline cards at 300, characterProcess at 180', () => {
  const { nodes } = buildCanvasGraph([scene], [shot], { characterMap: defaultCharMap });

  it('directorStage3D node has width 300', () => {
    const n = nodes.find(n => n.type === 'directorStage3D');
    expect(n).toBeDefined();
    expect(n!.style).toEqual({ width: 300 });
  });

  it('geminiComposite node has width 300', () => {
    const n = nodes.find(n => n.type === 'geminiComposite');
    expect(n).toBeDefined();
    expect(n!.style).toEqual({ width: 300 });
  });

  it('finalHD node has width 300', () => {
    const n = nodes.find(n => n.type === 'finalHD');
    expect(n).toBeDefined();
    expect(n!.style).toEqual({ width: 300 });
  });

  it('videoGeneration node has width 300', () => {
    const n = nodes.find(n => n.type === 'videoGeneration');
    expect(n).toBeDefined();
    expect(n!.style).toEqual({ width: 300 });
  });

  it('characterProcess stays at 180', () => {
    const n = nodes.find(n => n.type === 'characterProcess');
    expect(n).toBeDefined();
    expect(n!.style).toEqual({ width: 180 });
  });
});

// ═══════════════════════════════════════════════════════════
// Merge Groups → VideoSegment node tests
// ═══════════════════════════════════════════════════════════

describe('mergeGroups: VideoSegment node creation', () => {
  const scene2 = { ...scene };
  const shot1 = { ...shot, id: 'shot1', shotNumber: 1, durationEstimate: '4s' };
  const shot2 = { ...shot, id: 'shot2', shotNumber: 2, durationEstimate: '3s' };
  const shot3 = { ...shot, id: 'shot3', shotNumber: 3, durationEstimate: '5s' };
  const opts = { characterMap: defaultCharMap };

  it('without mergeGroups, creates individual videoGeneration nodes', () => {
    const { nodes } = buildCanvasGraph([scene2], [shot1, shot2, shot3], opts);
    const videoNodes = nodes.filter(n => n.type === 'videoGeneration');
    const segmentNodes = nodes.filter(n => n.type === 'videoSegment');
    expect(videoNodes).toHaveLength(3);
    expect(segmentNodes).toHaveLength(0);
  });

  it('with mergeGroup for 2 shots, creates 1 videoSegment + 1 videoGeneration', () => {
    const { nodes, edges } = buildCanvasGraph([scene2], [shot1, shot2, shot3], {
      ...opts,
      mergeGroups: [{
        groupId: 'g1',
        shotIds: ['shot1', 'shot2'],
        totalDuration: 7,
        driftRisk: 'low',
        recommendedProvider: 'jimeng',
        mergeRationale: 'same scene, same characters',
      }],
    });

    const segmentNodes = nodes.filter(n => n.type === 'videoSegment');
    const videoNodes = nodes.filter(n => n.type === 'videoGeneration');
    expect(segmentNodes).toHaveLength(1);
    expect(videoNodes).toHaveLength(1); // shot3 only

    // Segment node has correct data
    const seg = segmentNodes[0];
    expect(seg.id).toBe('videoseg-g1');
    const d = seg.data as Record<string, unknown>;
    expect(d.nodeType).toBe('videoSegment');
    expect(d.shotGroupId).toBe('g1');
    expect(d.shotIds).toEqual(['shot1', 'shot2']);
    expect(d.totalDurationSeconds).toBe(7);
    expect(d.driftRisk).toBe('low');
    expect(d.recommendedProvider).toBe('jimeng');
    expect((d.shots as unknown[]).length).toBe(2);

    // Both FinalHD nodes connect to the segment node
    const segEdges = edges.filter(e => e.target === 'videoseg-g1');
    expect(segEdges).toHaveLength(2);
    expect(segEdges.map(e => e.source).sort()).toEqual(['finalhd-shot1', 'finalhd-shot2']);

    // Shot3 has normal video node
    expect(videoNodes[0].id).toBe('video-shot3');
  });

  it('single-shot mergeGroup degrades to videoGeneration', () => {
    const { nodes } = buildCanvasGraph([scene2], [shot1, shot2], {
      ...opts,
      mergeGroups: [{
        groupId: 'g-single',
        shotIds: ['shot1'],
        totalDuration: 4,
        driftRisk: 'low',
        recommendedProvider: 'jimeng',
      }],
    });

    const segmentNodes = nodes.filter(n => n.type === 'videoSegment');
    const videoNodes = nodes.filter(n => n.type === 'videoGeneration');
    expect(segmentNodes).toHaveLength(0); // single-shot group degrades
    expect(videoNodes).toHaveLength(2); // both shots get videoGeneration
  });

  it('all 3 shots merged → 1 segment, 0 videoGeneration', () => {
    const { nodes, edges } = buildCanvasGraph([scene2], [shot1, shot2, shot3], {
      ...opts,
      mergeGroups: [{
        groupId: 'g-all',
        shotIds: ['shot1', 'shot2', 'shot3'],
        totalDuration: 12,
        driftRisk: 'medium',
        recommendedProvider: 'kling',
      }],
    });

    const segmentNodes = nodes.filter(n => n.type === 'videoSegment');
    const videoNodes = nodes.filter(n => n.type === 'videoGeneration');
    expect(segmentNodes).toHaveLength(1);
    expect(videoNodes).toHaveLength(0);

    // All 3 FinalHD nodes connect to the segment
    const segEdges = edges.filter(e => e.target === 'videoseg-g-all');
    expect(segEdges).toHaveLength(3);
  });

  it('videoSegment node has width 300', () => {
    const { nodes } = buildCanvasGraph([scene2], [shot1, shot2], {
      ...opts,
      mergeGroups: [{
        groupId: 'gw',
        shotIds: ['shot1', 'shot2'],
        totalDuration: 7,
        driftRisk: 'low',
        recommendedProvider: 'jimeng',
      }],
    });

    const seg = nodes.find(n => n.type === 'videoSegment');
    expect(seg).toBeDefined();
    expect(seg!.style).toEqual({ width: 300 });
  });

  it('segment node includes sceneLocation and characterRefs', () => {
    const { nodes } = buildCanvasGraph([scene2], [shot1, shot2], {
      ...opts,
      mergeGroups: [{
        groupId: 'gc',
        shotIds: ['shot1', 'shot2'],
        totalDuration: 7,
        driftRisk: 'low',
        recommendedProvider: 'jimeng',
      }],
    });

    const d = nodes.find(n => n.type === 'videoSegment')!.data as Record<string, unknown>;
    expect(d.sceneLocation).toBe('Grand Hall');
    expect(d.sceneTimeOfDay).toBe('day');
    const cRefs = d.characterRefs as Array<{ name: string }>;
    expect(cRefs.length).toBeGreaterThan(0);
    expect(cRefs[0].name).toBe('Alice');
  });
});
