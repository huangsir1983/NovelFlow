export type WorkbenchConsistencySeverity = 'info' | 'warning' | 'error';

export interface WorkbenchBeatDraft {
  id: string;
  title: string;
  summary: string;
  order: number;
}

export interface WorkbenchSceneDraft {
  id: string;
  beat_id?: string;
  heading: string;
  core_event: string;
  order: number;
}

export interface WorkbenchAISuggestion {
  id: string;
  beat_id?: string;
  scene_id?: string;
  title: string;
  recommendation: string;
  reason: string;
  applied: boolean;
  created_at: string;
}

export interface WorkbenchConsistencyIssue {
  id: string;
  severity: WorkbenchConsistencySeverity;
  message: string;
  related_ids: string[];
  rule_code: string;
}
