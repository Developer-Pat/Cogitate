/**
 * splitStreamingMarkdown — the render-equivalence corpus.
 *
 * THE CONTRACT, IN TWO HALVES. Both matter, and a test of only the first would
 * pass against a splitter that never splits (which is correct but useless):
 *
 *   1. CORRECTNESS — rendering the blocks separately must produce the SAME DOM
 *      as rendering the document whole. This is what keeps streaming text from
 *      changing shape mid-arrival.
 *   2. USEFULNESS — it must actually split the prose case, or there is no
 *      performance gain to justify the module.
 *
 * Plus: where splitting would be unsafe it must DECLINE (return one block).
 */
import { describe, it, expect, vi } from 'vitest'
import { render, cleanup } from '@testing-library/react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { CodeBlock } from '@/components/features/agentInteraction/MessageBubble'
import { splitStreamingMarkdown } from '../streamingMarkdown'

// MessageBubble's exact configuration, so the comparison is of the real path
const MD = ({ text }: { text: string }) => (
  <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]} components={{ code: CodeBlock }}>
    {text}
  </ReactMarkdown>
)

/**
 * React places whitespace text nodes between adjacent elements when they are
 * siblings in ONE tree, and omits them when they are separate subtrees. So raw
 * innerHTML differs by "> <" vs "><" even when the markdown is identical —
 * normalize that away before comparing, or every case looks different.
 */
const norm = (html: string) => html.replace(/>\s+</g, '><').replace(/\s+/g, ' ').trim()

const renderWhole = (md: string) => {
  cleanup()
  return norm(render(<MD text={md} />).container.innerHTML)
}

const renderSplit = (md: string) => {
  cleanup()
  const blocks = splitStreamingMarkdown(md)
  const r = render(<div>{blocks.map((b, i) => <MD key={i} text={b} />)}</div>)
  return norm((r.container.firstElementChild as HTMLElement).innerHTML)
}

const para = 'The bicycle stays upright because the rider steers the wheels back under the centre of mass.'

const cases: Array<{ name: string; md: string; mustSplit?: boolean; mustDecline?: boolean }> = [
  { name: 'plain paragraphs', md: `${para}\n\n${para}\n\n${para}\n\n${para}`, mustSplit: true },
  { name: 'tight list', md: `- one\n- two\n- three\n\n${para}`, mustSplit: true },

  // the two failure modes that motivated the conservative rules — must DECLINE
  { name: 'LOOSE list (blank line between items)', md: '- one\n\n- two\n\n- three', mustDecline: true },
  { name: 'loose list then prose (the list ends at the prose — safe to cut)', md: `- alpha\n\n- beta\n\n${para}`, mustSplit: true },
  { name: 'nested list, blank line before sub-list', md: '- top one\n  - nested a\n  - nested b\n\n- top two', mustDecline: true },
  { name: 'reference-style link definition', md: `See [the docs][ref].\n\n${para}\n\n[ref]: https://example.com/d`, mustDecline: true },

  { name: 'fenced code with blank lines inside', md: 'Intro.\n\n```js\nconst a = 1\n\nconst b = 2\n```\n\nOutro.', mustSplit: true },
  { name: 'GFM table', md: '| a | b |\n|---|---|\n| 1 | 2 |' },
  { name: 'blockquote with two paragraphs', md: '> first\n>\n> second' },
  { name: 'setext heading', md: 'My Heading\n==========\n\nText after.', mustSplit: true },
  {
    name: 'realistic answer (heading + prose + list + code)',
    md: `# How it works\n\n${para}\n\n- point one\n- point two\n\n\`\`\`python\ndef go():\n    return 1\n\`\`\`\n\n${para}`,
  },
  { name: 'prose-heavy (the real streaming case)', md: `${para}\n\n${para}\n\n${para}\n\n${para}\n\n${para}\n\n${para}`, mustSplit: true },
]

describe('splitStreamingMarkdown', () => {
  it.each(cases)('renders identically whether whole or split: $name', ({ md }) => {
    expect(renderSplit(md)).toBe(renderWhole(md))
  })

  it.each(cases.filter((c) => c.mustSplit))('actually splits: $name', ({ md }) => {
    expect(splitStreamingMarkdown(md).length).toBeGreaterThan(1)
  })

  it.each(cases.filter((c) => c.mustDecline))('declines to split where it is unsafe: $name', ({ md }) => {
    expect(splitStreamingMarkdown(md)).toEqual([md])
  })

  it('leaves a fence intact — blank lines inside code are not boundaries', () => {
    const md = '```js\nconst a = 1\n\n\n\nconst b = 2\n```'
    expect(splitStreamingMarkdown(md)).toEqual([md])
  })

  it('splits a growing document into a stable prefix plus a growing tail', () => {
    // The property the optimisation depends on: once a block is finished, its
    // text does not change as more arrives — so a memo keyed on the text holds.
    const v1 = splitStreamingMarkdown(`${para}\n\n${para}`)
    const v2 = splitStreamingMarkdown(`${para}\n\n${para}\n\nhalf a sent`)
    expect(v2.length).toBeGreaterThanOrEqual(v1.length)
    expect(v2.slice(0, v1.length)).toEqual(v1)
  })

  it('is cheap — a string scan, not a parse', () => {
    // Guards against someone later replacing it with a real markdown parse,
    // which would re-introduce the cost it exists to remove.
    const spy = vi.spyOn(console, 'log')
    const big = Array.from({ length: 400 }, () => para).join('\n\n')
    const t0 = performance.now()
    for (let i = 0; i < 200; i++) splitStreamingMarkdown(big)
    const perCall = (performance.now() - t0) / 200
    spy.mockRestore()
    expect(perCall).toBeLessThan(5) // ms per call on a ~35 KB document
  })
})
