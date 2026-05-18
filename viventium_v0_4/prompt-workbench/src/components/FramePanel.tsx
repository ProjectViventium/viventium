import { Activity, Clock3 } from 'lucide-react';
import type { FrameLog } from '../types';

interface Props {
  frames: FrameLog[];
}

export function FramePanel({ frames }: Props) {
  const tokenTotal = frames.reduce((sum, frame) => {
    return sum + Object.values(frame.layer_tokens ?? {}).reduce((inner, value) => inner + Number(value || 0), 0);
  }, 0);

  return (
    <div className="inspector-block">
      <div className="section-title">
        <Activity size={16} />
        <span>Prompt Traces</span>
      </div>
      <p className="small-copy">A trace is local metadata about a prompt run: surface, model, assembled layers, token estimates, and routing decisions. It does not show private prompt text here.</p>
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
              <small>{frame.provider} {frame.model}</small>
            </div>
          </div>
        ))}
        {!frames.length && <p className="small-copy">No prompt trace logs yet. Run a flow with trace telemetry enabled and this view will show the local metadata trail.</p>}
      </div>
    </div>
  );
}
