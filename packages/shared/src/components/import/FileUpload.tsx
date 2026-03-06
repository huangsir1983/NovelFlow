'use client';

import React, { useCallback, useState, useRef } from 'react';

interface FileUploadProps {
  accept?: string;
  maxSizeMB?: number;
  onFileSelect: (file: File) => void;
  disabled?: boolean;
  label?: string;
  hint?: string;
}

export function FileUpload({
  accept = '.txt,.md,.docx,.epub,.pdf',
  maxSizeMB = 50,
  onFileSelect,
  disabled = false,
  label = '拖拽文件到此处，或点击上传',
  hint = '支持 TXT / MD / DOCX / EPUB / PDF',
}: FileUploadProps) {
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateAndSelect = useCallback(
    (file: File) => {
      setError(null);
      const maxBytes = maxSizeMB * 1024 * 1024;
      if (file.size > maxBytes) {
        setError(`文件过大，最大 ${maxSizeMB}MB`);
        return;
      }
      const ext = file.name.split('.').pop()?.toLowerCase() || '';
      const allowed = accept.split(',').map((s) => s.trim().replace('.', ''));
      if (!allowed.includes(ext)) {
        setError(`不支持的格式: .${ext}`);
        return;
      }
      onFileSelect(file);
    },
    [accept, maxSizeMB, onFileSelect],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      if (disabled) return;
      const file = e.dataTransfer.files[0];
      if (file) validateAndSelect(file);
    },
    [disabled, validateAndSelect],
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) validateAndSelect(file);
    },
    [validateAndSelect],
  );

  return (
    <div
      className={`
        relative cursor-pointer rounded-xl border-2 border-dashed p-12 text-center transition-all
        ${dragOver ? 'border-indigo-500 bg-indigo-500/10' : 'border-white/10 hover:border-white/20'}
        ${disabled ? 'pointer-events-none opacity-50' : ''}
      `}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        onChange={handleChange}
        className="hidden"
        disabled={disabled}
      />
      <div className="mb-3 text-4xl text-white/20">
        <svg className="mx-auto h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
      </div>
      <p className="mb-1 text-sm text-white/60">{label}</p>
      <p className="text-xs text-white/30">{hint}</p>
      {error && <p className="mt-3 text-sm text-error">{error}</p>}
    </div>
  );
}
