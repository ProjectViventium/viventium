import type {
  AuthStatus,
  DraftRecord,
  EvalBank,
  EvalRun,
  FlowGraph,
  FrameLog,
  PromptDetail,
  PromptRevision,
  PromptRow,
  PromptWorkbenchContext,
  ScheduledPrompt,
  ScheduledPromptMemoryProposal,
  ScheduledPromptTemplate,
  ScheduledPromptRun,
  SyncStatus,
  VariableRegistry,
  VariableRenderResult,
} from './types';
import { readLocalStorage, writeLocalStorage } from './storage';

function workbenchToken() {
  const params = new URLSearchParams(window.location.search);
  const token = params.get('workbench_token');
  if (token) {
    writeLocalStorage('viventium.promptWorkbench.launchToken', token);
    params.delete('workbench_token');
    const next = `${window.location.pathname}${params.toString() ? `?${params.toString()}` : ''}${window.location.hash}`;
    window.history.replaceState({}, '', next);
    return token;
  }
  return readLocalStorage('viventium.promptWorkbench.launchToken') || '';
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const token = workbenchToken();
  const response = await fetch(path, {
    headers: {
      'content-type': 'application/json',
      ...(token ? { 'x-viventium-workbench-token': token } : {}),
      ...(init?.headers || {}),
    },
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

export function getAuthStatus() {
  return api<AuthStatus>('/api/auth/status');
}

export function getVariables() {
  return api<VariableRegistry>('/api/variables');
}

export function getNightlyScheduledPromptTemplate() {
  return api<ScheduledPromptTemplate>('/api/scheduled-prompts/templates/nightly-subconscious');
}

export function renderVariables(promptText: string) {
  return api<VariableRenderResult>('/api/variables/render', {
    method: 'POST',
    body: JSON.stringify({ promptText }),
  });
}

export function getScheduledPrompts() {
  return api<{ scheduledPrompts: ScheduledPrompt[] }>('/api/scheduled-prompts');
}

export function createScheduledPrompt(payload: Partial<ScheduledPrompt> & { title: string; promptText: string }) {
  return api<ScheduledPrompt>('/api/scheduled-prompts', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateScheduledPrompt(id: string, payload: Partial<ScheduledPrompt>) {
  return api<ScheduledPrompt>(`/api/scheduled-prompts/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function deleteScheduledPrompt(id: string) {
  return api<{ success: boolean }>(`/api/scheduled-prompts/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

export function manualRunScheduledPrompt(id: string, confirmUserLevelDelivery = false) {
  return api<{ run?: ScheduledPromptRun; dispatch?: unknown }>(`/api/scheduled-prompts/${encodeURIComponent(id)}/manual-runs`, {
    method: 'POST',
    body: JSON.stringify({ confirmUserLevelDelivery }),
  });
}

export function getScheduledPromptRuns(id: string) {
  return api<{ runs: ScheduledPromptRun[] }>(`/api/scheduled-prompts/${encodeURIComponent(id)}/runs`);
}

export function getScheduledPromptMemoryProposals(id: string) {
  return api<{ proposals: ScheduledPromptMemoryProposal[]; contract: string }>(
    `/api/scheduled-prompts/${encodeURIComponent(id)}/memory-proposals`,
  );
}

export function applyScheduledPromptMemoryProposal(id: string, proposalId: string, apply = false) {
  return api<{ proposalId: string; applied: boolean; result: unknown }>(
    `/api/scheduled-prompts/${encodeURIComponent(id)}/memory-proposals/${encodeURIComponent(proposalId)}/apply`,
    {
      method: 'POST',
      body: JSON.stringify({ apply }),
    },
  );
}

export function getPrompt(id: string) {
  return api<PromptDetail>(`/api/prompts/${encodeURIComponent(id)}`);
}

export function getPromptRevision(id: string, revision: string) {
  return api<PromptRevision>(`/api/prompts/${encodeURIComponent(id)}/revisions/${encodeURIComponent(revision)}`);
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
