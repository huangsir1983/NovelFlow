'use client';

import React, { useState, useCallback, useEffect } from 'react';
import { useChainTemplateStore } from '../../../stores/chainTemplateStore';
import { useProjectStore } from '../../../stores';
import type { ChainTemplate } from '../../../types/chainWorkflow';

/* ═══════════════════════════════════════════════════════════════
   CanvasLeftToolbar — 左侧竖排工具栏 + 展开面板
   ───────────────────────────────────────────────────────────────
   参照 Tapnow/即梦 风格，图标竖排贴左边缘。
   点击图标展开对应功能面板（添加节点、资产、模板、文件管理、图片编辑器）。
   ═══════════════════════════════════════════════════════════════ */

const TOOLBAR_WIDTH = 44;
const PANEL_WIDTH = 380;

type PanelKey = 'addNode' | 'assets' | 'templates' | 'fileManager' | 'imageEditor' | null;

/* ── Icon SVGs ── */
const PlusIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
    <circle cx="10" cy="10" r="9" stroke="currentColor" strokeWidth="1.5" />
    <path d="M10 6v8M6 10h8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

const AssetsIcon = () => (
  <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
    <path d="M9 2L15 6v6l-6 4-6-4V6l6-4z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
    <path d="M9 8v6M3 6l6 4 6-4" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
  </svg>
);

const TemplatesIcon = () => (
  <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
    <rect x="2" y="2" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.3" />
    <rect x="10" y="2" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.3" />
    <rect x="2" y="10" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.3" />
    <rect x="10" y="10" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.3" />
  </svg>
);

const HistoryIcon = () => (
  <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
    <circle cx="9" cy="9" r="7" stroke="currentColor" strokeWidth="1.3" />
    <path d="M9 5v4.5l3 2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const EditorIcon = () => (
  <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
    <rect x="2" y="2" width="14" height="14" rx="2" stroke="currentColor" strokeWidth="1.3" />
    <path d="M6 2v14M2 6h14" stroke="currentColor" strokeWidth="1.3" />
    <circle cx="12" cy="12" r="2.5" stroke="currentColor" strokeWidth="1.3" />
  </svg>
);

const TOOLBAR_ITEMS: Array<{
  key: PanelKey & string;
  Icon: React.FC;
  label: string;
}> = [
  { key: 'addNode', Icon: PlusIcon, label: '添加节点' },
  { key: 'assets', Icon: AssetsIcon, label: '资产' },
  { key: 'templates', Icon: TemplatesIcon, label: '模板' },
  { key: 'fileManager', Icon: HistoryIcon, label: '文件管理' },
  { key: 'imageEditor', Icon: EditorIcon, label: '图片编辑器' },
];

/* ══════════════════════════════════════════════════════════════ */

export function CanvasLeftToolbar() {
  const [activePanel, setActivePanel] = useState<PanelKey>(null);

  const togglePanel = useCallback((key: PanelKey) => {
    setActivePanel((prev) => (prev === key ? null : key));
  }, []);

  return (
    <>
      {/* ── Icon Bar ── */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: '50%',
          transform: 'translateY(-50%)',
          zIndex: 60,
          width: TOOLBAR_WIDTH,
          backgroundColor: 'rgba(17,24,39,0.92)',
          borderRadius: '0 16px 16px 0',
          backdropFilter: 'blur(12px)',
          border: '1px solid rgba(75,85,99,0.35)',
          borderLeft: 'none',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          padding: '12px 0',
          gap: 4,
          boxShadow: '2px 0 16px rgba(0,0,0,0.3)',
          pointerEvents: 'auto',
        }}
      >
        {TOOLBAR_ITEMS.map(({ key, Icon, label }) => {
          const isActive = activePanel === key;
          return (
            <button
              key={key}
              onClick={() => togglePanel(key as PanelKey)}
              title={label}
              style={{
                width: 34,
                height: 34,
                borderRadius: 10,
                border: 'none',
                backgroundColor: isActive ? 'rgba(99,102,241,0.2)' : 'transparent',
                color: isActive ? '#a5b4fc' : '#9ca3af',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'all 0.15s',
                outline: 'none',
              }}
              onMouseEnter={(e) => {
                if (!isActive) e.currentTarget.style.backgroundColor = 'rgba(55,65,81,0.6)';
              }}
              onMouseLeave={(e) => {
                if (!isActive) e.currentTarget.style.backgroundColor = 'transparent';
              }}
            >
              <Icon />
            </button>
          );
        })}

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* User avatar placeholder */}
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: '50%',
            background: 'rgba(75,85,99,0.4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 11,
            fontWeight: 600,
            color: '#9ca3af',
          }}
        >
          U
        </div>
      </div>

      {/* ── Expandable Panel ── */}
      {activePanel && (
        <div
          style={{
            position: 'absolute',
            left: TOOLBAR_WIDTH + 4,
            top: '50%',
            transform: 'translateY(-50%)',
            zIndex: 55,
            width: PANEL_WIDTH,
            maxHeight: '75vh',
            backgroundColor: 'rgba(17,24,39,0.96)',
            borderRadius: 14,
            border: '1px solid rgba(75,85,99,0.35)',
            backdropFilter: 'blur(12px)',
            boxShadow: '4px 4px 24px rgba(0,0,0,0.4)',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            pointerEvents: 'auto',
          }}
        >
          {activePanel === 'addNode' && <AddNodePanel />}
          {activePanel === 'assets' && <AssetsPanel />}
          {activePanel === 'templates' && <TemplatesPanel />}
          {activePanel === 'fileManager' && <FileManagerPanel />}
          {activePanel === 'imageEditor' && <ImageEditorPanel />}
        </div>
      )}

      {/* Backdrop click to close */}
      {activePanel && (
        <div
          onClick={() => setActivePanel(null)}
          style={{
            position: 'absolute',
            inset: 0,
            zIndex: 54,
          }}
        />
      )}
    </>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Panel: 添加节点
   ═══════════════════════════════════════════════════════════════ */

const ADD_NODE_ITEMS = [
  { icon: '📝', label: '文本', desc: '脚本、广告词、品牌文案', type: 'text' },
  { icon: '🖼', label: '图片', desc: '生成或导入图片', type: 'image' },
  { icon: '🎬', label: '视频', desc: '生成或导入视频', type: 'video' },
  { icon: '🔊', label: '音频', desc: '配音、音效、背景音乐', type: 'audio' },
];

function AddNodePanel() {
  return (
    <div style={{ padding: '16px' }}>
      <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 10, letterSpacing: '0.04em' }}>
        添加节点
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {ADD_NODE_ITEMS.map((item) => (
          <div
            key={item.type}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '10px 12px',
              borderRadius: 10,
              cursor: 'pointer',
              transition: 'background 0.15s',
              backgroundColor: 'transparent',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'rgba(55,65,81,0.5)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
          >
            <div style={{
              width: 36,
              height: 36,
              borderRadius: 10,
              background: 'rgba(55,65,81,0.4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 18,
            }}>
              {item.icon}
            </div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 500, color: '#e5e7eb' }}>
                {item.label}
              </div>
              <div style={{ fontSize: 11, color: '#6b7280', marginTop: 1 }}>
                {item.desc}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div style={{ height: 1, background: 'rgba(75,85,99,0.25)', margin: '12px 0' }} />

      <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 8 }}>添加资源</div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '10px 12px',
          borderRadius: 10,
          cursor: 'pointer',
          transition: 'background 0.15s',
        }}
        onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'rgba(55,65,81,0.5)'; }}
        onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
      >
        <div style={{
          width: 36, height: 36, borderRadius: 10,
          background: 'rgba(55,65,81,0.4)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 16, color: '#9ca3af',
        }}>
          ⬆
        </div>
        <div style={{ fontSize: 13, fontWeight: 500, color: '#e5e7eb' }}>上传</div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Panel: 资产
   ═══════════════════════════════════════════════════════════════ */

const ASSET_CATEGORIES = ['全部', '人物', '场景', '物品', '风格', '音效', '其他'];

function AssetsPanel() {
  const [tab, setTab] = useState<'my' | 'public'>('my');
  const [category, setCategory] = useState('全部');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Tab header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '14px 16px 0',
      }}>
        <div style={{ display: 'flex', gap: 16 }}>
          <TabButton active={tab === 'my'} onClick={() => setTab('my')}>我的资产</TabButton>
          <TabButton active={tab === 'public'} onClick={() => setTab('public')}>公共资产</TabButton>
        </div>
        <button style={{
          fontSize: 11, padding: '4px 10px', borderRadius: 8,
          border: '1px solid rgba(99,102,241,0.4)', background: 'rgba(99,102,241,0.1)',
          color: '#a5b4fc', cursor: 'pointer',
        }}>
          ✦ AI角色库
        </button>
      </div>

      {/* Search */}
      <div style={{ padding: '10px 16px' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '7px 12px', borderRadius: 8,
          background: 'rgba(55,65,81,0.3)', border: '1px solid rgba(75,85,99,0.3)',
        }}>
          <span style={{ fontSize: 12, color: '#6b7280' }}>🔍</span>
          <input
            placeholder="搜索资产包..."
            style={{
              flex: 1, background: 'none', border: 'none', outline: 'none',
              fontSize: 12, color: '#e5e7eb',
            }}
          />
        </div>
      </div>

      {/* Category chips */}
      <div style={{ display: 'flex', gap: 6, padding: '0 16px 10px', flexWrap: 'wrap' }}>
        {ASSET_CATEGORIES.map((cat) => (
          <button
            key={cat}
            onClick={() => setCategory(cat)}
            style={{
              padding: '4px 12px', borderRadius: 14, border: 'none', cursor: 'pointer',
              fontSize: 11, fontWeight: 500,
              backgroundColor: category === cat ? '#fff' : 'rgba(55,65,81,0.4)',
              color: category === cat ? '#111' : '#9ca3af',
              transition: 'all 0.15s',
            }}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Content area */}
      <div style={{
        flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '40px 16px', color: '#6b7280', fontSize: 13,
      }}>
        暂无资产
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Panel: 模板 (复用 chainTemplateStore)
   ═══════════════════════════════════════════════════════════════ */

function TemplatesPanel() {
  const [tab, setTab] = useState<'public' | 'my'>('public');
  const { templates, fetchTemplates } = useChainTemplateStore();
  const projectId = useProjectStore((s) => s.project?.id ?? null);

  useEffect(() => {
    if (projectId) fetchTemplates(projectId);
  }, [projectId, fetchTemplates]);

  const builtinTemplates = templates.filter((t) => t.isBuiltin);
  const myTemplates = templates.filter((t) => !t.isBuiltin);
  const displayList = tab === 'public' ? builtinTemplates : myTemplates;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Tab header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '14px 16px 0',
      }}>
        <div style={{ display: 'flex', gap: 16 }}>
          <TabButton active={tab === 'public'} onClick={() => setTab('public')}>公共模板</TabButton>
          <TabButton active={tab === 'my'} onClick={() => setTab('my')}>我的模板</TabButton>
        </div>
        <button style={{
          fontSize: 14, color: '#6b7280', background: 'none', border: 'none',
          cursor: 'pointer', padding: '2px 6px',
        }}>
          ⛶
        </button>
      </div>

      {/* Search */}
      <div style={{ padding: '10px 16px' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '7px 12px', borderRadius: 8,
          background: 'rgba(55,65,81,0.3)', border: '1px solid rgba(75,85,99,0.3)',
        }}>
          <span style={{ fontSize: 12, color: '#6b7280' }}>🔍</span>
          <input
            placeholder="搜索资产包..."
            style={{
              flex: 1, background: 'none', border: 'none', outline: 'none',
              fontSize: 12, color: '#e5e7eb',
            }}
          />
        </div>
      </div>

      {/* Template grid */}
      <div style={{
        flex: 1, overflowY: 'auto', padding: '0 16px 16px',
        display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10,
        alignContent: 'start',
      }}>
        {displayList.length === 0 ? (
          <div style={{
            gridColumn: 'span 2', textAlign: 'center',
            padding: '40px 0', color: '#6b7280', fontSize: 13,
          }}>
            {tab === 'my' ? '暂无自定义模板' : '暂无公共模板'}
          </div>
        ) : (
          displayList.map((tpl) => (
            <TemplateCard key={tpl.id} template={tpl} />
          ))
        )}
      </div>
    </div>
  );
}

function TemplateCard({ template }: { template: ChainTemplate }) {
  return (
    <div
      style={{
        borderRadius: 10,
        overflow: 'hidden',
        cursor: 'pointer',
        transition: 'transform 0.15s',
        background: 'rgba(55,65,81,0.3)',
        border: '1px solid rgba(75,85,99,0.25)',
      }}
      onMouseEnter={(e) => { e.currentTarget.style.transform = 'scale(1.02)'; }}
      onMouseLeave={(e) => { e.currentTarget.style.transform = 'scale(1)'; }}
    >
      {/* Color banner */}
      <div style={{
        height: 80,
        background: `linear-gradient(135deg, ${template.color}33, ${template.color}11)`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 28,
      }}>
        {template.icon}
      </div>
      <div style={{ padding: '8px 10px' }}>
        <div style={{ fontSize: 12, fontWeight: 500, color: '#e5e7eb', lineHeight: 1.3 }}>
          {template.name}
        </div>
        <div style={{ fontSize: 10, color: '#6b7280', marginTop: 3 }}>
          {template.steps.length} 步骤 · ~{template.estimatedMinutes}分钟
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Panel: 文件管理
   ═══════════════════════════════════════════════════════════════ */

function FileManagerPanel() {
  const [tab, setTab] = useState<'images' | 'videos'>('images');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Tab header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '14px 16px 0',
      }}>
        <div style={{ display: 'flex', gap: 16 }}>
          <TabButton active={tab === 'images'} onClick={() => setTab('images')}>图片历史</TabButton>
          <TabButton active={tab === 'videos'} onClick={() => setTab('videos')}>视频历史</TabButton>
        </div>
        <button style={{
          fontSize: 14, color: '#6b7280', background: 'none', border: 'none',
          cursor: 'pointer', padding: '2px 6px',
        }}>
          ⛶
        </button>
      </div>

      {/* Content */}
      <div style={{
        flex: 1, padding: '16px', display: 'flex',
        alignItems: 'center', justifyContent: 'center',
        color: '#6b7280', fontSize: 13,
      }}>
        {tab === 'images' ? '暂无图片历史' : '暂无视频历史'}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Panel: 图片编辑器
   ═══════════════════════════════════════════════════════════════ */

const EDITOR_TOOLS = [
  { icon: '🖼', label: '图片编辑器节点', desc: '编辑和处理图片', highlight: true },
  { icon: '🧍', label: '姿势生成器', desc: '' },
  { icon: '🎨', label: '涂鸦生视频', desc: '' },
  { icon: '✏️', label: '涂鸦生图', desc: '' },
];

function ImageEditorPanel() {
  return (
    <div style={{ padding: '16px' }}>
      <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 10, letterSpacing: '0.04em' }}>
        高级编辑
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {EDITOR_TOOLS.map((tool) => (
          <div
            key={tool.label}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '10px 12px',
              borderRadius: 10,
              cursor: 'pointer',
              backgroundColor: tool.highlight ? 'rgba(99,102,241,0.15)' : 'transparent',
              border: tool.highlight ? '1px solid rgba(99,102,241,0.3)' : '1px solid transparent',
              transition: 'background 0.15s',
            }}
            onMouseEnter={(e) => {
              if (!tool.highlight) e.currentTarget.style.backgroundColor = 'rgba(55,65,81,0.5)';
            }}
            onMouseLeave={(e) => {
              if (!tool.highlight) e.currentTarget.style.backgroundColor = 'transparent';
            }}
          >
            <div style={{
              width: 36, height: 36, borderRadius: 10,
              background: tool.highlight ? 'rgba(99,102,241,0.2)' : 'rgba(55,65,81,0.4)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 18,
            }}>
              {tool.icon}
            </div>
            <div>
              <div style={{
                fontSize: 13, fontWeight: 500,
                color: tool.highlight ? '#c7d2fe' : '#e5e7eb',
              }}>
                {tool.label}
              </div>
              {tool.desc && (
                <div style={{ fontSize: 11, color: '#6b7280', marginTop: 1 }}>
                  {tool.desc}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Shared: Tab button
   ═══════════════════════════════════════════════════════════════ */

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        fontSize: 13,
        fontWeight: active ? 600 : 400,
        color: active ? '#f3f4f6' : '#6b7280',
        background: 'none',
        border: 'none',
        borderBottom: active ? '2px solid #f3f4f6' : '2px solid transparent',
        cursor: 'pointer',
        paddingBottom: 8,
        transition: 'all 0.15s',
      }}
    >
      {children}
    </button>
  );
}

export default CanvasLeftToolbar;
