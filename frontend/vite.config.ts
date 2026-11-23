/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import fs from 'fs'
import { fileURLToPath } from 'node:url'
import { aliases } from './aliases'

// Read version from the ROOT pyproject.toml — the same file `./cogitate.sh release` treats as the
// version's home and the same one the backend reports. frontend/package.json says 0.0.0 and is never
// bumped, so reading it here put "v0.0.0" in the header of a 0.1.x build.
const packageJson = JSON.parse(fs.readFileSync('./package.json', 'utf-8'))
const rootPyproject = fs.readFileSync(fileURLToPath(new URL('../pyproject.toml', import.meta.url)), 'utf-8')
const appVersion = rootPyproject.match(/^version\s*=\s*"([^"]+)"/m)?.[1] ?? packageJson.version ?? '0.0.0-dev'

// https://vite.dev/config/
// PORTS (2026-09-15). The launcher EXPORTS these, so the dev server and its API
// proxy stay in step with what the backend actually bound. Defaults match the
// house launcher (8000 / 5173) for the bare `npx vite` case outside cogitate.sh.
const BACKEND_PORT = process.env.COGITATE_BACKEND_PORT ?? '8000'
const FRONTEND_PORT = Number(process.env.COGITATE_FRONTEND_PORT ?? '5173')
const BACKEND_ORIGIN = `http://localhost:${BACKEND_PORT}`

// THE PROXY — declared ONCE and given to BOTH servers. The development server
// and the production server must reach the backend identically, and relying on
// Vite's fallback from `preview.proxy` down to `server.proxy` makes that an
// implicit contract a later edit could drop silently. Same reasoning as
// aliases.ts: one definition, every consumer.
const PROXY = {
  '/api': {
    target: BACKEND_ORIGIN,
    changeOrigin: true,
    // WebSocket upgrade passthrough (agent panel WS, chat WS)
    ws: true,
  },
  // Static assets (profile images) are served by the backend — without this
  // proxy the frontend returns the SPA fallback (text/html) and images render
  // broken.
  '/static': {
    target: BACKEND_ORIGIN,
    changeOrigin: true,
  },
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  define: {
    // Inject app version for cache busting
    'import.meta.env.VITE_APP_VERSION': JSON.stringify(appVersion),
  },
  resolve: {
    // THE LOCATOR — imported from aliases.ts so the app build and the test
    // runner cannot drift apart (see that file for why).
    alias: aliases,
  },
  build: {
    // Cache busting with content hashes
    rollupOptions: {
      output: {
        entryFileNames: 'assets/[name].[hash].js',
        chunkFileNames: 'assets/[name].[hash].js',
        assetFileNames: 'assets/[name].[hash].[ext]',
      },
    },
    // Disable caching headers during development
    sourcemap: true,
  },
  server: {
    host: '0.0.0.0',
    port: FRONTEND_PORT,
    proxy: PROXY,
  },
  // THE PRODUCTION SERVER — serves the built bundle. It binds the SAME port as
  // the development server, deliberately: the app's state (auth token, settings,
  // message history) lives in ORIGIN-SCOPED browser storage, so a mode change
  // that moved the port would log the user out, empty their history, and sever
  // the BroadcastChannel the tabs use to coordinate. One origin, one port, one
  // server at a time. (Vite calls this command "preview"; what it serves IS the
  // production build.)
  preview: {
    host: '0.0.0.0',
    port: FRONTEND_PORT,
    proxy: PROXY,
  },
})

// NOTE: there is deliberately NO `test:` block here. vitest prefers a dedicated
// vitest.config.ts and does NOT merge this file, so a `test:` block in here is
// dead config — it reads as authoritative and changes nothing. The test config
// lives in vitest.config.ts, and the path alias both need comes from aliases.ts.
