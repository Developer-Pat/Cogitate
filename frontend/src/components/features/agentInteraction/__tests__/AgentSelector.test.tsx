/**
 * AgentSelector — the agent picker in the chat header.
 *
 * Written for the availability tip (the user's ask): the green check carried an
 * `aria-label` and no visible tooltip, so a sighted user had no way to learn what the
 * badge meant. These tests pin the tip on BOTH branches — the red cross is the same
 * control carrying the opposite state, and leaving it untipped would recreate the
 * exact gap for the case that most needs explaining.
 *
 * They also pin the mechanism: DaisyUI `tooltip` + `data-tip`, NOT PortalTooltip. The
 * header's tips open downward inside the `h-dvh` root and nothing clips them, which is
 * why the two tips already on this control ("Select agent team", "Select an agent") do
 * the same. A tooltip that is clipped and a tooltip that is missing look identical to
 * the user, so this test is deliberately about the attribute being present.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import AgentSelector from '../AgentSelector'
import type { Agent } from '@/types/agentInteraction'

const agent = (over: Partial<Agent> = {}): Agent =>
  ({
    id: '1',
    name: 'Bob',
    provider: 'openrouter',
    model: 'openrouter/inclusionai/ling-3.0-flash',
    isAvailable: true,
    ...over,
  }) as Agent

describe('AgentSelector availability badge', () => {
  it('tips the green check so a sighted user learns what it means', () => {
    const bob = agent()
    render(<AgentSelector agents={[bob]} selectedAgent={bob} onAgentSelect={vi.fn()} />)

    const badge = screen.getByLabelText('Available')
    expect(badge.getAttribute('data-tip')).toBe('This agent is available')
    expect(badge.className).toContain('tooltip')
    expect(badge.className).toContain('tooltip-bottom')
  })

  it('tips the red cross the same way — same control, opposite state', () => {
    const off = agent({ isAvailable: false })
    render(<AgentSelector agents={[off]} selectedAgent={off} onAgentSelect={vi.fn()} />)

    const badge = screen.getByLabelText('Unavailable')
    expect(badge.getAttribute('data-tip')).toBe('This agent is unavailable')
    expect(badge.className).toContain('tooltip')
  })

  it('tips the provider badge with BOTH the provider and the model', () => {
    const bob = agent({ provider: 'openrouter', model: 'openrouter/inclusionai/ling-3.0-flash' })
    render(<AgentSelector agents={[bob]} selectedAgent={bob} onAgentSelect={vi.fn()} />)

    const badge = screen.getByText('openrouter')
    expect(badge.getAttribute('data-tip')).toBe(
      'Provider: openrouter · Model: openrouter/inclusionai/ling-3.0-flash'
    )
    // same mechanism as its neighbour, on the badge itself — no extra wrapper
    expect(badge.className).toContain('tooltip')
    expect(badge.className).toContain('tooltip-bottom')
  })

  it('degrades to the provider alone when there is no model to name', () => {
    const bare = agent({ provider: 'ollama', model: '' })
    render(<AgentSelector agents={[bare]} selectedAgent={bare} onAgentSelect={vi.fn()} />)

    expect(screen.getByText('ollama').getAttribute('data-tip')).toBe('Provider: ollama')
  })
})
