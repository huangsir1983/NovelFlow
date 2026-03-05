'use client';

import { useLocale, useTranslations } from 'next-intl';
import { useRouter, usePathname } from '@/i18n/navigation';
import { useTransition } from 'react';
import type { Locale } from '@/i18n/config';

export function LanguageSwitcher() {
  const locale = useLocale() as Locale;
  const t = useTranslations('lang');
  const router = useRouter();
  const pathname = usePathname();
  const [isPending, startTransition] = useTransition();

  const switchLocale = () => {
    const nextLocale: Locale = locale === 'zh' ? 'en' : 'zh';
    startTransition(() => {
      router.replace(pathname, { locale: nextLocale });
    });
  };

  return (
    <button
      type="button"
      onClick={switchLocale}
      disabled={isPending}
      className="rounded-md px-2.5 py-1 text-xs font-medium text-white/50 transition-colors hover:bg-white/5 hover:text-white/80 disabled:opacity-50"
      aria-label={t('label')}
    >
      {t('switchTo')}
    </button>
  );
}
