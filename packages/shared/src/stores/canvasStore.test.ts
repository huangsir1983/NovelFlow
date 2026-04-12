import { describe, it, expect, beforeEach } from 'vitest';
import { useCanvasStore } from './canvasStore';
import type { Node, Edge } from '@xyflow/react';

// Helper: create a DirectorStage3D node for testing
function makeStage3DNode(
  id: string,
  sceneId: string,
  overrides?: Record<string, unknown>,
): Node {
  return {
    id,
    type: 'directorStage3D',
    position: { x: 0, y: 0 },
    data: {
      nodeType: 'directorStage3D',
      label: '3D导演台',
      status: 'idle',
      sceneId,
      stageCharacters: [
        {
          id: 'char-0',
          name: '高令宁',
          x: -1,
          y: 0,
          z: 0.5,
          rotationY: 30,
          color: '#06b6d4',
          scale: 1.2,
          jointAngles: { head: { x: 10, y: 5, z: 0 } },
          presetName: 'sitting',
        },
        {
          id: 'char-1',
          name: '林婉',
          x: 2,
          y: 0,
          z: -0.5,
          rotationY: -15,
          color: '#f472b6',
          scale: 1,
          jointAngles: {},
          presetName: 'standing',
        },
      ],
      cameraState: {
        position: { x: 0.5, y: 1.2, z: 3.0 },
        fov: 60,
        target: { x: 0, y: 0.5, z: 0 },
      },
      screenshotBase64: 'OLD_SCREENSHOT',
      screenshotStorageKey: 'old/screenshot.jpg',
      characterScreenshots: [
        {
          stageCharId: 'char-0',
          stageCharName: '高令宁',
          color: '#06b6d4',
          screenshot: 'CHAR0_SCREENSHOT_BASE64',
          bbox: { left: 10, top: 20, width: 30, height: 60 },
        },
        {
          stageCharId: 'char-1',
          stageCharName: '林婉',
          color: '#f472b6',
          screenshot: 'CHAR1_SCREENSHOT_BASE64',
          bbox: { left: 50, top: 15, width: 25, height: 55 },
        },
      ],
      progress: 0,
      ...overrides,
    },
  };
}

function makeGeminiCompositeNode(id: string, sceneId: string): Node {
  return {
    id,
    type: 'geminiComposite',
    position: { x: 400, y: 0 },
    data: {
      nodeType: 'geminiComposite',
      label: 'Gemini合成',
      status: 'idle',
      sceneId,
      progress: 0,
    },
  };
}

function makeCharProcessNode(id: string, sceneId: string, charName: string, refUrl: string): Node {
  return {
    id,
    type: 'characterProcess',
    position: { x: -400, y: 0 },
    data: {
      nodeType: 'characterProcess',
      label: charName,
      status: 'idle',
      sceneId,
      characterName: charName,
      visualRefUrl: refUrl,
      visualRefStorageKey: `refs/${charName}.jpg`,
    },
  };
}

describe('DirectorStage3D copy/paste', () => {
  beforeEach(() => {
    // Reset store to clean state
    useCanvasStore.setState({
      nodes: [],
      edges: [],
      stage3DClipboard: null,
    });
  });

  it('copyStage3D stores stageCharacters and cameraState in clipboard', () => {
    const node = makeStage3DNode('node-1', 'scene-1');
    useCanvasStore.setState({ nodes: [node] });

    useCanvasStore.getState().copyStage3D('node-1');

    const clipboard = useCanvasStore.getState().stage3DClipboard;
    expect(clipboard).not.toBeNull();
    expect(clipboard!.stageCharacters).toHaveLength(2);
    expect(clipboard!.stageCharacters[0].name).toBe('高令宁');
    expect(clipboard!.stageCharacters[0].rotationY).toBe(30);
    expect(clipboard!.stageCharacters[0].jointAngles).toEqual({ head: { x: 10, y: 5, z: 0 } });
    expect(clipboard!.cameraState).toEqual({
      position: { x: 0.5, y: 1.2, z: 3.0 },
      fov: 60,
      target: { x: 0, y: 0.5, z: 0 },
    });
    expect(clipboard!.screenshotBase64).toBe('OLD_SCREENSHOT');
    expect(clipboard!.screenshotStorageKey).toBe('old/screenshot.jpg');
  });

  it('copyStage3D stores sceneId for validation', () => {
    const node = makeStage3DNode('node-1', 'scene-42');
    useCanvasStore.setState({ nodes: [node] });

    useCanvasStore.getState().copyStage3D('node-1');

    expect(useCanvasStore.getState().stage3DClipboard!.sceneId).toBe('scene-42');
  });

  it('pasteStage3D deep-copies data to target node with same sceneId', () => {
    const source = makeStage3DNode('node-1', 'scene-1');
    const target = makeStage3DNode('node-2', 'scene-1', {
      stageCharacters: [],
      cameraState: undefined,
      screenshotBase64: '',
    });
    useCanvasStore.setState({ nodes: [source, target] });

    useCanvasStore.getState().copyStage3D('node-1');
    const result = useCanvasStore.getState().pasteStage3D('node-2');

    expect(result).toBe(true);
    const targetData = useCanvasStore.getState().nodes.find(n => n.id === 'node-2')!.data as Record<string, unknown>;
    const chars = targetData.stageCharacters as Array<Record<string, unknown>>;
    expect(chars).toHaveLength(2);
    expect(chars[0].name).toBe('高令宁');
    expect(chars[0].rotationY).toBe(30);
    expect((targetData.cameraState as Record<string, unknown>)).toEqual({
      position: { x: 0.5, y: 1.2, z: 3.0 },
      fov: 60,
      target: { x: 0, y: 0.5, z: 0 },
    });
  });

  it('pasteStage3D rejects target node with different sceneId', () => {
    const source = makeStage3DNode('node-1', 'scene-1');
    const target = makeStage3DNode('node-2', 'scene-2', { stageCharacters: [] });
    useCanvasStore.setState({ nodes: [source, target] });

    useCanvasStore.getState().copyStage3D('node-1');
    const result = useCanvasStore.getState().pasteStage3D('node-2');

    expect(result).toBe(false);
    // Target should be unchanged
    const targetChars = (useCanvasStore.getState().nodes.find(n => n.id === 'node-2')!.data as Record<string, unknown>).stageCharacters;
    expect(targetChars).toEqual([]);
  });

  it('pasteStage3D does nothing when clipboard is empty', () => {
    const target = makeStage3DNode('node-2', 'scene-1');
    useCanvasStore.setState({ nodes: [target] });

    const result = useCanvasStore.getState().pasteStage3D('node-2');

    expect(result).toBe(false);
  });

  it('pasted data is independent (modifying target does not affect clipboard)', () => {
    const source = makeStage3DNode('node-1', 'scene-1');
    const target = makeStage3DNode('node-2', 'scene-1', { stageCharacters: [] });
    useCanvasStore.setState({ nodes: [source, target] });

    useCanvasStore.getState().copyStage3D('node-1');
    useCanvasStore.getState().pasteStage3D('node-2');

    // Mutate the pasted data
    const targetData = useCanvasStore.getState().nodes.find(n => n.id === 'node-2')!.data as Record<string, unknown>;
    const pastedChars = targetData.stageCharacters as Array<Record<string, unknown>>;
    pastedChars[0].name = 'MUTATED';

    // Clipboard should be unaffected
    const clipboard = useCanvasStore.getState().stage3DClipboard!;
    expect(clipboard.stageCharacters[0].name).toBe('高令宁');
  });

  it('pasteStage3D copies source screenshot to target as preview', () => {
    const source = makeStage3DNode('node-1', 'scene-1');
    const target = makeStage3DNode('node-2', 'scene-1', {
      screenshotBase64: 'TARGET_OLD_BASE64',
      screenshotStorageKey: 'target/old/path.jpg',
    });
    useCanvasStore.setState({ nodes: [source, target] });

    useCanvasStore.getState().copyStage3D('node-1');
    useCanvasStore.getState().pasteStage3D('node-2');

    const targetData = useCanvasStore.getState().nodes.find(n => n.id === 'node-2')!.data as Record<string, unknown>;
    // Should have source's screenshot, not target's old one
    expect(targetData.screenshotBase64).toBe('OLD_SCREENSHOT');
    expect(targetData.screenshotStorageKey).toBe('old/screenshot.jpg');
  });

  it('pasteStage3D propagates screenshot data to downstream GeminiComposite node', () => {
    const source = makeStage3DNode('node-1', 'scene-1');
    const target = makeStage3DNode('node-2', 'scene-1', {
      stageCharacters: [],
      characterScreenshots: undefined,
      screenshotBase64: undefined,
    });
    const gemini = makeGeminiCompositeNode('gemini-2', 'scene-1');
    const cp1 = makeCharProcessNode('cp-1', 'scene-1', '高令宁', 'http://ref/gaolingning.jpg');
    const cp2 = makeCharProcessNode('cp-2', 'scene-1', '林婉', 'http://ref/linwan.jpg');

    const edges: Edge[] = [
      { id: 'e-cp1-target', source: 'cp-1', target: 'node-2' },
      { id: 'e-cp2-target', source: 'cp-2', target: 'node-2' },
      { id: 'e-target-gemini', source: 'node-2', target: 'gemini-2' },
    ];
    useCanvasStore.setState({ nodes: [source, target, gemini, cp1, cp2], edges });

    useCanvasStore.getState().copyStage3D('node-1');
    useCanvasStore.getState().pasteStage3D('node-2');

    // GeminiComposite should have received the scene screenshot
    const geminiData = useCanvasStore.getState().nodes.find(n => n.id === 'gemini-2')!.data as Record<string, unknown>;
    expect(geminiData.sceneScreenshotBase64).toBe('OLD_SCREENSHOT');

    // characterMappings should have been built
    const mappings = geminiData.characterMappings as Array<Record<string, unknown>>;
    expect(mappings).toHaveLength(2);
    expect(mappings[0].stageCharName).toBe('高令宁');
    expect(mappings[0].poseScreenshot).toBe('CHAR0_SCREENSHOT_BASE64');
    expect(mappings[0].referenceImageUrl).toBe('http://ref/gaolingning.jpg');
    expect(mappings[1].stageCharName).toBe('林婉');
    expect(mappings[1].poseScreenshot).toBe('CHAR1_SCREENSHOT_BASE64');
    expect(mappings[1].referenceImageUrl).toBe('http://ref/linwan.jpg');
  });
});
