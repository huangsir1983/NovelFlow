'use client';

import { useEffect, useState } from 'react';
import type { AIProvider } from '../../types/aiProvider';
import { useAIProviderStore } from '../../stores/aiProviderStore';
import { ProviderCard } from './ProviderCard';
import { ProviderForm } from './ProviderForm';

interface AIProviderSettingsProps {
  t: (key: string) => string;
}

export function AIProviderSettings({ t }: AIProviderSettingsProps) {
  const { providers, loading, error, fetchProviders } = useAIProviderStore();
  const [showForm, setShowForm] = useState(false);
  const [editingProvider, setEditingProvider] = useState<AIProvider | null>(null);

  useEffect(() => {
    fetchProviders();
  }, [fetchProviders]);

  const handleEdit = (provider: AIProvider) => {
    setEditingProvider(provider);
    setShowForm(true);
  };

  const handleAdd = () => {
    setEditingProvider(null);
    setShowForm(true);
  };

  const handleCloseForm = () => {
    setShowForm(false);
    setEditingProvider(null);
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-white">{t('settings.aiProviders')}</h2>
          <p className="mt-1 text-xs text-white/40">{t('settings.aiProvidersDesc')}</p>
        </div>
        <button
          type="button"
          onClick={handleAdd}
          className="brand-gradient rounded-lg px-4 py-2 text-sm font-medium text-white shadow"
        >
          {t('settings.addProvider')}
        </button>
      </div>

      {loading && <div className="text-center text-sm text-white/40">{t('common.loading')}</div>}
      {error && <div className="rounded bg-red-500/10 p-3 text-sm text-red-400">{error}</div>}

      {!loading && providers.length === 0 && (
        <div className="rounded-lg border border-dashed border-white/10 p-8 text-center">
          <p className="text-sm text-white/40">{t('settings.noProviders')}</p>
          <p className="mt-1 text-xs text-white/20">{t('settings.noProvidersHint')}</p>
        </div>
      )}

      <div className="grid gap-4">
        {providers.map((provider) => (
          <ProviderCard key={provider.id} provider={provider} onEdit={handleEdit} t={t} />
        ))}
      </div>

      {showForm && (
        <ProviderForm editingProvider={editingProvider} onClose={handleCloseForm} t={t} />
      )}
    </div>
  );
}
