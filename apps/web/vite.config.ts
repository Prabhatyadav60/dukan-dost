import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The dev server forwards API calls to FastAPI, so one HTTPS tunnel (ngrok on :5173) serves
// both the app and the API to phones — merchant and customer alike.
// e2e runs its own API (API_PROXY_TARGET) so tests never touch the app you are using
const env = (globalThis as { process?: { env: Record<string, string | undefined> } }).process?.env ?? {};
const api = env.API_PROXY_TARGET ?? 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    allowedHosts: true,
    proxy: { '/v1': api, '/public': api, '/healthz': api },
  },
});
