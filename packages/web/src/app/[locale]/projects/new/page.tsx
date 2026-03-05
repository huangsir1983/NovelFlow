'use client';

import { useState } from 'react';
import { useRouter } from '@/i18n/navigation';
import { useTranslations } from 'next-intl';
import { WizardLayout } from '@novelflow/shared/components';
import type { WizardStep } from '@novelflow/shared/components';
import { useEdition } from '@novelflow/shared/hooks';
import { fetchAPI } from '@novelflow/shared/lib';
import type { Project, ImportSource } from '@novelflow/shared/types';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';

const SOURCE_KEYS: Record<string, { titleKey: string; descKey: string }> = {
  novel: { titleKey: 'sources.novelTitle', descKey: 'sources.novelDesc' },
  script: { titleKey: 'sources.scriptTitle', descKey: 'sources.scriptDesc' },
  blank: { titleKey: 'sources.blankTitle', descKey: 'sources.blankDesc' },
};

export default function NewProjectPage() {
  const router = useRouter();
  const t = useTranslations();
  const { edition, getFeatureConfig } = useEdition();
  const config = getFeatureConfig();

  const WIZARD_STEPS: WizardStep[] = [
    { id: 'source', label: t('newProject.chooseSource') },
    { id: 'upload', label: t('newProject.projectInfo') },
    { id: 'confirm', label: t('newProject.confirm') },
  ];

  const [currentStep, setCurrentStep] = useState(0);
  const [projectName, setProjectName] = useState('');
  const [description, setDescription] = useState('');
  const [importSource, setImportSource] = useState<ImportSource>('novel');
  const [creating, setCreating] = useState(false);

  const handleCreate = async () => {
    if (!projectName.trim()) return;
    setCreating(true);
    try {
      const project = await fetchAPI<Project>('/api/projects', {
        method: 'POST',
        body: JSON.stringify({
          name: projectName,
          description,
          import_source: importSource,
          edition,
        }),
      });
      router.push(`/projects/${project.id}`);
    } catch (err) {
      console.error('Failed to create project:', err);
      setCreating(false);
    }
  };

  const wizardLabels = {
    prev: t('wizard.prev'),
    next: t('wizard.next'),
  };

  return (
    <WizardLayout
      steps={WIZARD_STEPS}
      currentStep={currentStep}
      onStepClick={(i) => i <= currentStep && setCurrentStep(i)}
      onNext={() => {
        if (currentStep === WIZARD_STEPS.length - 1) {
          handleCreate();
        } else {
          setCurrentStep((s) => Math.min(s + 1, WIZARD_STEPS.length - 1));
        }
      }}
      onPrev={() => {
        if (currentStep === 0) {
          router.push('/');
        } else {
          setCurrentStep((s) => Math.max(s - 1, 0));
        }
      }}
      canNext={currentStep === 0 || (currentStep === 1 && !!projectName.trim()) || currentStep === 2}
      labels={wizardLabels}
      headerExtra={<LanguageSwitcher />}
    >
      {/* Step 1: Source selection */}
      {currentStep === 0 && (
        <div className="space-y-8">
          <h2 className="text-center text-2xl font-bold text-white">{t('newProject.chooseSource')}</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {config.import_sources.map((source) => {
              const keys = SOURCE_KEYS[source];
              return (
                <button
                  key={source}
                  type="button"
                  onClick={() => {
                    setImportSource(source as ImportSource);
                    setCurrentStep(1);
                  }}
                  className={`rounded-xl border p-6 text-left transition-all ${
                    importSource === source
                      ? 'border-brand bg-brand/10'
                      : 'border-white/[0.06] bg-bg-1 hover:border-white/20'
                  }`}
                >
                  <h3 className="mb-2 text-lg font-semibold text-white">
                    {keys ? t(keys.titleKey) : source}
                  </h3>
                  <p className="text-sm text-white/50">
                    {keys ? t(keys.descKey) : ''}
                  </p>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Step 2: Project info */}
      {currentStep === 1 && (
        <div className="space-y-6">
          <h2 className="text-center text-2xl font-bold text-white">{t('newProject.projectInfo')}</h2>
          <div>
            <label htmlFor="name" className="mb-2 block text-sm font-medium text-white/70">
              {t('newProject.projectName')}
            </label>
            <input
              id="name"
              type="text"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              placeholder={t('newProject.projectNamePlaceholder')}
              className="w-full rounded-lg border border-white/[0.06] bg-bg-1 px-4 py-3 text-white placeholder-white/30 outline-none transition-colors focus:border-brand focus:ring-2 focus:ring-brand/30"
            />
          </div>
          <div>
            <label htmlFor="desc" className="mb-2 block text-sm font-medium text-white/70">
              {t('newProject.projectDesc')}
            </label>
            <textarea
              id="desc"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t('newProject.projectDescPlaceholder')}
              className="w-full rounded-lg border border-white/[0.06] bg-bg-1 px-4 py-3 text-white placeholder-white/30 outline-none transition-colors focus:border-brand focus:ring-2 focus:ring-brand/30"
            />
          </div>
        </div>
      )}

      {/* Step 3: Confirm */}
      {currentStep === 2 && (
        <div className="space-y-6 text-center">
          <h2 className="text-2xl font-bold text-white">{t('newProject.confirmTitle')}</h2>
          <div className="rounded-xl border border-white/[0.06] bg-bg-1 p-6 text-left">
            <dl className="space-y-4">
              <div>
                <dt className="text-xs text-white/40">{t('newProject.labelName')}</dt>
                <dd className="text-lg text-white">{projectName}</dd>
              </div>
              {description && (
                <div>
                  <dt className="text-xs text-white/40">{t('newProject.labelDesc')}</dt>
                  <dd className="text-sm text-white/70">{description}</dd>
                </div>
              )}
              <div>
                <dt className="text-xs text-white/40">{t('newProject.labelSource')}</dt>
                <dd className="text-white">
                  {SOURCE_KEYS[importSource] ? t(SOURCE_KEYS[importSource].titleKey) : importSource}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-white/40">{t('newProject.labelEdition')}</dt>
                <dd className="text-white">{t(`editions.${edition}`)}</dd>
              </div>
            </dl>
          </div>
          <button
            type="button"
            onClick={handleCreate}
            disabled={creating}
            className="brand-gradient rounded-lg px-8 py-3 font-semibold text-white shadow-lg transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {creating ? t('newProject.creating') : t('newProject.create')}
          </button>
        </div>
      )}
    </WizardLayout>
  );
}
