export type PipelineRunStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';
export type NodeExecutionStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled';

export interface NodeExecution {
  node_id: string;
  status: NodeExecutionStatus;
  started_at?: string;
  finished_at?: string;
  error_message?: string;
}

export interface AgentRun {
  id: string;
  agent_name: string;
  status: NodeExecutionStatus;
  node_id?: string;
  started_at?: string;
  finished_at?: string;
}

export interface DebugMetric {
  name: string;
  value: number;
  unit: 'ms' | 'count' | 'cost';
  tags?: Record<string, string>;
}

export interface PipelineRun {
  id: string;
  project_id: string;
  workflow_id: string;
  status: PipelineRunStatus;
  nodes: NodeExecution[];
  agents: AgentRun[];
  debug_metrics: DebugMetric[];
  created_at: string;
  updated_at: string;
}
