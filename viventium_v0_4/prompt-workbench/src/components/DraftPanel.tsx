import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { CheckCircle2, Clock3, Eye, FileDiff, PencilLine, Trash2 } from 'lucide-react';
import { renderVariables } from '../api';
import type { DraftRecord, ScheduledPrompt } from '../types';
import { RenderedPrompt } from './RenderedPrompt';

interface Props {
  drafts: DraftRecord[];
  selectedScheduledPrompt?: ScheduledPrompt;
  onOpenSchedule?: () => void;
  onApply: (draft: DraftRecord) => void;
  onDiscard: (draft: DraftRecord) => void;
}

export function DraftPanel({ drafts, selectedScheduledPrompt, onOpenSchedule, onApply, onDiscard }: Props) {
  const [scheduledMode, setScheduledMode] = useState<'prompt' | 'rendered' | 'variables'>('rendered');
  const supportsWorkbenchRendering = Boolean(selectedScheduledPrompt && selectedScheduledPrompt.sourceKind !== 'user_schedule');
  const activeDrafts = drafts.filter((draft) => draft.status === 'draft');
  const pastDrafts = drafts.filter((draft) => draft.status !== 'draft').slice(0, 6);
  const scheduledPreviewQuery = useQuery({
    queryKey: ['scheduledPromptDraftPreview', selectedScheduledPrompt?.id, selectedScheduledPrompt?.promptText],
    queryFn: () => renderVariables(selectedScheduledPrompt?.promptText ?? ''),
    enabled: Boolean(supportsWorkbenchRendering && selectedScheduledPrompt?.promptText?.trim()),
  });

  useEffect(() => {
    if (selectedScheduledPrompt?.sourceKind === 'user_schedule' && scheduledMode !== 'prompt') {
      setScheduledMode('prompt');
    }
  }, [selectedScheduledPrompt?.id, selectedScheduledPrompt?.sourceKind, scheduledMode]);

  return (
    <div className="inspector-block draft-panel">
      <div className="section-title">
        <FileDiff size={16} />
        <span>Draft Review</span>
      </div>
      <p className="small-copy">
        {selectedScheduledPrompt
          ? supportsWorkbenchRendering
            ? 'Selected scheduled prompt object. Source-file drafts remain separate; this preview renders the private schedule prompt exactly as the GlassHive worker sees it.'
            : 'Selected user-level schedule. Drafts shows the stored scheduler prompt text; Workbench variable rendering is not applied to this Viventium-agent route.'
          : 'Apply writes source prompt or eval files only. Live push stays separate and requires dry-run review.'}
      </p>
      {selectedScheduledPrompt && (
        <article className="draft-card scheduled-draft-card">
          <div className="draft-card-head">
            <div>
              <strong>{selectedScheduledPrompt.title}</strong>
              <small>{selectedScheduledPrompt.sourceLabel ?? 'Scheduled prompt'} · {selectedScheduledPrompt.executor ?? 'viventium_agent'} · {selectedScheduledPrompt.channel ?? 'workbench'}</small>
            </div>
            <span className={`draft-status ${selectedScheduledPrompt.active ? 'draft' : 'discarded'}`}>
              {selectedScheduledPrompt.active ? 'enabled' : 'paused'}
            </span>
          </div>
          <div className="scheduled-draft-toolbar">
            <div className="segmented slim" role="tablist" aria-label="Scheduled prompt draft view">
              <button role="tab" aria-selected={scheduledMode === 'prompt'} className={scheduledMode === 'prompt' ? 'active' : ''} onClick={() => setScheduledMode('prompt')}>
                <PencilLine size={13} />
                Prompt
              </button>
              {supportsWorkbenchRendering && (
                <>
                  <button role="tab" aria-selected={scheduledMode === 'rendered'} className={scheduledMode === 'rendered' ? 'active' : ''} onClick={() => setScheduledMode('rendered')}>
                    <Eye size={13} />
                    Rendered
                  </button>
                  <button role="tab" aria-selected={scheduledMode === 'variables'} className={scheduledMode === 'variables' ? 'active' : ''} onClick={() => setScheduledMode('variables')}>
                    <Clock3 size={13} />
                    Variables
                  </button>
                </>
              )}
            </div>
            <button className="mini-action" onClick={onOpenSchedule}>
              Open schedule editor
            </button>
          </div>
          {scheduledMode === 'prompt' && <pre>{selectedScheduledPrompt.promptText}</pre>}
          {scheduledMode === 'rendered' && supportsWorkbenchRendering && (
            <RenderedPrompt markdown={scheduledPreviewQuery.data?.rendered ?? selectedScheduledPrompt.promptText} />
          )}
          {scheduledMode === 'variables' && supportsWorkbenchRendering && (
            <div className="scheduled-draft-variables">
              {scheduledPreviewQuery.isLoading && <p className="small-copy">Rendering variables...</p>}
              {scheduledPreviewQuery.error instanceof Error && <p className="small-copy">{scheduledPreviewQuery.error.message}</p>}
              {(scheduledPreviewQuery.data?.variableSnapshot.items ?? []).map((item) => (
                <details key={`${item.placeholder}-${item.hash}`} open>
                  <summary>
                    <span>{item.placeholder}</span>
                    <code>{item.hash}</code>
                  </summary>
                  <pre>{item.rendered}</pre>
                </details>
              ))}
            </div>
          )}
          {!supportsWorkbenchRendering && (
            <p className="small-copy user-schedule-render-note">
              Rendered variables are intentionally hidden here because this existing schedule runs through the Viventium agent scheduler, not the Workbench GlassHive renderer.
            </p>
          )}
        </article>
      )}
      {!activeDrafts.length && (
        <p className="small-copy">No pending drafts. Source edits and live imports appear here before they can touch markdown.</p>
      )}
      {activeDrafts.map((draft) => (
        <article className="draft-card" key={draft.id}>
          <div className="draft-card-head">
            <div>
              <strong>{humanDraftKind(draft.kind)}</strong>
              <small>{friendlyPath(draft.targetPath)} · {draft.changeSummary?.label ?? 'changes pending'}{draft.duplicateCount && draft.duplicateCount > 1 ? ` · ${draft.duplicateCount} duplicate saves grouped` : ''}</small>
            </div>
            <span className={`draft-status ${draft.status}`}>{draft.status}</span>
          </div>
          <pre>{trimPatch(draft.patch)}</pre>
          <div className="draft-actions">
            <button className="mini-action" onClick={() => onApply(draft)}>
              <CheckCircle2 size={14} />
              {draft.kind === 'eval-edit' ? 'Apply eval draft' : 'Apply to source'}
            </button>
            <button className="mini-action" onClick={() => onDiscard(draft)}>
              <Trash2 size={14} />
              Discard draft
            </button>
          </div>
        </article>
      ))}
      {!!pastDrafts.length && (
        <div className="draft-history-list">
          <h3>Recent draft history</h3>
          {pastDrafts.map((draft) => (
            <div className="history-pill" key={draft.id}>
              {draft.status} · {draft.changeSummary?.label ?? 'changes'} · {friendlyPath(draft.targetPath)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function humanDraftKind(kind: string) {
  if (kind === 'live-import') return 'Live import';
  if (kind === 'source-edit') return 'Source edit';
  return kind.replace(/[._-]+/g, ' ');
}

function friendlyPath(path: string) {
  const parts = path.split(/[\\/]/).filter(Boolean);
  return parts.slice(-2).join('/');
}

function trimPatch(patch: string) {
  const lines = patch.split('\n').map((line) => line.replace(/([ab]\/).*?source_of_truth\/prompts\//, '$1prompts/'));
  return lines.slice(0, 18).join('\n') + (lines.length > 18 ? '\n...' : '');
}
