import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import '@xyflow/react/dist/style.css';
import 'flexlayout-react/style/combined.css';
import './styles.css';
import App from './App';
import { PanelErrorBoundary } from './components/PanelErrorBoundary';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 10_000,
    },
  },
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <PanelErrorBoundary label="Prompt Workbench">
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </PanelErrorBoundary>
  </React.StrictMode>,
);
