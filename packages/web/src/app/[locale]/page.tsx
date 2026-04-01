'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { useEdition } from '@unrealmake/shared/hooks';
import { Edition, EDITION_ORDER, Project } from '@unrealmake/shared/types';
import { fetchAPI } from '@unrealmake/shared/lib/api';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';

const EDITION_KEYS: Record<Edition, string> = {
  [Edition.NORMAL]: 'normal',
  [Edition.CANVAS]: 'canvas',
  [Edition.HIDDEN]: 'hidden',
  [Edition.ULTIMATE]: 'ultimate',
};

function timeAgo(dateStr: string, locale: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = now - then;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return locale === 'zh' ? '刚刚' : 'just now';
  if (mins < 60) return locale === 'zh' ? `${mins} 分钟前` : `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return locale === 'zh' ? `${hours} 小时前` : `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return locale === 'zh' ? `${days} 天前` : `${days}d ago`;
  const months = Math.floor(days / 30);
  return locale === 'zh' ? `${months} 个月前` : `${months}mo ago`;
}

export default function HomePage() {
  const router = useRouter();
  const { edition, setEdition } = useEdition();
  const t = useTranslations();

  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAPI<Project[]>('/api/projects')
      .then(setProjects)
      .catch(() => setProjects([]))
      .finally(() => setLoading(false));
  }, []);

  const handleDelete = async (proj: Project) => {
    if (!confirm(t('common.confirmDeleteProject', { name: proj.name }))) return;
    try {
      await fetchAPI(`/api/projects/${proj.id}`, { method: 'DELETE' });
      setProjects((prev) => prev.filter((p) => p.id !== proj.id));
    } catch {
      // ignore
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center bg-bg-0 px-4 pt-16">
      {/* Language switcher & Settings */}
      <div className="absolute right-4 top-4 flex items-center gap-2">
        <button
          type="button"
          onClick={() => router.push('/settings')}
          className="rounded-lg p-2 text-white/40 transition-colors hover:bg-white/5 hover:text-white/80"
          title={t('settings.title')}
        >
          <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
            <path d="M10 12.5C11.3807 12.5 12.5 11.3807 12.5 10C12.5 8.61929 11.3807 7.5 10 7.5C8.61929 7.5 7.5 8.61929 7.5 10C7.5 11.3807 8.61929 12.5 10 12.5Z" stroke="currentColor" strokeWidth="1.5" />
            <path d="M16.0667 12.3333C15.9482 12.5994 15.9131 12.8952 15.9661 13.1819C16.0191 13.4687 16.1576 13.7329 16.3633 13.94L16.4067 13.9833C16.5722 14.1487 16.7036 14.3453 16.7935 14.5614C16.8834 14.7776 16.9299 15.0091 16.9305 15.2429C16.931 15.4767 16.8856 15.7084 16.7967 15.925C16.7078 16.1416 16.5773 16.3389 16.4125 16.505C16.2477 16.6711 16.0514 16.8029 15.8355 16.8933C15.6196 16.9837 15.3882 17.0307 15.1544 17.0318C14.9206 17.0328 14.6888 16.9879 14.4722 16.8995C14.2556 16.811 14.0582 16.681 13.8917 16.5167L13.8483 16.4733C13.6413 16.2676 13.377 16.1291 13.0903 16.0761C12.8036 16.0231 12.5078 16.0582 12.2417 16.1767C11.9808 16.2896 11.7587 16.4749 11.6014 16.7111C11.4441 16.9473 11.3582 17.224 11.3533 17.5083V17.6667C11.3533 18.1087 11.1777 18.5326 10.8651 18.8452C10.5526 19.1577 10.1287 19.3333 9.68667 19.3333C9.24464 19.3333 8.82072 19.1577 8.50816 18.8452C8.1956 18.5326 8.02 18.1087 8.02 17.6667V17.5833C8.00939 17.2915 7.91416 17.009 7.74593 16.7712C7.57769 16.5334 7.34394 16.3509 7.07333 16.2467C6.80724 16.1282 6.51145 16.0931 6.22471 16.1461C5.93798 16.1991 5.67374 16.3376 5.46667 16.5433L5.42333 16.5867C5.25689 16.751 5.05944 16.881 4.84286 16.9695C4.62627 17.058 4.39448 17.1028 4.16067 17.1018C3.92686 17.1007 3.6955 17.0537 3.47959 16.9633C3.26368 16.8729 3.06711 16.7411 2.90167 16.575C2.73622 16.4089 2.60566 16.2116 2.51672 15.995C2.42778 15.7784 2.38217 15.5467 2.38326 15.3129C2.38434 15.0791 2.43208 14.8478 2.52297 14.6314C2.61386 14.4151 2.74612 14.2182 2.91 14.0533L2.95333 14.01C3.15903 13.8029 3.29753 13.5387 3.35053 13.2519C3.40354 12.9652 3.36843 12.6694 3.25 12.4033C3.13713 12.1425 2.95182 11.9203 2.71561 11.7631C2.47941 11.6058 2.20272 11.5199 1.91833 11.515H1.66667C1.22464 11.515 0.800716 11.3394 0.488156 11.0268C0.175595 10.7143 0 10.2904 0 9.84833C0 9.40631 0.175595 8.98238 0.488156 8.66982C0.800716 8.35726 1.22464 8.18167 1.66667 8.18167H1.75C2.04181 8.17105 2.32432 8.07583 2.56211 7.90759C2.7999 7.73936 2.98241 7.50561 3.08667 7.235C3.2051 6.96891 3.24021 6.67311 3.18721 6.38638C3.1342 6.09965 2.9957 5.83541 2.79 5.62833L2.74667 5.585C2.58279 5.41856 2.45282 5.22111 2.36435 5.00452C2.27589 4.78794 2.23087 4.55614 2.23193 4.32233C2.23298 4.08853 2.28009 3.85716 2.37049 3.64126C2.4609 3.42535 2.59262 3.22877 2.75833 3.06333C2.92453 2.89789 3.12184 2.76733 3.33848 2.67839C3.55511 2.58945 3.78724 2.54384 4.021 2.54492C4.25481 2.54601 4.48661 2.59375 4.70319 2.68464C4.91978 2.77553 5.11647 2.90779 5.28167 3.07167L5.325 3.115C5.53207 3.3207 5.79631 3.4592 6.08305 3.5122C6.36978 3.56521 6.66558 3.5301 6.93167 3.41167H7C7.2609 3.29879 7.48302 3.11349 7.64029 2.87728C7.79756 2.64107 7.88347 2.36438 7.88833 2.08V1.66667C7.88833 1.22464 8.06393 0.800716 8.37649 0.488156C8.68905 0.175595 9.11297 0 9.555 0C9.99703 0 10.4209 0.175595 10.7335 0.488156C11.0461 0.800716 11.2217 1.22464 11.2217 1.66667V1.75C11.2265 2.03438 11.3124 2.31107 11.4697 2.54728C11.627 2.78349 11.8491 2.96879 12.11 3.08167C12.3761 3.2001 12.6719 3.23521 12.9586 3.1822C13.2454 3.1292 13.5096 2.9907 13.7167 2.785L13.76 2.74167C13.9252 2.57779 14.1219 2.44782 14.3385 2.35935C14.5551 2.27089 14.7869 2.22587 15.0207 2.22693C15.2545 2.22798 15.4858 2.27509 15.7018 2.36549C15.9177 2.4559 16.1142 2.58762 16.2797 2.75333C16.4451 2.91953 16.5757 3.11684 16.6646 3.33348C16.7536 3.55011 16.7992 3.78224 16.7981 4.016C16.797 4.24981 16.7493 4.4816 16.6584 4.69819C16.5675 4.91478 16.4353 5.11147 16.2714 5.27667L16.228 5.32C16.0223 5.52707 15.8838 5.79131 15.8308 6.07805C15.7778 6.36478 15.8129 6.66058 15.9313 6.92667V7C16.0442 7.2609 16.2295 7.48302 16.4657 7.64029C16.7019 7.79756 16.9786 7.88347 17.2630 7.88833H17.6667C18.1087 7.88833 18.5326 8.06393 18.8452 8.37649C19.1577 8.68905 19.3333 9.11297 19.3333 9.555C19.3333 9.99703 19.1577 10.4209 18.8452 10.7335C18.5326 11.0461 18.1087 11.2217 17.6667 11.2217H17.5833C17.2989 11.2265 17.0222 11.3124 16.786 11.4697C16.5498 11.627 16.3645 11.8491 16.2517 12.11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
        <LanguageSwitcher />
      </div>

      {/* Header */}
      <div className="mb-8 text-center">
        <h1 className="mb-2 text-3xl font-bold text-white">
          虚幻<span className="text-brand">造物</span>
        </h1>
        <p className="text-sm text-white/50">
          {t('common.tagline')}
        </p>
      </div>

      {/* Edition Switcher */}
      <div className="mb-6 flex gap-2 rounded-full bg-bg-1 p-1">
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
      <p className="mb-6 text-xs text-white/30">
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

      {/* Recent Projects */}
      <div className="mt-12 w-full max-w-2xl">
        <h2 className="mb-4 text-sm font-medium text-white/60">
          {t('common.recentProjects')}
        </h2>

        {loading ? (
          <div className="py-8 text-center text-sm text-white/30">
            {t('common.loading')}
          </div>
        ) : projects.length === 0 ? (
          <div className="py-8 text-center text-sm text-white/30">
            {t('common.noProjects')}
          </div>
        ) : (
          <div className="space-y-2">
            {projects.map((proj) => (
              <div
                key={proj.id}
                className="group flex items-center gap-4 rounded-lg bg-bg-1 px-4 py-3 transition-colors hover:bg-bg-2 cursor-pointer"
                onClick={() => router.push(`/projects/${proj.id}`)}
              >
                {/* Project info */}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-medium text-white">
                      {proj.name}
                    </span>
                    <span className="shrink-0 rounded bg-white/5 px-1.5 py-0.5 text-[10px] text-white/40">
                      {t(`stages.${proj.stage}`)}
                    </span>
                  </div>
                  {proj.description && (
                    <p className="mt-0.5 truncate text-xs text-white/30">
                      {proj.description}
                    </p>
                  )}
                </div>

                {/* Time */}
                <span className="shrink-0 text-xs text-white/20">
                  {timeAgo(proj.updated_at, t('lang.switchTo') === 'EN' ? 'zh' : 'en')}
                </span>

                {/* Delete button */}
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(proj);
                  }}
                  className="shrink-0 rounded p-1 text-white/0 transition-colors group-hover:text-white/20 hover:!text-red-400 hover:bg-white/5"
                  title={t('common.deleteProject')}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="3 6 5 6 21 6" />
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="mt-auto py-8 text-xs text-white/20">
        {t('common.version')}
      </div>
    </div>
  );
}
