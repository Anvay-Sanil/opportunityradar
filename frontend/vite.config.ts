import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiUrl = env.VITE_API_URL?.trim();
  if (mode === 'production' && env.VERCEL === '1' && !apiUrl) {
    throw new Error('Set VITE_API_URL to the deployed FastAPI URL in Vercel, then rebuild.');
  }
  if (apiUrl) {
    const url = new URL(apiUrl);
    if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password || url.search || url.hash || !['', '/', '/api', '/api/'].includes(url.pathname)) {
      throw new Error('VITE_API_URL must be an HTTP(S) backend origin, optionally ending in /api.');
    }
    if (mode === 'production' && env.VERCEL === '1' && url.protocol !== 'https:') {
      throw new Error('Vercel production builds require an HTTPS backend URL.');
    }
  }
  return {
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: env.VITE_PROXY_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  };
})
