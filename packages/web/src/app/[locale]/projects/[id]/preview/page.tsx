import { StageScaffold } from '@/components/stages/StageScaffold';

export default function PreviewPage() {
  return (
    <StageScaffold
      stage="preview"
      title="Preview Stage"
      description="Premiere/CapCut-style previsualization timeline for animatic validation, subtitle/TTS checks, and export readiness."
      checklist={[
        'Play Animatic with timeline tracks and baseline transition controls.',
        'Validate writeback traceability from Preview back to Board and Workbench.',
        'Export preview package and CapCut draft mapping for downstream delivery.',
      ]}
    />
  );
}
