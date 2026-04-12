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

describe('Expression node receives character reference image as input', () => {
  const charMapWithRef = {
    Alice: {
      name: 'Alice',
      appearance: {},
      costume: {},
      visualRefUrl: 'http://test/alice-ref.png',
      visualRefStorageKey: 'assets/characters/alice-ref.png',
    },
  };

  it('should set inputImageUrl and inputStorageKey from charRef on Expression node', () => {
    const { nodes } = buildCanvasGraph([scene], [shot], { characterMap: charMapWithRef });
    const exNode = nodes.find(n => n.id === 'imgproc-expression-shot1-Alice');
    expect(exNode).toBeDefined();

    const data = exNode!.data as Record<string, unknown>;
    expect(data.inputImageUrl).toBe('http://test/alice-ref.png');
    expect(data.inputStorageKey).toBe('assets/characters/alice-ref.png');
  });

  it('should leave inputImageUrl undefined when charRef has no visualRefUrl', () => {
    const { nodes } = buildCanvasGraph([scene], [shot], { characterMap: defaultCharMap });
    const exNode = nodes.find(n => n.id === 'imgproc-expression-shot1-Alice');
    const data = exNode!.data as Record<string, unknown>;
    expect(data.inputImageUrl).toBeUndefined();
    expect(data.inputStorageKey).toBeUndefined();
  });
});

describe('ViewAngle node removal — CharacterProcess connects directly to Expression', () => {
  const opts = { characterMap: defaultCharMap };

  it('should NOT contain any viewAngle imageProcess node', () => {
    const { nodes } = buildCanvasGraph([scene], [shot], opts);
    const viewAngleNodes = nodes.filter(
      n => (n.data as Record<string, unknown>).processType === 'viewAngle',
    );
    expect(viewAngleNodes).toHaveLength(0);
  });

  it('should have a direct edge from CharacterProcess to Expression', () => {
    const { edges } = buildCanvasGraph([scene], [shot], opts);
    const cpToEx = edges.find(
      e => e.source === `charproc-shot1-Alice` && e.target === `imgproc-expression-shot1-Alice`,
    );
    expect(cpToEx).toBeDefined();
    expect(cpToEx!.type).toBe('pipeline');
  });

  it('should NOT have any edge involving a viewAngle node id', () => {
    const { edges } = buildCanvasGraph([scene], [shot], opts);
    const viewAngleEdges = edges.filter(
      e => e.source.includes('viewangle') || e.target.includes('viewangle'),
    );
    expect(viewAngleEdges).toHaveLength(0);
  });

  it('should NOT have a bypass edge from viewAngle to pose3D', () => {
    const { edges } = buildCanvasGraph([scene], [shot], opts);
    const vaToP3d = edges.filter(
      e => e.source.startsWith('imgproc-viewAngle-') && e.target.startsWith('pose3d-'),
    );
    expect(vaToP3d).toHaveLength(0);
  });

  it('should still have Pose3D node for each character', () => {
    const { nodes } = buildCanvasGraph([scene], [shot], opts);
    const pose3d = nodes.find(n => n.id === `pose3d-shot1-Alice`);
    expect(pose3d).toBeDefined();
    expect((pose3d!.data as Record<string, unknown>).nodeType).toBe('pose3D');
  });

  it('should still have Pose3D → Expression bypass edge', () => {
    const { edges } = buildCanvasGraph([scene], [shot], opts);
    const p3dToEx = edges.find(
      e => e.source === `pose3d-shot1-Alice` && e.target === `imgproc-expression-shot1-Alice`,
    );
    expect(p3dToEx).toBeDefined();
    expect(p3dToEx!.type).toBe('bypass');
  });
});

describe('Post-composite: BlendRefine replaced by Expression (Gemini)', () => {
  const opts = { characterMap: defaultCharMap };

  it('should NOT contain any blendRefine node', () => {
    const { nodes } = buildCanvasGraph([scene], [shot], opts);
    const brNodes = nodes.filter(n => n.type === 'blendRefine');
    expect(brNodes).toHaveLength(0);
  });

  it('should contain a post-composite expression imageProcess node', () => {
    const { nodes } = buildCanvasGraph([scene], [shot], opts);
    const peNode = nodes.find(n => n.id === 'imgproc-expression-shot1-scene');
    expect(peNode).toBeDefined();
    expect(peNode!.type).toBe('imageProcess');
    const data = peNode!.data as Record<string, unknown>;
    expect(data.nodeType).toBe('imageProcess');
    expect(data.processType).toBe('expression');
  });

  it('should have Composite → post-composite expression pipeline edge', () => {
    const { edges } = buildCanvasGraph([scene], [shot], opts);
    const edge = edges.find(
      e => e.source === 'composite-shot1' && e.target === 'imgproc-expression-shot1-scene',
    );
    expect(edge).toBeDefined();
    expect(edge!.type).toBe('pipeline');
  });

  it('should have post-composite expression → Lighting pipeline edge', () => {
    const { edges } = buildCanvasGraph([scene], [shot], opts);
    const edge = edges.find(
      e => e.source === 'imgproc-expression-shot1-scene' && e.target === 'lighting-shot1',
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

  it('should have a default expressionPrompt on post-composite expression node', () => {
    const { nodes } = buildCanvasGraph([scene], [shot], opts);
    const peNode = nodes.find(n => n.id === 'imgproc-expression-shot1-scene');
    const data = peNode!.data as Record<string, unknown>;
    expect(data.expressionPrompt).toBeTruthy();
  });
});

describe('Character HDUpscale removal — Expression connects directly to Matting', () => {
  const opts = { characterMap: defaultCharMap };

  it('should NOT contain any character hdUpscale node', () => {
    const { nodes } = buildCanvasGraph([scene], [shot], opts);
    const charHdNodes = nodes.filter(
      n =>
        (n.data as Record<string, unknown>).processType === 'hdUpscale' &&
        !n.id.endsWith('-bg'),
    );
    expect(charHdNodes).toHaveLength(0);
  });

  it('should have a direct edge from Expression to Matting', () => {
    const { edges } = buildCanvasGraph([scene], [shot], opts);
    const exToMt = edges.find(
      e =>
        e.source === `imgproc-expression-shot1-Alice` &&
        e.target === `imgproc-matting-shot1-Alice`,
    );
    expect(exToMt).toBeDefined();
    expect(exToMt!.type).toBe('pipeline');
  });

  it('should NOT have Expression→hdUpscale or hdUpscale→Matting edges', () => {
    const { edges } = buildCanvasGraph([scene], [shot], opts);
    const hdEdges = edges.filter(
      e =>
        (e.source.includes('hdUpscale') || e.target.includes('hdUpscale')) &&
        !e.source.endsWith('-bg') &&
        !e.target.endsWith('-bg'),
    );
    expect(hdEdges).toHaveLength(0);
  });

  it('should still have Matting node for each character', () => {
    const { nodes } = buildCanvasGraph([scene], [shot], opts);
    const mt = nodes.find(n => n.id === `imgproc-matting-shot1-Alice`);
    expect(mt).toBeDefined();
    expect((mt!.data as Record<string, unknown>).processType).toBe('matting');
  });
});
