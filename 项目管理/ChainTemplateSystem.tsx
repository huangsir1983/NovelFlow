// ============================================================
// ChainTemplateSystem.tsx
// 链模板系统：左侧胶囊栏 + 拖拽替换 + 模板编辑器
//
// 内置模板：
//   A. 九宫格生图流  → 九宫格生视频
//   B. 资产合成流    → 场景角度换 + 角色换 + 去背 + 溶图 + 视频首帧
//   C. 直出提示词流  → 直接 imagePrompt → 视频（最简）
//   D. 用户自定义模板（可创建/编辑/删除）
// ============================================================

import React, { useState, useCallback, useRef } from 'react';
import { useCanvasStore } from '../../store/canvasStore';
import { NodeData, ImageContent, WorkflowStep } from '../../types';

// ── 类型 ─────────────────────────────────────────────────────
export interface ChainTemplate {
  id: string;
  name: string;
  description: string;
  icon: string;
  color: string;
  tags: string[];
  isBuiltin: boolean;
  steps: TemplateStep[];
  videoProvider: 'jimeng' | 'kling' | 'runway' | 'pika';
  estimatedMinutes: number; // 预计耗时（单次）
}

export interface TemplateStep {
  id: string;
  name: string;
  type: string;           // 对应 WorkflowStepType
  description: string;
  params: Record<string, unknown>;
  optional: boolean;
  uiHint?: string;        // 给用户看的提示
}

// ── 内置模板定义 ──────────────────────────────────────────────
export const BUILTIN_TEMPLATES: ChainTemplate[] = [
  {
    id: 'tpl_grid9',
    name: '九宫格生图流',
    description: '先生成九宫格参考图，从中选取最佳帧，再用九宫格生视频',
    icon: '⊞',
    color: '#534AB7',
    tags: ['精细', '多选', '高质量'],
    isBuiltin: true,
    videoProvider: 'jimeng',
    estimatedMinutes: 8,
    steps: [
      {
        id: 's1', name: '生成九宫格参考图',
        type: 'generate-grid9',
        description: '用同一提示词生成9张候选图，排列为3×3网格',
        params: { grid: 3, style: 'cinematic', seed_variance: true },
        optional: false,
        uiHint: '将生成9张候选，你可以框选最满意的一张',
      },
      {
        id: 's2', name: '用户选帧',
        type: 'user-select-frame',
        description: '从九宫格中选择最佳帧作为视频首帧',
        params: { require_user_confirm: true },
        optional: false,
        uiHint: '需要人工确认，系统会暂停等待你点击选择',
      },
      {
        id: 's3', name: '九宫格生视频',
        type: 'grid9-to-video',
        description: '将九宫格整体作为参考，生成连贯视频',
        params: { use_grid_as_reference: true, motion_strength: 0.6 },
        optional: false,
        uiHint: '即梦 API，以九宫格整体作为参考增强一致性',
      },
    ],
  },
  {
    id: 'tpl_asset_compose',
    name: '资产合成流',
    description: '从资产库取场景图 → 换角度 → 角色换动作/表情/角度 → 去背景 → 合图 → 溶图优化 → 视频首帧',
    icon: '◈',
    color: '#1D9E75',
    tags: ['资产库', '高一致性', '精细合成'],
    isBuiltin: true,
    videoProvider: 'kling',
    estimatedMinutes: 12,
    steps: [
      {
        id: 's1', name: '场景角度变换',
        type: 'scene-angle-transform',
        description: '从资产库取场景参考图，AI生成指定角度的新视角',
        params: { source: 'asset-library', angle_mode: 'auto-from-storyboard' },
        optional: false,
        uiHint: '自动从分镜文本推断所需镜头角度',
      },
      {
        id: 's2', name: '角色动作/表情/角度调整',
        type: 'character-pose-adjust',
        description: '从资产库取角色参考图，按分镜描述调整姿态、表情、角度',
        params: { source: 'asset-library', ref_weight: 0.85, preserve_face: true },
        optional: false,
        uiHint: '高参考权重(0.85)保持角色一致性',
      },
      {
        id: 's3', name: '角色去背景',
        type: 'remove-background',
        description: 'AI精确抠图，保留透明通道',
        params: { method: 'ai-matting', edge_refine: true, feather: 1.5 },
        optional: false,
      },
      {
        id: 's4', name: '场景+角色合成',
        type: 'composite-layers',
        description: '将去背角色合入场景，自动匹配光线/阴影/色温',
        params: { auto_shadow: true, color_match: true, depth_blend: true },
        optional: false,
        uiHint: '自动匹配光线色温，使角色融入场景',
      },
      {
        id: 's5', name: '溶图优化',
        type: 'blend-refine',
        description: '对合成边缘进行溶图处理，消除穿帮感',
        params: { blend_radius: 8, frequency_match: true },
        optional: false,
        uiHint: '频率匹配技术消除合成边缘',
      },
      {
        id: 's6', name: '视频首帧确认',
        type: 'set-video-keyframe',
        description: '将溶图结果设为视频生成的锁定首帧',
        params: { lock_first_frame: true },
        optional: false,
      },
    ],
  },
  {
    id: 'tpl_direct',
    name: '直出提示词流',
    description: '最简流程：分镜提示词 → 直接生图 → 生视频。速度最快，适合快速出样',
    icon: '→',
    color: '#378ADD',
    tags: ['快速', '简单', '批量'],
    isBuiltin: true,
    videoProvider: 'jimeng',
    estimatedMinutes: 3,
    steps: [
      {
        id: 's1', name: '直接生成图片',
        type: 'generate-image-direct',
        description: '直接用 imagePrompt 生成图片，无额外合成步骤',
        params: { style: 'cinematic', quality: 'standard' },
        optional: false,
      },
      {
        id: 's2', name: '直接生成视频',
        type: 'generate-video-direct',
        description: '图片直接作为首帧生成视频',
        params: { provider: 'jimeng', duration: 5 },
        optional: false,
      },
    ],
  },
  {
    id: 'tpl_emotion_portrait',
    name: '情感特写流',
    description: '专为情感/内心戏设计：柔焦背景 + 面部特写 + 慢速推镜视频',
    icon: '◉',
    color: '#D4537E',
    tags: ['情感', '特写', '慢镜'],
    isBuiltin: true,
    videoProvider: 'kling',
    estimatedMinutes: 10,
    steps: [
      {
        id: 's1', name: '生成柔焦背景',
        type: 'generate-background',
        description: '大光圈柔焦虚化背景，突出主体',
        params: { bokeh: true, abstraction: 0.4, style: 'emotional' },
        optional: false,
      },
      {
        id: 's2', name: '生成面部特写',
        type: 'character-pose-adjust',
        description: '特写角度，重点刻画表情细节',
        params: { angle: 'close-up', expression_intensity: 0.85, preserve_face: true },
        optional: false,
      },
      {
        id: 's3', name: '去背合成',
        type: 'remove-background',
        params: { method: 'ai-matting', edge_refine: true, feather: 3 },
        description: '软边缘镂空，与柔焦背景自然融合',
        optional: false,
      },
      {
        id: 's4', name: '情感滤镜',
        type: 'apply-filter',
        description: '根据情绪施加色调：悲伤→冷蓝/温馨→暖金',
        params: { filter: 'emotion-auto', halation: 0.12 },
        optional: false,
      },
      {
        id: 's5', name: '慢速推镜视频',
        type: 'generate-video-direct',
        description: '可灵慢速推进，配合情感节奏',
        params: { provider: 'kling', motion: 'slow-push', duration: 6 },
        optional: false,
      },
    ],
  },
];

// ── 模板 Store（简单内存存储，可接入你的持久化层） ─────────────
let _customTemplates: ChainTemplate[] = [];
let _listeners: Array<() => void> = [];

const templateStore = {
  getAll: () => [...BUILTIN_TEMPLATES, ..._customTemplates],
  add: (tpl: ChainTemplate) => { _customTemplates.push(tpl); _listeners.forEach(l => l()); },
  update: (tpl: ChainTemplate) => {
    const idx = _customTemplates.findIndex(t => t.id === tpl.id);
    if (idx >= 0) { _customTemplates[idx] = tpl; _listeners.forEach(l => l()); }
  },
  delete: (id: string) => { _customTemplates = _customTemplates.filter(t => t.id !== id); _listeners.forEach(l => l()); },
  subscribe: (fn: () => void) => { _listeners.push(fn); return () => { _listeners = _listeners.filter(l => l !== fn); }; },
};

function useTemplates() {
  const [, forceUpdate] = React.useReducer(x => x + 1, 0);
  React.useEffect(() => templateStore.subscribe(forceUpdate), []);
  return templateStore.getAll();
}

// ── 主组件：左侧胶囊栏 ───────────────────────────────────────
export const ChainTemplateSidebar: React.FC = () => {
  const templates = useTemplates();
  const [showEditor, setShowEditor] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<ChainTemplate | null>(null);
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const { selectedNodeIds, nodes } = useCanvasStore();

  const handleEdit = (tpl: ChainTemplate) => {
    setEditingTemplate({ ...tpl });
    setShowEditor(true);
  };

  const handleNewTemplate = () => {
    setEditingTemplate(null);
    setShowEditor(true);
  };

  return (
    <>
      {/* 胶囊侧边栏 */}
      <div style={{
        position: 'absolute',
        left: 0,
        top: 16,
        zIndex: 70,
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        padding: '0 0 0 0',
      }}>
        <div style={{ fontSize: 9, color: 'var(--color-text-tertiary)', padding: '0 8px', letterSpacing: '0.06em', marginBottom: 2 }}>
          链模板
        </div>
        {templates.map(tpl => (
          <TemplateCapsule
            key={tpl.id}
            template={tpl}
            isDragging={draggedId === tpl.id}
            onDragStart={() => setDraggedId(tpl.id)}
            onDragEnd={() => setDraggedId(null)}
            onEdit={() => handleEdit(tpl)}
            selectedNodeIds={selectedNodeIds}
            nodes={nodes}
          />
        ))}

        {/* 新建模板按钮 */}
        <button
          onClick={handleNewTemplate}
          style={{
            width: 36,
            height: 28,
            borderRadius: '0 8px 8px 0',
            border: '0.5px dashed var(--color-border-secondary)',
            background: 'transparent',
            color: 'var(--color-text-tertiary)',
            cursor: 'pointer',
            fontSize: 16,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginTop: 4,
          }}
          title="新建自定义链模板"
        >
          +
        </button>
      </div>

      {/* 模板编辑器 Modal */}
      {showEditor && (
        <TemplateEditor
          initial={editingTemplate}
          onSave={(tpl) => {
            if (editingTemplate && !editingTemplate.isBuiltin) {
              templateStore.update(tpl);
            } else {
              templateStore.add({ ...tpl, id: `tpl_custom_${Date.now()}`, isBuiltin: false });
            }
            setShowEditor(false);
          }}
          onCancel={() => setShowEditor(false)}
          onDelete={editingTemplate && !editingTemplate.isBuiltin ? () => {
            templateStore.delete(editingTemplate.id);
            setShowEditor(false);
          } : undefined}
        />
      )}
    </>
  );
};

// ── 胶囊按钮 ─────────────────────────────────────────────────
const TemplateCapsule: React.FC<{
  template: ChainTemplate;
  isDragging: boolean;
  onDragStart: () => void;
  onDragEnd: () => void;
  onEdit: () => void;
  selectedNodeIds: Set<string>;
  nodes: Map<string, NodeData>;
}> = ({ template, isDragging, onDragStart, onDragEnd, onEdit, selectedNodeIds, nodes }) => {
  const [hovered, setHovered] = useState(false);
  const { applyTemplateToSelected } = useChainApply();

  const canApply = selectedNodeIds.size > 0;

  return (
    <div
      style={{
        position: 'relative',
        display: 'flex',
        alignItems: 'stretch',
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* 主胶囊 */}
      <div
        draggable
        onDragStart={(e) => {
          e.dataTransfer.setData('templateId', template.id);
          onDragStart();
        }}
        onDragEnd={onDragEnd}
        style={{
          width: 36,
          height: 52,
          borderRadius: '0 12px 12px 0',
          background: template.color + (isDragging ? 'cc' : '20'),
          border: `0.5px solid ${template.color}66`,
          borderLeft: `3px solid ${template.color}`,
          cursor: 'grab',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 2,
          transition: 'transform 0.1s, background 0.1s',
          transform: isDragging ? 'translateX(4px)' : 'none',
          userSelect: 'none',
        }}
      >
        <span style={{ fontSize: 14, lineHeight: 1 }}>{template.icon}</span>
        <div style={{
          fontSize: 8,
          color: template.color,
          fontWeight: 500,
          textAlign: 'center',
          maxWidth: 30,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          lineHeight: 1.2,
        }}>
          {template.name.slice(0, 4)}
        </div>
        <div style={{ fontSize: 8, color: template.color + '99' }}>
          ~{template.estimatedMinutes}m
        </div>
      </div>

      {/* 展开tooltip */}
      {hovered && (
        <div style={{
          position: 'absolute',
          left: 42,
          top: 0,
          background: 'var(--color-background-primary)',
          border: '0.5px solid var(--color-border-tertiary)',
          borderRadius: 10,
          padding: '10px 12px',
          minWidth: 200,
          zIndex: 200,
          boxShadow: '2px 2px 10px rgba(0,0,0,0.08)',
        }}>
          {/* 模板标题 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
            <span style={{ fontSize: 14 }}>{template.icon}</span>
            <span style={{ fontWeight: 500, fontSize: 13, color: 'var(--color-text-primary)' }}>{template.name}</span>
            {template.isBuiltin && (
              <span style={{ fontSize: 9, padding: '1px 5px', borderRadius: 4, background: '#E6F1FB', color: '#0C447C' }}>内置</span>
            )}
          </div>
          <div style={{ fontSize: 11, color: 'var(--color-text-secondary)', marginBottom: 8, lineHeight: 1.5 }}>
            {template.description}
          </div>

          {/* 步骤列表 */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 3, marginBottom: 8 }}>
            {template.steps.map((step, i) => (
              <div key={step.id} style={{ display: 'flex', gap: 6, alignItems: 'flex-start' }}>
                <div style={{
                  width: 14,
                  height: 14,
                  borderRadius: '50%',
                  background: template.color + '22',
                  border: `0.5px solid ${template.color}66`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 8,
                  color: template.color,
                  flexShrink: 0,
                  marginTop: 1,
                }}>
                  {i + 1}
                </div>
                <div>
                  <div style={{ fontSize: 11, color: 'var(--color-text-primary)', fontWeight: 500 }}>{step.name}</div>
                  {step.uiHint && <div style={{ fontSize: 10, color: 'var(--color-text-tertiary)' }}>{step.uiHint}</div>}
                </div>
              </div>
            ))}
          </div>

          {/* 标签 */}
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 8 }}>
            {template.tags.map(tag => (
              <span key={tag} style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4, background: template.color + '15', color: template.color }}>
                {tag}
              </span>
            ))}
            <span style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4, background: 'var(--color-background-secondary)', color: 'var(--color-text-secondary)' }}>
              {template.videoProvider}
            </span>
          </div>

          {/* 操作按钮 */}
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              onClick={() => canApply && applyTemplateToSelected(template)}
              disabled={!canApply}
              style={{
                flex: 1,
                fontSize: 11,
                padding: '5px 0',
                borderRadius: 6,
                border: `0.5px solid ${template.color}`,
                background: canApply ? template.color + '15' : 'var(--color-background-secondary)',
                color: canApply ? template.color : 'var(--color-text-tertiary)',
                cursor: canApply ? 'pointer' : 'not-allowed',
              }}
            >
              {canApply ? `应用到选中(${selectedNodeIds.size})` : '请先框选分镜行'}
            </button>
            <button
              onClick={onEdit}
              style={{
                fontSize: 11,
                padding: '5px 10px',
                borderRadius: 6,
                border: '0.5px solid var(--color-border-tertiary)',
                background: 'transparent',
                color: 'var(--color-text-secondary)',
                cursor: 'pointer',
              }}
            >
              {template.isBuiltin ? '查看' : '编辑'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

// ── 应用模板 Hook ────────────────────────────────────────────
function useChainApply() {
  const { nodes, selectedNodeIds, updateNodeContent, updateNode } = useCanvasStore();

  const applyTemplateToSelected = useCallback((template: ChainTemplate) => {
    // 从选中节点中找出图片类型节点，替换其 workflowSteps
    selectedNodeIds.forEach(nodeId => {
      const node = nodes.get(nodeId);
      if (!node) return;

      if (node.type === 'image') {
        const newSteps: WorkflowStep[] = template.steps
          .filter(s => s.type !== 'generate-video-direct' && s.type !== 'grid9-to-video')
          .map(s => ({
            id: s.id,
            name: s.name,
            type: s.type as any,
            status: 'idle' as any,
            params: { ...s.params },
            optional: s.optional,
          }));
        updateNodeContent(nodeId, { workflowSteps: newSteps });
        updateNode(nodeId, { status: 'ready', moduleType: undefined });
      }

      if (node.type === 'video') {
        const videoStep = template.steps.find(s => s.type === 'generate-video-direct' || s.type === 'grid9-to-video');
        if (videoStep) {
          updateNodeContent(nodeId, {
            provider: (videoStep.params.provider as any) || template.videoProvider,
          });
        }
      }
    });
  }, [nodes, selectedNodeIds, updateNodeContent, updateNode]);

  return { applyTemplateToSelected };
}

// ── 模板编辑器 ────────────────────────────────────────────────
const TemplateEditor: React.FC<{
  initial: ChainTemplate | null;
  onSave: (tpl: ChainTemplate) => void;
  onCancel: () => void;
  onDelete?: () => void;
}> = ({ initial, onSave, onCancel, onDelete }) => {
  const [name, setName] = useState(initial?.name || '');
  const [description, setDescription] = useState(initial?.description || '');
  const [color, setColor] = useState(initial?.color || '#378ADD');
  const [provider, setProvider] = useState<ChainTemplate['videoProvider']>(initial?.videoProvider || 'jimeng');
  const [steps, setSteps] = useState<TemplateStep[]>(initial?.steps || []);
  const [estMinutes, setEstMinutes] = useState(initial?.estimatedMinutes || 5);

  const addStep = () => {
    setSteps(prev => [...prev, {
      id: `s${Date.now()}`,
      name: '新步骤',
      type: 'generate-image-direct',
      description: '',
      params: {},
      optional: false,
    }]);
  };

  const removeStep = (id: string) => setSteps(prev => prev.filter(s => s.id !== id));

  const updateStep = (id: string, patch: Partial<TemplateStep>) => {
    setSteps(prev => prev.map(s => s.id === id ? { ...s, ...patch } : s));
  };

  const STEP_TYPES = [
    'generate-background', 'generate-character', 'generate-grid9',
    'character-pose-adjust', 'remove-background', 'composite-layers',
    'apply-filter', 'adjust-lighting', 'add-props', 'motion-blur',
    'color-grade', 'blend-refine', 'scene-angle-transform',
    'set-video-keyframe', 'grid9-to-video', 'generate-video-direct',
    'user-select-frame',
  ];

  const handleSave = () => {
    if (!name.trim()) return;
    const tpl: ChainTemplate = {
      id: initial?.id || `tpl_custom_${Date.now()}`,
      name: name.trim(),
      description: description.trim(),
      icon: initial?.icon || '◆',
      color,
      tags: [],
      isBuiltin: false,
      videoProvider: provider,
      estimatedMinutes: estMinutes,
      steps,
    };
    onSave(tpl);
  };

  return (
    <div style={{
      position: 'absolute',
      inset: 0,
      background: 'rgba(0,0,0,0.3)',
      zIndex: 300,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
    }}>
      <div style={{
        background: 'var(--color-background-primary)',
        borderRadius: 14,
        border: '0.5px solid var(--color-border-tertiary)',
        width: 480,
        maxHeight: '80vh',
        overflow: 'auto',
        padding: 20,
      }}>
        <div style={{ fontWeight: 500, fontSize: 15, marginBottom: 16 }}>
          {initial?.isBuiltin ? '查看链模板' : initial ? '编辑链模板' : '新建链模板'}
        </div>

        {/* 基本信息 */}
        <label style={labelStyle}>模板名称</label>
        <input value={name} onChange={e => setName(e.target.value)} disabled={initial?.isBuiltin}
          style={inputStyle} placeholder="如：资产合成流" />

        <label style={labelStyle}>描述</label>
        <textarea value={description} onChange={e => setDescription(e.target.value)} disabled={initial?.isBuiltin}
          style={{ ...inputStyle, height: 60, resize: 'none' }} />

        <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
          <div style={{ flex: 1 }}>
            <label style={labelStyle}>视频平台</label>
            <select value={provider} onChange={e => setProvider(e.target.value as any)} disabled={initial?.isBuiltin}
              style={inputStyle}>
              <option value="jimeng">即梦</option>
              <option value="kling">可灵</option>
              <option value="runway">Runway</option>
              <option value="pika">Pika</option>
            </select>
          </div>
          <div style={{ flex: 1 }}>
            <label style={labelStyle}>预计耗时(分钟)</label>
            <input type="number" value={estMinutes} onChange={e => setEstMinutes(Number(e.target.value))}
              disabled={initial?.isBuiltin} style={inputStyle} min={1} max={60} />
          </div>
          <div>
            <label style={labelStyle}>颜色</label>
            <input type="color" value={color} onChange={e => setColor(e.target.value)}
              disabled={initial?.isBuiltin} style={{ ...inputStyle, width: 48, padding: 2 }} />
          </div>
        </div>

        {/* 步骤列表 */}
        <label style={labelStyle}>工作流步骤</label>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 10 }}>
          {steps.map((step, i) => (
            <div key={step.id} style={{
              border: '0.5px solid var(--color-border-tertiary)',
              borderRadius: 8,
              padding: '8px 10px',
            }}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
                <div style={{ width: 18, height: 18, borderRadius: '50%', background: color + '22', border: `0.5px solid ${color}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, color, flexShrink: 0 }}>{i + 1}</div>
                <input value={step.name} onChange={e => updateStep(step.id, { name: e.target.value })}
                  disabled={initial?.isBuiltin}
                  style={{ ...inputStyle, margin: 0, flex: 1 }} placeholder="步骤名称" />
                {!initial?.isBuiltin && (
                  <button onClick={() => removeStep(step.id)} style={{ fontSize: 12, color: '#E24B4A', border: 'none', background: 'none', cursor: 'pointer' }}>×</button>
                )}
              </div>
              <select value={step.type} onChange={e => updateStep(step.id, { type: e.target.value })}
                disabled={initial?.isBuiltin} style={{ ...inputStyle, margin: '0 0 4px 0', fontSize: 11 }}>
                {STEP_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
              <input value={step.description} onChange={e => updateStep(step.id, { description: e.target.value })}
                disabled={initial?.isBuiltin}
                style={{ ...inputStyle, margin: 0, fontSize: 11 }} placeholder="步骤说明（可选）" />
            </div>
          ))}
          {!initial?.isBuiltin && (
            <button onClick={addStep} style={{ fontSize: 11, padding: '6px 0', borderRadius: 6, border: '0.5px dashed var(--color-border-secondary)', background: 'transparent', color: 'var(--color-text-secondary)', cursor: 'pointer' }}>
              + 添加步骤
            </button>
          )}
        </div>

        {/* 按钮行 */}
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          {onDelete && (
            <button onClick={onDelete} style={{ fontSize: 12, padding: '6px 14px', borderRadius: 6, border: '0.5px solid #E24B4A', color: '#E24B4A', background: 'transparent', cursor: 'pointer', marginRight: 'auto' }}>
              删除模板
            </button>
          )}
          <button onClick={onCancel} style={{ fontSize: 12, padding: '6px 14px', borderRadius: 6, border: '0.5px solid var(--color-border-tertiary)', background: 'transparent', color: 'var(--color-text-secondary)', cursor: 'pointer' }}>
            {initial?.isBuiltin ? '关闭' : '取消'}
          </button>
          {!initial?.isBuiltin && (
            <button onClick={handleSave} disabled={!name.trim()} style={{ fontSize: 12, padding: '6px 14px', borderRadius: 6, border: 'none', background: '#378ADD', color: '#fff', cursor: name.trim() ? 'pointer' : 'not-allowed', opacity: name.trim() ? 1 : 0.5 }}>
              保存模板
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

const labelStyle: React.CSSProperties = {
  display: 'block', fontSize: 11, color: 'var(--color-text-secondary)', marginBottom: 4, marginTop: 10,
};
const inputStyle: React.CSSProperties = {
  width: '100%', fontSize: 12, padding: '6px 8px', borderRadius: 6,
  border: '0.5px solid var(--color-border-tertiary)', background: 'var(--color-background-secondary)',
  color: 'var(--color-text-primary)', outline: 'none', marginBottom: 4, boxSizing: 'border-box',
};

// ── 拖放目标：节点上的 Drop Zone ─────────────────────────────
export const ChainDropTarget: React.FC<{ nodeId: string }> = ({ nodeId }) => {
  const [dragOver, setDragOver] = useState(false);
  const { nodes } = useCanvasStore();
  const { applyTemplateToSelected } = useChainApply();

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const templateId = e.dataTransfer.getData('templateId');
    const template = templateStore.getAll().find(t => t.id === templateId);
    if (!template) return;
    // 临时将该节点加入选中
    useCanvasStore.getState().selectNode(nodeId);
    applyTemplateToSelected(template);
    setDragOver(false);
  };

  return (
    <div
      onDragOver={e => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
      style={{
        position: 'absolute',
        inset: 0,
        borderRadius: 10,
        border: dragOver ? '2px dashed #378ADD' : 'none',
        background: dragOver ? 'rgba(59,138,221,0.06)' : 'transparent',
        pointerEvents: dragOver ? 'all' : 'none',
        zIndex: 10,
        transition: 'all 0.12s',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      {dragOver && (
        <span style={{ fontSize: 11, color: '#378ADD', fontWeight: 500 }}>放下替换链</span>
      )}
    </div>
  );
};

export { templateStore };
