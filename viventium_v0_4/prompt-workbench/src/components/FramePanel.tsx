import { Activity, AlertTriangle, Clock3, RefreshCcw } from 'lucide-react';
import type { FrameHealth, FrameLog } from '../types';

interface Props {
  frames: FrameLog[];
  health?: FrameHealth;
  loading: boolean;
  loadFailed: boolean;
  onRefresh: () => void;
}

const healthCopy: Record<FrameHealth['reason'], string> = {
  none: 'Trace source healthy.',
  no_trace_events: 'No traces are recorded yet. Run a prompt flow to create a local metadata trace.',
  invalid_trace_events: 'Some trace records were rejected. Only strict valid metadata is shown.',
  trusted_log_rejected: 'An unsafe log file was rejected. Only trusted metadata is shown.',
  trusted_log_unavailable: 'The local Core trace source is unavailable. Confirm Core is running, then retry.',
};

export function FramePanel({ frames, health, loading, loadFailed, onRefresh }: Props) {
  const tokenTotal = frames.reduce((sum, frame) => {
    return sum + Object.values(frame.layer_tokens ?? {}).reduce((inner, value) => inner + Number(value || 0), 0);
  }, 0);
  const status = loadFailed ? 'unavailable' : loading && !health ? 'loading' : health?.status ?? 'unavailable';
  const statusMessage = loadFailed
    ? 'Prompt trace status could not be loaded. Retry the local request.'
    : health
      ? healthCopy[health.reason]
      : 'The local Core trace source is unavailable. Confirm Core is running, then retry.';
  const showWarning = status === 'degraded' || status === 'unavailable';

  return (
    <div className="inspector-block">
      <div className="section-title">
        <Activity size={16} />
        <span>Prompt Traces</span>
      </div>
      <p className="small-copy">A trace is local metadata about a prompt run: surface, model, assembled layers, token estimates, and routing decisions. It does not show private prompt text here.</p>
      <div className={`trace-source-status${showWarning ? ' has-warning' : ''}`} data-state={status} role="status" aria-live="polite">
        {showWarning && <AlertTriangle size={14} aria-hidden="true" />}
        <div>
          <strong>{status === 'loading' ? 'Loading trace source…' : statusMessage}</strong>
          <span>Local diagnostic · not release evidence</span>
        </div>
        <button className="mini-action trace-refresh" type="button" onClick={onRefresh} disabled={loading}>
          <RefreshCcw size={13} aria-hidden="true" />
          {showWarning ? 'Retry' : 'Refresh'}
        </button>
      </div>
      <div className="frame-metrics">
        <div><strong>{frames.length}</strong><span>trace events</span></div>
        <div><strong>{tokenTotal.toLocaleString()}</strong><span>tokens</span></div>
      </div>
      <div className="frame-list">
        {frames.slice(0, 6).map((frame, index) => (
          <div className="frame-row" key={`${frame.time}-${index}`}>
            <Clock3 size={14} />
            <div>
              <strong>{frame.surface} / {frame.family}</strong>
              <small>{new Date(frame.time).toLocaleString()} · Provider ID {frame.provider} · Model ID {frame.model}</small>
            </div>
          </div>
        ))}
        {!frames.length && !loading && <p className="small-copy trace-empty">{statusMessage}</p>}
      </div>
    </div>
  );
}
