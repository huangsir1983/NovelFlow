# Workflow Schema 规格说明

> 版本：2.0
> 日期：2026-03-06
> 目标：支撑三段式产品中的中段 `Tapnow/TapFlow` 式可执行无限画布
> 关联文档：`docs/CANVAS_SYSTEM_DESIGN.md`、`docs/CANVAS_API_SPEC.md`

---

## 1. 设计目标

工作流 Schema 用于统一以下对象：

- 前端画布结构
- 后端持久化结构
- 节点执行契约
- 结果工件映射
- 回写动作记录
- 协作与评审信息

Schema 的核心原则是：画布描述的是“编排与执行”，项目真相层描述的是“业务对象本身”。

---

## 2. 顶层模型

```ts
interface Workflow {
  id: string;
  projectId: string;
  name: string;
  description?: string;
  editionScope: 'normal' | 'canvas' | 'hidden' | 'ultimate';
  stage: 'middle';
  sourceType: 'novel' | 'script' | 'scene' | 'chapter' | 'mixed';
  templateId?: string;
  status: 'draft' | 'active' | 'archived';
  schemaVersion: number;
  workflowJson: WorkflowJson;
  createdBy: string;
  updatedBy: string;
  createdAt: string;
  updatedAt: string;
}
```

```ts
interface WorkflowJson {
  meta: WorkflowMeta;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  groups?: WorkflowGroup[];
  comments?: WorkflowComment[];
  viewport?: WorkflowViewport;
  runtime?: WorkflowRuntimeConfig;
  collaboration?: WorkflowCollaborationMeta;
}
```

---

## 3. 元信息结构

```ts
interface WorkflowMeta {
  title: string;
  description?: string;
  templateCategory?: 'story_to_shot' | 'micro_drama' | 'visual_style' | 'custom';
  recommendedFor?: Array<'normal' | 'canvas' | 'hidden' | 'ultimate'>;
  contextScope: {
    projectId: string;
    chapterIds?: string[];
    sceneIds?: string[];
    shotIds?: string[];
  };
  writeBackTargets?: Array<'story_bible' | 'beat' | 'scene' | 'shot' | 'asset' | 'animatic'>;
  createdFromStage?: 'front';
  canSendToPreview?: boolean;
}
```

---

## 4. 节点结构

```ts
interface WorkflowNode {
  id: string;
  type: string;
  title: string;
  group: 'input' | 'analysis' | 'creative' | 'director' | 'visual' | 'generation' | 'quality' | 'output' | 'control';
  editionRequired: 'normal' | 'canvas' | 'hidden' | 'ultimate';
  position: { x: number; y: number };
  size?: { width: number; height: number };
  data: WorkflowNodeData;
  ports: WorkflowPorts;
  ui?: WorkflowNodeUiState;
}
```

```ts
interface WorkflowNodeData {
  config: Record<string, unknown>;
  inputBindings?: NodeInputBinding[];
  outputSummary?: NodeOutputSummary;
  latestRunId?: string;
  resultRefs?: string[];
  writeBackPolicy?: 'manual' | 'suggested' | 'disabled';
  riskLevel?: 'low' | 'medium' | 'high';
  tags?: string[];
}
```

```ts
interface WorkflowPorts {
  inputs: Array<{ id: string; name: string; schema: string; required: boolean }>;
  outputs: Array<{ id: string; name: string; schema: string }>;
}
```

```ts
interface WorkflowNodeUiState {
  collapsed?: boolean;
  selectedVariantId?: string;
  displayMode?: 'summary' | 'result' | 'config' | 'compare';
  commentCount?: number;
  frameId?: string;
}
```

---

## 5. 连线结构

```ts
interface WorkflowEdge {
  id: string;
  sourceNodeId: string;
  sourcePortId: string;
  targetNodeId: string;
  targetPortId: string;
  kind: 'data' | 'control' | 'reference';
  required: boolean;
  ui?: {
    highlighted?: boolean;
    label?: string;
  };
}
```

约束要求：

- 连线必须通过 schema 校验
- 非 `Hidden` / `Ultimate` 不允许创建高阶控制边
- 非法环路必须在保存阶段阻断

---

## 6. 分组与 Frame

```ts
interface WorkflowGroup {
  id: string;
  title: string;
  type: 'scene_frame' | 'chapter_frame' | 'review_frame' | 'asset_frame';
  nodeIds: string[];
  bounds: { x: number; y: number; width: number; height: number };
  color?: string;
}
```

Frame 是画布中吸收自 Figma/Miro 的重要协作增强单元，但不能替代业务结构本身。

---

## 7. 评论与协作

```ts
interface WorkflowComment {
  id: string;
  anchorType: 'workflow' | 'group' | 'node' | 'artifact' | 'writeback';
  anchorId: string;
  body: string;
  status: 'open' | 'resolved';
  authorId: string;
  createdAt: string;
}
```

```ts
interface WorkflowCollaborationMeta {
  mode: 'edit' | 'review' | 'present';
  presenceEnabled: boolean;
  shareTokenId?: string;
}
```

---

## 8. 运行时结构

```ts
interface WorkflowRuntimeConfig {
  runMode: 'template' | 'manual' | 'experiment';
  defaultExecutionMode: 'full' | 'single_node' | 'forward_from_node';
  retryPolicy?: 'none' | 'safe_retry';
}
```

运行态建议：

- Phase 1 仅支持 `template` 与有限 `manual`
- `experiment` 仅对 `Ultimate` 打开

---

## 9. 工件与回写映射

```ts
interface NodeArtifactRef {
  id: string;
  artifactType: 'text' | 'prompt' | 'image' | 'video' | 'audio' | 'subtitle' | 'animatic' | 'report';
  version: number;
  sourceNodeId: string;
}
```

```ts
interface WriteBackAction {
  id: string;
  sourceNodeId: string;
  artifactId: string;
  targetType: 'story_bible' | 'beat' | 'scene' | 'shot' | 'asset' | 'animatic';
  targetId: string;
  mode: 'append' | 'replace' | 'merge';
  status: 'pending' | 'confirmed' | 'rejected';
}
```

---

## 10. Phase 1 最小约束

Phase 1 保存的 `workflowJson` 至少应满足：

- 有模板来源或明确入口上下文
- 有完整节点列表与连线列表
- 节点结果能关联工件
- 回写动作可被记录
- 评论锚点可被保存
- 视口状态可恢复

---

## 11. 版本兼容策略

- `schemaVersion` 必填
- 新增字段优先采用向后兼容方式扩展
- 删除旧字段前必须提供迁移器
- `Normal` 不可保存超过其权限的高阶结构

---

## 12. 结论

Workflow Schema 的设计必须服务于“可执行中段”这一核心定位。
它不是画图数据格式，而是影视生产编排与结果回写的数据契约。
