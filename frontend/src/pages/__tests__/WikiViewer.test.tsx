import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@/test/test-utils'
import WikiViewer from '../WikiViewer'

// mermaid is mocked for the palette test below; the wikilink tests are unaffected
// (they only assert that no raw fence text leaks through).
const mermaidMock = vi.hoisted(() => ({
  initialize: vi.fn().mockResolvedValue(undefined),
  render: vi.fn().mockResolvedValue({ svg: '<svg data-testid="mermaid-svg"></svg>' }),
}))
vi.mock('mermaid', () => ({ default: mermaidMock }))

const MERMAID_PAGE = [
  '---', 'title: Palette', '---', '# Palette', '',
  '```mermaid', 'flowchart TD', '    A --> B', '```',
].join('\n')

/** Render the viewer on a page with one diagram, under a theme whose base surface is `base100`. */
async function renderUnderTheme(themeName: string, base100: string) {
  vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) =>
    Promise.resolve({
      ok: true,
      headers: { get: () => 'application/json' },
      json: () => url === '/api/v1/wiki'
        ? Promise.resolve({ tree: [] })
        : Promise.resolve({ content: MERMAID_PAGE, children: [] }),
    })))
  document.documentElement.setAttribute('data-theme', themeName)
  document.documentElement.style.setProperty('--color-base-100', base100)
  render(<WikiViewer />)
  await screen.findByTestId('mermaid-svg', {}, { timeout: 3000 })
}

// The wikilink conversion is internal to the component; test through
// render with a mocked fetch that returns content containing wikilinks.
describe('WikiViewer wikilink conversion', () => {
  it('renders alias-form wikilinks [[path|label]] as real links', async () => {
    const content = [
      '---',
      'title: Test',
      '---',
      '# Test',
      'See [[dev-notes/agents/agent-lifecycle|Agent Lifecycle]] and [[cognitive-profiles]].',
    ].join('\n')

    const jsonHeaders = { get: () => 'application/json' }
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => {
      // WikiViewer fetches the tree (/api/v1/wiki) + the current page
      return Promise.resolve({
        ok: true,
        headers: jsonHeaders,
        json: () =>
          url === '/api/v1/wiki'
            ? Promise.resolve({ tree: [] })
            : Promise.resolve({ content, children: [] }),
      })
    }))

    render(<WikiViewer />)
    await screen.findByText(/Agent Lifecycle/, {}, { timeout: 3000 })
    // Assert the alias-form link converted to a real anchor
    const link = screen.getByRole('link', { name: 'Agent Lifecycle' })
    expect(link).toHaveAttribute('href', '/wiki/dev-notes/agents/agent-lifecycle')
    // bare-form link also works
    const bare = screen.getByRole('link', { name: 'Cognitive Profiles' })
    expect(bare).toHaveAttribute('href', '/wiki/cognitive-profiles')
  })

  // A spaced wiki path is a legal target: 66 pages in this corpus have a space
  // in the filename ("UI Atlas.md", "Paths and Path Resolution.md",
  // "Message map.md"). The converter's character class used to stop at the
  // space, so every such link rendered as literal [[...]] text in the viewer.
  it('renders wikilinks whose path contains a space', async () => {
    const content = [
      '---',
      'title: Test',
      '---',
      '# Test',
      'See [[atlas/ui/UI Atlas|UI Atlas]] and [[dev-notes/architecture/Paths and Path Resolution]].',
    ].join('\n')

    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) =>
      Promise.resolve({
        ok: true,
        headers: { get: () => 'application/json' },
        json: () => url === '/api/v1/wiki'
          ? Promise.resolve({ tree: [] })
          : Promise.resolve({ content, children: [] }),
      })))

    render(<WikiViewer />)
    const aliased = await screen.findByRole('link', { name: 'UI Atlas' }, { timeout: 3000 })
    expect(aliased).toHaveAttribute('href', '/wiki/atlas/ui/UI%20Atlas')
    // No alias: the label is the last path segment, as Obsidian shows it.
    const bare = screen.getByRole('link', { name: 'Paths and Path Resolution' })
    expect(bare).toHaveAttribute('href', '/wiki/dev-notes/architecture/Paths%20and%20Path%20Resolution')
  })
})

describe('WikiViewer mermaid palette — darkness, not the theme NAME', () => {
  beforeEach(() => {
    mermaidMock.initialize.mockClear()
  })
  afterEach(() => {
    document.documentElement.style.removeProperty('--color-base-100')
    document.documentElement.removeAttribute('data-theme')
  })

  // THE REGRESSION (2026-10-10): the palette was chosen with
  // `data-theme === 'dark'`, which is true for ONE of the app's twelve dark themes.
  // The other eleven (coffee, night, dim, dracula, …) got mermaid's LIGHT palette —
  // pale nodes with dark text on a dark page. Assert on a theme NOT named 'dark'.
  it('gives a non-"dark" dark theme the dark palette', async () => {
    await renderUnderTheme('coffee', 'oklch(24% 0.023 329.708)')

    const call = mermaidMock.initialize.mock.calls.at(-1)?.[0]
    expect(call?.theme).toBe('dark')
  })

  // mermaid's `useMaxWidth` (on by default) scales a wide diagram DOWN to the
  // column — a 2466px figure rendered at 0.30, ~5px text. The figure keeps its
  // natural size and the box scrolls; this guards the per-type config.
  it('turns shrink-to-column off so a wide figure stays readable', async () => {
    await renderUnderTheme('dark', 'oklch(25.33% 0.016 252.42)')

    const call = mermaidMock.initialize.mock.calls.at(-1)?.[0]
    expect(call?.flowchart?.useMaxWidth).toBe(false)
    expect(call?.sequence?.useMaxWidth).toBe(false)
  })

  // A figure wider than the column needs a way to be seen whole. The popout is a native
  // <dialog> opened with showModal(); jsdom implements neither the top layer nor the method,
  // so the call is stubbed — what is asserted is that the control exists, is reachable, and
  // opens the dialog rather than, say, navigating.
  it('opens a full-screen popout for a figure too wide for the column', async () => {
    const showModal = vi.fn();
    HTMLDialogElement.prototype.showModal = showModal;
    await renderUnderTheme('dark', 'oklch(25.33% 0.016 252.42)');

    fireEvent.click(screen.getByRole('button', { name: /expand the figure/i }));

    expect(showModal).toHaveBeenCalled();
    expect(document.querySelector('dialog.modal[open], dialog.modal')).toBeTruthy();
  })

  it('gives a light theme the light palette', async () => {
    await renderUnderTheme('light', 'oklch(100% 0 0)')

    const call = mermaidMock.initialize.mock.calls.at(-1)?.[0]
    expect(call?.theme).toBe('default')
  })
})

describe('WikiViewer mermaid rendering', () => {
  it('renders mermaid fences as diagram containers, not raw code', async () => {
    const content = [
      '---',
      'title: Mermaid Test',
      '---',
      '# Mermaid Test',
      '',
      '```mermaid',
      'flowchart TD',
      '    A --> B',
      '```',
      '',
      'Regular code stays a code block:',
      '',
      '```python',
      'x = 1',
      '```',
    ].join('\n')

    const jsonHeaders = { get: () => 'application/json' }
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => {
      return Promise.resolve({
        ok: true,
        headers: jsonHeaders,
        json: () =>
          url === '/api/v1/wiki'
            ? Promise.resolve({ tree: [] })
            : Promise.resolve({ content, children: [] }),
      })
    }))

    render(<WikiViewer />)
    // The python fence should render as a highlighted code element
    // (highlight.js splits text into hljs spans, so match by function)
    await screen.findByText((text) => text.includes('x ='), {}, { timeout: 3000 })
    // The mermaid fence should NOT appear as raw text — either a rendered
    // SVG (mermaid.render resolved) or the loading state; assert no raw
    // 'flowchart TD' text leaks through as code content.
    expect(screen.queryByText('flowchart TD')).toBeNull()
    expect(screen.queryByText('A --> B')).toBeNull()
  })
})

// The tree is re-read on NAVIGATION, not once per mount: the corpus changes under
// a mounted view, and a sidebar holding a moved or deleted path 404s when clicked.
// The count assertion after the dust settles also pins the thing that must NOT
// happen — a refetch that re-triggers itself.
describe('WikiViewer wiki tree — re-read on navigation', () => {
  const treeCalls = (m: ReturnType<typeof vi.fn>) =>
    m.mock.calls.filter((c) => c[0] === '/api/v1/wiki').length

  afterEach(() => {
    window.history.pushState({}, '', '/')
  })

  it('refetches the tree when the wiki route changes, and does not then storm', async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) =>
      Promise.resolve({
        ok: true,
        headers: { get: () => 'application/json' },
        json: () =>
          url === '/api/v1/wiki'
            ? Promise.resolve({ tree: [] })
            : Promise.resolve({
                content: url.includes('dev-notes/agents') ? '# Agents page' : '# Site Index page',
                children: [],
              }),
      }))
    vi.stubGlobal('fetch', fetchMock)

    render(<WikiViewer />)
    await waitFor(() => expect(treeCalls(fetchMock)).toBe(1))

    // navigate the way the router does (BrowserRouter listens for popstate)
    await act(async () => {
      window.history.pushState({}, '', '/wiki/dev-notes/agents')
      window.dispatchEvent(new PopStateEvent('popstate'))
    })

    // the route change took effect…
    await screen.findByText('Agents page', {}, { timeout: 3000 })
    // …and it re-read the tree exactly once more
    await waitFor(() => expect(treeCalls(fetchMock)).toBe(2))

    // bounded: no second refetch follows the tree swap
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(treeCalls(fetchMock)).toBe(2)
  })
})
