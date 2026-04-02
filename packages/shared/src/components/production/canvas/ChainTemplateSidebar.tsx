'use client';

// ============================================================
// ChainTemplateSidebar.tsx
// 链模板系统：左侧胶囊栏 + 拖拽替换 + 模板编辑器
//
// 适配版：使用 chainTemplateStore / workflowExecutionStore / canvasStore
// ============================================================

import React, { useState, useCallback, useEffect } from 'react';
import { useChainTemplateStore } from '../../../stores/chainTemplateStore';
import { useWorkflowExecutionStore } from '../../../stores/workflowExecutionStore';
import { useCanvasStore } from '../../../stores/canvasStore';
import { useProjectStore } from '../../../stores';
import type { ChainTemplate, ChainStep } from '../../../types/chainWorkflow';

// ── 步骤类型下拉选项（17 种） ────────────────────────────────
const STEP_TYPES = [
  'generate-background',
  'generate-character',
  'generate-grid9',
  'character-pose-adjust',
  'remove-background',
  'composite-layers',
  'apply-filter',
  'adjust-lighting',
  'add-props',
  'motion-blur',
  'color-grade',
  'blend-refine',
  'scene-angle-transform',
  'set-video-keyframe',
  'grid9-to-video',
  'generate-video-direct',
  'user-select-frame',
] as const;

// ── 主组件：左侧胶囊栏 ───────────────────────────────────────
export const ChainTemplateSidebar: React.FC = () => {
  const {
    templates,
    fetchTemplates,
    createTemplate,
    updateTemplate,
    deleteTemplate,
    openEditor,
    closeEditor,
    editorOpen,
    editingTemplate,
  } = useChainTemplateStore();

  const projectStore = useProjectStore();
  const { selectedNodeIds, nodes } = useCanvasStore();
  const { startExecution } = useWorkflowExecutionStore();

  const [draggedId, setDraggedId] = useState<string | null>(null);

  // 组件 mount 时从后端加载模板
  const projectId = projectStore.project?.id ?? null;
  useEffect(() => {
    if (projectId) {
      fetchTemplates(projectId);
    }
  }, [projectId, fetchTemplates]);

  // 应用模板：走后端执行引擎
  const applyTemplate = useCallback(
    async (template: ChainTemplate) => {
      if (selectedNodeIds.length === 0) return;
      if (!projectId) return;
      try {
        await startExecution(projectId, projectId, template.id, selectedNodeIds);
      } catch (e) {
        console.error('Failed to start execution:', e);
      }
    },
    [selectedNodeIds, projectId, startExecution],
  );

  const handleEdit = (tpl: ChainTemplate) => {
    openEditor({ ...tpl });
  };

  const handleNewTemplate = () => {
    openEditor(null);
  };

  const handleSave = async (tpl: Omit<ChainTemplate, 'id' | 'isBuiltin' | 'version'> & { id?: string }) => {
    if (!projectId) return;
    if (editingTemplate && !editingTemplate.isBuiltin) {
      await updateTemplate(editingTemplate.id, tpl);
    } else {
      await createTemplate(projectId, tpl);
    }
  };

  const handleDelete = async () => {
    if (editingTemplate && !editingTemplate.isBuiltin) {
      await deleteTemplate(editingTemplate.id);
    }
  };

  return (
    <>
      {/* 胶囊侧边栏 — 紧贴导航盘右侧 */}
      <div
        style={{
          position: 'absolute',
          left: 170,   // 半圆盘宽度(RADIUS=140+padding) 右侧
          top: '50%',
          transform: 'translateY(-50%)',
          zIndex: 70,
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
          padding: '0 0 0 0',
        }}
      >
        <div
          style={{
            fontSize: 9,
            color: 'rgba(255,255,255,0.35)',
            padding: '0 4px',
            letterSpacing: '0.06em',
            marginBottom: 2,
            textAlign: 'center',
          }}
        >
          链模板
        </div>

        {templates.map((tpl) => (
          <TemplateCapsule
            key={tpl.id}
            template={tpl}
            isDragging={draggedId === tpl.id}
            onDragStart={() => setDraggedId(tpl.id)}
            onDragEnd={() => setDraggedId(null)}
            onEdit={() => handleEdit(tpl)}
            selectedNodeIds={selectedNodeIds}
            onApply={() => applyTemplate(tpl)}
          />
        ))}

        {/* 新建模板按钮 */}
        <button
          onClick={handleNewTemplate}
          style={{
            width: 36,
            height: 28,
            borderRadius: '0 8px 8px 0',
            border: '0.5px dashed rgba(75,85,99,0.5)',
            background: 'transparent',
            color: 'rgba(255,255,255,0.35)',
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
      {editorOpen && (
        <TemplateEditor
          initial={editingTemplate}
          onSave={handleSave}
          onCancel={closeEditor}
          onDelete={
            editingTemplate && !editingTemplate.isBuiltin ? handleDelete : undefined
          }
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
  selectedNodeIds: string[];
  onApply: () => void;
}> = ({ template, isDragging, onDragStart, onDragEnd, onEdit, selectedNodeIds, onApply }) => {
  const [hovered, setHovered] = useState(false);

  const canApply = selectedNodeIds.length > 0;

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
        <div
          style={{
            fontSize: 8,
            color: template.color,
            fontWeight: 500,
            textAlign: 'center',
            maxWidth: 30,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            lineHeight: 1.2,
          }}
        >
          {template.name.slice(0, 4)}
        </div>
        <div style={{ fontSize: 8, color: template.color + '99' }}>
          ~{template.estimatedMinutes}m
        </div>
      </div>

      {/* hover 展开 tooltip */}
      {hovered && (
        <div
          style={{
            position: 'absolute',
            left: 42,
            top: 0,
            background: 'rgba(17,24,39,0.97)',
            border: '0.5px solid rgba(75,85,99,0.5)',
            borderRadius: 10,
            padding: '10px 12px',
            minWidth: 200,
            zIndex: 200,
            boxShadow: '2px 2px 10px rgba(0,0,0,0.08)',
          }}
        >
          {/* 模板标题 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
            <span style={{ fontSize: 14 }}>{template.icon}</span>
            <span style={{ fontWeight: 500, fontSize: 13, color: 'var(--color-text-primary)' }}>
              {template.name}
            </span>
            {template.isBuiltin && (
              <span
                style={{
                  fontSize: 9,
                  padding: '1px 5px',
                  borderRadius: 4,
                  background: '#E6F1FB',
                  color: '#0C447C',
                }}
              >
                内置
              </span>
            )}
          </div>
          <div
            style={{
              fontSize: 11,
              color: 'var(--color-text-secondary)',
              marginBottom: 8,
              lineHeight: 1.5,
            }}
          >
            {template.description}
          </div>

          {/* 步骤列表 */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 3, marginBottom: 8 }}>
            {template.steps.map((step, i) => (
              <div key={step.id} style={{ display: 'flex', gap: 6, alignItems: 'flex-start' }}>
                <div
                  style={{
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
                  }}
                >
                  {i + 1}
                </div>
                <div>
                  <div style={{ fontSize: 11, color: 'var(--color-text-primary)', fontWeight: 500 }}>
                    {step.name}
                  </div>
                  {step.uiHint && (
                    <div style={{ fontSize: 10, color: 'var(--color-text-tertiary)' }}>
                      {step.uiHint}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* 标签 */}
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 8 }}>
            {template.tags.map((tag) => (
              <span
                key={tag}
                style={{
                  fontSize: 10,
                  padding: '2px 6px',
                  borderRadius: 4,
                  background: template.color + '15',
                  color: template.color,
                }}
              >
                {tag}
              </span>
            ))}
            <span
              style={{
                fontSize: 10,
                padding: '2px 6px',
                borderRadius: 4,
                background: 'var(--color-background-secondary)',
                color: 'var(--color-text-secondary)',
              }}
            >
              {template.videoProvider}
            </span>
          </div>

          {/* 操作按钮 */}
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              onClick={() => canApply && onApply()}
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
              {canApply ? `应用到选中(${selectedNodeIds.length})` : '请先框选分镜行'}
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

// ── 模板编辑器 ────────────────────────────────────────────────
const TemplateEditor: React.FC<{
  initial: ChainTemplate | null;
  onSave: (tpl: Omit<ChainTemplate, 'id' | 'isBuiltin' | 'version'> & { id?: string }) => void;
  onCancel: () => void;
  onDelete?: () => void;
}> = ({ initial, onSave, onCancel, onDelete }) => {
  const [name, setName] = useState(initial?.name || '');
  const [description, setDescription] = useState(initial?.description || '');
  const [color, setColor] = useState(initial?.color || '#378ADD');
  const [provider, setProvider] = useState<ChainTemplate['videoProvider']>(
    initial?.videoProvider || 'jimeng',
  );
  const [steps, setSteps] = useState<ChainStep[]>(initial?.steps || []);
  const [estMinutes, setEstMinutes] = useState(initial?.estimatedMinutes || 5);

  const addStep = () => {
    setSteps((prev) => [
      ...prev,
      {
        id: `s${Date.now()}`,
        name: '新步骤',
        type: 'generate-image-direct',
        description: '',
        params: {},
        optional: false,
      },
    ]);
  };

  const removeStep = (id: string) => setSteps((prev) => prev.filter((s) => s.id !== id));

  const updateStep = (id: string, patch: Partial<ChainStep>) => {
    setSteps((prev) => prev.map((s) => (s.id === id ? { ...s, ...patch } : s)));
  };

  const handleSave = () => {
    if (!name.trim()) return;
    onSave({
      id: initial?.id,
      name: name.trim(),
      description: description.trim(),
      icon: initial?.icon || '◆',
      color,
      tags: initial?.tags || [],
      steps,
      videoProvider: provider,
      estimatedMinutes: estMinutes,
      shareMode: initial?.shareMode,
      createdBy: initial?.createdBy,
    });
  };

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        background: 'rgba(0,0,0,0.3)',
        zIndex: 300,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div
        style={{
          background: 'var(--color-background-primary)',
          borderRadius: 14,
          border: '0.5px solid var(--color-border-tertiary)',
          width: 480,
          maxHeight: '80vh',
          overflow: 'auto',
          padding: 20,
        }}
      >
        <div style={{ fontWeight: 500, fontSize: 15, marginBottom: 16 }}>
          {initial?.isBuiltin ? '查看链模板' : initial ? '编辑链模板' : '新建链模板'}
        </div>

        {/* 基本信息 */}
        <label style={labelStyle}>模板名称</label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={initial?.isBuiltin}
          style={inputStyle}
          placeholder="如：资产合成流"
        />

        <label style={labelStyle}>描述</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          disabled={initial?.isBuiltin}
          style={{ ...inputStyle, height: 60, resize: 'none' }}
        />

        <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
          <div style={{ flex: 1 }}>
            <label style={labelStyle}>视频平台</label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value as ChainTemplate['videoProvider'])}
              disabled={initial?.isBuiltin}
              style={inputStyle}
            >
              <option value="jimeng">即梦</option>
              <option value="kling">可灵</option>
              <option value="runway">Runway</option>
              <option value="pika">Pika</option>
            </select>
          </div>
          <div style={{ flex: 1 }}>
            <label style={labelStyle}>预计耗时(分钟)</label>
            <input
              type="number"
              value={estMinutes}
              onChange={(e) => setEstMinutes(Number(e.target.value))}
              disabled={initial?.isBuiltin}
              style={inputStyle}
              min={1}
              max={60}
            />
          </div>
          <div>
            <label style={labelStyle}>颜色</label>
            <input
              type="color"
              value={color}
              onChange={(e) => setColor(e.target.value)}
              disabled={initial?.isBuiltin}
              style={{ ...inputStyle, width: 48, padding: 2 }}
            />
          </div>
        </div>

        {/* 步骤列表 */}
        <label style={labelStyle}>工作流步骤</label>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 10 }}>
          {steps.map((step, i) => (
            <div
              key={step.id}
              style={{
                border: '0.5px solid var(--color-border-tertiary)',
                borderRadius: 8,
                padding: '8px 10px',
              }}
            >
              <div
                style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}
              >
                <div
                  style={{
                    width: 18,
                    height: 18,
                    borderRadius: '50%',
                    background: color + '22',
                    border: `0.5px solid ${color}`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 10,
                    color,
                    flexShrink: 0,
                  }}
                >
                  {i + 1}
                </div>
                <input
                  value={step.name}
                  onChange={(e) => updateStep(step.id, { name: e.target.value })}
                  disabled={initial?.isBuiltin}
                  style={{ ...inputStyle, margin: 0, flex: 1 }}
                  placeholder="步骤名称"
                />
                {!initial?.isBuiltin && (
                  <button
                    onClick={() => removeStep(step.id)}
                    style={{
                      fontSize: 12,
                      color: '#E24B4A',
                      border: 'none',
                      background: 'none',
                      cursor: 'pointer',
                    }}
                  >
                    x
                  </button>
                )}
              </div>
              <select
                value={step.type}
                onChange={(e) => updateStep(step.id, { type: e.target.value as ChainStep['type'] })}
                disabled={initial?.isBuiltin}
                style={{ ...inputStyle, margin: '0 0 4px 0', fontSize: 11 }}
              >
                {STEP_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              <input
                value={step.description}
                onChange={(e) => updateStep(step.id, { description: e.target.value })}
                disabled={initial?.isBuiltin}
                style={{ ...inputStyle, margin: 0, fontSize: 11 }}
                placeholder="步骤说明（可选）"
              />
            </div>
          ))}
          {!initial?.isBuiltin && (
            <button
              onClick={addStep}
              style={{
                fontSize: 11,
                padding: '6px 0',
                borderRadius: 6,
                border: '0.5px dashed var(--color-border-secondary)',
                background: 'transparent',
                color: 'var(--color-text-secondary)',
                cursor: 'pointer',
              }}
            >
              + 添加步骤
            </button>
          )}
        </div>

        {/* 按钮行 */}
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          {onDelete && (
            <button
              onClick={onDelete}
              style={{
                fontSize: 12,
                padding: '6px 14px',
                borderRadius: 6,
                border: '0.5px solid #E24B4A',
                color: '#E24B4A',
                background: 'transparent',
                cursor: 'pointer',
                marginRight: 'auto',
              }}
            >
              删除模板
            </button>
          )}
          <button
            onClick={onCancel}
            style={{
              fontSize: 12,
              padding: '6px 14px',
              borderRadius: 6,
              border: '0.5px solid var(--color-border-tertiary)',
              background: 'transparent',
              color: 'var(--color-text-secondary)',
              cursor: 'pointer',
            }}
          >
            {initial?.isBuiltin ? '关闭' : '取消'}
          </button>
          {!initial?.isBuiltin && (
            <button
              onClick={handleSave}
              disabled={!name.trim()}
              style={{
                fontSize: 12,
                padding: '6px 14px',
                borderRadius: 6,
                border: 'none',
                background: '#378ADD',
                color: '#fff',
                cursor: name.trim() ? 'pointer' : 'not-allowed',
                opacity: name.trim() ? 1 : 0.5,
              }}
            >
              保存模板
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

// ── 拖放目标：节点上的 Drop Zone ─────────────────────────────
export const ChainDropTarget: React.FC<{ nodeId: string }> = ({ nodeId }) => {
  const [dragOver, setDragOver] = useState(false);
  const { startExecution } = useWorkflowExecutionStore();
  const { templates } = useChainTemplateStore();
  const projectStore = useProjectStore();

  const onDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const templateId = e.dataTransfer.getData('templateId');
    if (!templateId) return;

    const template = templates.find((t) => t.id === templateId);
    if (!template) return;

    const projectId = projectStore.project?.id;
    if (!projectId) return;

    // 选中该节点并通过后端执行引擎应用模板
    useCanvasStore.getState().selectNodes([nodeId]);
    try {
      await startExecution(projectId, projectId, template.id, [nodeId]);
    } catch (err) {
      console.error('Failed to apply template via drop:', err);
    }
  };

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
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

// ── 样式常量 ─────────────────────────────────────────────────
const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: 11,
  color: 'var(--color-text-secondary)',
  marginBottom: 4,
  marginTop: 10,
};

const inputStyle: React.CSSProperties = {
  width: '100%',
  fontSize: 12,
  padding: '6px 8px',
  borderRadius: 6,
  border: '0.5px solid var(--color-border-tertiary)',
  background: 'var(--color-background-secondary)',
  color: 'var(--color-text-primary)',
  outline: 'none',
  marginBottom: 4,
  boxSizing: 'border-box',
};
