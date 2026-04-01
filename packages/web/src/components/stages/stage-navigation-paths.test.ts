import {
  STAGE_ROUTE_ORDER,
  buildStagePath,
  getNextStageRoute,
  getPreviousStageRoute,
} from '@unrealmake/shared/hooks/useStageNavigation';

describe('stage navigation helpers', () => {
  it('builds project stage paths', () => {
    expect(buildStagePath('project-x', 'workbench')).toBe('/projects/project-x/workbench');
    expect(buildStagePath('project-x', 'board')).toBe('/projects/project-x/board');
    expect(buildStagePath('project-x', 'preview')).toBe('/projects/project-x/preview');
  });

  it('keeps route order and prev/next transitions', () => {
    expect(STAGE_ROUTE_ORDER).toEqual(['workbench', 'board', 'preview']);
    expect(getNextStageRoute('workbench')).toBe('board');
    expect(getNextStageRoute('board')).toBe('preview');
    expect(getNextStageRoute('preview')).toBeNull();

    expect(getPreviousStageRoute('preview')).toBe('board');
    expect(getPreviousStageRoute('board')).toBe('workbench');
    expect(getPreviousStageRoute('workbench')).toBeNull();
  });
});
