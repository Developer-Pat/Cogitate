import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useSessionManagement } from '../useSessionManagement'
import { sessionSyncService } from '@/services/sessionSyncService'
import { useCognitiveHubStore } from '@/stores/cognitiveHubStore'
import { useNotificationStore } from '@/stores/notificationStore'
import { IdService } from '@/services/domain/IdService'

/**
 * A DELETE THAT DID NOT HAPPEN MUST SAY SO (2026-09-19).
 *
 * The delete path removes the row from the store BEFORE it calls the backend, so
 * a swallowed rejection left the UI claiming a deletion the backend never made.
 * The catch now reloads the list (the row comes back) and raises an error
 * notification. These tests pin that, because the failure is invisible in the
 * happy path and the browser half is hard to stage (the page confirms with a
 * native dialog, which freezes the harness).
 */
describe('useSessionManagement — the failed session delete', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    // the mount load must not touch the network
    vi.spyOn(sessionSyncService, 'reloadSessionsWithMessages').mockResolvedValue([] as never)
    vi.spyOn(sessionSyncService, 'getSessions').mockResolvedValue([] as never)
    vi.spyOn(sessionSyncService, 'convertToFrontendSession').mockImplementation(
      (s: unknown) => s as never
    )
  })

  it('reloads the list and tells the user when the backend refuses the delete', async () => {
    const { result } = renderHook(() => useSessionManagement())
    await act(async () => {}) // flush the mount load (keeps the act() warning away)

    const removeSpy = vi.spyOn(useCognitiveHubStore.getState(), 'removeSession')
    const errorSpy = vi.spyOn(useNotificationStore.getState(), 'addError')
    vi.spyOn(IdService, 'isTempId').mockReturnValue(false)
    const deleteSpy = vi
      .spyOn(sessionSyncService, 'deleteSession')
      .mockRejectedValue(new Error('HTTP 404'))
    const reloadSpy = vi
      .spyOn(sessionSyncService, 'reloadSessionsWithMessages')
      .mockResolvedValue([] as never)

    act(() => {
      result.current.deleteSession('4242')
    })

    // the optimistic removal — the very thing that makes a silent failure a lie
    expect(removeSpy).toHaveBeenCalledWith('4242')

    await waitFor(() => expect(deleteSpy).toHaveBeenCalledWith('4242'))
    // …and then the two halves of the fix: say so, and put the list back
    await waitFor(() => expect(errorSpy).toHaveBeenCalled())
    expect(errorSpy.mock.calls[0][0]).toMatch(/delete/i)
    await waitFor(() => expect(reloadSpy).toHaveBeenCalled())
  })

  it('does not call the backend for a temp session (nothing to delete there)', async () => {
    const { result } = renderHook(() => useSessionManagement())
    await act(async () => {}) // flush the mount load

    vi.spyOn(IdService, 'isTempId').mockReturnValue(true)
    const deleteSpy = vi.spyOn(sessionSyncService, 'deleteSession')

    act(() => {
      result.current.deleteSession('session-123')
    })

    expect(deleteSpy).not.toHaveBeenCalled()
  })
})
