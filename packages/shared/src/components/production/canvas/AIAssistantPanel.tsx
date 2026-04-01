'use client';

// ══════════════════════════════════════════════════════════════
// AIAssistantPanel.tsx — Tapnow 式右侧 AI 助手面板
// ══════════════════════════════════════════════════════════════

import { memo, useRef, useEffect, useState, useCallback } from 'react';
import { useCanvasStore } from '../../../stores/canvasStore';
import { useProjectStore } from '../../../stores/projectStore';
import { fetchAPI } from '../../../lib/api';

// SSE stream helper (raw fetch, since fetchAPIStream doesn't parse SSE events)
const API_BASE_URL = 'http://localhost:8000';

async function fetchSSE(
  endpoint: string,
  body: Record<string, unknown>,
  onEvent: (evt: { type: string; content?: string; message?: string }) => void,
) {
  const res = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);

  const reader = res.body?.getReader();
  if (!reader) throw new Error('No stream');
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try { onEvent(JSON.parse(line.slice(6))); } catch { /* skip */ }
      }
    }
  }
}

function AIAssistantPanelComponent() {
  const aiPanelOpen = useCanvasStore((s) => s.aiPanelOpen);
  const setAIPanelOpen = useCanvasStore((s) => s.setAIPanelOpen);
  const aiMessages = useCanvasStore((s) => s.aiMessages);
  const addAIMessage = useCanvasStore((s) => s.addAIMessage);
  const appendToLastAIMessage = useCanvasStore((s) => s.appendToLastAIMessage);
  const aiProcessing = useCanvasStore((s) => s.aiProcessing);
  const setAIProcessing = useCanvasStore((s) => s.setAIProcessing);
  const nodes = useCanvasStore((s) => s.nodes);
  const setNodes = useCanvasStore((s) => s.setNodes);

  const scenes = useProjectStore((s) => s.scenes);
  const projectId = useProjectStore((s) => s.project?.id);
  const projectName = useProjectStore((s) => s.project?.name);

  // ── Selected node context ──
  const selectedNodeIds = useCanvasStore((s) => s.selectedNodeIds);
  const inspectedNodeId = useCanvasStore((s) => s.inspectedNodeId);
  const activeNodeId = inspectedNodeId || (selectedNodeIds.length === 1 ? selectedNodeIds[0] : null);
  const activeNode = activeNodeId ? nodes.find((n) => n.id === activeNodeId) : null;
  const activeNodeData = activeNode?.data as { heading?: string; description?: string; coreEvent?: string; nodeType?: string; moduleType?: string; shotNumber?: number } | null;

  const [input, setInput] = useState('');
  const msgEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    msgEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [aiMessages]);

  // ── Send chat message (SSE stream) ──
  const sendChat = useCallback(async (message: string) => {
    if (!message.trim() || aiProcessing) return;
    setInput('');
    addAIMessage({ id: `u-${Date.now()}`, role: 'user', content: message, timestamp: Date.now() });
    addAIMessage({ id: `a-${Date.now()}`, role: 'assistant', content: '', timestamp: Date.now() });
    setAIProcessing(true);

    try {
      const ctx = `项目：${projectName || '未命名'}，共 ${scenes.length} 个场景`;
      await fetchSSE('/api/canvas/agent/chat', {
        message, project_context: ctx, project_id: projectId,
      }, (evt) => {
        if (evt.type === 'text' && evt.content) appendToLastAIMessage(evt.content);
        if (evt.type === 'error') appendToLastAIMessage(`\n[错误] ${evt.message}`);
      });
    } catch (err) {
      appendToLastAIMessage(`\n[连接错误] ${err instanceof Error ? err.message : '未知'}`);
    } finally {
      setAIProcessing(false);
    }
  }, [aiProcessing, projectId, projectName, scenes.length, addAIMessage, appendToLastAIMessage, setAIProcessing]);

  // ── Quick action: batch assign modules ──
  const handleAssignModules = useCallback(async () => {
    if (aiProcessing || scenes.length === 0) return;
    addAIMessage({ id: `u-${Date.now()}`, role: 'user', content: '分析所有场景的模块类型', timestamp: Date.now() });
    addAIMessage({ id: `a-${Date.now()}`, role: 'assistant', content: '正在分析场景类型...', timestamp: Date.now() });
    setAIProcessing(true);

    try {
      const payload = scenes.map((s) => ({
        sceneId: s.id,
        text: s.description || '',
        coreEvent: s.core_event || '',
        heading: s.heading || '',
        location: s.location || '',
        narrativeMode: s.narrative_mode || 'mixed',
        emotionBeat: s.emotion_beat || '',
        dialogueBudget: s.dialogue_budget || 'medium',
        emotionalPeak: s.emotional_peak || '',
        characters: (s.characters_present || []) as string[],
      }));

      const results = await fetchAPI<Array<{ sceneId: string; moduleType: string; reason?: string }>>(
        '/api/canvas/agent/assign-modules',
        { method: 'POST', body: JSON.stringify({ scenes: payload, project_id: projectId }) },
      );

      // Update canvas nodes
      const moduleMap = new Map<string, string>();
      for (const r of results) {
        if (r.sceneId && r.moduleType) moduleMap.set(r.sceneId, r.moduleType);
      }
      if (moduleMap.size > 0) {
        setNodes(nodes.map((n) => {
          const sceneId = (n.data as { sceneId?: string }).sceneId;
          const mt = sceneId ? moduleMap.get(sceneId) : undefined;
          return mt ? { ...n, data: { ...n.data, moduleType: mt } } : n;
        }));
      }

      const labels: Record<string, string> = {
        dialogue: '💬 对话', action: '⚔️ 动作', suspense: '🔍 悬疑',
        landscape: '🏔 转场', emotion: '💭 情感',
      };
      const summary = results.map((r) => {
        const scene = scenes.find((s) => s.id === r.sceneId);
        return `- ${scene?.heading || r.sceneId} → ${labels[r.moduleType] || r.moduleType}${r.reason ? `（${r.reason}）` : ''}`;
      }).join('\n');

      appendToLastAIMessage(`\n\n分析完成！共 ${results.length} 个场景：\n\n${summary}`);
    } catch (err) {
      appendToLastAIMessage(`\n[错误] ${err instanceof Error ? err.message : '分析失败'}`);
    } finally {
      setAIProcessing(false);
    }
  }, [aiProcessing, scenes, nodes, projectId, addAIMessage, appendToLastAIMessage, setAIProcessing, setNodes]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(input); }
  }, [input, sendChat]);

  if (!aiPanelOpen) return null;

  return (
    <div style={{
      position: 'fixed', top: 0, right: 0, bottom: 0,
      width: 340, background: '#0a0f1a', zIndex: 9999,
      display: 'flex', flexDirection: 'column',
      borderLeft: '1px solid rgba(255,255,255,0.06)',
    }}>

      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2">
          <span className="text-base">✦</span>
          <span className="text-[13px] font-medium text-white/80">AI 创作助手</span>
        </div>
        <button onClick={() => setAIPanelOpen(false)}
          className="w-6 h-6 rounded-md flex items-center justify-center text-white/30 hover:text-white/60 hover:bg-white/5 transition-colors">
          ✕
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {aiMessages.length === 0 && (
          <div className="text-center pt-8">
            <div className="text-2xl mb-3">✦</div>
            <div className="text-[15px] font-medium text-white/70 mb-1">Hi!</div>
            <div className="text-[14px] text-white/40 mb-6">今天一起创作点什么？</div>
            <div className="flex flex-wrap gap-2 justify-center">
              <QuickBtn label="◎ 分析所有场景" onClick={handleAssignModules} disabled={aiProcessing} />
              <QuickBtn label="♪ 审核节奏" onClick={() => sendChat('请分析全部场景的叙事节奏，检查情绪曲线、反转密度、爽点分布、钩子-悬念衔接是否合理')} disabled={aiProcessing} />
              <QuickBtn label="⊘ 检查一致性" onClick={() => sendChat('请检查角色、场景、道具的一致性，包括角色外貌是否矛盾、场景衔接是否断裂、母题道具是否在关键时刻出现')} disabled={aiProcessing} />
              <QuickBtn label="✎ 优化对白" onClick={() => sendChat('请优化当前选中场景的对白，控制对白预算，确保每句≤15字，强化潜台词，保持角色性格一致')} disabled={aiProcessing} />
              <QuickBtn label="⚑ 制片预检" onClick={() => sendChat('请对全部场景进行制片预检，检查分镜覆盖度、视觉提示词就绪度、角色锚点完备度，估算生成成本')} disabled={aiProcessing} />
              <QuickBtn label="→ 下一步怎么走" onClick={() => sendChat('根据当前项目状态，下一步应该做什么？')} disabled={aiProcessing} />
            </div>
          </div>
        )}

        {aiMessages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[280px] rounded-xl px-3.5 py-2.5 text-[13px] leading-[1.7] ${
              msg.role === 'user' ? 'bg-indigo-500/20 text-white/80' : 'bg-white/[0.04] text-white/60'
            }`}>
              <div className="whitespace-pre-wrap break-words">{msg.content || (aiProcessing ? '...' : '')}</div>
            </div>
          </div>
        ))}
        <div ref={msgEndRef} />
      </div>

      {/* Quick actions when messages exist */}
      {aiMessages.length > 0 && (
        <div style={{ display: 'flex', gap: 6, padding: '8px 16px', borderTop: '1px solid rgba(255,255,255,0.04)', flexWrap: 'wrap' }}>
          <QuickBtn label="◎ 场景" onClick={handleAssignModules} disabled={aiProcessing} />
          <QuickBtn label="♪ 节奏" onClick={() => sendChat('分析叙事节奏')} disabled={aiProcessing} />
          <QuickBtn label="⊘ 一致性" onClick={() => sendChat('检查一致性')} disabled={aiProcessing} />
          <QuickBtn label="✎ 对白" onClick={() => sendChat('优化对白')} disabled={aiProcessing} />
          <QuickBtn label="⚑ 预检" onClick={() => sendChat('制片预检')} disabled={aiProcessing} />
        </div>
      )}

      {/* Input area — with context card above */}
      <div className="px-3 pb-3">
        {/* Selected node context (above input, like Tapnow's reference area) */}
        {activeNodeData && (
          <div style={{
            marginBottom: 8, borderRadius: 10, padding: '8px 10px',
            background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)',
          }}>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400/80">
                {activeNodeData.nodeType === 'scene' ? 'Scene' : activeNodeData.nodeType === 'shot' ? `Shot #${activeNodeData.shotNumber}` : 'Node'}
              </span>
              {activeNodeData.heading && (
                <span className="text-[11px] text-white/50 truncate flex-1">{activeNodeData.heading}</span>
              )}
            </div>
            <div className="text-[11px] text-white/40 leading-[1.5] line-clamp-2">
              {activeNodeData.coreEvent || activeNodeData.description || ''}
            </div>
          </div>
        )}
        <div className="relative rounded-xl border border-white/[0.08] bg-white/[0.03] overflow-hidden">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="描述操作或引用 @ ..."
            rows={2}
            className="w-full bg-transparent text-[13px] text-white/80 placeholder-white/20 px-3.5 py-3 resize-none focus:outline-none"
          />
          <div className="flex items-center justify-between px-3 pb-2">
            <span className="text-[10px] text-white/15">Shift+Enter 换行</span>
            <button
              onClick={() => sendChat(input)}
              disabled={!input.trim() || aiProcessing}
              className={`w-7 h-7 rounded-full flex items-center justify-center text-[12px] transition-colors ${
                input.trim() && !aiProcessing ? 'bg-indigo-500 text-white hover:bg-indigo-400' : 'bg-white/5 text-white/15'
              }`}
            >↑</button>
          </div>
        </div>
      </div>
    </div>
  );
}

function QuickBtn({ label, onClick, disabled }: { label: string; onClick: () => void; disabled?: boolean }) {
  return (
    <button onClick={onClick} disabled={disabled}
      className="flex items-center gap-1.5 rounded-lg border border-white/[0.08] px-3 py-2 text-[12px] text-white/50 hover:text-white/70 hover:bg-white/[0.04] transition-colors disabled:opacity-30">
      {label}
    </button>
  );
}

export const AIAssistantPanel = memo(AIAssistantPanelComponent);
