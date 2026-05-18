import { Component, type ErrorInfo, type ReactNode } from 'react';
import { RotateCcw } from 'lucide-react';

interface Props {
  children: ReactNode;
  label: string;
}

interface State {
  error?: Error;
}

export class PanelErrorBoundary extends Component<Props, State> {
  state: State = {};

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[Prompt Workbench] ${this.props.label} panel failed`, error, info.componentStack);
  }

  render() {
    if (!this.state.error) {
      return this.props.children;
    }
    const staleBundle = isDynamicImportError(this.state.error);
    return (
      <div className="panel-error" role="alert">
        <strong>{this.props.label} could not load</strong>
        <p>
          {staleBundle
            ? 'The local app bundle changed while this browser tab was open. Reload the workbench to fetch the current files.'
            : 'This panel hit a local UI error. Reset the panel and try again; reload if it repeats.'}
        </p>
        <div className="panel-error-actions">
          <button className="mini-action" onClick={() => window.location.reload()}>
            <RotateCcw size={14} />
            Reload workbench
          </button>
          <button className="mini-action" onClick={() => this.setState({ error: undefined })}>
            Reset panel
          </button>
        </div>
      </div>
    );
  }
}

function isDynamicImportError(error: Error) {
  const text = `${error.name} ${error.message}`;
  return /ChunkLoadError|dynamically imported module|Importing a module script failed|Failed to fetch/i.test(text);
}
