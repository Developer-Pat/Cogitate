import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { notifyBus } from './services/notifyBus'
import { useNotificationStore } from './stores/notificationStore'
import { frontendLoggingService } from './services/frontendLoggingService'

// THE NOTIFY BUS REGISTRATION (2026-09-04, the _34 consolidation):
// the apiClient's failure machinery (the outage tracker + the
// final-error log) fires through this leaf bus — the handlers
// register HERE, at the boot, after the whole module graph is
// loaded (the apiClient sits at the BOTTOM of both stacks — it
// can never import them directly; see notifyBus.ts).
notifyBus.register({
  error: (title, message, duration) => useNotificationStore.getState().addError(title, message, duration),
  success: (title, message, duration) => useNotificationStore.getState().addSuccess(title, message, duration),
  log: (source, message, error) => frontendLoggingService.error(source, message, error),
})

// Initialize automatic logging (captures errors, navigation, performance)
import './utils/autoLogging'

// Initialize Cogitate DevTools (window.__cogitate__ for browser DevTools)
import './utils/cogitateDevTools'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
