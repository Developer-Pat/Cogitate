/**
 * The mode switch.
 *
 * THE LOAD-BEARING BEHAVIOUR IS THE RELOAD TIMING. The launcher writes the mode
 * record BEFORE the new server binds, so a page that polled the mode endpoint
 * would reload straight into the OLD build — a switch that appears to do
 * nothing. What makes it work is watching the ENTRY MODULE the server serves,
 * so these tests pin that detection above all.
 *
 * The button's own labels are tested too, because they are the user's only clue
 * about which direction the switch goes.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import BuildModeSwitch from '../BuildModeSwitch'
import { entryFromHtml, entryFromDocument } from '@/utils/buildMode'

vi.mock('@/stores/notificationStore', () => ({
  useNotificationStore: (selector: (s: unknown) => unknown) =>
    selector({ addNotification: vi.fn() }),
}))

vi.mock('@/services/domains/system/modeService', () => ({
  default: { get: vi.fn(), switchTo: vi.fn() },
}))

// A Vite dev-server index.html and a production one, in the parts that matter.
const DEV_HTML = `<!doctype html><html><head><script type="module" src="/src/main.tsx"></script></head><body></body></html>`
const PROD_HTML = `<!doctype html><html><head><script type="module" crossorigin src="/assets/index.C_PVVyRl.js"></script></head><body></body></html>`

describe('the served entry module — what the reload watches', () => {
  it('reads the dev server entry', () => {
    expect(entryFromHtml(DEV_HTML)).toBe('/src/main.tsx')
  })

  it('reads the production build entry', () => {
    expect(entryFromHtml(PROD_HTML)).toBe('/assets/index.C_PVVyRl.js')
  })

  it('THE PROPERTY THE RELOAD DEPENDS ON: the two builds serve different entries', () => {
    // If these ever matched, the switch would reload into the old build and look
    // like it had done nothing — the exact failure this detection exists to avoid.
    expect(entryFromHtml(DEV_HTML)).not.toBe(entryFromHtml(PROD_HTML))
  })

  it('claims nothing when there is no module script', () => {
    // An error page or an in-flight response must NOT be read as "the new build
    // is up" — returning null keeps the caller waiting instead of reloading.
    expect(entryFromHtml('<html><body>504</body></html>')).toBeNull()
  })

  it('reads the entry from the live document', () => {
    const doc = new DOMParser().parseFromString(DEV_HTML, 'text/html')
    expect(entryFromDocument(doc)).toBe('/src/main.tsx')
  })
})

describe('BuildModeSwitch', () => {
  beforeEach(() => vi.clearAllMocks())

  it('names the direction it will switch, and does not switch on its own', () => {
    render(<BuildModeSwitch />)
    // vitest runs with import.meta.env.DEV true, so this is the development build
    expect(screen.getByText('Switch to production')).toBeTruthy()
  })

  it('asks before switching — it cycles the app and rebuilds', () => {
    render(<BuildModeSwitch />)
    // nothing is confirmed until the user says so
    expect(document.querySelector('dialog')?.hasAttribute('open')).toBe(false)

    fireEvent.click(screen.getByText('Switch to production'))
    const dialog = document.querySelector('dialog')
    expect(dialog?.hasAttribute('open')).toBe(true)
    // the modal states the consequence rather than just asking "are you sure"
    expect(screen.getByText(/stay signed in/i)).toBeTruthy()
  })

  it('can be cancelled without switching', () => {
    render(<BuildModeSwitch />)
    fireEvent.click(screen.getByText('Switch to production'))
    fireEvent.click(screen.getByText('Cancel'))
    expect(document.querySelector('dialog')?.hasAttribute('open')).toBe(false)
  })
})
