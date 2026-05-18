import type { DraftRecord, EvalBank, EvalRun, FlowGraph, FrameLog, PromptDetail, PromptRow, PromptWorkbenchContext, SyncStatus } from './types';

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { 'content-type': 'application/json', ...(init?.headers || {}) },
    ...init,
  });
  if (!response.ok) {
    throw new Error(await responseMessage(response));
  }
  return (await response.json()) as T;
}

async function responseMessage(response: Response) {
  const text = await response.text();
  if (!text) return response.statusText;
  try {
    const payload = JSON.parse(text) as { detail?: unknown };
    const detail = payload.detail;
    if (typeof detail === 'string') return detail;
    if (detail && typeof detail === 'object' && 'message' in detail) {
      return String((detail as { message?: unknown }).message || response.statusText);
    }
  } catch {
    return text;
  }
  return text;
}

export function getPrompts() {
  return api<{ prompts: PromptRow[]; flow: FlowGraph; evalBank: EvalBank }>('/api/prompts');
}

export function getPrompt(id: string) {
  return api<PromptDetail>(`/api/prompts/${encodeURIComponent(id)}`);
}

export function getPromptWorkbenchContext(id: string) {
  return api<PromptWorkbenchContext>(`/api/prompts/${encodeURIComponent(id)}/workbench-context`);
}

export function renderPrompt(promptId: string, variables: Record<string, unknown> = {}) {
  return api<{ id: string; rendered: string; renderedHash: string; variables: string[] }>('/api/prompts/render', {
    method: 'POST',
    body: JSON.stringify({ promptId, variables }),
  });
}

export function getSyncStatus() {
  return api<SyncStatus>('/api/sync/status');
}

export function pullLive() {
  return api<unknown>('/api/sync/pull-live', { method: 'POST', body: JSON.stringify({ env: 'local' }) });
}

export function pushDryRun() {
  return api<{ reviewToken: string; returnCode: number; stdoutTail: string; stderrTail: string }>('/api/sync/push-live-dry-run', {
    method: 'POST',
    body: JSON.stringify({ env: 'local' }),
  });
}

export function pushReviewed(reviewToken: string) {
  return api<{ returnCode: number; stdoutTail: string; stderrTail: string; parsed?: unknown }>('/api/sync/push-live-reviewed', {
    method: 'POST',
    body: JSON.stringify({ env: 'local', reviewToken }),
  });
}

export function importLiveDraft(agentId: string, promptId?: string) {
  return api<DraftRecord | { status: 'requires_manual_target'; reason: string; candidatePromptIds: string[]; agentId?: string }>(
    '/api/sync/import-live-draft',
    {
      method: 'POST',
      body: JSON.stringify({ agentId, promptId }),
    },
  );
}

export function createDraft(targetPath: string, newText: string, reason: string) {
  return api<DraftRecord>('/api/drafts', {
    method: 'POST',
    body: JSON.stringify({ targetPath, newText, reason, kind: 'source-edit' }),
  });
}

export function getDrafts() {
  return api<{ drafts: DraftRecord[] }>('/api/drafts');
}

export function applyDraft(id: string, idempotencyToken: string) {
  return api<{ id: string; status: string; targetPath: string; newHash: string; alreadyApplied?: boolean }>(`/api/drafts/${encodeURIComponent(id)}/apply`, {
    method: 'POST',
    body: JSON.stringify({ idempotencyToken }),
  });
}

export function discardDraft(id: string) {
  return api<{ id: string; status: string; targetPath: string }>(`/api/drafts/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  });
}

export function runEval(options: { maxCases?: number; live?: boolean; family?: string; surface?: string; promptId?: string } = {}) {
  return api<EvalRun>('/api/evals/run', {
    method: 'POST',
    body: JSON.stringify({
      maxCases: options.maxCases ?? 1,
      live: options.live ?? false,
      family: options.family || undefined,
      surface: options.surface || undefined,
      promptId: options.promptId || undefined,
    }),
  });
}

export function createEvalCaseDraft(options: { familyId: string; caseId: string; updatedCase: Record<string, unknown>; create?: boolean; reason?: string }) {
  return api<DraftRecord>('/api/evals/case-draft', {
    method: 'POST',
    body: JSON.stringify({
      familyId: options.familyId,
      caseId: options.caseId,
      updatedCase: options.updatedCase,
      create: options.create ?? false,
      reason: options.reason || `Workbench eval edit for ${options.familyId}/${options.caseId}`,
    }),
  });
}

export function getEvalRuns() {
  return api<{ runs: EvalRun[] }>('/api/evals/runs');
}

export function getFrames() {
  return api<{ frames: FrameLog[] }>('/api/frames');
}
