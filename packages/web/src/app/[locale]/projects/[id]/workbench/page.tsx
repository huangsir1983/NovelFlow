import { StageScaffold } from '@/components/stages/StageScaffold';

export default function WorkbenchPage() {
  return (
    <StageScaffold
      stage="workbench"
      title="Workbench Stage"
      description="Sudowrite-style writing workbench for import, beats/scenes editing, AI suggestions, and consistency review."
      checklist={[
        'Import source text and normalize chapters, characters, and scenes.',
        'Edit Beat/Scene structure with clear writeback targets.',
        'Review AI suggestions and consistency warnings before promoting to Board.',
      ]}
    />
  );
}
