export type SyncState = "synced" | "live-ahead" | "source-ahead" | "conflict";

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
  workingTreeBaseText?: string | null;
  workingTreeChanged?: boolean;
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

export interface PromptRevision {
  promptId: string;
  revision: string;
  path: string;
  text: string;
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
  workingTree?: boolean;
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
  status: "draft" | "applied" | "discarded";
  mappedPromptId?: string;
  agentId?: string;
  duplicate?: boolean;
  duplicateCount?: number;
  promptId?: string;
}

export interface EvalFamily {
  id: string;
  goal: string;
  runner?: "background_activation" | "background_execution" | string;
  executionTarget?: {
    agentId: string;
    promptRef: string;
  };
  semanticJudge?: boolean;
  promptRefs?: string[];
  runtimeContextRefs?: string[];
  cases: Array<{
    id: string;
    surface: string;
    prompt: string;
    promptRefs?: string[];
    semanticJudge?: boolean;
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
  selectedCaseCount?: number;
  semanticJudgeRequired?: boolean;
  runnerSummary?: {
    status?: string;
    blockedReason?: string;
    resultCount?: number;
    completedCount?: number;
    failedCount?: number;
    semanticJudgedCount?: number;
    semanticPassedCount?: number;
    semanticFailedCount?: number;
    semanticJudgeUnavailableCount?: number;
    duplicateResponseQualityFailureCount?: number;
    unresolvedAsyncQualityFailureCount?: number;
  } | null;
  executionTarget?: {
    mode: "direct_background_agent";
    agentId: string;
    promptRef: string;
  } | null;
  lineageManifest?: {
    schemaVersion?: number;
    manifestHash: string;
    familyIds?: string[];
    caseIds?: string[];
    rootPromptIds?: string[];
    promptCount?: number;
    runtimeContextCount?: number;
    promptDependencies: Array<{
      id: string;
      kind?: string;
      status?: string;
      direct?: boolean;
      contentHash?: string | null;
      renderedHash?: string | null;
      deliveryKind?: string;
    }>;
    runtimeContextDependencies: Array<{
      id: string;
      kind: string;
      tag?: string;
      lifecycle?: string;
      owner?: string;
      valuePolicy?: string;
      roleContract?: string;
      contractHash?: string;
      status?: string;
    }>;
  };
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
  qaCoverage: Array<{
    id: string;
    title: string;
    source: string;
    lastRun?: string;
  }>;
  relatedConfig?: Array<{
    id: string;
    title: string;
    path: string;
    selector: string;
    summary: string;
    status: string;
    items: string[];
    gitHistory: GitHistoryRow[];
  }>;
  sync?: SyncAgent;
  delivery?: {
    kind: "managed_agent" | "compiled_runtime";
    label: string;
    statusSource: string;
    target: string;
    state: string;
  };
  runtimePromptBundle?: {
    status: string;
    reason: string;
    promptState: string;
    promptAffected: boolean;
    liveBundleAvailable: boolean;
    driftCount?: number | null;
    candidateCount?: number | null;
    sourcePromptCount?: number | null;
    livePromptCount?: number | null;
    compareReviewed?: boolean;
  } | null;
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

export interface AuthStatus {
  authenticated: boolean;
  admin: boolean;
  method: string;
  userId?: string | null;
  email?: string | null;
  reason?: string | null;
}

export interface VariableRegistry {
  variables: Array<{
    name: string;
    kind: string;
    wrapper: string;
    description: string;
  }>;
  functions: Array<{
    name: string;
    kind: string;
    wrapper: string;
    description: string;
    arguments?: string[];
  }>;
}

export interface VariableRenderResult {
  rendered: string;
  renderedHash: string;
  variableSnapshot: {
    resolvedAt: string;
    userId: string;
    items: Array<{
      placeholder: string;
      wrapper: string;
      kind: string;
      hash: string;
      value: unknown;
      rendered: string;
    }>;
  };
  variableSnapshotJson: string;
  variableSnapshotHash: string;
}

export interface ScheduledPromptRun {
  runId: string;
  taskId?: string;
  definitionId?: string;
  versionId?: string;
  dueAt?: string;
  startedAt?: string;
  completedAt?: string;
  status: string;
  executor: string;
  renderedHash?: string;
  variableSnapshotHash?: string;
  glasshiveProjectId?: string;
  glasshiveWorkerId?: string;
  glasshiveRunId?: string;
  resultSummary?: string;
  errorClass?: string;
  requestedReasoningEffort?: string | null;
  effectiveReasoningEffort?: string | null;
  reasoningFallbackReason?: string | null;
  privateDetailPointer?: string;
  updatedAt?: string;
}

export interface ScheduledPrompt {
  id: string;
  taskId?: string;
  userId?: string;
  title: string;
  sourcePromptId?: string;
  templateId?: string;
  promptText: string;
  schedule: Record<string, unknown>;
  timezone?: string;
  active: boolean;
  channel?: string | string[];
  executor?: string;
  conversationPolicy?: "new" | "same";
  memoryWriteMode: string;
  myFolder?: string;
  workspaceRoot?: string | null;
  workspaceAlias?: string | null;
  executionProfile?: string | null;
  executionMode?: string | null;
  executionModel?: string | null;
  reasoningEffort?: string | null;
  glasshiveWorkerStrategy?: "same_worker" | "new_worker_each_run" | null;
  nextRunAt?: string;
  lastStatus?: string;
  latestVersion?: {
    id: string;
    versionNumber: number;
    renderedHash: string;
    variableSnapshotHash: string;
    createdAt: string;
  };
  recentRuns: ScheduledPromptRun[];
  sourceKind?: "workbench_definition" | "user_schedule";
  sourceLabel?: string;
  createdAt: string;
  updatedAt: string;
}

export interface ScheduledPromptTemplate {
  id: string;
  title: string;
  promptText: string;
  schedule: Record<string, unknown>;
  active: boolean;
  memoryWriteMode: string;
}

export interface ScheduledPromptMemoryProposal {
  proposalId: string;
  fileName: string;
  updatedAt?: string;
  actionCount: number;
  actions: Array<{
    action: "set" | "delete";
    key: string;
    valueHash?: string | null;
    valuePreview?: string;
    reason?: string;
  }>;
}

export interface ScheduledPromptPeripheryArtifact {
  artifactId: string;
  moduleId: string;
  sidecarFileName: string;
  markdownFileName: string;
  relativePath: string;
  markdownRelativePath: string;
  markdownExists: boolean;
  schemaVersion: number;
  generatedAt: string;
  updatedAt?: string | null;
  confidence: string;
  severity: string;
  timeSensitivity: string;
  ttl: string;
  staleAfter: string;
  sourceRefCount: number;
  sourceRefsResolvedCount: number;
  sourceRefsUnresolvedCount: number;
  snapshotRefHash?: string | null;
  snapshotAvailable?: boolean | null;
  stale: boolean;
  qualityStatus: "passed" | "warning" | "failed" | "legacy" | string;
  scheduledRunRefHash?: string | null;
  contentCounts: Record<string, number>;
}

export interface ScheduledPromptInvalidPeripheryArtifact {
  fileName: string;
  relativePath: string;
  reason: string;
  missingFields?: string[];
  invalidFields?: string[];
}

export interface ScheduledPromptPeripheryIndex {
  generatedAt?: string | null;
  artifactCount: number;
  invalidArtifactCount: number;
  qualityCounts: Record<string, number>;
  modules: Array<{
    moduleId: string;
    description: string;
    latestArtifactId?: string | null;
    latestGeneratedAt?: string | null;
    latestQualityStatus?: string | null;
    artifactCount: number;
  }>;
}

export interface ScheduledPromptPeripherySnapshot {
  schemaVersion: number;
  snapshotRef?: string | null;
  snapshotId?: string | null;
  generatedAt?: string | null;
  status: "complete" | "degraded" | "not_created" | string;
  missingPrerequisites: string[];
  counts: Record<string, number>;
  sourceRefCount: number;
  contentHash?: string;
  labelsHash?: string;
}

export interface ScheduledPromptPeripheryArtifactDetail {
  artifact: ScheduledPromptPeripheryArtifact;
  sidecar: Record<string, unknown>;
  markdown: string;
  usage: string;
}
