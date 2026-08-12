import { useEffect, useMemo, useState, useTransition } from 'react';
import Editor, { DiffEditor, loader } from '@monaco-editor/react';
import * as monaco from 'monaco-editor';
import EditorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker';
import { useMutation, useQuery } from '@tanstack/react-query';
import { CheckCircle2, Columns3, FileDiff, FlaskConical, GitCommitHorizontal, History, PanelLeftClose, PanelLeftOpen, Play, Save, ShieldCheck, Trash2 } from 'lucide-react';
import { createDraft, getPromptRevision, getPromptWorkbenchContext } from '../api';
import { choosePromptDiffText } from '../promptDiff';
import { readLocalStorage, writeLocalStorage } from '../storage';
import type { DraftRecord, EvalFamily, GitHistoryRow, PromptDetail, PromptWorkbenchContext } from '../types';
import { RenderedPrompt } from './RenderedPrompt';

type MonacoWorkerHost = typeof globalThis & {
  MonacoEnvironment?: {
    getWorker: () => Worker;
  };
};

(globalThis as MonacoWorkerHost).MonacoEnvironment = {
  getWorker: () => new EditorWorker(),
};

loader.config({ monaco });

interface Props {
  prompt?: PromptDetail;
  loading: boolean;
  themeMode: 'light' | 'dark';
  onDirtyChange?: (dirty: boolean) => void;
  onSaved: () => void;
  onLog: (message: string) => void;
  onApplyDraft: (draft: DraftRecord) => void;
  onDiscardDraft: (draft: DraftRecord) => void;
  onRunEval: (options: { maxCases?: number; live?: boolean; family?: string; surface?: string; promptId?: string; caseIds?: string[] }) => void;
  reviewRequestKey?: number;
}

export function PromptEditor({ prompt, loading, themeMode, onDirtyChange, onSaved, onLog, onApplyDraft, onDiscardDraft, onRunEval, reviewRequestKey }: Props) {
  const [body, setBody] = useState('');
  const [activeTab, setActiveTab] = useState<'edit' | 'rendered' | 'diff' | 'history'>('edit');
  const [metadataDraft, setMetadataDraft] = useState<Record<string, unknown>>({});
  const [selectedPatch, setSelectedPatch] = useState<{ title: string; patch: string } | null>(null);
  const [diffBaseRevision, setDiffBaseRevision] = useState('current');
  const [metaOpen, setMetaOpen] = useState(() => {
    return readLocalStorage('viventium.promptWorkbench.promptMetaOpen') !== 'false';
  });
  const [, startTransition] = useTransition();
  const editorTheme = themeMode === 'dark' ? 'vs-dark' : 'vs';
  const selectTab = (tab: 'edit' | 'rendered' | 'diff' | 'history') => startTransition(() => setActiveTab(tab));
  const contextQuery = useQuery({
    queryKey: ['promptWorkbenchContext', prompt?.id],
    queryFn: () => getPromptWorkbenchContext(prompt!.id),
    enabled: Boolean(prompt?.id),
    refetchInterval: 15_000,
  });
  const selectedHistoryRevision = Boolean(prompt?.id && diffBaseRevision !== 'current' && diffBaseRevision !== 'working-tree-base');
  const revisionQuery = useQuery({
    queryKey: ['promptRevision', prompt?.id, diffBaseRevision],
    queryFn: () => getPromptRevision(prompt!.id, diffBaseRevision),
    enabled: selectedHistoryRevision,
    retry: false,
  });

  useEffect(() => {
    writeLocalStorage('viventium.promptWorkbench.promptMetaOpen', String(metaOpen));
  }, [metaOpen]);

  useEffect(() => {
    setBody(prompt?.body ?? '');
    setMetadataDraft(prompt?.metadata ?? {});
    setActiveTab(prompt?.body?.trim() ? 'edit' : 'rendered');
    setSelectedPatch(null);
    setDiffBaseRevision(prompt?.workingTreeChanged ? 'working-tree-base' : 'current');
  }, [prompt?.id, prompt?.body, prompt?.metadata, prompt?.workingTreeChanged]);

  const metadataChanged = Boolean(prompt && JSON.stringify(metadataDraft) !== JSON.stringify(prompt.metadata));
  const changed = Boolean(prompt && (body !== prompt.body || metadataChanged));
  const draftMutation = useMutation({
    mutationFn: async () => {
      if (!prompt) throw new Error('No prompt selected');
      const nextText = replacePromptText(prompt, metadataDraft, body);
      return createDraft(prompt.path, nextText, `Workbench edit for ${prompt.id}`);
    },
    onSuccess: (draft) => {
      onLog(draft.duplicate ? `Matching draft already exists for ${friendlyPath(draft.targetPath)}.` : `Draft ${draft.id} created. Review it before applying to markdown.`);
      setBody(prompt?.body ?? '');
      setMetadataDraft(prompt?.metadata ?? {});
      setSelectedPatch({ title: `Draft ${draft.id}`, patch: draft.patch });
      setActiveTab('history');
      onSaved();
    },
    onError: (error) => onLog(String(error)),
  });

  const nextText = useMemo(() => prompt ? replacePromptText(prompt, metadataDraft, body) : '', [prompt, metadataDraft, body]);
  const context = contextQuery.data;
  const pendingDrafts = context?.drafts.filter((draft) => draft.status === 'draft') ?? [];
  const latestEval = context?.evalRuns[0];
  const runtimeBundle = context?.runtimePromptBundle;
  const showMetaPanel = metaOpen && activeTab !== 'history';
  const hasWorkingTreeSourceChange = Boolean(prompt?.workingTreeChanged);
  const currentPromptText = prompt?.text ?? '';
  const diffBaseOptions = useMemo(() => {
    const options = [
      { value: 'current', label: 'Applied source file' },
      ...(hasWorkingTreeSourceChange ? [{ value: 'working-tree-base', label: 'Git HEAD before local edits' }] : []),
      ...((prompt?.gitHistory ?? [])
        .filter((row) => !row.workingTree)
        .map((row) => ({ value: row.commit, label: `${row.commit} · ${row.date} · ${row.subject}` }))),
    ];
    return options;
  }, [prompt?.gitHistory, hasWorkingTreeSourceChange]);
  useEffect(() => {
    if (!diffBaseOptions.some((option) => option.value === diffBaseRevision)) {
      setDiffBaseRevision('current');
    }
  }, [diffBaseOptions, diffBaseRevision]);
  const diffBaseLabel = diffBaseOptions.find((option) => option.value === diffBaseRevision)?.label ?? 'Applied source file';
  const selectedDiffBaseText = diffBaseRevision === 'current'
    ? currentPromptText
    : diffBaseRevision === 'working-tree-base'
      ? prompt?.workingTreeBaseText ?? ''
      : revisionQuery.data?.text ?? '';
  const diffTargetLabel = changed ? 'editor buffer' : 'applied source file';
  const { original: diffOriginal, modified: diffModified } = choosePromptDiffText({
    changed,
    currentPromptText,
    nextText,
    workingTreeChanged: hasWorkingTreeSourceChange,
    workingTreeBaseText: prompt?.workingTreeBaseText,
    selectedBaseText: selectedDiffBaseText,
  });
  const sourceStateLabel = changed && pendingDrafts.length
    ? 'unsaved edits + draft waiting'
    : changed && hasWorkingTreeSourceChange
      ? 'unsaved edits + source changed'
    : pendingDrafts.length
      ? 'draft waiting'
    : changed
      ? 'unsaved edits'
      : hasWorkingTreeSourceChange
        ? 'source changed in working tree'
        : 'source clean';
  const evalBlockedReason = changed
    ? 'Save this edit as a draft, then apply or discard it before running evals.'
    : pendingDrafts.length
      ? `Apply or discard ${pendingDrafts.length} pending draft${pendingDrafts.length === 1 ? '' : 's'} before running evals.`
      : '';
  const reviewFirstDraft = () => {
    const draft = pendingDrafts[0];
    if (!draft) return;
    setSelectedPatch({ title: `Draft ${draft.id}`, patch: draft.patch });
    setActiveTab('history');
  };

  useEffect(() => {
    if (reviewRequestKey && pendingDrafts.length) {
      reviewFirstDraft();
    }
  }, [reviewRequestKey, pendingDrafts.length]);

  useEffect(() => {
    onDirtyChange?.(changed);
  }, [changed, onDirtyChange]);

  if (loading) {
    return <div className="empty-state">Loading prompt...</div>;
  }
  if (!prompt) {
    return <div className="empty-state">Select a prompt to inspect source, rendered output, and lineage.</div>;
  }

  return (
    <div className="prompt-detail">
      <div className="editor-header">
        <div>
          <h2>{humanPromptName(prompt.id)}</h2>
          <p>{prompt.id}</p>
        </div>
        <div className="prompt-meta-row">
          <span className={pendingDrafts.length ? 'attention' : changed || hasWorkingTreeSourceChange ? 'dirty' : ''}>{sourceStateLabel}</span>
          <span>{pendingDrafts.length} draft{pendingDrafts.length === 1 ? '' : 's'}</span>
          <span>{context?.linkedEvals.caseCount ?? 0} eval cases</span>
        </div>
        <div className="segmented slim" role="tablist" aria-label="Prompt detail view">
          <button role="tab" aria-selected={activeTab === 'edit'} className={activeTab === 'edit' ? 'active' : ''} onClick={() => selectTab('edit')}><Columns3 size={14} /> Edit</button>
          <button role="tab" aria-selected={activeTab === 'rendered'} className={activeTab === 'rendered' ? 'active' : ''} onClick={() => selectTab('rendered')}>Rendered</button>
          <button role="tab" aria-selected={activeTab === 'diff'} className={activeTab === 'diff' ? 'active' : ''} onClick={() => selectTab('diff')}><FileDiff size={14} /> Diff</button>
          <button role="tab" aria-selected={activeTab === 'history'} className={activeTab === 'history' ? 'active' : ''} onClick={() => selectTab('history')}><History size={14} /> History</button>
        </div>
        <button
          className="toolbar-button icon-button"
          onClick={() => setMetaOpen((value) => !value)}
          aria-label={metaOpen ? 'Hide prompt metadata sidebar' : 'Show prompt metadata sidebar'}
          aria-pressed={metaOpen}
          title={metaOpen ? 'Hide prompt metadata sidebar' : 'Show prompt metadata sidebar'}
        >
          {metaOpen ? <PanelLeftClose size={16} /> : <PanelLeftOpen size={16} />}
        </button>
        <button
          className="toolbar-button primary"
          disabled={!changed || draftMutation.isPending}
          title={changed ? 'Create a reviewed draft. This does not push live.' : 'No prompt changes to save'}
          onClick={() => draftMutation.mutate()}
        >
          <Save size={16} />
          Save draft
        </button>
        {pendingDrafts.length > 0 && (
          <button className="toolbar-button" onClick={reviewFirstDraft} title="Open the pending draft diff">
            <FileDiff size={16} />
            Review draft
          </button>
        )}
      </div>
      <div className="prompt-review-strip">
        <span><ShieldCheck size={14} /> {changed ? 'Unsaved edit in the editor buffer.' : pendingDrafts.length ? 'Source file is unchanged until draft is applied.' : 'Source file is applied.'}</span>
        <span><FileDiff size={14} /> Diff compares {diffBaseLabel} to {diffTargetLabel}</span>
        {hasWorkingTreeSourceChange && <span><FileDiff size={14} /> Diff shows working-tree source changes</span>}
        <span><FlaskConical size={14} /> {latestEval ? `Last eval used applied source: ${latestEval.returnCode === 0 ? 'ok' : `code ${latestEval.returnCode}`}` : 'No eval run recorded for this prompt'}</span>
        <span title={deliveryTitle(context?.delivery, runtimeBundle)}><GitCommitHorizontal size={14} /> {deliveryLabel(context?.delivery, runtimeBundle)}</span>
        {pendingDrafts.length > 0 && (
          <button className="workflow-inline-action" onClick={reviewFirstDraft}>
            Review draft
          </button>
        )}
      </div>
      {(changed || pendingDrafts.length > 0) && (
        <div className="workflow-callout">
          <strong>{pendingDrafts.length ? 'Step 1: review the draft' : 'Unsaved edit not ready for eval'}</strong>
          <span>{pendingDrafts.length ? 'Apply the reviewed draft to source, or discard it. Then run evals and Push dry-run from the applied source.' : 'Save a draft and review the diff before this change can be evaluated or pushed.'}</span>
          {pendingDrafts.length > 0 && <button className="mini-action" onClick={reviewFirstDraft}>Review/apply draft</button>}
        </div>
      )}

      <div className={`editor-grid ${showMetaPanel ? '' : 'meta-collapsed'} ${activeTab === 'history' ? 'history-focus' : ''}`}>
        {showMetaPanel && (
          <div className="frontmatter-panel">
            <h3>Frontmatter</h3>
            <FrontmatterForm metadata={metadataDraft} onChange={setMetadataDraft} />
            <h3>Includes</h3>
            <div className="chips">
              {prompt.includes.length ? prompt.includes.map((include) => <span key={include}>{include}</span>) : <em>none</em>}
            </div>
            <h3>Variables</h3>
            <div className="chips">
              {prompt.variables.length ? prompt.variables.map((variable) => <span key={variable}>{variable}</span>) : <em>none</em>}
            </div>
            <h3>Dependents</h3>
            <div className="chips">
              {prompt.dependents.length ? prompt.dependents.map((dependent) => <span key={dependent}>{dependent}</span>) : <em>none</em>}
            </div>
            <h3>Git History</h3>
            <div className="history-list">
              {prompt.gitHistory.length ? prompt.gitHistory.map((row) => (
                <div className="history-row" key={`${row.commit}-${row.date}`}>
                  <code>{row.commit}</code>
                  <span>{row.subject}</span>
                  <small>{row.date}</small>
                </div>
              )) : <em>none</em>}
            </div>
          </div>
        )}
        <div className="monaco-panel">
          {activeTab === 'edit' && (
            <Editor
              height="100%"
              language="markdown"
              theme={editorTheme}
              value={body}
              options={{
                automaticLayout: true,
                minimap: { enabled: false },
                wordWrap: 'on',
                fontSize: 13,
                lineHeight: 21,
                scrollBeyondLastLine: false,
              }}
              onChange={(value) => setBody(value ?? '')}
            />
          )}
          {activeTab === 'rendered' && <RenderedPrompt markdown={prompt.rendered} />}
          {activeTab === 'diff' && (
            <div className="diff-panel">
              <div className="diff-toolbar">
                <label className="diff-select-label">
                  <span>Compare from</span>
                  <select value={diffBaseRevision} onChange={(event) => setDiffBaseRevision(event.target.value)}>
                    {diffBaseOptions.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </label>
                <span className="diff-target-label">to {diffTargetLabel}</span>
                {revisionQuery.isFetching && <span className="diff-status">Loading revision...</span>}
                {revisionQuery.isError && <span className="diff-status error">Revision unavailable</span>}
              </div>
              <div className="diff-editor-shell">
                <DiffEditor
                  height="100%"
                  language="markdown"
                  theme={editorTheme}
                  original={diffOriginal}
                  modified={diffModified}
                  keepCurrentOriginalModel
                  keepCurrentModifiedModel
                  options={{
                    automaticLayout: true,
                    readOnly: true,
                    renderSideBySide: true,
                    diffWordWrap: 'on',
                    wordWrapOverride1: 'on',
                    wordWrapOverride2: 'on',
                    minimap: { enabled: false },
                    wordWrap: 'on',
                    fontSize: 13,
                    lineHeight: 21,
                    scrollBeyondLastLine: false,
                  }}
                />
              </div>
            </div>
          )}
          {activeTab === 'history' && (
            <PromptHistoryView
              drafts={context?.drafts ?? []}
              gitHistory={context?.gitHistory ?? prompt.gitHistory}
              evalFamilies={context?.linkedEvals.families ?? []}
              evalRuns={context?.evalRuns ?? []}
              qaCoverage={context?.qaCoverage ?? []}
              relatedConfig={context?.relatedConfig ?? []}
              selectedPatch={selectedPatch}
              onSelectPatch={setSelectedPatch}
              onApplyDraft={onApplyDraft}
              onDiscardDraft={onDiscardDraft}
              blockedReason={evalBlockedReason}
              onRunEval={(familyId) => onRunEval({ promptId: prompt.id, family: familyId, maxCases: 1, live: false })}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function PromptHistoryView({
  drafts,
  gitHistory,
  evalFamilies,
  evalRuns,
  qaCoverage,
  relatedConfig,
  selectedPatch,
  onSelectPatch,
  onApplyDraft,
  onDiscardDraft,
  blockedReason,
  onRunEval,
}: {
  drafts: DraftRecord[];
  gitHistory: GitHistoryRow[];
  evalFamilies: EvalFamily[];
  evalRuns: Array<{ id: string; returnCode: number; family?: string; surface?: string; resultCount?: number; artifactName?: string; promptHash?: string }>;
  qaCoverage: Array<{ id: string; title: string; source: string; lastRun?: string }>;
  relatedConfig: NonNullable<PromptWorkbenchContext['relatedConfig']>;
  selectedPatch: { title: string; patch: string } | null;
  onSelectPatch: (patch: { title: string; patch: string } | null) => void;
  onApplyDraft: (draft: DraftRecord) => void;
  onDiscardDraft: (draft: DraftRecord) => void;
  blockedReason?: string;
  onRunEval: (familyId: string) => void;
}) {
  const pending = drafts.filter((draft) => draft.status === 'draft');
  const history = drafts.filter((draft) => draft.status !== 'draft');
  return (
    <div className="prompt-history-view">
      <section className="history-section">
        <div className="history-section-head">
          <h3>What Changed</h3>
          <span>{pending.length} pending</span>
        </div>
        {!drafts.length && <p className="small-copy">No draft history for this prompt yet.</p>}
        {pending.map((draft) => (
          <div className="change-row" key={draft.id}>
            <button onClick={() => onSelectPatch({ title: `Draft ${draft.id}`, patch: draft.patch })}>
              <strong>{draft.changeSummary?.label ?? 'draft changes'}</strong>
              <small>{friendlyPath(draft.targetPath)} · {new Date(draft.createdAt).toLocaleString()}</small>
            </button>
            <button className="mini-action" onClick={() => onApplyDraft(draft)}><CheckCircle2 size={14} /> {draft.kind === 'eval-edit' ? 'Apply eval draft' : 'Apply to source'}</button>
            <button className="mini-action" onClick={() => onDiscardDraft(draft)}><Trash2 size={14} /> Discard</button>
          </div>
        ))}
        {history.slice(0, 5).map((draft) => (
          <button className="history-pill" key={draft.id} onClick={() => onSelectPatch({ title: `${draft.status} draft ${draft.id}`, patch: draft.patch })}>
            {draft.status} · {draft.changeSummary?.label ?? 'changes'} · {friendlyPath(draft.targetPath)}
          </button>
        ))}
      </section>

      <section className="history-section">
        <div className="history-section-head">
          <h3>Git History</h3>
          <span>{gitHistory.length} entries</span>
        </div>
        {gitHistory.map((row) => (
          <button className="git-row" key={`${row.commit}-${row.date}`} onClick={() => onSelectPatch({ title: `${row.commit} ${row.subject}`, patch: row.patch || '' })}>
            <code>{row.commit}</code>
            <span>{row.subject}</span>
            <small>{row.changeSummary?.label ?? row.date}</small>
          </button>
        ))}
      </section>

      <section className="history-section config-section">
        <div className="history-section-head">
          <h3>Related Config</h3>
          <span>{relatedConfig.length} files</span>
        </div>
        {!relatedConfig.length && <p className="small-copy">No linked config surfaces for this prompt.</p>}
        <div className="related-config-grid">
          {relatedConfig.map((config) => (
            <article className="related-config-card" key={config.id}>
              <div className="related-config-title">
                <strong>{config.title}</strong>
                <small>{friendlyPath(config.path)} · {config.selector}</small>
              </div>
              <p>{config.summary}</p>
              <ul>
                {config.items.slice(0, 7).map((item) => <li key={item}>{item}</li>)}
              </ul>
              <div className="config-history-row">
                {config.gitHistory.slice(0, 3).map((row) => (
                  <span key={`${config.id}-${row.commit}`}>{row.commit} · {row.subject}</span>
                ))}
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="history-section wide">
        <div className="history-section-head">
          <h3>Linked Evals and QA</h3>
          <span>{evalFamilies.reduce((sum, family) => sum + (family.cases?.length ?? 0), 0)} cases</span>
        </div>
        {blockedReason && (
          <div className="workflow-callout compact">
            <strong>Apply draft before eval</strong>
            <span>{blockedReason}</span>
          </div>
        )}
        <div className="linked-eval-grid">
          {evalFamilies.map((family) => (
            <article className="linked-eval-card" key={family.id}>
              <div>
                <strong>{family.id}</strong>
                <small>{family.goal}</small>
              </div>
              <button
                className="mini-action"
                disabled={Boolean(blockedReason)}
                title={blockedReason || 'Run preview for this eval family'}
                onClick={() => onRunEval(family.id)}
              >
                <Play size={14} /> {blockedReason ? 'Review draft first' : 'Run preview'}
              </button>
              <ul>
                {(family.cases ?? []).slice(0, 4).map((testCase) => (
                  <li key={testCase.id}><span>{testCase.id}</span><small>{testCase.surface}</small></li>
                ))}
              </ul>
            </article>
          ))}
          {!evalFamilies.length && <p className="small-copy">No eval families are mapped to this prompt yet.</p>}
        </div>
        <div className="qa-chip-row">
          {qaCoverage.map((row) => <span key={row.id}>{row.id} · {row.title}</span>)}
        </div>
        <div className="run-list compact">
          {evalRuns.slice(0, 4).map((run) => (
            <div className="run-row" key={run.id}>
              <code>{run.id}</code>
              <span>{run.family ?? 'selected cases'}</span>
              <small>{run.returnCode === 0 ? 'ok' : `code ${run.returnCode}`} · {run.resultCount ?? 0} case(s){run.promptHash ? ` · ${run.promptHash}` : ''}</small>
            </div>
          ))}
        </div>
      </section>

      <section className="history-section patch-preview">
        <div className="history-section-head">
          <h3>{selectedPatch?.title ?? 'Preview'}</h3>
          <span>diff</span>
        </div>
        <pre>{selectedPatch?.patch || 'Select a draft or git row to preview the exact change.'}</pre>
      </section>
    </div>
  );
}

function FrontmatterForm({ metadata, onChange }: { metadata: Record<string, unknown>; onChange: (value: Record<string, unknown>) => void }) {
  const update = (key: string, value: unknown) => onChange({ ...metadata, [key]: value });
  const includesText = Array.isArray(metadata.includes) ? metadata.includes.join('\n') : '';
  return (
    <div className="frontmatter-form">
      {(['id', 'owner_layer', 'target', 'status', 'safety_class', 'output_contract'] as const).map((key) => (
        <label key={key}>
          <span>{key}</span>
          <input value={String(metadata[key] ?? '')} onChange={(event) => update(key, event.target.value)} />
        </label>
      ))}
      <label>
        <span>version</span>
        <input
          type="number"
          value={Number(metadata.version ?? 1)}
          onChange={(event) => update('version', Number(event.target.value || 1))}
        />
      </label>
      <label>
        <span>includes</span>
        <textarea
          value={includesText}
          onChange={(event) => update('includes', event.target.value.split('\n').map((line) => line.trim()).filter(Boolean))}
        />
      </label>
    </div>
  );
}

function friendlyPath(path: string) {
  const parts = path.split(/[\\/]/).filter(Boolean);
  return parts.slice(-2).join('/');
}

function replacePromptText(prompt: PromptDetail, metadata: Record<string, unknown>, body: string) {
  return `---\n${serializeFrontmatter(metadata)}---\n${body.trimEnd()}\n`;
}

function serializeFrontmatter(metadata: Record<string, unknown>) {
  const preferred = ['id', 'owner_layer', 'target', 'version', 'status', 'safety_class', 'required_context', 'output_contract', 'includes'];
  const keys = [...preferred.filter((key) => key in metadata), ...Object.keys(metadata).filter((key) => !preferred.includes(key))];
  return keys.map((key) => serializeYamlEntry(key, metadata[key], 0)).join('');
}

function serializeYamlEntry(key: string, value: unknown, indent: number): string {
  const prefix = ' '.repeat(indent);
  if (Array.isArray(value)) {
    if (!value.length) return `${prefix}${key}: []\n`;
    return `${prefix}${key}:\n${value.map((item) => serializeYamlArrayItem(item, indent + 2)).join('')}`;
  }
  if (value && typeof value === 'object') {
    return `${prefix}${key}:\n${Object.entries(value as Record<string, unknown>).map(([childKey, childValue]) => serializeYamlEntry(childKey, childValue, indent + 2)).join('')}`;
  }
  return `${prefix}${key}: ${formatYamlScalar(value)}\n`;
}

function serializeYamlArrayItem(value: unknown, indent: number): string {
  const prefix = ' '.repeat(indent);
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const entries = Object.entries(value as Record<string, unknown>);
    if (!entries.length) return `${prefix}- {}\n`;
    const [firstKey, firstValue] = entries[0];
    const first = `${prefix}- ${firstKey}: ${formatYamlScalar(firstValue)}\n`;
    const rest = entries.slice(1).map(([key, item]) => serializeYamlEntry(key, item, indent + 2)).join('');
    return first + rest;
  }
  return `${prefix}- ${formatYamlScalar(value)}\n`;
}

function formatYamlScalar(value: unknown) {
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  const text = String(value ?? '');
  if (!text) return '""';
  return /^[A-Za-z0-9_.:/ -]+$/.test(text) ? text : JSON.stringify(text);
}

function humanPromptName(id: string) {
  const label = id.split('.').slice(1).join(' ') || id;
  return label.replace(/[._-]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function deliveryLabel(
  delivery?: PromptWorkbenchContext['delivery'],
  bundle?: PromptWorkbenchContext['runtimePromptBundle'],
) {
  if (delivery?.kind === 'managed_agent') {
    return `Managed agent: ${humanDeliveryState(delivery.state)}`;
  }
  if (!bundle) return 'Compiled runtime: checking';
  switch (bundle.promptState) {
    case 'synced':
      return 'Compiled runtime: live';
    case 'source-only':
    case 'drift':
      return 'Compiled runtime: needs rebuild';
    case 'bundle-unavailable':
      return 'Compiled runtime: not found';
    case 'other-drift':
      return 'Compiled runtime: other drift';
    default:
      return 'Compiled runtime: unknown';
  }
}

function deliveryTitle(
  delivery?: PromptWorkbenchContext['delivery'],
  bundle?: PromptWorkbenchContext['runtimePromptBundle'],
) {
  if (delivery?.kind === 'managed_agent') {
    return `This prompt is delivered through the managed agent source/live sync boundary. Current state: ${humanDeliveryState(delivery.state)}.`;
  }
  if (!bundle) return 'Checking compiled prompt bundle status.';
  const count = bundle.driftCount ?? 0;
  if (bundle.promptAffected) {
    return `This prompt differs from the compiled runtime prompt bundle. Drift count: ${count}.`;
  }
  if (bundle.promptState === 'other-drift') {
    return `This prompt matches the compiled bundle, but other prompts differ. Drift count: ${count}.`;
  }
  if (bundle.promptState === 'bundle-unavailable') {
    return 'No compiled runtime prompt bundle was found for drift comparison.';
  }
  return `Prompt bundle status: ${bundle.status}.`;
}

function humanDeliveryState(state?: string) {
  if (state === 'synced') return 'synced';
  if (state === 'source-ahead') return 'source changed';
  if (state === 'live-ahead') return 'live changed';
  if (state === 'conflict') return 'needs merge';
  if (state === 'not-mapped') return 'unit not mapped';
  return state || 'unknown';
}
