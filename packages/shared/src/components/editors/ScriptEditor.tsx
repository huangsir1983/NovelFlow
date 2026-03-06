'use client';

import React, { useState, useRef, useCallback } from 'react';

interface ScriptEditorProps {
  content: string;
  onChange?: (content: string) => void;
  onAIAction?: (action: string, selectedText: string) => void;
  readOnly?: boolean;
  placeholder?: string;
}

export function ScriptEditor({
  content,
  onChange,
  onAIAction,
  readOnly = false,
  placeholder = '开始编写你的场景...',
}: ScriptEditorProps) {
  const [selectedText, setSelectedText] = useState('');
  const [showToolbar, setShowToolbar] = useState(false);
  const [toolbarPos, setToolbarPos] = useState({ x: 0, y: 0 });
  const editorRef = useRef<HTMLTextAreaElement>(null);

  const handleSelect = useCallback(() => {
    const editor = editorRef.current;
    if (!editor) return;

    const selected = editor.value.substring(editor.selectionStart, editor.selectionEnd);
    if (selected.trim()) {
      setSelectedText(selected);
      // Position toolbar near selection
      const rect = editor.getBoundingClientRect();
      setToolbarPos({
        x: Math.min(rect.width - 200, Math.max(0, (editor.selectionStart / editor.value.length) * rect.width)),
        y: -40,
      });
      setShowToolbar(true);
    } else {
      setShowToolbar(false);
      setSelectedText('');
    }
  }, []);

  const aiActions = [
    { id: 'rewrite', label: '改写' },
    { id: 'expand', label: '扩写' },
    { id: 'condense', label: '缩写' },
    { id: 'dialogue_optimize', label: '对话优化' },
  ];

  return (
    <div className="relative h-full">
      {/* AI Floating Toolbar */}
      {showToolbar && onAIAction && (
        <div
          className="absolute z-10 flex gap-1 rounded-lg border border-white/10 bg-bg-2 p-1 shadow-lg"
          style={{ left: toolbarPos.x, top: toolbarPos.y }}
        >
          {aiActions.map((action) => (
            <button
              key={action.id}
              type="button"
              onClick={() => {
                onAIAction(action.id, selectedText);
                setShowToolbar(false);
              }}
              className="rounded-md px-3 py-1.5 text-xs text-white/70 transition-colors hover:bg-indigo-500/20 hover:text-indigo-400"
            >
              {action.label}
            </button>
          ))}
        </div>
      )}

      {/* Editor */}
      <textarea
        ref={editorRef}
        value={content}
        onChange={(e) => onChange?.(e.target.value)}
        onSelect={handleSelect}
        onBlur={() => setTimeout(() => setShowToolbar(false), 200)}
        readOnly={readOnly}
        placeholder={placeholder}
        className="h-full w-full resize-none bg-transparent p-6 font-mono text-sm leading-relaxed text-white/80 outline-none placeholder:text-white/20"
        spellCheck={false}
      />
    </div>
  );
}
