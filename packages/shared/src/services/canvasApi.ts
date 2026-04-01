// ══════════════════════════════════════════════════════════════
// canvasApi.ts — 画布后端 API 调用封装
// ══════════════════════════════════════════════════════════════

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ── 画布 CRUD ──

export async function fetchCanvasData(projectId: string) {
  const res = await fetch(`${API_BASE}/api/projects/${projectId}/canvas`);
  if (!res.ok) {
    if (res.status === 404) return null;
    throw new Error(`Failed to fetch canvas: ${res.status}`);
  }
  return res.json();
}

export async function saveCanvasData(projectId: string, workflowJson: unknown) {
  const res = await fetch(`${API_BASE}/api/projects/${projectId}/canvas`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ workflow_json: workflowJson }),
  });
  if (!res.ok) throw new Error(`Failed to save canvas: ${res.status}`);
  return res.json();
}

// ── Agent 服务 ──

export async function analyzeStoryboard(nodeId: string, content: {
  rawText: string;
  characterIds: string[];
  sceneAssetId?: string;
  emotion: string;
}, assets: unknown[]) {
  const res = await fetch(`${API_BASE}/api/canvas/agent/analyze-storyboard`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ node_id: nodeId, content, assets }),
  });
  if (!res.ok) throw new Error(`Storyboard analysis failed: ${res.status}`);
  return res.json();
}

export async function assignModules(nodes: Array<{ nodeId: string; text: string }>) {
  const res = await fetch(`${API_BASE}/api/canvas/agent/assign-modules`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nodes }),
  });
  if (!res.ok) throw new Error(`Module assignment failed: ${res.status}`);
  return res.json();
}

export async function optimizePrompt(type: 'image' | 'video', currentPrompt: string, context: {
  rawText: string;
  emotion: string;
  moduleType: string;
  shotType: string;
}) {
  const res = await fetch(`${API_BASE}/api/canvas/agent/optimize-prompt`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ type, current_prompt: currentPrompt, context }),
  });
  if (!res.ok) throw new Error(`Prompt optimization failed: ${res.status}`);
  return res.json();
}

export async function reviewComposition(imageBase64: string, storyboardText: string, moduleType: string) {
  const res = await fetch(`${API_BASE}/api/canvas/agent/review-composition`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image_base64: imageBase64, storyboard_text: storyboardText, module_type: moduleType }),
  });
  if (!res.ok) throw new Error(`Composition review failed: ${res.status}`);
  return res.json();
}

// ── 节点执行 ──

export async function executeNode(nodeId: string, nodeType: string, content: unknown) {
  const res = await fetch(`${API_BASE}/api/canvas/nodes/${nodeId}/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ node_type: nodeType, content }),
  });
  if (!res.ok) throw new Error(`Node execution failed: ${res.status}`);
  return res.json();
}

export async function batchExecute(nodeIds: string[]) {
  const res = await fetch(`${API_BASE}/api/canvas/batch-execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ node_ids: nodeIds }),
  });
  if (!res.ok) throw new Error(`Batch execution failed: ${res.status}`);
  return res.json();
}

// ── 数据同步 ──

export async function syncFromProject(projectId: string) {
  const res = await fetch(`${API_BASE}/api/canvas/sync/from-project`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: projectId }),
  });
  if (!res.ok) throw new Error(`Sync from project failed: ${res.status}`);
  return res.json();
}

export async function syncToProject(projectId: string, results: unknown[]) {
  const res = await fetch(`${API_BASE}/api/canvas/sync/to-project`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: projectId, results }),
  });
  if (!res.ok) throw new Error(`Sync to project failed: ${res.status}`);
  return res.json();
}
