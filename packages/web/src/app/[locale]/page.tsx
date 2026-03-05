'use client';

import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { useEdition } from '@novelflow/shared/hooks';
import { Edition, EDITION_ORDER } from '@novelflow/shared/types';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';

const EDITION_KEYS: Record<Edition, string> = {
  [Edition.NORMAL]: 'normal',
  [Edition.CANVAS]: 'canvas',
  [Edition.HIDDEN]: 'hidden',
  [Edition.ULTIMATE]: 'ultimate',
};

export default function HomePage() {
  const router = useRouter();
  const { edition, setEdition } = useEdition();
  const t = useTranslations();

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-bg-0 px-4">
      {/* Language switcher */}
      <div className="absolute right-4 top-4">
        <LanguageSwitcher />
      </div>

      {/* Header */}
      <div className="mb-12 text-center">
        <h1 className="mb-2 text-3xl font-bold text-white">
          Novel<span className="text-brand">Flow</span>
        </h1>
        <p className="text-sm text-white/50">
          {t('common.tagline')}
        </p>
      </div>

      {/* Edition Switcher */}
      <div className="mb-8 flex gap-2 rounded-full bg-bg-1 p-1">
        {EDITION_ORDER.map((ed) => (
          <button
            key={ed}
            type="button"
            onClick={() => setEdition(ed)}
            className={`rounded-full px-4 py-1.5 text-sm font-medium transition-all ${
              edition === ed
                ? 'brand-gradient text-white shadow-lg'
                : 'text-white/50 hover:text-white/80'
            }`}
          >
            {t(`editions.${EDITION_KEYS[ed]}`)}
          </button>
        ))}
      </div>

      {/* Current edition info */}
      <p className="mb-8 text-xs text-white/30">
        {t(`editions.${EDITION_KEYS[edition]}Desc`)}
      </p>

      {/* Create Project Button */}
      <button
        type="button"
        onClick={() => router.push('/projects/new')}
        className="brand-gradient rounded-lg px-8 py-3 text-base font-semibold text-white shadow-lg shadow-brand/25 transition-all hover:shadow-xl hover:shadow-brand/30 active:scale-[0.98]"
      >
        {t('common.createProject')}
      </button>

      {/* Footer */}
      <div className="mt-16 text-xs text-white/20">
        {t('common.version')}
      </div>
    </div>
  );
}
