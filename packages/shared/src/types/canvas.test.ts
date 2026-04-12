/**
 * TDD tests for new canvas node types:
 * - DirectorStage3DNodeData
 * - GeminiCompositeNodeData
 * - SceneBGNodeData depth map fields
 */
import { describe, it, expect } from 'vitest';
import type {
  DirectorStage3DNodeData,
  GeminiCompositeNodeData,
  SceneBGNodeData,
  CanvasNodeData,
} from './canvas';

describe('DirectorStage3DNodeData', () => {
  const base: DirectorStage3DNodeData = {
    label: '3D导演台',
    status: 'idle',
    sceneId: 'scene-1',
    shotId: 'shot-1',
    nodeType: 'directorStage3D',
    progress: 0,
  };

  it('satisfies BaseNodeData constraints', () => {
    expect(base.label).toBe('3D导演台');
    expect(base.status).toBe('idle');
    expect(base.sceneId).toBe('scene-1');
    expect(base.nodeType).toBe('directorStage3D');
  });

  it('accepts optional panorama and depth map fields', () => {
    const withPanorama: DirectorStage3DNodeData = {
      ...base,
      panoramaUrl: 'https://example.com/vr.jpg',
      panoramaStorageKey: 'assets/vr/001.jpg',
      depthMapUrl: 'https://example.com/depth.png',
      depthMapStorageKey: 'assets/depth/001.png',
    };
    expect(withPanorama.panoramaUrl).toBe('https://example.com/vr.jpg');
    expect(withPanorama.depthMapUrl).toBe('https://example.com/depth.png');
  });

  it('accepts characterRefs array', () => {
    const withChars: DirectorStage3DNodeData = {
      ...base,
      characterRefs: [
        { characterName: '高令宁', visualRefUrl: 'https://ref.jpg', color: '#06b6d4' },
        { characterName: '林婉', visualRefUrl: 'https://ref2.jpg', color: '#f472b6' },
      ],
    };
    expect(withChars.characterRefs).toHaveLength(2);
    expect(withChars.characterRefs![0].characterName).toBe('高令宁');
  });

  it('accepts propRefs array', () => {
    const withProps: DirectorStage3DNodeData = {
      ...base,
      propRefs: [
        { propName: '古剑', visualRefUrl: 'https://prop.jpg' },
      ],
    };
    expect(withProps.propRefs).toHaveLength(1);
  });

  it('accepts screenshot output fields', () => {
    const withScreenshot: DirectorStage3DNodeData = {
      ...base,
      screenshotBase64: 'base64data...',
      screenshotStorageKey: 'assets/screenshots/001.jpg',
      characterScreenshots: [
        { stageCharId: 'char-0', stageCharName: '高令宁', color: '#06b6d4', screenshot: 'b64...' },
      ],
    };
    expect(withScreenshot.characterScreenshots).toHaveLength(1);
  });

  it('is included in CanvasNodeData union', () => {
    const node: CanvasNodeData = base;
    expect(node.nodeType).toBe('directorStage3D');
  });
});

describe('GeminiCompositeNodeData', () => {
  const base: GeminiCompositeNodeData = {
    label: 'Gemini合成',
    status: 'idle',
    sceneId: 'scene-1',
    shotId: 'shot-1',
    nodeType: 'geminiComposite',
    progress: 0,
  };

  it('satisfies BaseNodeData constraints', () => {
    expect(base.label).toBe('Gemini合成');
    expect(base.status).toBe('idle');
    expect(base.nodeType).toBe('geminiComposite');
  });

  it('accepts scene screenshot input', () => {
    const withInput: GeminiCompositeNodeData = {
      ...base,
      sceneScreenshotBase64: 'base64...',
      sceneScreenshotStorageKey: 'assets/screenshots/scene.jpg',
      sceneDescription: '黄昏时分的古宅大厅',
    };
    expect(withInput.sceneScreenshotBase64).toBe('base64...');
    expect(withInput.sceneDescription).toBe('黄昏时分的古宅大厅');
  });

  it('accepts character mappings', () => {
    const withMappings: GeminiCompositeNodeData = {
      ...base,
      characterMappings: [
        {
          stageCharId: 'char-0',
          stageCharName: '高令宁',
          color: '#06b6d4',
          poseScreenshot: 'b64pose...',
          referenceImageUrl: 'https://ref.jpg',
          referenceStorageKey: 'assets/ref/001.jpg',
        },
      ],
    };
    expect(withMappings.characterMappings).toHaveLength(1);
    expect(withMappings.characterMappings![0].poseScreenshot).toBe('b64pose...');
  });

  it('accepts output fields', () => {
    const withOutput: GeminiCompositeNodeData = {
      ...base,
      outputImageUrl: 'https://output.jpg',
      outputImageBase64: 'b64result...',
      outputStorageKey: 'assets/output/001.jpg',
    };
    expect(withOutput.outputImageUrl).toBe('https://output.jpg');
  });

  it('is included in CanvasNodeData union', () => {
    const node: CanvasNodeData = base;
    expect(node.nodeType).toBe('geminiComposite');
  });
});

describe('SceneBGNodeData depth map fields', () => {
  it('accepts depthMapUrl and depthMapStorageKey', () => {
    const sceneBG: SceneBGNodeData = {
      label: '场景背景',
      status: 'idle',
      sceneId: 'scene-1',
      nodeType: 'sceneBG',
      viewAngle: { yaw: 0, pitch: 0 },
      progress: 0,
      depthMapUrl: 'https://depth.png',
      depthMapStorageKey: 'assets/depth/001.png',
    };
    expect(sceneBG.depthMapUrl).toBe('https://depth.png');
    expect(sceneBG.depthMapStorageKey).toBe('assets/depth/001.png');
  });

  it('depth map fields are optional', () => {
    const sceneBG: SceneBGNodeData = {
      label: '场景背景',
      status: 'idle',
      sceneId: 'scene-1',
      nodeType: 'sceneBG',
      viewAngle: { yaw: 0, pitch: 0 },
      progress: 0,
    };
    expect(sceneBG.depthMapUrl).toBeUndefined();
    expect(sceneBG.depthMapStorageKey).toBeUndefined();
  });
});
