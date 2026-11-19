// THE NOTIFY BUS (2026-09-04, the _34 consolidation)
//
// The apiClient sits at the BOTTOM of the logging + notification
// stacks (frontendLoggingService -> logsService -> apiClient;
// notificationStore -> notificationConfigStore ->
// notificationConfigService -> apiClient) — a static import of
// either stack into the client would close a cycle (the _33
// app-killer class), and a DYNAMIC import raced the vitest module
// registry across test-file transitions (the full-suite hang).
//
// THE BUS: a leaf module (imports NOTHING) that the apiClient
// imports STATICALLY — safe by construction. The real handlers
// (the notification store + the logging funnel) register ONCE at
// the app boot (main.tsx), after the module graph is fully loaded.
// Until then (and in tests that don't register), the no-op
// defaults keep the client silent — a failure is never amplified
// by an unregistered bus.

export interface NotifyHandlers {
  error: (title: string, message: string, duration: number) => void
  success: (title: string, message: string, duration: number) => void
  log: (source: string, message: string, error: Error) => void
}

const noop = (): void => undefined

let handlers: NotifyHandlers = { error: noop, success: noop, log: noop }

export const notifyBus = {
  register(next: NotifyHandlers): void {
    handlers = next
  },

  error(title: string, message: string, duration: number): void {
    handlers.error(title, message, duration)
  },

  success(title: string, message: string, duration: number): void {
    handlers.success(title, message, duration)
  },

  log(source: string, message: string, error: Error): void {
    handlers.log(source, message, error)
  },
}
