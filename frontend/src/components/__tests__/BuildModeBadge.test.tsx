/**
 * The build-mode badge (the frontend mode switch, Phase A).
 *
 * Both branches are tested through the exported pure decision, so neither
 * depends on stubbing `import.meta.env` — Vite bakes that flag in at build time
 * and it is not meant to be faked.
 *
 * Two of these tests are house rules encoded: the label stays STATE ONLY, and
 * nothing is hover-hidden.
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import BuildModeBadge from '../BuildModeBadge'
import { buildModeInfo } from '@/utils/buildMode'

describe('BuildModeBadge', () => {
  it('labels the development build, and says WHY it is slower', () => {
    const { label, tip } = buildModeInfo(true)
    expect(label).toBe('DEV')
    // the badge's job is to explain the performance the user is feeling
    expect(tip).toMatch(/unbundled/)
    expect(tip).toMatch(/unminified/)
    expect(tip).toMatch(/StrictMode/)
  })

  it('labels the production build honestly — what a deployment runs', () => {
    const { label, tip } = buildModeInfo(false)
    expect(label).toBe('PROD')
    expect(tip).toMatch(/minified/)
  })

  it('keeps the label to STATE ONLY', () => {
    // a badge that grows into a sentence stops being a badge
    expect(buildModeInfo(true).label.length).toBeLessThanOrEqual(4)
    expect(buildModeInfo(false).label.length).toBeLessThanOrEqual(4)
  })

  it('renders the label and wires the explanation to the DaisyUI tooltip', () => {
    render(<BuildModeBadge />)

    // vitest runs with import.meta.env.DEV true, so this is the development build
    expect(screen.getByText('DEV')).toBeTruthy()

    const wrapper = document.querySelector('.tooltip')
    expect(wrapper).toBeTruthy()
    expect(wrapper!.getAttribute('data-tip')).toBe(buildModeInfo(true).tip)
  })

  it('is always visible — no hover-hidden control', () => {
    render(<BuildModeBadge />)
    // the house rule: no hover-hidden/opacity-0 controls
    expect(document.querySelector('.opacity-0')).toBeNull()
    expect(screen.getByText('DEV').className).not.toMatch(/opacity-0|hidden/)
  })
})
