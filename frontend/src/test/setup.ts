/**
 * Vitest Test Setup
 *
 * Configures testing environment with:
 * - @testing-library/jest-dom matchers
 * - Mock for localStorage
 */

import '@testing-library/jest-dom'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

// Cleanup after each test
afterEach(() => {
  cleanup()
})

// ── THE NATIVE-DIALOG POLYFILL ────────────────────────────────────────────────────────────────
// jsdom ships the `HTMLDialogElement` INTERFACE but none of its methods, so the house modal shell
// (`ProviderModal`: `<dialog className="modal">` + `showModal()` on mount) throws on render in a
// test. Polyfill the three methods rather than special-casing test-only branches into the shell:
// `open` is a reflected attribute, so setting it is exactly what opening/closing means here, and
// `close` dispatches the event the shell listens for so its parent-state sync still runs.
if (typeof HTMLDialogElement !== 'undefined' && !HTMLDialogElement.prototype.showModal) {
  const proto = HTMLDialogElement.prototype as unknown as {
    show: (this: HTMLDialogElement) => void
    showModal: (this: HTMLDialogElement) => void
    close: (this: HTMLDialogElement, returnValue?: string) => void
  }
  proto.show = function () {
    this.open = true
  }
  proto.showModal = function () {
    this.open = true
  }
  proto.close = function (returnValue?: string) {
    this.open = false
    if (returnValue !== undefined) this.returnValue = returnValue
    this.dispatchEvent(new Event('close'))
  }
}

// Mock localStorage
const localStorageMock = {
  store: {} as Record<string, string>,

  getItem(key: string): string | null {
    return this.store[key] ?? null
  },

  setItem(key: string, value: string): void {
    this.store[key] = value
  },

  removeItem(key: string): void {
    delete this.store[key]
  },

  clear(): void {
    this.store = {}
  },
}

// Mock localStorage globally
Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
  writable: true,
  configurable: true,
})

// Reset mocks after each test
afterEach(() => {
  vi.clearAllMocks()
  localStorageMock.clear()
})
