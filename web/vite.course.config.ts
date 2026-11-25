import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';

/**
 * Плеер курса одним файлом для build.py. Курс открывают двойным щелчком, а с file:// браузер
 * не грузит модули и части сборки, поэтому формат — обычный скрипт (iife) без разбиения.
 */
export default defineConfig({
  plugins: [react()],
  define: { 'process.env.NODE_ENV': JSON.stringify('production') },
  publicDir: false,
  build: {
    outDir: fileURLToPath(new URL('../backend/glava/modules/course/assets', import.meta.url)),
    emptyOutDir: false,
    target: 'es2022',
    rollupOptions: {
      input: fileURLToPath(new URL('./src/course/main.tsx', import.meta.url)),
      output: { format: 'iife', entryFileNames: 'course.js', inlineDynamicImports: true },
    },
  },
});
