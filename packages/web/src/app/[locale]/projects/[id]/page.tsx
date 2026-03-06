'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { useEdition, useProjectStore } from '@unrealmake/shared/hooks';
import { WizardLayout, WorkspaceLayout } from '@unrealmake/shared/components';
import { FileUpload, ImportProgress, KnowledgeReview } from '@unrealmake/shared/components';
import { BeatList } from '@unrealmake/shared/components';
import { ScriptEditor } from '@unrealmake/shared/components';
import { ProjectNav, AIAssistant } from '@unrealmake/shared/components';
import type { WizardStep } from '@unrealmake/shared/components';
import { fetchAPI } from '@unrealmake/shared/lib';
import type { Project, Chapter, Beat, Scene, Character, Location } from '@unrealmake/shared/types';
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

interface ImportResult {
  chapter_count: number;
  character_count: number;
  beat_count: number;
  scene_count: number;
  location_count: number;
  stage: string;
}

interface ImportStep {
  id: string;
  label: string;
  status: 'pending' | 'running' | 'done' | 'error';
}

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
  const tImport = useTranslations('import');
  const tEditor = useTranslations('editor');
  const tBeats = useTranslations('beats');
  const { getFeatureConfig } = useEdition();
  const config = getFeatureConfig();

  const store = useProjectStore();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [importSteps, setImportSteps] = useState<ImportStep[]>([]);
  const [importError, setImportError] = useState<string | null>(null);
  const [editorContent, setEditorContent] = useState('');

  const WIZARD_STEPS: WizardStep[] = [
    { id: 'import', label: tStages('import') },
    { id: 'knowledge', label: tStages('knowledge') },
    { id: 'beats', label: tStages('beat_sheet') },
    { id: 'script', label: tStages('script') },
    { id: 'storyboard', label: tStages('storyboard') },
  ];

  // Load project and data
  useEffect(() => {
    const loadProject = async () => {
      try {
        const project = await fetchAPI<Project>(`/api/projects/${projectId}`);
        store.setProject(project);
        setCurrentStep(STAGE_TO_STEP[project.stage] ?? 0);

        // Load related data if past import stage
        if (project.stage !== 'import') {
          const [chapters, beats, scenes, characters, locations] = await Promise.all([
            fetchAPI<Chapter[]>(`/api/projects/${projectId}/beats`).catch(() => []),
            fetchAPI<Beat[]>(`/api/projects/${projectId}/beats`),
            fetchAPI<Scene[]>(`/api/projects/${projectId}/scenes`),
            fetchAPI<Character[]>(`/api/projects/${projectId}/characters`),
            fetchAPI<Location[]>(`/api/projects/${projectId}/locations`),
          ]);

          // Actually fetch chapters from a dedicated endpoint — but since we don't have one yet,
          // we just set what we have
          store.setBeats(beats);
          store.setScenes(scenes);
          store.setCharacters(characters);
          store.setLocations(locations);

          // Load knowledge base
          try {
            const kb = await fetchAPI<{ world_building: Record<string, unknown>; style_guide: Record<string, unknown> }>(
              `/api/projects/${projectId}/knowledge`,
            );
            store.setWorldBuilding(kb.world_building);
            store.setStyleGuide(kb.style_guide);
          } catch {
            // Knowledge base may not exist yet
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };
    loadProject();
    return () => store.reset();
  }, [projectId]);

  // Handle file upload & import
  const handleFileUpload = useCallback(
    async (file: File) => {
      store.setImporting(true);
      setImportError(null);
      setImportSteps([
        { id: 'upload', label: tImport('stepUpload'), status: 'running' },
        { id: 'chapters', label: tImport('stepChapters'), status: 'pending' },
        { id: 'characters', label: tImport('stepCharacters'), status: 'pending' },
        { id: 'beats', label: tImport('stepBeats'), status: 'pending' },
        { id: 'knowledge', label: tImport('stepKnowledge'), status: 'pending' },
      ]);

      try {
        const formData = new FormData();
        formData.append('file', file);

        // Mark upload as done, chapters as running
        setImportSteps((prev) =>
          prev.map((s) =>
            s.id === 'upload' ? { ...s, status: 'done' } :
            s.id === 'chapters' ? { ...s, status: 'running' } : s
          ),
        );

        const response = await fetch(`http://localhost:8000/api/projects/${projectId}/import/novel`, {
          method: 'POST',
          body: formData,
        });

        if (!response.ok) {
          const err = await response.json().catch(() => ({ detail: 'Import failed' }));
          throw new Error(err.detail);
        }

        const result: ImportResult = await response.json();

        // Mark all steps as done
        setImportSteps((prev) => prev.map((s) => ({ ...s, status: 'done' as const })));

        // Update project stage
        store.setProject(store.project ? { ...store.project, stage: 'knowledge' } : null);
        setCurrentStep(1);

        // Reload data
        const [beats, scenes, characters, locations] = await Promise.all([
          fetchAPI<Beat[]>(`/api/projects/${projectId}/beats`),
          fetchAPI<Scene[]>(`/api/projects/${projectId}/scenes`),
          fetchAPI<Character[]>(`/api/projects/${projectId}/characters`),
          fetchAPI<Location[]>(`/api/projects/${projectId}/locations`),
        ]);
        store.setBeats(beats);
        store.setScenes(scenes);
        store.setCharacters(characters);
        store.setLocations(locations);

        try {
          const kb = await fetchAPI<{ world_building: Record<string, unknown>; style_guide: Record<string, unknown> }>(
            `/api/projects/${projectId}/knowledge`,
          );
          store.setWorldBuilding(kb.world_building);
          store.setStyleGuide(kb.style_guide);
        } catch {
          // ignore
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Import failed';
        setImportError(message);
        setImportSteps((prev) =>
          prev.map((s) =>
            s.status === 'running' ? { ...s, status: 'error' } : s
          ),
        );
      } finally {
        store.setImporting(false);
      }
    },
    [projectId, store, tImport],
  );

  // Handle knowledge confirm → advance to beat_sheet
  const handleConfirmKnowledge = useCallback(async () => {
    try {
      await fetchAPI(`/api/projects/${projectId}`, {
        method: 'PUT',
        body: JSON.stringify({ stage: 'beat_sheet' }),
      });
      store.setProject(store.project ? { ...store.project, stage: 'beat_sheet' } : null);
      setCurrentStep(2);
    } catch {
      // ignore
    }
  }, [projectId, store]);

  // Handle AI action from editor
  const handleAIAction = useCallback(
    (action: string, text: string) => {
      // Copy text to AI assistant panel (for workspace mode)
      // For wizard mode, we could open a modal
    },
    [],
  );

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-bg-0">
        <div className="text-white/40">{tProject('loadingProject')}</div>
      </div>
    );
  }

  if (error || !store.project) {
    return (
      <div className="flex h-screen items-center justify-center bg-bg-0">
        <div className="text-center">
          <p className="mb-2 text-error">{tProject('loadFailed')}</p>
          <p className="text-sm text-white/40">{error}</p>
        </div>
      </div>
    );
  }

  const project = store.project;
  const isKnownStage = STAGE_KEYS.includes(project.stage as StageKey);
  const stageLabel = isKnownStage ? tStages(project.stage as StageKey) : project.stage;
  const isKnownEdition = EDITION_KEYS.includes(project.edition as EditionKey);
  const editionLabel = isKnownEdition ? tEditions(project.edition as EditionKey) : project.edition;
  const wizardLabels = { prev: tWizard('prev'), next: tWizard('next') };

  // ── Wizard Step Content ────────────────────────────────────────
  const renderWizardContent = () => {
    switch (currentStep) {
      case 0: // Import
        return (
          <div className="py-8">
            <h2 className="mb-6 text-center text-xl font-bold text-white">{tImport('title')}</h2>
            {importSteps.length > 0 ? (
              <div className="mx-auto max-w-md">
                <ImportProgress steps={importSteps} error={importError} />
              </div>
            ) : (
              <FileUpload
                onFileSelect={handleFileUpload}
                disabled={store.importing}
                label={tImport('dropHint')}
                hint={tImport('formatHint')}
              />
            )}
          </div>
        );

      case 1: // Knowledge Review
        return (
          <div className="py-8">
            <h2 className="mb-6 text-center text-xl font-bold text-white">{tImport('knowledgeReview')}</h2>
            <KnowledgeReview
              characters={store.characters}
              locations={store.locations}
              worldBuilding={store.worldBuilding}
              styleGuide={store.styleGuide}
              onConfirm={handleConfirmKnowledge}
              confirmLabel={tImport('confirmKnowledge')}
            />
          </div>
        );

      case 2: // Beat Sheet
        return (
          <div className="py-8">
            <h2 className="mb-6 text-center text-xl font-bold text-white">{tBeats('title')}</h2>
            <BeatList
              beats={store.beats}
              selectedBeatId={store.selectedBeatId || undefined}
              onSelectBeat={(id) => store.selectBeat(id)}
            />
          </div>
        );

      case 3: // Script
        return (
          <div className="py-8">
            <h2 className="mb-6 text-center text-xl font-bold text-white">{tEditor('title')}</h2>
            <div className="h-[500px] rounded-lg border border-white/[0.06] bg-bg-1">
              <ScriptEditor
                content={editorContent}
                onChange={setEditorContent}
                onAIAction={handleAIAction}
                placeholder={tEditor('placeholder')}
              />
            </div>
          </div>
        );

      case 4: // Storyboard (placeholder)
        return (
          <div className="py-12 text-center">
            <h2 className="mb-4 text-xl font-bold text-white">{tStages('storyboard')}</h2>
            <p className="text-white/40">{tStepHints('step4')}</p>
          </div>
        );

      default:
        return null;
    }
  };

  // ── Wizard Mode (Normal) ───────────────────────────────────────
  if (config.ui_mode === 'wizard') {
    return (
      <WizardLayout
        steps={WIZARD_STEPS}
        currentStep={currentStep}
        onStepClick={(i) => i <= (STAGE_TO_STEP[project.stage] ?? 0) && setCurrentStep(i)}
        onNext={() => setCurrentStep((s) => Math.min(s + 1, WIZARD_STEPS.length - 1))}
        onPrev={() => setCurrentStep((s) => Math.max(s - 1, 0))}
        canNext={currentStep < (STAGE_TO_STEP[project.stage] ?? 0)}
        labels={wizardLabels}
        headerExtra={<LanguageSwitcher />}
      >
        {renderWizardContent()}
      </WizardLayout>
    );
  }

  // ── Workspace Mode (Canvas+) ──────────────────────────────────
  const workspaceLabels = {
    toggleSidebar: tAria('toggleSidebar'),
    toggleRightPanel: tAria('toggleRightPanel'),
    onlineText: tCommon('online', { count: '' }).trim(),
  };

  // Determine main content based on active section
  const renderMainContent = () => {
    if (project.stage === 'import') {
      return (
        <div className="flex h-full items-center justify-center p-8">
          <div className="w-full max-w-lg">
            <h2 className="mb-6 text-center text-xl font-bold text-white">{tImport('title')}</h2>
            {importSteps.length > 0 ? (
              <ImportProgress steps={importSteps} error={importError} />
            ) : (
              <FileUpload
                onFileSelect={handleFileUpload}
                disabled={store.importing}
                label={tImport('dropHint')}
                hint={tImport('formatHint')}
              />
            )}
          </div>
        </div>
      );
    }

    if (project.stage === 'knowledge') {
      return (
        <div className="mx-auto max-w-2xl p-8">
          <h2 className="mb-6 text-xl font-bold text-white">{tImport('knowledgeReview')}</h2>
          <KnowledgeReview
            characters={store.characters}
            locations={store.locations}
            worldBuilding={store.worldBuilding}
            styleGuide={store.styleGuide}
            onConfirm={handleConfirmKnowledge}
            confirmLabel={tImport('confirmKnowledge')}
          />
        </div>
      );
    }

    // Default: show beat list + script editor side by side
    return (
      <div className="flex h-full">
        {/* Left: Beat list */}
        <div className="w-80 shrink-0 overflow-auto border-r border-white/[0.06] p-4">
          <h3 className="mb-3 text-sm font-semibold text-white/50">{tBeats('title')}</h3>
          <BeatList
            beats={store.beats}
            selectedBeatId={store.selectedBeatId || undefined}
            onSelectBeat={(id) => store.selectBeat(id)}
          />
        </div>
        {/* Right: Editor */}
        <div className="flex-1">
          <ScriptEditor
            content={editorContent}
            onChange={setEditorContent}
            onAIAction={handleAIAction}
            placeholder={tEditor('placeholder')}
          />
        </div>
      </div>
    );
  };

  return (
    <WorkspaceLayout
      projectName={project.name}
      labels={workspaceLabels}
      headerExtra={<LanguageSwitcher />}
      sidebar={
        <ProjectNav
          chapters={store.chapters}
          characters={store.characters}
          selectedId={store.selectedChapterId || store.selectedCharacterId || undefined}
          activeSection={store.activeSection}
          onSelectItem={(type, id) => {
            if (type === 'chapter') store.selectChapter(id);
            else if (type === 'character') store.selectCharacter(id);
          }}
          onSectionChange={(section) => store.setActiveSection(section)}
        />
      }
      main={renderMainContent()}
      rightPanel={<AIAssistant projectId={projectId} />}
      statusBar={
        <div className="flex w-full items-center justify-between">
          <span>{tCommon('autoSaved')}</span>
          <span>
            {stageLabel} &middot; {editionLabel}
          </span>
        </div>
      }
    />
  );
}
