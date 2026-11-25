import react from '@vitejs/plugin-react';
import { rmSync } from 'node:fs';
import { fileURLToPath, URL } from 'node:url';
import type { Plugin } from 'vite';
import { defineConfig } from 'vitest/config';

const BACKEND = 'http://127.0.0.1:8200';

/** Служебный воркер MSW нужен только в разработке, в сборку он не попадает. */
function dropMockWorker(): Plugin {
  return {
    name: 'drop-mock-worker',
    apply: 'build',
    closeBundle() {
      rmSync(fileURLToPath(new URL('./dist/mockServiceWorker.js', import.meta.url)), { force: true });
    },
  };
}

export default defineConfig(({ mode }) => {
  const mock = mode === 'mock' || process.env.VITE_MOCK === '1';
  return {
    plugins: [react(), dropMockWorker()],
    resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
    define: mock ? { 'import.meta.env.VITE_MOCK': JSON.stringify('1') } : {},
    server: {
      host: '127.0.0.1',
      port: 5190,
      strictPort: true,
      proxy: mock ? undefined : { '^/api/': BACKEND, '^/course/': BACKEND, '^/learn/': BACKEND },
    },
    build: {
      rollupOptions: {
        output: { manualChunks: { react: ['react', 'react-dom', 'react-router-dom'], mantine: ['@mantine/core', '@mantine/hooks'], katex: ['katex'] } },
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      css: false,
      testTimeout: 20_000,
      include: ['src/**/*.test.{ts,tsx}'],
    },
  };
});
