import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { aliases } from './aliases'

export default defineConfig({
  plugins: [react()],
  // THE LOCATOR — the SAME definition the app build uses (aliases.ts), so
  // '@/...' cannot resolve in one context and silently fail in the other. This
  // is why the alias lives in its own module: vitest prefers THIS file and does
  // not merge vite.config.ts, so duplicating the alias here would drift.
  resolve: {
    alias: aliases,
  },
  test: {
    globals: true,
    environment: 'jsdom',
    testTimeout: 10000,
    // THE POOL CAP (approved 2026-09-17). Vitest sizes its worker pool from
    // os.cpus().length, and this box reports 24 -- but that is 24 LOGICAL CPUs,
    // i.e. 12 physical cores with SMT, so two workers contend inside each
    // physical core rather than getting one each. Uncapped, a full-suite run
    // spawned ~24 jsdom workers and saturated the machine, taking the desktop
    // down with it (a REISUB was needed to recover) while a local llama-server
    // was also resident.
    //
    // 4 is deliberately conservative and leaves most of the physical cores for
    // the dev server, the editor and whatever else is running. The suite is
    // still quick at this width; raise it if runs feel slow, but check
    // `cat /proc/loadavg` first and remember the box is shared.
    maxWorkers: 4,
    minWorkers: 1,
    setupFiles: ['./src/test/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'src/test/',
        '**/*.d.ts',
        '**/*.config.*',
        '**/dist/**',
      ],
    },
  },
})