import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render } from '@testing-library/react'
import ReactMarkdown from 'react-markdown'
import { CodeBlock } from '../MessageBubble'

describe('CodeBlock (the hydration-safe inline/block split)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders INLINE code as a bare <code> (never a <pre> — the hydration rule)', () => {
    // inline code: `code` inside a paragraph — react-markdown v10
    // passes NO inline prop; the discriminator is the language class
    const { container } = render(
      <ReactMarkdown components={{ code: CodeBlock }}>
        {'Use the `alert()` function here.'}
      </ReactMarkdown>,
    )
    // the paragraph must NOT contain a <pre>
    const ps = container.querySelectorAll('p')
    expect(ps.length).toBeGreaterThan(0)
    ps.forEach((p) => {
      expect(p.querySelector('pre')).toBeNull()
    })
    // the inline code renders as a <code>
    const codes = container.querySelectorAll('code')
    expect(codes.length).toBeGreaterThan(0)
  })

  it('renders BLOCK code with the <pre> wrapper', () => {
    const { container } = render(
      <ReactMarkdown components={{ code: CodeBlock }}>
        {'```js\nconst x = 1\n```'}
      </ReactMarkdown>,
    )
    const pre = container.querySelector('pre')
    expect(pre).not.toBeNull()
    // the block <pre> is NOT inside a <p>
    const preParent = pre?.parentElement
    expect(preParent?.tagName).not.toBe('P')
  })
})
