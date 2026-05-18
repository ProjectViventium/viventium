import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Actions,
  DockLocation,
  Layout,
  Model,
  type IJsonModel,
  type TabNode,
} from 'flexlayout-react';
import { Activity, GitCompareArrows, Map, PencilLine, RotateCcw, TestTube2 } from 'lucide-react';
import { readLocalStorage, removeLocalStorage, writeLocalStorage } from '../storage';
import type { DraftRecord, EvalBank, EvalRun, FlowGraph, FrameLog, PromptDetail, PromptRow, SyncStatus } from '../types';
import { PanelErrorBoundary } from './PanelErrorBoundary';

const PromptFlow = lazy(() => import('./PromptFlow').then((module) => ({ default: module.PromptFlow })));
const PromptEditor = lazy(() => import('./PromptEditor').then((module) => ({ default: module.PromptEditor })));
const DriftBoard = lazy(() => import('./DriftBoard').then((module) => ({ default: module.DriftBoard })));
const DraftPanel = lazy(() => import('./DraftPanel').then((module) => ({ default: module.DraftPanel })));
const EvalPanel = lazy(() => import('./EvalPanel').then((module) => ({ default: module.EvalPanel })));
const FramePanel = lazy(() => import('./FramePanel').then((module) => ({ default: module.FramePanel })));

interface Props {
  prompts: PromptRow[];
  flow?: FlowGraph;
  selectedPromptId: string;
  selectedPrompt?: PromptDetail;
  promptLoading: boolean;
  syncStatus?: SyncStatus;
  reviewToken: string;
  drafts: DraftRecord[];
  evalBank?: EvalBank;
  evalRuns: EvalRun[];
  evalRunning: boolean;
  frames: FrameLog[];
  themeMode: 'light' | 'dark';
  selectedPromptDirty: boolean;
  evalBlockReason?: string;
  pushBlockReason?: string;
  focusRequest?: { tab: DockTabId; promptMode?: 'history'; nonce: number };
  onSelectPrompt: (id: string) => void;
  onPromptDirtyChange: (dirty: boolean) => void;
  onPromptSaved: () => void;
  onLog: (message: string) => void;
  onImport: (agentId: string, promptId: string) => void;
  onPushReviewed: () => void;
  onManualMerge: (agentId: string, promptId: string) => void;
  onApplyDraft: (draft: DraftRecord) => void;
  onDiscardDraft: (draft: DraftRecord) => void;
  onRunEval: (options: { maxCases?: number; live?: boolean; family?: string; surface?: string; promptId?: string }) => void;
  onSaveEvalCase: (options: { familyId: string; caseId: string; updatedCase: Record<string, unknown>; create?: boolean }) => void;
}

const layoutStorageKey = 'viventium.promptWorkbench.dockLayout.v4';

const tabDefinitions = {
  flow: { name: 'Flow', icon: Map, component: 'flow' },
  prompt: { name: 'Prompt', icon: PencilLine, component: 'prompt' },
  live: { name: 'Live Drift', icon: GitCompareArrows, component: 'live' },
  drafts: { name: 'Drafts', icon: PencilLine, component: 'drafts' },
  evals: { name: 'Evals', icon: TestTube2, component: 'evals' },
  frames: { name: 'Prompt Traces', icon: Activity, component: 'frames' },
} as const;

type DockTabId = keyof typeof tabDefinitions;

export function WorkbenchDock({
  prompts,
  flow,
  selectedPromptId,
  selectedPrompt,
  promptLoading,
  syncStatus,
  reviewToken,
  drafts,
  evalBank,
  evalRuns,
  evalRunning,
  frames,
  themeMode,
  selectedPromptDirty,
  evalBlockReason,
  pushBlockReason,
  focusRequest,
  onSelectPrompt,
  onPromptDirtyChange,
  onPromptSaved,
  onLog,
  onImport,
  onPushReviewed,
  onManualMerge,
  onApplyDraft,
  onDiscardDraft,
  onRunEval,
  onSaveEvalCase,
}: Props) {
  const [layoutModel, setLayoutModel] = useState(() => loadDockModel());
  const layoutModelRef = useRef(layoutModel);
  const persistTimer = useRef(0);
  const pendingPersistModel = useRef<Model | null>(null);

  const schedulePersistDockModel = useCallback((model: Model) => {
    pendingPersistModel.current = model;
    window.clearTimeout(persistTimer.current);
    persistTimer.current = window.setTimeout(() => {
      const current = pendingPersistModel.current;
      pendingPersistModel.current = null;
      persistTimer.current = 0;
      if (current) persistDockModel(current);
    }, 180);
  }, []);

  useEffect(() => () => window.clearTimeout(persistTimer.current), []);

  useEffect(() => {
    layoutModelRef.current = layoutModel;
  }, [layoutModel]);

  useEffect(() => {
    if (!focusRequest) return;
    const next = Model.fromJson(layoutModelRef.current.toJson());
    if (!next.getNodeById(focusRequest.tab)) {
      next.doAction(Actions.addTab(tabJson(focusRequest.tab), 'primary', DockLocation.CENTER, -1, true));
    } else {
      next.doAction(Actions.selectTab(focusRequest.tab));
    }
    setLayoutModel(next);
    schedulePersistDockModel(next);
  }, [focusRequest?.nonce, schedulePersistDockModel]);

  const tabState = useMemo(
    () => ({
      prompts,
      flow,
      selectedPromptId,
      selectedPrompt,
      promptLoading,
      syncStatus,
      reviewToken,
      drafts,
      evalBank,
      evalRuns,
      evalRunning,
      frames,
      themeMode,
      selectedPromptDirty,
      evalBlockReason,
      pushBlockReason,
    }),
    [prompts, flow, selectedPromptId, selectedPrompt, promptLoading, syncStatus, reviewToken, drafts, evalBank, evalRuns, evalRunning, frames, themeMode, selectedPromptDirty, evalBlockReason, pushBlockReason],
  );

  const resetLayout = () => {
    const model = Model.fromJson(defaultDockLayout);
    removeLocalStorage(layoutStorageKey);
    setLayoutModel(model);
  };

  const factory = (node: TabNode) => {
    const component = node.getComponent();
    if (component === 'flow') {
      return (
        <PanelErrorBoundary label="Flow">
          <Suspense fallback={<div className="empty-state">Loading Flow...</div>}>
            <PromptFlow
              prompts={tabState.prompts}
              flow={tabState.flow}
              selectedPromptId={tabState.selectedPromptId}
              onSelect={onSelectPrompt}
            />
          </Suspense>
        </PanelErrorBoundary>
      );
    }
    if (component === 'prompt') {
      return (
        <PanelErrorBoundary label="Prompt">
          <Suspense fallback={<div className="empty-state">Loading Prompt...</div>}>
            <PromptEditor
              prompt={tabState.selectedPrompt}
              loading={tabState.promptLoading}
              themeMode={tabState.themeMode}
              onDirtyChange={onPromptDirtyChange}
              onSaved={onPromptSaved}
              onLog={onLog}
              onApplyDraft={onApplyDraft}
              onDiscardDraft={onDiscardDraft}
              onRunEval={onRunEval}
              reviewRequestKey={focusRequest?.tab === 'prompt' && focusRequest.promptMode === 'history' ? focusRequest.nonce : undefined}
            />
          </Suspense>
        </PanelErrorBoundary>
      );
    }
    if (component === 'live') {
      return (
        <div className="dock-panel-scroll">
          <PanelErrorBoundary label="Live Drift">
            <Suspense fallback={<div className="empty-state">Loading Live Drift...</div>}>
              <DriftBoard
                status={tabState.syncStatus}
                selectedPromptId={tabState.selectedPromptId}
                reviewToken={tabState.reviewToken}
                pushBlockReason={tabState.pushBlockReason}
                onImport={onImport}
                onPushReviewed={onPushReviewed}
                onManualMerge={onManualMerge}
              />
            </Suspense>
          </PanelErrorBoundary>
        </div>
      );
    }
    if (component === 'drafts') {
      return (
        <div className="dock-panel-scroll">
          <PanelErrorBoundary label="Drafts">
            <Suspense fallback={<div className="empty-state">Loading Drafts...</div>}>
              <DraftPanel drafts={tabState.drafts} onApply={onApplyDraft} onDiscard={onDiscardDraft} />
            </Suspense>
          </PanelErrorBoundary>
        </div>
      );
    }
    if (component === 'evals') {
      return (
        <PanelErrorBoundary label="Evals">
          <Suspense fallback={<div className="empty-state">Loading Evals...</div>}>
            <EvalPanel
              evalBank={tabState.evalBank}
              selectedPromptId={tabState.selectedPromptId}
              runs={tabState.evalRuns}
              running={tabState.evalRunning}
              blockedReason={tabState.evalBlockReason}
              onRun={onRunEval}
              onSaveCase={onSaveEvalCase}
            />
          </Suspense>
        </PanelErrorBoundary>
      );
    }
    if (component === 'frames') {
      return (
        <div className="dock-panel-scroll">
          <PanelErrorBoundary label="Prompt Traces">
            <Suspense fallback={<div className="empty-state">Loading Prompt Traces...</div>}>
              <FramePanel frames={tabState.frames} />
            </Suspense>
          </PanelErrorBoundary>
        </div>
      );
    }
    return <div className="empty-state">Open a workbench view.</div>;
  };

  return (
    <div className="dock-workspace">
      <div className={`dock-host ${themeMode === 'dark' ? 'flexlayout__theme_dark' : 'flexlayout__theme_light'}`}>
        <button className="dock-reset-button" onClick={resetLayout} title="Restore default tabs and panes">
          <RotateCcw size={14} />
          Reset
        </button>
        <Layout
          model={layoutModel}
          factory={factory}
          onModelChange={schedulePersistDockModel}
          onRenderTab={(node, renderValues) => {
            const component = node.getComponent() as DockTabId | undefined;
            const definition = component ? tabDefinitions[component] : undefined;
            if (!definition) return;
            const Icon = definition.icon;
            renderValues.leading = <Icon size={13} />;
          }}
        />
      </div>
    </div>
  );
}

function loadDockModel() {
  for (const staleKey of [
    'viventium.promptWorkbench.dockLayout.v1',
    'viventium.promptWorkbench.dockLayout.v2',
    'viventium.promptWorkbench.dockLayout.v3',
  ]) {
    removeLocalStorage(staleKey);
  }
  const saved = readLocalStorage(layoutStorageKey);
  if (saved) {
    try {
      return Model.fromJson(JSON.parse(saved) as IJsonModel);
    } catch {
      removeLocalStorage(layoutStorageKey);
    }
  }
  return Model.fromJson(defaultDockLayout);
}

function persistDockModel(model: Model) {
  writeLocalStorage(layoutStorageKey, JSON.stringify(model.toJson()));
}

const defaultDockLayout: IJsonModel = {
  global: {
    enableEdgeDock: true,
    tabEnableClose: true,
    tabEnableRename: false,
    tabSetEnableMaximize: true,
    tabSetEnableTabScrollbar: true,
    tabSetMinWidth: 260,
    tabSetMinHeight: 220,
  },
  borders: [],
  layout: {
    type: 'row',
    id: 'root',
    weight: 100,
    children: [
      {
        type: 'tabset',
        id: 'primary',
        weight: 100,
        selected: 0,
        children: [
          { type: 'tab', id: 'flow', name: 'Flow', component: 'flow', enableClose: false, enableRename: false },
          { type: 'tab', id: 'prompt', name: 'Prompt', component: 'prompt', enableClose: false, enableRename: false },
          { type: 'tab', id: 'live', name: 'Live Drift', component: 'live', enableClose: true, enableRename: false },
          { type: 'tab', id: 'drafts', name: 'Drafts', component: 'drafts', enableClose: true, enableRename: false },
          { type: 'tab', id: 'evals', name: 'Evals', component: 'evals', enableClose: true, enableRename: false },
          { type: 'tab', id: 'frames', name: 'Prompt Traces', component: 'frames', enableClose: true, enableRename: false },
        ],
      },
    ],
  },
};

function tabJson(tab: DockTabId) {
  const definition = tabDefinitions[tab];
  return {
    type: 'tab' as const,
    id: tab,
    name: definition.name,
    component: definition.component,
    enableClose: tab !== 'flow' && tab !== 'prompt',
    enableRename: false,
  };
}
