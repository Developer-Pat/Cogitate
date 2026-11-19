/**
 * PromptHistoryList — the History tab's rows.
 *
 * Written for the trash-button change (the user's ask): the per-row delete used to
 * hide behind a ⋮ dropdown holding exactly one item. These tests pin that it is now
 * DIRECTLY reachable, so a later "tidy-up" cannot quietly put it back behind a menu —
 * which is the exact regression a hidden control invites.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import PromptHistoryList from '../PromptHistoryList'
import { usePromptHistoryStore } from '@/stores/promptHistoryStore'

vi.mock('@/stores/notificationStore', () => ({
  useNotificationStore: (selector: (s: unknown) => unknown) =>
    selector({ addNotification: vi.fn() }),
}))

describe('PromptHistoryList', () => {
  beforeEach(() => {
    usePromptHistoryStore.setState({ prompts: [] })
  })

  it('deletes from a directly-visible button, with no menu in the way', () => {
    usePromptHistoryStore.getState().addPrompt('a prompt to remove', '16')
    render(<PromptHistoryList />)

    const del = screen.getByLabelText('Remove this prompt from the history')
    expect(del).toBeTruthy()

    fireEvent.click(del)
    expect(usePromptHistoryStore.getState().prompts).toHaveLength(0)
  })

  it('leaves no dropdown or "more actions" control on the row', () => {
    usePromptHistoryStore.getState().addPrompt('a prompt', '16')
    const { container } = render(<PromptHistoryList />)

    expect(container.querySelector('.dropdown')).toBeNull()
    expect(screen.queryByLabelText(/More actions/i)).toBeNull()
    // the visible trash is the only per-row destructive control
    expect(screen.getAllByLabelText('Remove this prompt from the history')).toHaveLength(1)
  })

  it('says so plainly when there is nothing in the history', () => {
    render(<PromptHistoryList />)
    expect(screen.getByText(/No prompts in the history yet/i)).toBeTruthy()
  })

  it('renders every stored prompt, alphabetically', () => {
    const { addPrompt } = usePromptHistoryStore.getState()
    addPrompt('zebra', '16')
    addPrompt('apple', '16')
    render(<PromptHistoryList />)

    const rows = screen.getAllByText(/^(zebra|apple)$/).map((n) => n.textContent)
    expect(rows).toEqual(['apple', 'zebra'])
  })
})
