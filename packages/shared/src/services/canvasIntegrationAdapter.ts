// ══════════════════════════════════════════════════════════════
// canvasIntegrationAdapter.ts — 现有系统 ↔ 无限画布 数据适配
//
// 将现有项目数据（Scene/Shot/Character/Location）
// 转换为画布节点并加载，以及将画布结果回写到项目。
// ══════════════════════════════════════════════════════════════

import { useInfiniteCanvasStore } from '../stores/infiniteCanvasStore';
import { useCanvasProjectStore } from '../stores/canvasProjectStore';
import type {
  CanvasNodeData,
  CanvasProjectAsset,
  CanvasChapter,
  CanvasScene,
  StoryboardContent,
  ImageContent,
  VideoContent,
} from '../types/canvas';
import type { Scene, Shot, Character, Location, Prop, Chapter } from '../types/project';

// ── 常量 ──

const NODE_GAP_X = 200;
const SCENE_GAP_Y = 160;
const CHAPTER_GAP_Y = 400;

// ══════════════════════════════════════════════════════════════
// 从现有系统加载数据到无限画布
// ══════════════════════════════════════════════════════════════

interface ProjectDataForCanvas {
  projectId: string;
  projectName: string;
  chapters: Chapter[];
  scenes: Scene[];
  shots: Shot[];
  characters: Character[];
  locations: Location[];
  props: Prop[];
}

export function loadProjectToCanvas(data: ProjectDataForCanvas): void {
  const canvasStore = useInfiniteCanvasStore.getState();
  const projectStore = useCanvasProjectStore.getState();

  // 1. 重置画布
  canvasStore.reset();
  projectStore.reset();

  // 2. 转换资产
  const assets: CanvasProjectAsset[] = [
    ...data.characters.map((c): CanvasProjectAsset => ({
      id: c.id,
      type: 'character',
      name: c.name,
      imageUrl: c.visual_reference || '',
      thumbnailUrl: c.visual_reference || '',
      description: c.description,
      tags: [
        c.appearance?.face,
        c.appearance?.hair,
        c.appearance?.body,
        c.appearance?.distinguishing_features,
        ...(c.casting_tags || []),
      ].filter(Boolean) as string[],
      characterTraits: [c.personality],
    })),
    ...data.locations.map((l): CanvasProjectAsset => ({
      id: l.id,
      type: 'scene',
      name: l.name,
      imageUrl: l.visual_reference || '',
      thumbnailUrl: l.visual_reference || '',
      description: l.visual_description || l.description,
      tags: [l.type, l.era_style, l.mood].filter(Boolean) as string[],
    })),
    ...data.props.map((p): CanvasProjectAsset => ({
      id: p.id,
      type: 'prop',
      name: p.name,
      imageUrl: p.visual_reference || '',
      thumbnailUrl: p.visual_reference || '',
      description: p.description,
      tags: [p.category],
      propCategory: p.category,
    })),
  ];

  // 3. 转换章节和场景
  const canvasChapters: CanvasChapter[] = data.chapters.map((ch) => ({
    id: ch.id,
    title: ch.title,
    order: ch.order,
    scenes: data.scenes.filter((s) => s.project_id === data.projectId).map((s) => s.id),
    plotLineId: '',
  }));

  const canvasScenes: CanvasScene[] = data.scenes.map((s) => ({
    id: s.id,
    chapterId: s.beat_id || data.chapters[0]?.id || '',
    title: s.heading,
    order: s.order,
    rawScript: s.description + '\n' + s.action,
    storyboards: data.shots.filter((sh) => sh.scene_id === s.id).map((sh) => sh.id),
    location: s.location,
    timeOfDay: s.time_of_day,
    characterIds: s.characters_present || [],
    mood: s.emotional_peak || '',
  }));

  // 4. 加载项目数据
  projectStore.loadProjectData({
    projectId: data.projectId,
    projectName: data.projectName,
    novelTitle: data.projectName,
    assets,
    chapters: canvasChapters,
    scenes: canvasScenes,
  });

  // 5. 创建画布节点
  const canvasNodes: CanvasNodeData[] = [];
  const connections: Array<{ from: string; to: string }> = [];

  let layoutX = 60;
  let layoutY = 60;

  // 按场景分组创建节点
  data.scenes.forEach((scene, sceneIdx) => {
    const sceneShots = data.shots
      .filter((sh) => sh.scene_id === scene.id)
      .sort((a, b) => a.order - b.order);

    sceneShots.forEach((shot, shotIdx) => {
      const baseX = layoutX + shotIdx * NODE_GAP_X * 3;
      const baseY = layoutY + sceneIdx * SCENE_GAP_Y;

      const characterIds = (shot.characters_in_frame || []).map((name) => {
        const char = data.characters.find((c) => c.name === name);
        return char?.id || name;
      });

      const locationAsset = data.locations.find((l) =>
        scene.location && l.name.includes(scene.location),
      );

      // 分镜节点
      const sbNodeId = shot.id;
      const sbNode: CanvasNodeData = {
        id: sbNodeId,
        type: 'storyboard',
        position: { x: baseX, y: baseY },
        size: { width: 185, height: 140 },
        status: 'idle',
        label: `分镜 ${sceneIdx + 1}-${shotIdx + 1}`,
        chapterId: scene.beat_id || data.chapters[0]?.id || '',
        sceneId: scene.id,
        upstreamIds: [],
        downstreamIds: [],
        createdAt: Date.now(),
        updatedAt: Date.now(),
        agentAssigned: false,
        content: {
          rawText: shot.description || shot.goal || '',
          imagePrompt: shot.visual_prompt || '',
          videoPrompt: '',
          characterIds,
          sceneAssetId: locationAsset?.id,
          propIds: [],
          shotType: mapFramingToShotType(shot.framing),
          emotion: shot.emotion_target || '',
          duration: parseDuration(shot.duration_estimate),
        } as StoryboardContent,
      };

      // 图片合成节点
      const imgNodeId = `img_${shot.id}`;
      const imgNode: CanvasNodeData = {
        id: imgNodeId,
        type: 'image',
        position: { x: baseX + NODE_GAP_X, y: baseY },
        size: { width: 165, height: 140 },
        status: 'idle',
        label: `合成图 ${sceneIdx + 1}-${shotIdx + 1}`,
        chapterId: scene.beat_id || data.chapters[0]?.id || '',
        sceneId: scene.id,
        upstreamIds: [sbNodeId],
        downstreamIds: [],
        createdAt: Date.now(),
        updatedAt: Date.now(),
        agentAssigned: false,
        content: {
          workflowSteps: [],
          intermediateUrls: [],
          width: 1920,
          height: 1080,
          sourceStoryboardId: sbNodeId,
        } as ImageContent,
      };

      // 视频生成节点
      const vidNodeId = `vid_${shot.id}`;
      const vidNode: CanvasNodeData = {
        id: vidNodeId,
        type: 'video',
        position: { x: baseX + NODE_GAP_X * 2, y: baseY },
        size: { width: 120, height: 140 },
        status: 'idle',
        label: `视频 ${sceneIdx + 1}-${shotIdx + 1}`,
        chapterId: scene.beat_id || data.chapters[0]?.id || '',
        sceneId: scene.id,
        upstreamIds: [imgNodeId],
        downstreamIds: [],
        createdAt: Date.now(),
        updatedAt: Date.now(),
        agentAssigned: false,
        content: {
          provider: 'jimeng',
          videoPrompt: '',
          duration: parseDuration(shot.duration_estimate),
          fps: 24,
          resolution: '1080p',
          sourceImageId: imgNodeId,
        } as VideoContent,
      };

      sbNode.downstreamIds = [imgNodeId];
      imgNode.downstreamIds = [vidNodeId];

      canvasNodes.push(sbNode, imgNode, vidNode);
      connections.push(
        { from: sbNodeId, to: imgNodeId },
        { from: imgNodeId, to: vidNodeId },
      );
    });
  });

  // 6. 加载到画布
  canvasStore.addNodes(canvasNodes);
  connections.forEach(({ from, to }, i) => {
    canvasStore.addConnection({
      id: `conn_${i}`,
      fromNodeId: from,
      toNodeId: to,
      type: 'data-flow',
    });
  });

  // 7. 自适应视图
  canvasStore.fitToContent();
}

// ══════════════════════════════════════════════════════════════
// 将画布结果回写到项目（更新 Shot 的 visual_prompt 等字段）
// ══════════════════════════════════════════════════════════════

export interface CanvasWriteBackResult {
  shotId: string;
  imagePrompt: string;
  videoPrompt: string;
  shotType: string;
  emotion: string;
  duration: number;
  generatedImageUrl?: string;
  generatedVideoUrl?: string;
}

export function extractWriteBackResults(): CanvasWriteBackResult[] {
  const nodes = useInfiniteCanvasStore.getState().nodes;
  const results: CanvasWriteBackResult[] = [];

  nodes.forEach((node) => {
    if (node.type !== 'storyboard') return;
    const content = node.content as StoryboardContent;
    if (!content.imagePrompt && !content.videoPrompt) return;

    // 找到下游图片和视频节点
    const imgNode = node.downstreamIds
      .map((id) => nodes.get(id))
      .find((n) => n?.type === 'image');
    const vidNode = imgNode?.downstreamIds
      .map((id) => nodes.get(id))
      .find((n) => n?.type === 'video');

    results.push({
      shotId: node.id,
      imagePrompt: content.imagePrompt,
      videoPrompt: content.videoPrompt,
      shotType: content.shotType,
      emotion: content.emotion,
      duration: content.duration,
      generatedImageUrl: imgNode ? (imgNode.content as ImageContent).resultImageUrl : undefined,
      generatedVideoUrl: vidNode ? (vidNode.content as VideoContent).resultVideoUrl : undefined,
    });
  });

  return results;
}

// ── 工具函数 ──

function mapFramingToShotType(framing: string): StoryboardContent['shotType'] {
  const map: Record<string, StoryboardContent['shotType']> = {
    ECU: 'close-up', CU: 'close-up', MCU: 'close-up',
    MS: 'medium', MLS: 'medium',
    FS: 'wide', WS: 'wide',
  };
  return map[framing] || 'medium';
}

function parseDuration(estimate: string): number {
  if (!estimate) return 5;
  const match = estimate.match(/(\d+)/);
  return match ? parseInt(match[1], 10) : 5;
}
