'use client';

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { API_BASE_URL } from '../../lib/api';

interface AIAssistantProps {
  projectId: string;
  onAIAction?: (action: string, text: string) => void;
}

export function AIAssistant({ projectId, onAIAction }: AIAssistantProps) {
  const [streaming, setStreaming] = useState(false);
  const [result, setResult] = useState('');
  const [inputText, setInputText] = useState('');
  const resultRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (resultRef.current) {
      resultRef.current.scrollTop = resultRef.current.scrollHeight;
    }
  }, [result]);

  const handleAction = useCallback(
    async (action: string) => {
      if (!inputText.trim() || streaming) return;
      setStreaming(true);
      setResult('');

      try {
        const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/ai/operate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text: inputText,
            operation: action,
          }),
        });

        if (!response.ok) {
          const err = await response.json().catch(() => ({ detail: 'Unknown error' }));
          setResult(`Error: ${err.detail}`);
          return;
        }

        const reader = response.body?.getReader();
        if (!reader) return;

        const decoder = new TextDecoder();
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const text = decoder.decode(value, { stream: true });
          // Parse SSE
          const lines = text.split('\n');
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                if (data.type === 'text') {
                  setResult((prev) => prev + data.content);
                } else if (data.type === 'error') {
                  setResult((prev) => prev + `\n[Error: ${data.message}]`);
                }
              } catch {
                // ignore parse errors in SSE
              }
            }
          }
        }
      } catch (err) {
        setResult(`连接错误: ${err instanceof Error ? err.message : 'Unknown'}`);
      } finally {
        setStreaming(false);
      }
    },
    [inputText, projectId, streaming],
  );

  const actions = [
    { id: 'rewrite', label: '改写', icon: '✎' },
    { id: 'expand', label: '扩写', icon: '↔' },
    { id: 'condense', label: '缩写', icon: '→←' },
    { id: 'dialogue_optimize', label: '对话优化', icon: '💬' },
  ];

  return (
    <div className="flex h-full flex-col p-4">
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-white/30">
        AI 助手
      </h3>

      {/* Input area */}
      <textarea
        value={inputText}
        onChange={(e) => setInputText(e.target.value)}
        placeholder="粘贴或输入需要 AI 处理的文本..."
        className="mb-3 h-32 w-full resize-none rounded-lg border border-white/[0.06] bg-bg-0/50 p-3 text-sm text-white/80 outline-none placeholder:text-white/20 focus:border-indigo-500/30"
      />

      {/* Quick Actions */}
      <div className="mb-3 grid grid-cols-2 gap-2">
        {actions.map((action) => (
          <button
            key={action.id}
            type="button"
            onClick={() => handleAction(action.id)}
            disabled={streaming || !inputText.trim()}
            className="rounded-lg border border-white/[0.06] bg-bg-1 px-3 py-2 text-xs text-white/60 transition-colors hover:border-indigo-500/30 hover:text-indigo-400 disabled:opacity-40"
          >
            {action.label}
          </button>
        ))}
      </div>

      {/* Result area */}
      {(result || streaming) && (
        <div
          ref={resultRef}
          className="flex-1 overflow-auto rounded-lg border border-white/[0.06] bg-bg-0/50 p-3"
        >
          <div className="mb-2 flex items-center gap-2">
            <span className="text-xs text-white/30">AI 输出</span>
            {streaming && (
              <span className="h-2 w-2 animate-pulse rounded-full bg-indigo-500" />
            )}
          </div>
          <div className="whitespace-pre-wrap text-sm leading-relaxed text-white/70">
            {result}
          </div>
        </div>
      )}
    </div>
  );
}
