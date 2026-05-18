import { CheckCircle2, FileDiff, Trash2 } from 'lucide-react';
import type { DraftRecord } from '../types';

interface Props {
  drafts: DraftRecord[];
  onApply: (draft: DraftRecord) => void;
  onDiscard: (draft: DraftRecord) => void;
}

export function DraftPanel({ drafts, onApply, onDiscard }: Props) {
  const activeDrafts = drafts.filter((draft) => draft.status === 'draft');
  const pastDrafts = drafts.filter((draft) => draft.status !== 'draft').slice(0, 6);

  return (
    <div className="inspector-block draft-panel">
      <div className="section-title">
        <FileDiff size={16} />
        <span>Draft Review</span>
      </div>
      <p className="small-copy">Apply writes source prompt or eval files only. Live push stays separate and requires dry-run review.</p>
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
