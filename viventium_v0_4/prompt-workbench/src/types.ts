export type SyncState = 'synced' | 'live-ahead' | 'source-ahead' | 'conflict';

export interface PromptRow {
  id: string;
  path: string;
  family: string;
  ownerLayer: string;
  target: string;
  version: number;
  status: string;
  safetyClass: string;
  contentHash: string;
  bodyHash: string;
  includeCount: number;
  charCount: number;
}

export interface FlowGraph {
  nodes: Array<{
    id: string;
    type: string;
    data: {
      label: string;
      family: string;
      hash?: string;
    };
  }>;
  edges: Array<{
    id: string;
    source: string;
    target: string;
    label?: string;
  }>;
}

export interface PromptDetail {
  id: string;
  path: string;
  text: string;
  metadata: Record<string, unknown>;
  body: string;
  rendered: string;
  contentHash: string;
  bodyHash: string;
  variables: string[];
  includes: string[];
  dependents: string[];
  gitHistory: Array<GitHistoryRow>;
}

export interface ChangeSummary {
  additions: number;
  deletions: number;
  label: string;
}

export interface GitHistoryRow {
  commit: string;
  date: string;
  subject: string;
  patch?: string;
  changeSummary?: ChangeSummary;
}

export interface SyncAgent {
  agentId: string;
  label: string;
  sourcePromptId?: string;
  sourceHash: string;
  liveHash?: string;
  state: SyncState;
  sourceChars: number;
  liveChars: number;
  liveTextAvailable: boolean;
}

export interface SyncStatus {
  generatedAt: string;
  sourceCommit: string;
  liveArtifactAvailable: boolean;
  liveArtifactName?: string;
  ledgerAvailable: boolean;
  counts: Record<SyncState, number>;
  agents: SyncAgent[];
}

export interface DraftRecord {
  id: string;
  kind: string;
  targetPath: string;
  baseHash: string;
  newHash: string;
  createdAt: string;
  appliedAt?: string;
  discardedAt?: string;
  reason: string;
  idempotencyToken: string;
  patch: string;
  changeSummary?: ChangeSummary;
  status: 'draft' | 'applied' | 'discarded';
  mappedPromptId?: string;
  agentId?: string;
  duplicate?: boolean;
  duplicateCount?: number;
  promptId?: string;
}

export interface EvalFamily {
  id: string;
  goal: string;
  promptRefs?: string[];
  cases: Array<{
    id: string;
    surface: string;
    prompt: string;
    promptRefs?: string[];
    rubric?: string[];
    expected_decision?: string;
    expected_surface?: string;
  }>;
}

export interface EvalBank {
  version: number;
  scope: string;
  familyCount: number;
  caseCount: number;
  families: EvalFamily[];
}

export interface EvalRun {
  id: string;
  mode?: string;
  returnCode: number;
  resultCount?: number;
  stdoutTail: string;
  stderrTail: string;
  artifactName?: string;
  privateOutputAvailable?: boolean;
  createdAt: string;
  live: boolean;
  maxCases: number;
  family?: string;
  surface?: string;
  promptId?: string;
  promptHash?: string;
  selectedCaseIds?: string[];
}

export interface PromptWorkbenchContext {
  promptId: string;
  path: string;
  contentHash: string;
  bodyHash: string;
  drafts: DraftRecord[];
  gitHistory: GitHistoryRow[];
  linkedEvals: {
    promptId: string;
    familyCount: number;
    caseCount: number;
    families: EvalFamily[];
  };
  evalRuns: EvalRun[];
  qaCoverage: Array<{ id: string; title: string; source: string; lastRun?: string }>;
  sync?: SyncAgent;
}

export interface FrameLog {
  time: string;
  surface: string;
  family: string;
  provider: string;
  model: string;
  layer_hashes: Record<string, string>;
  layer_tokens: Record<string, number>;
  decision: Record<string, unknown>;
}
