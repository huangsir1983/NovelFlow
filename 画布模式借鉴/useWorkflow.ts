// ============================================================
// useWorkflow.ts - 工作流Hook（核心业务逻辑）
// ============================================================
import { useCallback } from 'react';
import { useCanvasStore } from '../store/canvasStore';
import { useAgentStore } from '../store/projectStore';
import { useProjectStore } from '../store/projectStore';
import { claudeAgent } from '../services/claudeAgent';
import { workflowEngine } from '../services/workflowEngine';
import { NodeData, ModuleType, StoryboardChain } from '../types';
import { MODULE_TEMPLATES, detectModuleType } from '../components/Modules/ModuleTemplates';

export function useWorkflow() {
  const canvas = useCanvasStore();
  const agent = useAgentStore();
  const project = useProjectStore();

  // ---------------------------
  // 执行单个节点
  // ---------------------------
  const runNode = useCallback(async (nodeId: string) => {
    const node = canvas.getNode(nodeId);
    if (!node) return;

    canvas.updateNodeStatus(nodeId, 'processing');

    try {
      if (node.type === 'storyboard') {
        // 分镜节点：由Agent生成提示词
        const taskId = agent.enqueueTask('analyze-storyboard', { nodeId }, nodeId);
        await claudeAgent.analyzeStoryboard(node, {
          assets: Array.from(useProjectStore.getState().assets.values()),
          onProgress: (content) => {
            canvas.updateNodeContent(nodeId, content);
          },
          onComplete: () => {
            canvas.updateNodeStatus(nodeId, 'done');
            // 触发下游就绪检查
            node.downstreamIds.forEach(id => {
              const down = canvas.getNode(id);
              if (down && down.upstreamIds.every(upId => canvas.getNode(upId)?.status === 'done')) {
                canvas.updateNodeStatus(id, 'ready');
              }
            });
          },
        });
        agent.updateTask(taskId, { status: 'done' });

      } else if (node.type === 'image') {
        // 图片节点：执行工作流步骤
        await workflowEngine.runImageWorkflow(node, {
          onStepUpdate: (stepId, status) => {
            canvas.updateNodeContent(nodeId, {
              workflowSteps: (node.content as any).workflowSteps.map((s: any) =>
                s.id === stepId ? { ...s, status } : s
              ),
            });
          },
          onComplete: (resultUrl) => {
            canvas.updateNodeContent(nodeId, { resultImageUrl: resultUrl });
            canvas.updateNodeStatus(nodeId, 'done');
          },
        });

      } else if (node.type === 'video') {
        // 视频节点：调用视频平台API
        await workflowEngine.runVideoGeneration(node, {
          onJobCreated: (jobId) => {
            canvas.updateNodeContent(nodeId, { jobId });
          },
          onComplete: (videoUrl, thumbnailUrl) => {
            canvas.updateNodeContent(nodeId, { resultVideoUrl: videoUrl, thumbnailUrl });
            canvas.updateNodeStatus(nodeId, 'done');
          },
        });
      }
    } catch (err) {
      console.error('Node execution failed:', err);
      canvas.updateNodeStatus(nodeId, 'error');
    }
  }, [canvas, agent]);

  // ---------------------------
  // Agent 自动为所有分镜节点分配模块类型
  // ---------------------------
  const runAgentAssign = useCallback(async () => {
    const storyboardNodes = Array.from(canvas.nodes.values())
      .filter(n => n.type === 'storyboard' && !n.moduleType);

    if (storyboardNodes.length === 0) return;

    canvas.setRunning(true);

    try {
      // 1. 先用本地关键词快速分配
      storyboardNodes.forEach(node => {
        const content = node.content as any;
        const guessed = detectModuleType(content.rawText || '');
        if (guessed) {
          canvas.updateNode(node.id, { moduleType: guessed });
        }
      });

      // 2. 对不确定的，发给Claude精确分析
      const uncertain = storyboardNodes.filter(n => !n.moduleType);
      if (uncertain.length > 0) {
        const taskId = agent.enqueueTask('batch-analyze-chapter', {
          nodeIds: uncertain.map(n => n.id),
        });
        const assignments = await claudeAgent.batchAssignModules(uncertain);
        assignments.forEach(({ nodeId, moduleType }) => {
          canvas.updateNode(nodeId, { moduleType, agentAssigned: true });
        });
        agent.updateTask(taskId, { status: 'done' });
      }

      // 3. 按章节+模块类型，自动将节点归入模块区域
      await autoOrganizeModules();

    } finally {
      canvas.setRunning(false);
    }
  }, [canvas, agent]);

  // ---------------------------
  // 批量执行（按依赖顺序，并行执行无依赖关系的节点）
  // ---------------------------
  const runBatch = useCallback(async () => {
    const allNodes = Array.from(canvas.nodes.values());
    const readyNodes = allNodes.filter(n => n.status === 'ready' || n.status === 'outdated');

    if (readyNodes.length === 0) return;

    canvas.setRunning(true);

    try {
      // 构建执行计划：拓扑排序 + 并行分组
      const plan = buildExecutionPlan(readyNodes, canvas.nodes);
      useProjectStore.getState().setExecutionPlan(plan);

      for (const group of plan.parallelGroups) {
        // 同一组可并行执行
        await Promise.all(group.map(nodeId => runNode(nodeId)));
      }
    } finally {
      canvas.setRunning(false);
      useProjectStore.getState().setExecutionPlan(null);
    }
  }, [canvas, runNode]);

  // ---------------------------
  // 编辑节点提示词
  // ---------------------------
  const editPrompt = useCallback((nodeId: string) => {
    const node = canvas.getNode(nodeId);
    if (!node || node.type !== 'storyboard') return;
    // 触发提示词编辑器（由父组件的modal系统处理）
    window.dispatchEvent(new CustomEvent('canvas:edit-prompt', { detail: { nodeId } }));
  }, [canvas]);

  // ---------------------------
  // 查看分镜链
  // ---------------------------
  const viewChain = useCallback((nodeId: string) => {
    const node = canvas.getNode(nodeId);
    if (!node) return;
    const rootId = node.type === 'storyboard' ? nodeId : node.upstreamIds[0] || nodeId;
    const chainNodes = canvas.getChainNodes(rootId);
    window.dispatchEvent(new CustomEvent('canvas:view-chain', { detail: { chainNodes } }));
  }, [canvas]);

  // ---------------------------
  // 自动组织模块区域
  // ---------------------------
  const autoOrganizeModules = useCallback(async () => {
    const nodes = Array.from(canvas.nodes.values()).filter(n => n.type === 'storyboard' && n.moduleType);

    // 按章节+模块类型分组
    const groups = new Map<string, NodeData[]>();
    nodes.forEach(node => {
      const key = `${node.chapterId}__${node.moduleType}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(node);
    });

    let moduleX = 40;
    let moduleY = 40;
    let rowHeight = 0;

    groups.forEach((groupNodes, key) => {
      const [chapterId, moduleType] = key.split('__');
      const template = MODULE_TEMPLATES[moduleType as ModuleType];
      if (!template) return;

      // 计算包围盒
      const existingModule = Array.from(canvas.modules.values())
        .find(m => m.chapterId === chapterId && m.type === moduleType as ModuleType);

      if (!existingModule) {
        const moduleId = `mod_${key}`;
        const modW = 560;
        const modH = 320;

        canvas.addModule({
          id: moduleId,
          type: moduleType as ModuleType,
          label: `${template.label} · ${chapterId}`,
          chapterId,
          position: { x: moduleX, y: moduleY },
          size: { width: modW, height: modH },
          nodeIds: groupNodes.map(n => n.id),
          collapsed: false,
          color: template.color,
          progress: { done: 0, total: groupNodes.length * 3 }, // storyboard + image + video
        });

        // 在模块内自动布局节点
        groupNodes.forEach((node, i) => {
          canvas.moveNode(node.id, {
            x: moduleX + 20 + i * 0,
            y: moduleY + 50 + Math.floor(i) * 110,
          });
        });

        rowHeight = Math.max(rowHeight, modH + 20);
        moduleX += modW + 20;
        if (moduleX > 1800) {
          moduleX = 40;
          moduleY += rowHeight;
          rowHeight = 0;
        }
      }
    });
  }, [canvas]);

  return { runNode, runBatch, runAgentAssign, editPrompt, viewChain };
}

// ---------------------------
// 构建执行计划（拓扑排序 + 并行分组）
// ---------------------------
function buildExecutionPlan(
  nodes: NodeData[],
  allNodes: Map<string, NodeData>
): { parallelGroups: string[][]; totalNodes: number; estimatedMinutes: number; estimatedApiCalls: number; chains: StoryboardChain[]; id: string } {
  // Kahn 算法拓扑排序
  const inDegree = new Map<string, number>();
  const nodeIds = new Set(nodes.map(n => n.id));

  nodes.forEach(n => {
    const deps = n.upstreamIds.filter(id => nodeIds.has(id));
    inDegree.set(n.id, deps.length);
  });

  const groups: string[][] = [];
  const remaining = new Set(nodes.map(n => n.id));

  while (remaining.size > 0) {
    const group = Array.from(remaining).filter(id => (inDegree.get(id) || 0) === 0);
    if (group.length === 0) break; // 环形依赖保护

    groups.push(group);
    group.forEach(id => {
      remaining.delete(id);
      const node = allNodes.get(id);
      node?.downstreamIds.forEach(downId => {
        if (inDegree.has(downId)) {
          inDegree.set(downId, (inDegree.get(downId) || 0) - 1);
        }
      });
    });
  }

  return {
    id: `plan_${Date.now()}`,
    parallelGroups: groups,
    totalNodes: nodes.length,
    estimatedMinutes: Math.ceil(nodes.length * 0.8),
    estimatedApiCalls: nodes.length * 3,
    chains: [],
  };
}
