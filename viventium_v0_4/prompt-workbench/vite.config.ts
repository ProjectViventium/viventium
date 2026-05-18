import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5179,
    proxy: {
      '/api': 'http://127.0.0.1:8781',
    },
  },
  preview: {
    host: '127.0.0.1',
    port: 4179,
  },
});
