import { AlertTriangle, ArrowDownToLine, GitCompareArrows, UploadCloud } from 'lucide-react';
import type { SyncStatus } from '../types';

interface Props {
  status?: SyncStatus;
  selectedPromptId: string;
  reviewToken?: string;
  pushBlockReason?: string;
  onImport: (agentId: string, promptId: string) => void;
  onPushReviewed: () => void;
  onManualMerge: (agentId: string, promptId: string) => void;
}

export function DriftBoard({ status, selectedPromptId, reviewToken, pushBlockReason, onImport, onPushReviewed, onManualMerge }: Props) {
  const rows = status?.agents ?? [];
  const active = rows.find((row) => row.sourcePromptId === selectedPromptId);
  const visibleRows = active
    ? [active, ...rows.filter((row) => row.agentId !== active.agentId)]
    : rows;
  const promptForAction = active?.sourcePromptId ?? selectedPromptId;
  const pushBlocked = Boolean(pushBlockReason) || rows.some((row) => row.state === 'live-ahead' || row.state === 'conflict');

  return (
    <div className="inspector-block">
      <div className="section-title">
        <GitCompareArrows size={16} />
        <span>Live Drift Board</span>
      </div>
      <div className="abc-grid">
        <div>
          <small>Live</small>
          <strong>{active ? active.liveTextAvailable ? 'available' : 'not pulled' : 'not managed here'}</strong>
        </div>
        <div>
          <small>Source</small>
          <strong>{active?.sourceChars ? `${active.sourceChars.toLocaleString()} chars` : 'prompt registry'}</strong>
        </div>
        <div>
          <small>Evaluated</small>
          <strong>{humanPromptName(selectedPromptId)}</strong>
        </div>
      </div>
      {!active && (
        <div className="workflow-callout compact" role="status">
          <strong>No managed live row for this prompt</strong>
          <span>This source unit is delivered through another owning layer. Live Drift actions stay disabled until an exact managed-agent row exists.</span>
        </div>
      )}
      <div className="drift-list">
        {visibleRows.slice(0, 12).map((row) => (
          <div key={row.agentId} className={`drift-row ${row.state}`}>
            <span>{driftIcon(row.state)}</span>
            <div>
              <strong>{row.label}</strong>
              <small>{driftHint(row.state)}</small>
            </div>
            <code>{humanState(row.state)}</code>
          </div>
        ))}
      </div>
      {pushBlockReason && (
        <div className="workflow-callout compact">
          <strong>Push is blocked</strong>
          <span>{pushBlockReason}</span>
        </div>
      )}
      <div className="action-strip">
        <button
          className="mini-action"
          disabled={!active?.agentId || !active.liveTextAvailable}
          onClick={() => active?.agentId && onImport(active.agentId, promptForAction)}
        >
          <ArrowDownToLine size={14} /> import
        </button>
        <button
          className="mini-action"
          disabled={!reviewToken || pushBlocked}
          onClick={onPushReviewed}
          title={pushBlockReason || (pushBlocked ? 'Import or merge live edits before pushing' : reviewToken ? 'Push reviewed dry-run to live' : 'Run Push dry-run first')}
        >
          <UploadCloud size={14} /> reviewed push
        </button>
        <button
          className="mini-action"
          disabled={!active?.agentId}
          onClick={() => active?.agentId && onManualMerge(active.agentId, promptForAction)}
        >
          <AlertTriangle size={14} /> merge
        </button>
      </div>
    </div>
  );
}

function driftIcon(state: string) {
  if (state === 'conflict') return <AlertTriangle size={15} />;
  if (state === 'live-ahead') return <ArrowDownToLine size={15} />;
  if (state === 'source-ahead') return <UploadCloud size={15} />;
  return <GitCompareArrows size={15} />;
}

function humanState(state: string) {
  if (state === 'synced') return 'synced';
  if (state === 'live-ahead') return 'live changed';
  if (state === 'source-ahead') return 'source changed';
  if (state === 'conflict') return 'needs merge';
  return state;
}

function driftHint(state: string) {
  if (state === 'synced') return 'source and live match';
  if (state === 'live-ahead') return 'import live edits before pushing';
  if (state === 'source-ahead') return 'dry-run then push reviewed';
  if (state === 'conflict') return 'choose import, source, or manual merge';
  return 'status unknown';
}

function humanPromptName(id: string) {
  const label = id.split('.').slice(1).join(' ') || id;
  return label.replace(/[._-]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}
