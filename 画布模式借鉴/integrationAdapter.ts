// ============================================================
// integrationAdapter.ts
// 与现有软件体系的接入适配器
// 
// 你的现有系统已完成：
// 1. 小说→剧本拆解（分镜级别）
// 2. 按场景分布的剧本结构
// 3. 角色/道具/场景图片资产库
// 4. 剧情线分析
// 5. 小说整体构架分析
//
// 这个适配器负责从你的现有系统读取上述数据，
// 并转化为无限画布所需的数据格式
// ============================================================

import { NodeData, ProjectAsset, Chapter, Scene, StoryboardChain, ModuleType } from '../types';
import { useCanvasStore } from '../store/canvasStore';
import { useProjectStore } from '../store/projectStore';
import { MODULE_TEMPLATES } from '../components/Modules/ModuleTemplates';

// ---------------------------
// 你现有系统的数据类型（根据实际情况调整）
// ---------------------------
export interface ExistingSystemData {
  // 来自分镜拆解模块的数据
  project: {
    id: string;
    name: string;
    novelTitle: string;
  };

  // 章节和场景结构（来自剧本拆解）
  chapters: Array<{
    id: string;
    title: string;
    order: number;
    plotLineId: string;
    scenes: Array<{
      id: string;
      title: string;
      order: number;
      rawScript: string;      // 原始剧本文本
      location: string;
      timeOfDay: string;
      mood: string;
      characterNames: string[];
      // 已拆解的初步分镜
      storyboards: Array<{
        id: string;
        text: string;
        order: number;
        characterNames: string[];
      }>;
    }>;
  }>;

  // 资产库（来自资产生成模块）
  assets: {
    characters: Array<{
      id: string;
      name: string;
      imageUrl: string;
      thumbnailUrl: string;
      description: string;
      appearance: string;   // 外貌描述
      personality: string;
    }>;
    scenes: Array<{
      id: string;
      name: string;
      imageUrl: string;
      thumbnailUrl: string;
      description: string;
      location: string;
    }>;
    props: Array<{
      id: string;
      name: string;
      imageUrl: string;
      thumbnailUrl: string;
      description: string;
      category: string;
    }>;
  };
}


// ============================================================
// 主接入函数：从你现有系统加载数据到无限画布
// ============================================================
export async function loadFromExistingSystem(
  projectId: string,
  fetchFn?: (url: string) => Promise<ExistingSystemData>
): Promise<void> {

  // 1. 获取现有系统数据（替换为你的实际API地址）
  const data: ExistingSystemData = fetchFn
    ? await fetchFn(`/api/projects/${projectId}/canvas-data`)
    : await fetch(`/api/projects/${projectId}/canvas-data`).then(r => r.json());

  // 2. 转换并加载到项目Store
  const projectAssets: ProjectAsset[] = [
    ...data.assets.characters.map(c => ({
      id: c.id,
      type: 'character' as const,
      name: c.name,
      imageUrl: c.imageUrl,
      thumbnailUrl: c.thumbnailUrl,
      description: c.description,
      tags: [c.appearance, c.personality].filter(Boolean),
      characterTraits: [c.personality],
    })),
    ...data.assets.scenes.map(s => ({
      id: s.id,
      type: 'scene' as const,
      name: s.name,
      imageUrl: s.imageUrl,
      thumbnailUrl: s.thumbnailUrl,
      description: s.description,
      tags: [s.location],
    })),
    ...data.assets.props.map(p => ({
      id: p.id,
      type: 'prop' as const,
      name: p.name,
      imageUrl: p.imageUrl,
      thumbnailUrl: p.thumbnailUrl,
      description: p.description,
      tags: [p.category],
      propCategory: p.category,
    })),
  ];

  const chapters: Chapter[] = data.chapters.map(ch => ({
    id: ch.id,
    title: ch.title,
    order: ch.order,
    plotLineId: ch.plotLineId,
    scenes: ch.scenes.map(s => s.id),
  }));

  const scenes: Scene[] = data.chapters.flatMap(ch =>
    ch.scenes.map(s => ({
      id: s.id,
      chapterId: ch.id,
      title: s.title,
      order: s.order,
      rawScript: s.rawScript,
      storyboards: s.storyboards.map(sb => sb.id),
      location: s.location,
      timeOfDay: s.timeOfDay,
      characterIds: s.characterNames.map(name =>
        data.assets.characters.find(c => c.name === name)?.id || name
      ),
      mood: s.mood,
    }))
  );

  useProjectStore.getState().loadProjectData({
    projectId: data.project.id,
    projectName: data.project.name,
    novelTitle: data.project.novelTitle,
    assets: projectAssets,
    chapters,
    scenes,
  });

  // 3. 将分镜转换为画布节点
  const canvasNodes: NodeData[] = [];
  const connections: Array<{ from: string; to: string }> = [];

  let layoutX = 60;
  let layoutY = 60;
  const SCENE_GAP_X = 600;
  const SCENE_GAP_Y = 400;
  const NODE_GAP_X = 180;

  data.chapters.forEach((chapter, ci) => {
    chapter.scenes.forEach((scene, si) => {
      scene.storyboards.forEach((sb, sbi) => {
        const characterIds = sb.characterNames.map(name =>
          data.assets.characters.find(c => c.name === name)?.id || name
        );
        const sceneAsset = data.assets.scenes.find(sa =>
          scene.location && sa.name.includes(scene.location)
        );

        const baseX = layoutX + si * SCENE_GAP_X;
        const baseY = layoutY + ci * SCENE_GAP_Y + sbi * 120;

        // 分镜节点
        const sbNodeId = sb.id;
        const sbNode: NodeData = {
          id: sbNodeId,
          type: 'storyboard',
          position: { x: baseX, y: baseY },
          size: { width: 185, height: 140 },
          status: 'idle',
          label: `分镜 ${ci + 1}-${sbi + 1}`,
          chapterId: chapter.id,
          sceneId: scene.id,
          upstreamIds: [],
          downstreamIds: [],
          createdAt: Date.now(),
          updatedAt: Date.now(),
          agentAssigned: false,
          content: {
            rawText: sb.text,
            imagePrompt: '',
            videoPrompt: '',
            characterIds,
            sceneAssetId: sceneAsset?.id,
            propIds: [],
            shotType: 'medium',
            emotion: scene.mood || '',
            duration: 5,
          },
        };

        // 图片合成节点
        const imgNodeId = `img_${sb.id}`;
        const imgNode: NodeData = {
          id: imgNodeId,
          type: 'image',
          position: { x: baseX + NODE_GAP_X, y: baseY },
          size: { width: 165, height: 140 },
          status: 'idle',
          label: `合成图 ${ci + 1}-${sbi + 1}`,
          chapterId: chapter.id,
          sceneId: scene.id,
          upstreamIds: [sbNodeId],
          downstreamIds: [],
          createdAt: Date.now(),
          updatedAt: Date.now(),
          agentAssigned: false,
          content: {
            workflowSteps: [],  // 由Agent分配模块后填充
            intermediateUrls: [],
            width: 1920,
            height: 1080,
            sourceStoryboardId: sbNodeId,
          },
        };

        // 视频生成节点
        const vidNodeId = `vid_${sb.id}`;
        const vidNode: NodeData = {
          id: vidNodeId,
          type: 'video',
          position: { x: baseX + NODE_GAP_X * 2, y: baseY },
          size: { width: 120, height: 140 },
          status: 'idle',
          label: `视频 ${ci + 1}-${sbi + 1}`,
          chapterId: chapter.id,
          sceneId: scene.id,
          upstreamIds: [imgNodeId],
          downstreamIds: [],
          createdAt: Date.now(),
          updatedAt: Date.now(),
          agentAssigned: false,
          content: {
            provider: 'jimeng',
            videoPrompt: '',
            duration: 5,
            fps: 24,
            resolution: '1080p',
            sourceImageId: imgNodeId,
          },
        };

        // 更新下游引用
        sbNode.downstreamIds = [imgNodeId];
        imgNode.downstreamIds = [vidNodeId];

        canvasNodes.push(sbNode, imgNode, vidNode);
        connections.push(
          { from: sbNodeId, to: imgNodeId },
          { from: imgNodeId, to: vidNodeId }
        );
      });
    });
  });

  // 4. 批量加载到画布Store
  const canvas = useCanvasStore.getState();
  canvas.addNodes(canvasNodes);
  connections.forEach(({ from, to }, i) => {
    canvas.addConnection({
      id: `conn_${i}`,
      fromNodeId: from,
      toNodeId: to,
      type: 'data-flow',
    });
  });

  // 5. 适配视图
  canvas.fitToContent();
}


// ============================================================
// 导出数据回现有系统（生成完成后的视频列表）
// ============================================================
export async function exportToExistingSystem(projectId: string): Promise<void> {
  const canvas = useCanvasStore.getState();
  const videoNodes = Array.from(canvas.nodes.values())
    .filter(n => n.type === 'video' && n.status === 'done');

  const exportData = videoNodes.map(n => ({
    nodeId: n.id,
    chapterId: n.chapterId,
    sceneId: n.sceneId,
    videoUrl: (n.content as any).resultVideoUrl,
    thumbnailUrl: (n.content as any).thumbnailUrl,
    duration: (n.content as any).duration,
  }));

  await fetch(`/api/projects/${projectId}/videos`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ videos: exportData }),
  });
}


// ============================================================
// 实时同步：当现有系统的分镜数据更新时，同步到画布
// ============================================================
export function watchExistingSystemUpdates(projectId: string): () => void {
  // 使用 WebSocket 或 SSE 监听上游数据变化
  const ws = new WebSocket(
    `${process.env.REACT_APP_WS_BASE_URL || 'ws://localhost:3001'}/projects/${projectId}/canvas-sync`
  );

  ws.onmessage = (event) => {
    const { type, payload } = JSON.parse(event.data);
    const canvas = useCanvasStore.getState();

    switch (type) {
      case 'storyboard-updated':
        // 分镜文本更新，标记下游为 outdated
        canvas.updateNodeContent(payload.storyboardId, { rawText: payload.newText });
        canvas.markDownstreamOutdated(payload.storyboardId);
        break;

      case 'asset-updated':
        // 资产库更新，提示用户相关节点可能需要重新生成
        useProjectStore.getState().addAsset(payload.asset);
        break;
    }
  };

  return () => ws.close();
}
