'use client';

import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { AIProviderSettings } from '@unrealmake/shared/components';

export default function SettingsPage() {
  const router = useRouter();
  const t = useTranslations();

  return (
    <div className="min-h-screen bg-bg-0 px-4 py-8">
      <div className="mx-auto max-w-2xl">
        {/* Header */}
        <div className="mb-8 flex items-center gap-4">
          <button
            type="button"
            onClick={() => router.back()}
            className="rounded-lg bg-white/5 p-2 text-white/60 hover:bg-white/10 hover:text-white"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M12.5 15L7.5 10L12.5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
          <h1 className="text-2xl font-bold text-white">{t('settings.title')}</h1>
        </div>

        {/* AI Provider Settings */}
        <AIProviderSettings t={t} />
      </div>
    </div>
  );
}
