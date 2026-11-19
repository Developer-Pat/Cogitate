import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@/test/test-utils'
import ImageManagement from '../ImageManagement'
import { useNotificationStore } from '@/stores/notificationStore'

const lastMessage = () => {
  const n = useNotificationStore.getState().notifications
  return n.length ? n[n.length - 1].message : ''
}

// ImageManagement bulk features — checkbox select-all + batch delete
// + multi-file upload. The page hits /api/v1/images (list + bulk).
describe('ImageManagement bulk features', () => {
  const images = [
    { filename: 'bob.png', url: '/static/bob.png', size: 100, mime: 'image/png', created_at: 1, used_by: [3], is_curated: true },
    { filename: 'free.png', url: '/static/free.png', size: 200, mime: 'image/png', created_at: 2, used_by: [] },
    { filename: 'orphan.png', url: '/static/orphan.png', size: 300, mime: 'image/png', created_at: 3, used_by: [] },
  ]

  const listResp = { images, total: 3, page: 1, page_size: 50 }

  beforeEach(() => {
    useNotificationStore.setState({ notifications: [] })
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      // apiClient prefixes baseUrl (http://localhost:8000) — match by suffix
      if (url.endsWith('/api/v1/images?page=1&page_size=50&curated=all&sort_by=filename&sort_dir=asc')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(listResp) })
      }
      if (url.endsWith('/api/v1/images/batch-delete') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            deleted: ['free.png', 'orphan.png'],
            failed: [{ filename: 'bob.png', reason: 'in use by agent(s) [3]' }],
            total_requested: 3,
            total_deleted: 2,
            total_failed: 1,
          }),
        })
      }
      if (url.includes('/api/v1/images/upload-bulk') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            added: [{ filename: 'new1.png', url: '/static/new1.png', size: 10 }],
            errors: [],
            total_requested: 1,
            total_added: 1,
            total_errors: 0,
          }),
        })
      }
      return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) })
    }))
  })

  it('select-all selects every shown row and shows the bulk bar', async () => {
    render(<ImageManagement />)
    await screen.findByText('bob.png', {}, { timeout: 3000 })
    const selectAll = document.querySelector('input[aria-label="Select all shown"]') as HTMLInputElement
    fireEvent.click(selectAll)
    await waitFor(() => expect(screen.getByText('3 selected')).toBeTruthy())
    // each row checkbox is checked
    const checks = document.querySelectorAll('tbody input[type="checkbox"]')
    expect(checks.length).toBe(3)
    checks.forEach((c) => expect((c as HTMLInputElement).checked).toBe(true))
  })

  it('batch delete confirms then reports in-use separately', async () => {
    render(<ImageManagement />)
    await screen.findByText('bob.png', {}, { timeout: 3000 })
    fireEvent.click(document.querySelector('input[aria-label="Select all shown"]') as HTMLInputElement)
    await waitFor(() => expect(screen.getByText('3 selected')).toBeTruthy())
    fireEvent.click(screen.getByText('Delete selected'))
    // confirm modal appears
    await screen.findByText('Delete 3 images?', {}, { timeout: 3000 })
    fireEvent.click(screen.getByText('Delete 3'))
    await waitFor(() => {
      const messages = useNotificationStore.getState().notifications.map((n) => n.message).join(' | ')
      expect(messages).toContain('Deleted 2 images')
    }, { timeout: 3000 })
    const messages = useNotificationStore.getState().notifications.map((n) => n.message).join(' | ')
    expect(messages).toContain('1 in use by agents')
  })

  it('filters to uploads only via the dropdown', async () => {
    render(<ImageManagement />)
    await screen.findByText('bob.png', {}, { timeout: 3000 })
    const select = document.querySelector('select[data-tip="Filter by curated status"]') as HTMLSelectElement
    fireEvent.change(select, { target: { value: 'false' } })
    await waitFor(() => {
      // fetch called with curated=false
      const calls = (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls
      expect(calls.some((call: unknown[]) => String(call[0]).includes('curated=false'))).toBe(true)
    }, { timeout: 3000 })
  })

  it('sorts by size when the Size header is clicked', async () => {
    render(<ImageManagement />)
    await screen.findByText('bob.png', {}, { timeout: 3000 })
    fireEvent.click(document.querySelector('button[data-tip="Sort by size"]') as HTMLButtonElement)
    await waitFor(() => {
      const calls = (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls
      expect(calls.some((call: unknown[]) => String(call[0]).includes('sort_by=size&sort_dir=asc'))).toBe(true)
    }, { timeout: 3000 })
    // second click toggles to desc
    fireEvent.click(document.querySelector('button[data-tip="Sort by size"]') as HTMLButtonElement)
    await waitFor(() => {
      const calls = (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls
      expect(calls.some((call: unknown[]) => String(call[0]).includes('sort_by=size&sort_dir=desc'))).toBe(true)
    }, { timeout: 3000 })
  })

  it('uploads multiple files through the bulk endpoint', async () => {
    render(<ImageManagement />)
    await screen.findByText('bob.png', {}, { timeout: 3000 })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    expect(input.hasAttribute('multiple')).toBe(true)
    const file = new File(['x'], 'new1.png', { type: 'image/png' })
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => expect(lastMessage()).toContain('Uploaded 1 image'), { timeout: 3000 })
  })
})
