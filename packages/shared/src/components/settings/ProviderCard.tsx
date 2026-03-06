'use client';

import { useState } from 'react';
import type { AIProvider } from '../../types/aiProvider';
import { PROVIDER_TYPE_LABELS } from '../../types/aiProvider';
import { useAIProviderStore } from '../../stores/aiProviderStore';

interface ProviderCardProps {
  provider: AIProvider;
  onEdit: (provider: AIProvider) => void;
  t: (key: string) => string;
}

export function ProviderCard({ provider, onEdit, t }: ProviderCardProps) {
  const { deleteProvider, updateProvider, testProvider } = useAIProviderStore();
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await testProvider(provider.id);
      setTestResult(result.success ? t('settings.testSuccess') : result.message);
    } catch {
      setTestResult(t('settings.testFailed'));
    }
    setTesting(false);
  };

  const handleToggle = async () => {
    await updateProvider(provider.id, { enabled: !provider.enabled });
  };

  const handleDelete = async () => {
    if (confirm(t('settings.confirmDelete'))) {
      await deleteProvider(provider.id);
    }
  };

  return (
    <div className={`rounded-lg border p-4 ${provider.enabled ? 'border-white/10 bg-bg-1' : 'border-white/5 bg-bg-1/50 opacity-60'}`}>
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="font-medium text-white">{provider.name}</h3>
          {provider.is_default && (
            <span className="rounded bg-brand/20 px-1.5 py-0.5 text-xs text-brand">{t('settings.default')}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleToggle}
            className={`rounded px-2 py-1 text-xs ${provider.enabled ? 'bg-green-500/20 text-green-400' : 'bg-white/5 text-white/40'}`}
          >
            {provider.enabled ? t('settings.enabled') : t('settings.disabled')}
          </button>
        </div>
      </div>

      <div className="mb-3 space-y-1 text-xs text-white/50">
        <div>{t('settings.type')}: {PROVIDER_TYPE_LABELS[provider.provider_type]}</div>
        <div>{t('settings.models')}: {(provider.models || []).length}</div>
        <div>{t('settings.apiKey')}: {provider.api_key_masked}</div>
        <div>{t('settings.priority')}: {provider.priority}</div>
      </div>

      {/* Model list */}
      {provider.models && provider.models.length > 0 && (
        <div className="mb-3 space-y-1">
          {provider.models.map((m) => (
            <div key={m.model_id} className="flex items-center gap-2 text-xs text-white/40">
              <span className="rounded bg-white/5 px-1.5 py-0.5">{m.capability_tier}</span>
              <span>{m.display_name || m.model_id}</span>
            </div>
          ))}
        </div>
      )}

      {testResult && (
        <div className={`mb-3 rounded p-2 text-xs ${testResult === t('settings.testSuccess') ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
          {testResult}
        </div>
      )}

      <div className="flex gap-2">
        <button type="button" onClick={handleTest} disabled={testing} className="rounded bg-white/5 px-3 py-1.5 text-xs text-white/70 hover:bg-white/10">
          {testing ? t('settings.testing') : t('settings.testConnection')}
        </button>
        <button type="button" onClick={() => onEdit(provider)} className="rounded bg-white/5 px-3 py-1.5 text-xs text-white/70 hover:bg-white/10">
          {t('settings.edit')}
        </button>
        <button type="button" onClick={handleDelete} className="rounded bg-red-500/10 px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/20">
          {t('settings.delete')}
        </button>
      </div>
    </div>
  );
}
