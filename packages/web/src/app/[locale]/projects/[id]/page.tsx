'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { useEdition } from '@novelflow/shared/hooks';
import { WizardLayout, WorkspaceLayout } from '@novelflow/shared/components';
import type { WizardStep } from '@novelflow/shared/components';
import { fetchAPI } from '@novelflow/shared/lib';
import type { Project } from '@novelflow/shared/types';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';

const STAGE_TO_STEP: Record<string, number> = {
  import: 0,
  knowledge: 1,
  beat_sheet: 2,
  script: 3,
  storyboard: 4,
  visual_prompt: 4,
  generation: 4,
  complete: 4,
};

const STAGE_KEYS = ['import', 'knowledge', 'beat_sheet', 'script', 'storyboard', 'visual_prompt', 'generation', 'complete'] as const;
type StageKey = typeof STAGE_KEYS[number];

const STEP_HINT_KEYS = ['step0', 'step1', 'step2', 'step3', 'step4'] as const;

const EDITION_KEYS = ['normal', 'canvas', 'hidden', 'ultimate'] as const;
type EditionKey = typeof EDITION_KEYS[number];

export default function ProjectPage() {
  const params = useParams();
  const projectId = params.id as string;
  const tStages = useTranslations('stages');
  const tStepHints = useTranslations('stepHints');
  const tEditions = useTranslations('editions');
  const tProject = useTranslations('project');
  const tWizard = useTranslations('wizard');
  const tCommon = useTranslations('common');
  const tAria = useTranslations('aria');
  const { getFeatureConfig } = useEdition();
  const config = getFeatureConfig();

  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState(0);

  const WIZARD_STEPS: WizardStep[] = [
    { id: 'import', label: tStages('import') },
    { id: 'knowledge', label: tStages('knowledge') },
    { id: 'beats', label: tStages('beat_sheet') },
    { id: 'script', label: tStages('script') },
    { id: 'storyboard', label: tStages('storyboard') },
  ];

  useEffect(() => {
    fetchAPI<Project>(`/api/projects/${projectId}`)
      .then((p) => {
        setProject(p);
        setCurrentStep(STAGE_TO_STEP[p.stage] ?? 0);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [projectId]);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-bg-0">
        <div className="text-white/40">{tProject('loadingProject')}</div>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="flex h-screen items-center justify-center bg-bg-0">
        <div className="text-center">
          <p className="mb-2 text-error">{tProject('loadFailed')}</p>
          <p className="text-sm text-white/40">{error}</p>
        </div>
      </div>
    );
  }

  const isKnownStage = STAGE_KEYS.includes(project.stage as StageKey);
  const stageLabel = isKnownStage ? tStages(project.stage as StageKey) : project.stage;

  const isKnownEdition = EDITION_KEYS.includes(project.edition as EditionKey);
  const editionLabel = isKnownEdition ? tEditions(project.edition as EditionKey) : project.edition;

  const wizardLabels = { prev: tWizard('prev'), next: tWizard('next') };

  // Wizard mode for Normal edition
  if (config.ui_mode === 'wizard') {
    const hintKey = STEP_HINT_KEYS[currentStep];
    return (
      <WizardLayout
        steps={WIZARD_STEPS}
        currentStep={currentStep}
        onStepClick={(i) => i <= currentStep && setCurrentStep(i)}
        onNext={() => setCurrentStep((s) => Math.min(s + 1, WIZARD_STEPS.length - 1))}
        onPrev={() => setCurrentStep((s) => Math.max(s - 1, 0))}
        labels={wizardLabels}
        headerExtra={<LanguageSwitcher />}
      >
        <div className="py-12 text-center">
          <h2 className="mb-4 text-2xl font-bold text-white">{project.name}</h2>
          <p className="mb-2 text-sm text-white/50">
            {tProject('stage')}: <span className="text-brand">{stageLabel}</span>
          </p>
          <p className="text-sm text-white/30">
            {tProject('currentStep')}: {WIZARD_STEPS[currentStep].label}
          </p>
          <div className="mx-auto mt-8 max-w-md rounded-xl border border-white/[0.06] bg-bg-1 p-8">
            <p className="text-white/40">
              {hintKey ? tStepHints(hintKey) : ''}
            </p>
          </div>
        </div>
      </WizardLayout>
    );
  }

  const workspaceLabels = {
    toggleSidebar: tAria('toggleSidebar'),
    toggleRightPanel: tAria('toggleRightPanel'),
    onlineText: tCommon('online', { count: '' }).trim(),
  };

  // Workspace mode for Canvas+ editions
  return (
    <WorkspaceLayout
      projectName={project.name}
      labels={workspaceLabels}
      headerExtra={<LanguageSwitcher />}
      sidebar={
        <div className="p-4">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-white/30">
            {tProject('navigation')}
          </h3>
          <nav className="space-y-1">
            {WIZARD_STEPS.map((step) => (
              <button
                key={step.id}
                type="button"
                className="w-full rounded-md px-3 py-2 text-left text-sm text-white/60 transition-colors hover:bg-white/5 hover:text-white"
              >
                {step.label}
              </button>
            ))}
          </nav>
        </div>
      }
      main={
        <div className="flex h-full items-center justify-center p-8">
          <div className="text-center">
            <h2 className="mb-4 text-2xl font-bold text-white">{project.name}</h2>
            <p className="mb-2 text-sm text-white/50">
              {tProject('stage')}: <span className="text-brand">{stageLabel}</span>
            </p>
            <p className="text-sm text-white/30">
              {tProject('workspaceMode')} &middot; {editionLabel}
            </p>
          </div>
        </div>
      }
      rightPanel={
        <div className="p-4">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-white/30">
            {tProject('aiAssistant')}
          </h3>
          <div className="rounded-lg border border-white/[0.06] bg-bg-0/50 p-4">
            <p className="text-sm text-white/40">
              {tProject('aiPlaceholder')}
            </p>
          </div>
        </div>
      }
      statusBar={
        <div className="flex w-full items-center justify-between">
          <span>{tCommon('autoSaved')}</span>
          <span>{editionLabel}</span>
        </div>
      }
    />
  );
}
