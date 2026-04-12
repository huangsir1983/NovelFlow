import { describe, it, expect } from 'vitest';
import { buildCanvasGraph } from './canvasLayout';
import type { ViewPoint } from '../types/canvas';

const scene = {
  id: 's1',
  heading: 'Scene 1',
  location: 'Grand Hall',
  timeOfDay: 'day',
  mood: '',
  summary: '',
  characters: ['Alice'],
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
  const twoCharScene = { ...scene, characters: ['Alice', 'Bob'] };
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
    characters: ['Alice', 'Bob'],
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
