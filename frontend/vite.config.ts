import { defineConfig } from 'vitest/config';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [tailwindcss()],
  server: { proxy: {
    '/api': process.env.MARKETLENS_DEV_API_URL || 'http://127.0.0.1:8000',
    '/health': process.env.MARKETLENS_DEV_API_URL || 'http://127.0.0.1:8000',
  } },
  test: { environment: 'jsdom', setupFiles: ['./src/test-setup.ts'], globals: true },
});
