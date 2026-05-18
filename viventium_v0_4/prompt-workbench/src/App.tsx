import { useEffect, useRef, useState, useTransition } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  ArrowDownToLine,
  BadgeCheck,
  Cable,
  Circle,
  GitBranch,
  Monitor,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  Play,
  RefreshCcw,
  Save,
  Search,
  Sun,
  UploadCloud,
  X,
} from 'lucide-react';
import {
  applyDraft,
  createEvalCaseDraft,
  discardDraft,
  getDrafts,
  getEvalRuns,
  getFrames,
  getPrompts,
  getPrompt,
  getSyncStatus,
  importLiveDraft,
  pullLive,
  pushDryRun,
  pushReviewed,
  runEval,
} from './api';
import { PromptAtlas } from './components/PromptAtlas';
import { WorkbenchDock } from './components/WorkbenchDock';
import { readLocalStorage, writeLocalStorage } from './storage';
import type { DraftRecord } from './types';

export default function App() {
  const queryClient = useQueryClient();
  const [selectedPromptId, setSelectedPromptId] = useState('main.conscious_agent');
  const [search, setSearch] = useState('');
  const [atlasOpen, setAtlasOpen] = useStoredBoolean('viventium.promptWorkbench.atlasOpen', true);
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [showStatusbar, setShowStatusbar] = useStoredBoolean('viventium.promptWorkbench.showStatusbar', false);
  const { themePreference, setThemePreference, resolvedTheme } = useThemePreference();
  const [commandLog, setCommandLog] = useState<string>('Ready.');
  const [reviewToken, setReviewToken] = useState('');
  const [selectedPromptDirty, setSelectedPromptDirty] = useState(false);
  const [dockFocusRequest, setDockFocusRequest] = useState<{ tab: 'prompt' | 'drafts' | 'evals' | 'live'; promptMode?: 'history'; nonce: number }>();
  const settingsRef = useRef<HTMLDivElement>(null);
  const [, startTransition] = useTransition();

  const promptsQuery = useQuery({ queryKey: ['prompts'], queryFn: getPrompts });
  const syncQuery = useQuery({ queryKey: ['sync'], queryFn: getSyncStatus, refetchInterval: 15_000 });
  const draftsQuery = useQuery({ queryKey: ['drafts'], queryFn: getDrafts, refetchInterval: 20_000 });
  const evalRunsQuery = useQuery({ queryKey: ['evalRuns'], queryFn: getEvalRuns, refetchInterval: 20_000 });
  const promptQuery = useQuery({
    queryKey: ['prompt', selectedPromptId],
    queryFn: () => getPrompt(selectedPromptId),
    enabled: Boolean(selectedPromptId),
  });
  const framesQuery = useQuery({ queryKey: ['frames'], queryFn: getFrames });

  const pullMutation = useMutation({
    mutationFn: pullLive,
    onSuccess: () => {
      setCommandLog('Live compare/pull finished. Sync status refreshed.');
      queryClient.invalidateQueries({ queryKey: ['sync'] });
    },
    onError: (error) => setCommandLog(String(error)),
  });

  const dryRunMutation = useMutation({
    mutationFn: pushDryRun,
    onSuccess: (data) => {
      setReviewToken(data.reviewToken);
      setCommandLog('Dry run finished. Reviewed push is unlocked after you inspect the diff.');
      queryClient.invalidateQueries({ queryKey: ['sync'] });
    },
    onError: (error) => setCommandLog(String(error)),
  });

  const evalMutation = useMutation({
    mutationFn: runEval,
    onSuccess: (data) => {
      const label = data.mode === 'synthetic-no-live-preview' ? 'Synthetic preview' : data.live ? 'Live eval' : 'Eval';
      setCommandLog(`${label} run ${data.id} completed with code ${data.returnCode}.`);
      queryClient.invalidateQueries({ queryKey: ['evalRuns'] });
    },
    onError: (error) => setCommandLog(String(error)),
  });

  const evalCaseDraftMutation = useMutation({
    mutationFn: createEvalCaseDraft,
    onSuccess: (draft) => {
      setCommandLog(`Eval draft ${draft.id} created. Review it before applying to the eval bank.`);
      queryClient.invalidateQueries({ queryKey: ['drafts'] });
      queryClient.invalidateQueries({ queryKey: ['promptWorkbenchContext'] });
    },
    onError: (error) => setCommandLog(String(error)),
  });

  const importMutation = useMutation({
    mutationFn: ({ agentId, promptId }: { agentId: string; promptId: string }) => importLiveDraft(agentId, promptId),
    onSuccess: (data) => {
      if (data.status === 'requires_manual_target') {
        setCommandLog(`Manual target required: ${data.reason} Candidates: ${data.candidatePromptIds.join(', ')}`);
        return;
      }
      setCommandLog(`Import draft ${data.id} created for ${data.targetPath}.`);
      queryClient.invalidateQueries({ queryKey: ['drafts'] });
      queryClient.invalidateQueries({ queryKey: ['promptWorkbenchContext'] });
    },
    onError: (error) => setCommandLog(String(error)),
  });

  const reviewedPushMutation = useMutation({
    mutationFn: () => pushReviewed(reviewToken),
    onSuccess: (data) => {
      setReviewToken('');
      setCommandLog(`Reviewed push finished with code ${data.returnCode}.`);
      queryClient.invalidateQueries({ queryKey: ['sync'] });
    },
    onError: (error) => setCommandLog(String(error)),
  });

  const applyDraftMutation = useMutation({
    mutationFn: (draft: DraftRecord) => applyDraft(draft.id, draft.idempotencyToken),
    onSuccess: (data, draft) => {
      setCommandLog(data.alreadyApplied ? `Marked draft ${data.id} resolved; the target already matched that change.` : `Applied draft ${data.id} to ${data.targetPath}.`);
      queryClient.invalidateQueries({ queryKey: ['drafts'] });
      queryClient.invalidateQueries({ queryKey: ['prompts'] });
      queryClient.invalidateQueries({ queryKey: ['prompt', draft.promptId || selectedPromptId] });
      queryClient.invalidateQueries({ queryKey: ['promptWorkbenchContext'] });
      queryClient.invalidateQueries({ queryKey: ['evalRuns'] });
      queryClient.invalidateQueries({ queryKey: ['sync'] });
    },
    onError: (error) => setCommandLog(String(error)),
  });

  const discardDraftMutation = useMutation({
    mutationFn: (draft: DraftRecord) => discardDraft(draft.id),
    onSuccess: (data, draft) => {
      setCommandLog(`Discarded draft ${data.id}.`);
      queryClient.invalidateQueries({ queryKey: ['drafts'] });
      queryClient.invalidateQueries({ queryKey: ['promptWorkbenchContext'] });
      queryClient.invalidateQueries({ queryKey: ['prompt', draft.promptId || selectedPromptId] });
      queryClient.invalidateQueries({ queryKey: ['sync'] });
      queryClient.invalidateQueries({ queryKey: ['evalRuns'] });
    },
    onError: (error) => setCommandLog(String(error)),
  });

  const prompts = promptsQuery.data?.prompts ?? [];
  const syncStatus = syncQuery.data;
  const activeDrafts = (draftsQuery.data?.drafts ?? []).filter((draft) => draft.status === 'draft');
  const activeBlockingDrafts = activeDrafts.filter(isWorkflowBlockingDraft);
  const selectedPromptBlockingDrafts = activeBlockingDrafts.filter((draft) =>
    draft.kind === 'eval-edit'
    || selectedPromptId === 'main.conscious_agent'
    || !draft.promptId
    || draft.promptId === selectedPromptId,
  );
  const selectedEvalDraftCount = selectedPromptBlockingDrafts.filter((draft) => draft.kind === 'eval-edit').length;
  const selectedPromptDraftCount = selectedPromptBlockingDrafts.length - selectedEvalDraftCount;
  const activeRow = syncStatus?.agents.find((agent) => agent.sourcePromptId === selectedPromptId)
    ?? syncStatus?.agents.find((agent) => agent.sourcePromptId === 'main.conscious_agent')
    ?? syncStatus?.agents[0];
  const liveDriftBlocksPush = Boolean(syncStatus?.agents.some((agent) => agent.state === 'live-ahead' || agent.state === 'conflict'));
  const evalBlockReason = selectedPromptDirty
    ? 'Save this edit as a draft, then apply or discard it before running evals.'
    : selectedPromptBlockingDrafts.length
      ? evalDraftBlockReason({
        evalDraftCount: selectedEvalDraftCount,
        promptDraftCount: selectedPromptDraftCount,
        promptId: selectedPromptId,
      })
      : '';
  const pushBlockReason = selectedPromptDirty
    ? 'Resolve the current unsaved prompt edit before Push dry-run.'
    : activeBlockingDrafts.length
      ? `Apply or discard ${activeBlockingDrafts.length} pending draft${activeBlockingDrafts.length === 1 ? '' : 's'} before Push dry-run. Dry-run reviews applied source only.`
      : '';
  const reviewedPushBlocked = liveDriftBlocksPush || Boolean(pushBlockReason);
  const reviewedPushState = pushBlockReason || liveDriftBlocksPush ? 'blocked' : reviewToken ? 'ready' : 'locked';
  const selectedPromptLabel = humanPromptName(selectedPromptId);
  const selectPrompt = (promptId: string) => {
    setSelectedPromptDirty(false);
    startTransition(() => setSelectedPromptId(promptId));
  };
  const runSelectedEval = () => {
    if (evalBlockReason) {
      focusBlockingDrafts();
      setCommandLog(evalBlockReason);
      return;
    }
    evalMutation.mutate({ promptId: selectedPromptId });
  };
  const runPushDryRun = () => {
    if (pushBlockReason) {
      focusBlockingDrafts();
      setReviewToken('');
      setCommandLog(pushBlockReason);
      return;
    }
    dryRunMutation.mutate();
  };
  const focusBlockingDrafts = () => {
    const hasSelectedPromptDraft = selectedPromptBlockingDrafts.some((draft) => draft.kind !== 'eval-edit' && draft.promptId === selectedPromptId);
    if (hasSelectedPromptDraft) {
      setDockFocusRequest({ tab: 'prompt', promptMode: 'history', nonce: Date.now() });
      return;
    }
    setDockFocusRequest({ tab: 'drafts', nonce: Date.now() });
  };

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'b' && !isEditableTarget(event.target)) {
        event.preventDefault();
        setAtlasOpen((value) => !value);
      }
      if (event.key === 'Escape') {
        setSettingsOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [setAtlasOpen]);

  useEffect(() => {
    if (!settingsOpen) return;
    const handlePointerDown = (event: PointerEvent) => {
      if (!settingsRef.current?.contains(event.target as Node)) {
        setSettingsOpen(false);
      }
    };
    document.addEventListener('pointerdown', handlePointerDown);
    return () => document.removeEventListener('pointerdown', handlePointerDown);
  }, [settingsOpen]);

  return (
    <div
      className={`app-shell ${atlasOpen ? '' : 'atlas-collapsed'} ${inspectorOpen ? '' : 'inspector-collapsed'} ${showStatusbar ? '' : 'statusbar-hidden'}`}
      data-theme={resolvedTheme}
    >
      <header className="topbar">
        <div className="topbar-brand-group">
          <div className="brand-area" ref={settingsRef}>
            <button
              className="brand-button"
              onClick={() => setSettingsOpen((value) => !value)}
              aria-expanded={settingsOpen}
              aria-haspopup="dialog"
              title="Workbench settings"
            >
              <img className="brand-logo" src="/viventium-logo.png" alt="Viventium" />
            </button>
            {settingsOpen && (
              <SettingsPopover
                themePreference={themePreference}
                onThemePreferenceChange={setThemePreference}
                showStatusbar={showStatusbar}
                onShowStatusbarChange={setShowStatusbar}
                onClose={() => setSettingsOpen(false)}
              />
            )}
          </div>
          <div className="topbar-title">
            <h1>Viventium Prompt Workbench</h1>
            <p>{selectedPromptLabel}</p>
          </div>
          <button
            className="toolbar-button icon-button topbar-icon-button"
            onClick={() => setAtlasOpen((value) => !value)}
            aria-label={atlasOpen ? 'Hide prompt flow sidebar' : 'Show prompt flow sidebar'}
            aria-pressed={atlasOpen}
            title={atlasOpen ? 'Hide prompt flow sidebar (Cmd/Ctrl+B)' : 'Show prompt flow sidebar (Cmd/Ctrl+B)'}
          >
            {atlasOpen ? <PanelLeftClose size={16} /> : <PanelLeftOpen size={16} />}
          </button>
        </div>
        <div className="topbar-center-group">
          <div className="environment-chip">
            <Circle size={9} fill="#22c55e" strokeWidth={0} />
            <span>Local only</span>
          </div>
          <label className="search-field">
            <Search size={15} />
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search prompt flow..." />
          </label>
        </div>
        <div className="topbar-action-group">
          <button className="toolbar-button topbar-action secondary-action-button" onClick={() => pullMutation.mutate()} disabled={pullMutation.isPending}>
            <ArrowDownToLine size={16} />
            Pull live
          </button>
          <button
            className={`toolbar-button topbar-action primary ${evalBlockReason ? 'attention-action' : ''}`}
            onClick={runSelectedEval}
            disabled={evalMutation.isPending}
            title={evalBlockReason ? `${evalBlockReason} Click to open the needed review.` : 'Run a no-live eval preview against applied source'}
          >
            <Play size={16} />
            {evalBlockReason ? 'Review draft' : 'Run preview'}
          </button>
          <button
            className={`toolbar-button topbar-action ${pushBlockReason ? 'attention-action' : ''}`}
            onClick={runPushDryRun}
            disabled={dryRunMutation.isPending}
            title={pushBlockReason ? `${pushBlockReason} Click to open drafts.` : 'Run guarded prompts-only dry-run'}
          >
            <UploadCloud size={16} />
            {pushBlockReason ? 'Open drafts' : 'Push dry-run'}
          </button>
          <button
            className="toolbar-button icon-button topbar-icon-button"
            onClick={() => setInspectorOpen((value) => !value)}
            aria-label={inspectorOpen ? 'Hide sync sidebar' : 'Show sync sidebar'}
            aria-pressed={inspectorOpen}
            title={inspectorOpen ? 'Hide sync sidebar' : 'Show sync sidebar'}
          >
            {inspectorOpen ? <PanelRightClose size={16} /> : <PanelRightOpen size={16} />}
          </button>
        </div>
        {commandLog !== 'Ready.' && (
          <div className="action-notice" role="status">
            {commandLog}
          </div>
        )}
      </header>

      <aside className={`atlas-pane ${atlasOpen ? '' : 'collapsed'}`}>
        <PromptAtlas
          prompts={prompts}
          flow={promptsQuery.data?.flow}
          searchTerm={search}
          selectedPromptId={selectedPromptId}
          onSelect={selectPrompt}
          syncStatus={syncStatus}
        />
      </aside>

      <main className="workbench-dock-shell">
        <WorkbenchDock
          prompts={prompts}
          flow={promptsQuery.data?.flow}
          selectedPromptId={selectedPromptId}
          selectedPrompt={promptQuery.data}
          promptLoading={promptQuery.isLoading}
          syncStatus={syncStatus}
          reviewToken={reviewToken}
          drafts={draftsQuery.data?.drafts ?? []}
          evalBank={promptsQuery.data?.evalBank}
          evalRuns={evalRunsQuery.data?.runs ?? []}
          evalRunning={evalMutation.isPending}
          frames={framesQuery.data?.frames ?? []}
          themeMode={resolvedTheme}
          selectedPromptDirty={selectedPromptDirty}
          evalBlockReason={evalBlockReason}
          pushBlockReason={pushBlockReason}
          focusRequest={dockFocusRequest}
          onSelectPrompt={selectPrompt}
          onPromptDirtyChange={setSelectedPromptDirty}
          onPromptSaved={() => {
            queryClient.invalidateQueries({ queryKey: ['prompt', selectedPromptId] });
            queryClient.invalidateQueries({ queryKey: ['prompts'] });
            queryClient.invalidateQueries({ queryKey: ['sync'] });
            queryClient.invalidateQueries({ queryKey: ['drafts'] });
            queryClient.invalidateQueries({ queryKey: ['promptWorkbenchContext', selectedPromptId] });
          }}
          onLog={setCommandLog}
          onImport={(agentId, promptId) => importMutation.mutate({ agentId, promptId })}
          onPushReviewed={() => {
            if (reviewedPushBlocked) {
              setReviewToken('');
              setCommandLog(pushBlockReason || 'Reviewed push blocked because live edits need import or merge first.');
              queryClient.invalidateQueries({ queryKey: ['sync'] });
              return;
            }
            reviewedPushMutation.mutate();
          }}
          onManualMerge={(agentId, promptId) => {
            setCommandLog('Manual merge starts by importing live into a reviewed draft; edit and apply the draft when the diff is acceptable.');
            importMutation.mutate({ agentId, promptId });
          }}
          onApplyDraft={(draft) => applyDraftMutation.mutate(draft)}
          onDiscardDraft={(draft) => discardDraftMutation.mutate(draft)}
          onRunEval={(options) => evalMutation.mutate(options)}
          onSaveEvalCase={(options) => evalCaseDraftMutation.mutate(options)}
        />
      </main>

      <aside className={`inspector-pane ${inspectorOpen ? '' : 'collapsed'}`}>
        <div className="inspector-block">
          <div className="section-title">
            <GitBranch size={16} />
            <span>Sync</span>
          </div>
          <div className="status-grid">
            {(['synced', 'live-ahead', 'source-ahead', 'conflict'] as const).map((state) => (
              <div key={state} className={`metric-card ${state}`}>
                <strong>{syncStatus?.counts?.[state] ?? 0}</strong>
                <span>{humanSyncLabel(state)}</span>
              </div>
            ))}
          </div>
          <div className={`large-status ${activeRow?.state ?? 'source-ahead'}`}>
            {statusIcon(activeRow?.state)}
            <div>
              <strong>{humanSyncLabel(activeRow?.state ?? 'source-ahead')}</strong>
              <span>{syncHint(activeRow?.state)}</span>
            </div>
          </div>
        </div>

        <div className="inspector-block">
          <div className="section-title">
            <Cable size={16} />
            <span>Workbench</span>
          </div>
          <div className="human-summary-list">
            <div>
              <strong>{draftsQuery.data?.drafts.filter((draft) => draft.status === 'draft').length ?? 0}</strong>
              <span>drafts waiting</span>
            </div>
            <div>
              <strong>{evalRunsQuery.data?.runs.length ?? 0}</strong>
              <span>eval runs tracked</span>
            </div>
            <div>
              <strong>{reviewedPushState}</strong>
              <span>reviewed push</span>
            </div>
          </div>
          <button className="toolbar-button compact" onClick={() => queryClient.invalidateQueries()}>
            <RefreshCcw size={15} />
            Refresh all
          </button>
        </div>
      </aside>

      {showStatusbar && (
        <footer className="statusbar">
          <span className="success-dot" />
          <span>{commandLog}</span>
          <span className="statusbar-spacer" />
          <span>{syncStatus?.sourceCommit ? 'source loaded' : 'source pending'}</span>
        </footer>
      )}
    </div>
  );
}

type ThemePreference = 'system' | 'light' | 'dark';
type ResolvedTheme = 'light' | 'dark';

function SettingsPopover({
  themePreference,
  onThemePreferenceChange,
  showStatusbar,
  onShowStatusbarChange,
  onClose,
}: {
  themePreference: ThemePreference;
  onThemePreferenceChange: (theme: ThemePreference) => void;
  showStatusbar: boolean;
  onShowStatusbarChange: (value: boolean) => void;
  onClose: () => void;
}) {
  return (
    <div className="settings-popover" role="dialog" aria-label="Workbench settings">
      <div className="settings-header">
        <div>
          <strong>Settings</strong>
          <span>Local workbench preferences</span>
        </div>
        <button className="toolbar-button icon-button small" onClick={onClose} title="Close settings">
          <X size={14} />
        </button>
      </div>

      <div className="settings-section">
        <span className="settings-label">Theme</span>
        <div className="segmented settings-theme" role="radiogroup" aria-label="Theme">
          <button
            className={themePreference === 'system' ? 'active' : ''}
            onClick={() => onThemePreferenceChange('system')}
            aria-checked={themePreference === 'system'}
            role="radio"
          >
            <Monitor size={14} />
            System
          </button>
          <button
            className={themePreference === 'light' ? 'active' : ''}
            onClick={() => onThemePreferenceChange('light')}
            aria-checked={themePreference === 'light'}
            role="radio"
          >
            <Sun size={14} />
            Light
          </button>
          <button
            className={themePreference === 'dark' ? 'active' : ''}
            onClick={() => onThemePreferenceChange('dark')}
            aria-checked={themePreference === 'dark'}
            role="radio"
          >
            <Moon size={14} />
            Dark
          </button>
        </div>
      </div>

      <label className="settings-toggle">
        <input type="checkbox" checked={showStatusbar} onChange={(event) => onShowStatusbarChange(event.target.checked)} />
        <span>
          <strong>Show status bar</strong>
          <small>Useful for action logs; hidden by default to keep the canvas clean.</small>
        </span>
      </label>

      <div className="settings-shortcut">
        <kbd>Cmd/Ctrl+B</kbd>
        toggles the Prompt Flow sidebar
      </div>
    </div>
  );
}

function useStoredBoolean(key: string, fallback: boolean) {
  const [value, setValue] = useState(() => {
    const stored = readLocalStorage(key);
    if (stored === null) return fallback;
    return stored === 'true';
  });

  useEffect(() => {
    writeLocalStorage(key, String(value));
  }, [key, value]);

  return [value, setValue] as const;
}

function useThemePreference() {
  const [themePreference, setThemePreference] = useState<ThemePreference>(() => {
    const stored = readLocalStorage('viventium.promptWorkbench.themePreference');
    return stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'system';
  });
  const [systemTheme, setSystemTheme] = useState<ResolvedTheme>(() => {
    if (typeof window === 'undefined') return 'light';
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  });

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const update = () => setSystemTheme(media.matches ? 'dark' : 'light');
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);

  useEffect(() => {
    writeLocalStorage('viventium.promptWorkbench.themePreference', themePreference);
  }, [themePreference]);

  return {
    themePreference,
    setThemePreference,
    resolvedTheme: themePreference === 'system' ? systemTheme : themePreference,
  };
}

function isEditableTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false;
  const tagName = target.tagName.toLowerCase();
  return tagName === 'input' || tagName === 'textarea' || tagName === 'select' || target.isContentEditable;
}

function statusIcon(state?: string) {
  if (state === 'synced') return <BadgeCheck size={18} />;
  if (state === 'conflict') return <AlertTriangle size={18} />;
  if (state === 'live-ahead') return <ArrowDownToLine size={18} />;
  return <Save size={18} />;
}

function humanSyncLabel(state: string) {
  if (state === 'synced') return 'Synced';
  if (state === 'live-ahead') return 'Live changed';
  if (state === 'source-ahead') return 'Source changed';
  if (state === 'conflict') return 'Needs merge';
  return state;
}

function syncHint(state?: string) {
  if (state === 'synced') return 'Source and live match.';
  if (state === 'live-ahead') return 'Import live changes before pushing.';
  if (state === 'conflict') return 'Choose a merge path first.';
  return 'Run dry-run before live push.';
}

function isWorkflowBlockingDraft(draft: DraftRecord) {
  return draft.kind === 'source-edit' || draft.kind === 'live-import' || draft.kind === 'eval-edit';
}

function evalDraftBlockReason({
  evalDraftCount,
  promptDraftCount,
  promptId,
}: {
  evalDraftCount: number;
  promptDraftCount: number;
  promptId: string;
}) {
  const total = evalDraftCount + promptDraftCount;
  if (evalDraftCount && !promptDraftCount) {
    return `Apply or discard ${evalDraftCount} pending eval draft${evalDraftCount === 1 ? '' : 's'} before running evals. Evals use the applied eval bank only.`;
  }
  if (evalDraftCount && promptDraftCount) {
    return `Apply or discard ${total} pending prompt/eval drafts before running evals. Evals use applied markdown and the applied eval bank only.`;
  }
  return `Apply or discard ${promptDraftCount} pending draft${promptDraftCount === 1 ? '' : 's'} for ${humanPromptName(promptId)} before running evals. Evals use applied source only.`;
}

function humanPromptName(id: string) {
  const label = id.split('.').slice(1).join(' ') || id;
  return label.replace(/[._-]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}
