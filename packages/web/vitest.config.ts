import path from 'node:path';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  esbuild: {
    jsx: 'automatic',
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
    include: ['src/**/*.test.{ts,tsx}', '../shared/src/**/*.test.{ts,tsx}'],
  },
  resolve: {
    alias: [
      { find: '@', replacement: path.resolve(__dirname, './src') },
      {
        find: /^@unrealmake\/shared\/(.*)$/,
        replacement: path.resolve(__dirname, '../shared/src/$1'),
      },
      {
        find: '@unrealmake/shared',
        replacement: path.resolve(__dirname, '../shared/src/index.ts'),
      },
    ],
  },
});
