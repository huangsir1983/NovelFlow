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
      characterMap: {
        Alice: {
          name: 'Alice',
          appearance: {},
          costume: {},
          visualRefUrl: undefined,
          visualRefStorageKey: undefined,
        },
      },
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
      characterMap: {
        Alice: {
          name: 'Alice',
          appearance: {},
          costume: {},
          visualRefUrl: undefined,
          visualRefStorageKey: undefined,
        },
      },
    });

    const sceneBGNode = nodes.find(n => n.type === 'sceneBG');
    expect(sceneBGNode).toBeDefined();

    const data = sceneBGNode!.data as Record<string, unknown>;
    expect(data.viewpoints).toEqual([]);
    expect(data.activeViewpointId).toBeUndefined();
    expect(data.panoramaUrl).toBe('http://test/panorama.jpg');
  });
});
