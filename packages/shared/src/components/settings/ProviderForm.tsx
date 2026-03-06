'use client';

import { useState, useEffect } from 'react';
import type {
  AIProvider,
  AIProviderCreateInput,
  AIModelConfig,
  ProviderType,
} from '../../types/aiProvider';
import {
  PROVIDER_TYPE_LABELS,
  DEFAULT_BASE_URLS,
  CAPABILITY_TIER_LABELS,
} from '../../types/aiProvider';
import { useAIProviderStore } from '../../stores/aiProviderStore';

interface ProviderFormProps {
  editingProvider: AIProvider | null;
  onClose: () => void;
  t: (key: string) => string;
}

const EMPTY_MODEL: AIModelConfig = {
  model_id: '',
  display_name: '',
  capability_tier: 'standard',
  max_tokens: 4096,
  supports_streaming: true,
  supports_image: false,
};

export function ProviderForm({ editingProvider, onClose, t }: ProviderFormProps) {
  const { createProvider, updateProvider } = useAIProviderStore();

  const [name, setName] = useState('');
  const [providerType, setProviderType] = useState<ProviderType>('gemini');
  const [baseUrl, setBaseUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [models, setModels] = useState<AIModelConfig[]>([{ ...EMPTY_MODEL }]);
  const [isDefault, setIsDefault] = useState(false);
  const [priority, setPriority] = useState(10);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (editingProvider) {
      setName(editingProvider.name);
      setProviderType(editingProvider.provider_type);
      setBaseUrl(editingProvider.base_url);
      setApiKey('');
      setModels(editingProvider.models.length > 0 ? editingProvider.models : [{ ...EMPTY_MODEL }]);
      setIsDefault(editingProvider.is_default);
      setPriority(editingProvider.priority);
    }
  }, [editingProvider]);

  const handleTypeChange = (type: ProviderType) => {
    setProviderType(type);
    if (!editingProvider) {
      setBaseUrl(DEFAULT_BASE_URLS[type]);
    }
  };

  const handleModelChange = (index: number, field: keyof AIModelConfig, value: unknown) => {
    const updated = [...models];
    updated[index] = { ...updated[index], [field]: value };
    setModels(updated);
  };

  const addModel = () => setModels([...models, { ...EMPTY_MODEL }]);

  const removeModel = (index: number) => {
    if (models.length > 1) {
      setModels(models.filter((_, i) => i !== index));
    }
  };

  const handleSubmit = async () => {
    if (!name.trim()) return;
    setSaving(true);

    try {
      const validModels = models.filter((m) => m.model_id.trim());
      if (editingProvider) {
        const updateData: Record<string, unknown> = {
          name,
          provider_type: providerType,
          base_url: baseUrl,
          models: validModels,
          is_default: isDefault,
          priority,
        };
        if (apiKey) {
          updateData.api_key = apiKey;
        }
        await updateProvider(editingProvider.id, updateData);
      } else {
        const input: AIProviderCreateInput = {
          name,
          provider_type: providerType,
          base_url: baseUrl,
          api_key: apiKey,
          models: validModels,
          is_default: isDefault,
          enabled: true,
          priority,
        };
        await createProvider(input);
      }
      onClose();
    } catch (e) {
      console.error('Failed to save provider:', e);
    }
    setSaving(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-lg bg-bg-0 p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-semibold text-white">
          {editingProvider ? t('settings.editProvider') : t('settings.addProvider')}
        </h2>

        <div className="space-y-4">
          {/* Provider Type */}
          <div>
            <label className="mb-1 block text-xs text-white/50">{t('settings.providerType')}</label>
            <div className="flex gap-2">
              {(Object.keys(PROVIDER_TYPE_LABELS) as ProviderType[]).map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => handleTypeChange(type)}
                  className={`rounded px-3 py-1.5 text-sm ${providerType === type ? 'bg-brand text-white' : 'bg-white/5 text-white/60 hover:bg-white/10'}`}
                >
                  {PROVIDER_TYPE_LABELS[type]}
                </button>
              ))}
            </div>
          </div>

          {/* Name */}
          <div>
            <label className="mb-1 block text-xs text-white/50">{t('settings.providerName')}</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t('settings.providerNamePlaceholder')}
              className="w-full rounded bg-white/5 px-3 py-2 text-sm text-white outline-none focus:ring-1 focus:ring-brand"
            />
          </div>

          {/* Base URL */}
          <div>
            <label className="mb-1 block text-xs text-white/50">Base URL</label>
            <input
              type="text"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://..."
              className="w-full rounded bg-white/5 px-3 py-2 text-sm text-white outline-none focus:ring-1 focus:ring-brand"
            />
          </div>

          {/* API Key */}
          <div>
            <label className="mb-1 block text-xs text-white/50">
              API Key {editingProvider && <span className="text-white/30">({t('settings.leaveBlank')})</span>}
            </label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={editingProvider ? '••••••••' : 'sk-...'}
              className="w-full rounded bg-white/5 px-3 py-2 text-sm text-white outline-none focus:ring-1 focus:ring-brand"
            />
          </div>

          {/* Models */}
          <div>
            <label className="mb-2 block text-xs text-white/50">{t('settings.models')}</label>
            <div className="space-y-3">
              {models.map((model, index) => (
                <div key={index} className="rounded border border-white/5 bg-white/[0.02] p-3">
                  <div className="mb-2 flex gap-2">
                    <input
                      type="text"
                      value={model.model_id}
                      onChange={(e) => handleModelChange(index, 'model_id', e.target.value)}
                      placeholder="model-id"
                      className="flex-1 rounded bg-white/5 px-2 py-1.5 text-xs text-white outline-none"
                    />
                    <input
                      type="text"
                      value={model.display_name}
                      onChange={(e) => handleModelChange(index, 'display_name', e.target.value)}
                      placeholder={t('settings.displayName')}
                      className="flex-1 rounded bg-white/5 px-2 py-1.5 text-xs text-white outline-none"
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <select
                      value={model.capability_tier}
                      onChange={(e) => handleModelChange(index, 'capability_tier', e.target.value)}
                      className="rounded bg-white/5 px-2 py-1.5 text-xs text-white outline-none"
                    >
                      {Object.entries(CAPABILITY_TIER_LABELS).map(([k, v]) => (
                        <option key={k} value={k}>{v}</option>
                      ))}
                    </select>
                    <label className="flex items-center gap-1 text-xs text-white/50">
                      <input
                        type="checkbox"
                        checked={model.supports_image}
                        onChange={(e) => handleModelChange(index, 'supports_image', e.target.checked)}
                      />
                      {t('settings.imageSupport')}
                    </label>
                    {models.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeModel(index)}
                        className="ml-auto text-xs text-red-400 hover:text-red-300"
                      >
                        {t('settings.removeModel')}
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
            <button
              type="button"
              onClick={addModel}
              className="mt-2 rounded bg-white/5 px-3 py-1 text-xs text-white/60 hover:bg-white/10"
            >
              + {t('settings.addModel')}
            </button>
          </div>

          {/* Priority + Default */}
          <div className="flex gap-4">
            <div className="flex-1">
              <label className="mb-1 block text-xs text-white/50">{t('settings.priority')}</label>
              <input
                type="number"
                value={priority}
                onChange={(e) => setPriority(Number(e.target.value))}
                min={0}
                className="w-full rounded bg-white/5 px-3 py-2 text-sm text-white outline-none"
              />
            </div>
            <div className="flex items-end">
              <label className="flex items-center gap-2 pb-2 text-xs text-white/60">
                <input
                  type="checkbox"
                  checked={isDefault}
                  onChange={(e) => setIsDefault(e.target.checked)}
                />
                {t('settings.setDefault')}
              </label>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded bg-white/5 px-4 py-2 text-sm text-white/60 hover:bg-white/10"
          >
            {t('settings.cancel')}
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={saving || !name.trim()}
            className="brand-gradient rounded px-4 py-2 text-sm font-medium text-white shadow disabled:opacity-50"
          >
            {saving ? t('settings.saving') : t('settings.save')}
          </button>
        </div>
      </div>
    </div>
  );
}
