import React, { useState, useEffect, useCallback, useRef } from 'react';
// THE TAB TITLE (2026-08-30, the user's consistency ask): the wiki
// never set one — the tab showed the index.html's default
// ('Cogitate™ - ...'). The viewed page's title now rides the house
// format ('Page | Cogitate™').
import { createPortal } from 'react-dom';
import { Maximize2, X } from 'lucide-react';
import Tooltip from '../components/ui/Tooltip';
import { usePageTitle } from '../hooks/usePageTitle';
import { isDarkThemeByLuminance } from '../hooks/useTheme';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import mermaid from 'mermaid';
import { frontendLoggingService } from '../services/frontendLoggingService';
import { useNavigate, useLocation, Link } from 'react-router-dom';

import 'highlight.js/styles/atom-one-dark.css';

// The pre-render default only; every diagram re-initialises per render with the
// palette its theme's DARKNESS calls for (see MermaidDiagram).
// A wide figure must NOT be scaled down to the column: mermaid's `useMaxWidth`
// (on by default) emits `width="100%"` + `max-width: <natural>`, so a 2466px
// diagram rendered at 736px — 0.30 scale, ~5px text, unreadable. Natural size,
// and the figure box scrolls instead (index.css). Set per diagram TYPE, because
// mermaid carries the flag under each type's own config.
const NATURAL_WIDTH = { useMaxWidth: false };
const NO_SHRINK = {
  flowchart: NATURAL_WIDTH, sequence: NATURAL_WIDTH, class: NATURAL_WIDTH,
  state: NATURAL_WIDTH, er: NATURAL_WIDTH, journey: NATURAL_WIDTH,
  gantt: NATURAL_WIDTH, gitGraph: NATURAL_WIDTH, pie: NATURAL_WIDTH,
  quadrantChart: NATURAL_WIDTH, mindmap: NATURAL_WIDTH, timeline: NATURAL_WIDTH,
  requirement: NATURAL_WIDTH, block: NATURAL_WIDTH, packet: NATURAL_WIDTH,
};

mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  securityLevel: 'loose',
  fontFamily: 'inherit',
  ...NO_SHRINK,
});

interface WikiNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  children?: WikiNode[];
}

interface WikiPage {
  path: string;
  title: string;
  content: string;
  frontmatter: Record<string, string>;
  children: { name: string; path: string }[];
}

function WikiSidebar({ tree, root, activePath }: { tree: WikiNode[]; root?: WikiNode; activePath: string }) {
  // Collapsed directory paths — everything starts collapsed so users drill
  // down instead of wading through fully-expanded trees.
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const initializedRef = useRef(false);

  // When the tree first loads, collapse every directory by default.
  useEffect(() => {
    if (initializedRef.current || tree.length === 0) return;
    const collectDirs = (nodes: WikiNode[]): string[] => {
      const dirs: string[] = [];
      for (const n of nodes) {
        if (n.type === 'directory') {
          dirs.push(n.path);
          dirs.push(...collectDirs(n.children || []));
        }
      }
      return dirs;
    };
    setCollapsed(new Set(collectDirs(tree)));
    initializedRef.current = true;
  }, [tree]);

  // Auto-expand the path to the active page (ancestors stay open so the
  // current location is always visible). Only expands — never re-collapses
  // what the user has manually opened.
  useEffect(() => {
    const segments = activePath.split('/');
    const ancestors = new Set<string>();
    // Include the full path itself so DIRECTORY pages (e.g. ui-atlas/pages)
    // also expand; harmless for file pages since files aren't in collapsed.
    for (let i = 1; i <= segments.length; i++) {
      ancestors.add(segments.slice(0, i).join('/'));
    }
    setCollapsed((prev) => {
      const next = new Set(prev);
      ancestors.forEach((a) => next.delete(a));
      return next;
    });
  }, [activePath, tree]);

  const toggleCollapse = (path: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  const renderNode = (node: WikiNode, depth: number = 0) => {
    const isActive = node.type === 'file' && node.path === activePath;
    const paddingLeft = `${depth * 1 + 0.75}rem`;

    if (node.type === 'directory') {
      const isCollapsed = collapsed.has(node.path);
      return (
        <div key={node.path}>
          <button
            onClick={() => toggleCollapse(node.path)}
            className="w-full flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-base-content/50 px-3 py-1.5 hover:text-base-content transition-colors text-left"
            style={{ paddingLeft }}
            title={isCollapsed ? `Expand ${node.name}` : `Collapse ${node.name}`}
          >
            <span className={`inline-block transition-transform ${isCollapsed ? '' : 'rotate-90'}`}>▸</span>
            {node.name}
          </button>
          {!isCollapsed && node.children?.map((child) => renderNode(child, depth + 1))}
        </div>
      );
    }

    return (
      <Link
        key={node.path}
        to={`/wiki/${node.path}`}
        className={[
          'block py-1.5 px-3 text-sm truncate transition-colors hover:bg-base-200',
          isActive ? 'text-primary font-medium bg-primary/5 border-l-2 border-l-primary' : 'text-base-content/70 hover:text-base-content',
        ].join(' ')}
        style={{ paddingLeft }}
        title={node.name}
      >
        {node.name}
      </Link>
    );
  };

  // When viewing atlas pages, root the tree at the atlas subtree so the
  // sidebar only shows atlas sections (main wiki nav stays clean).
  const nodes = root ? (root.children || []) : tree;
  const header = root ? 'UI Atlas' : 'Wiki';

  return (
    <div className="w-52 flex-shrink-0 border-r border-base-300 overflow-y-auto h-full">
      <div className="px-3 py-3 border-b border-base-300">
        <h2 className="text-sm font-semibold">{header}</h2>
        {root && (
          <Link
            to="/wiki"
            className="text-xs text-readout hover:text-primary mt-1 block"
          >
            ← Main Wiki
          </Link>
        )}
      </div>
      {nodes.map((node) => renderNode(node))}
    </div>
  );
}

/** Render a mermaid diagram with loading + error states. */
/**
 * THE FIGURE POPOUT — a figure too wide for the column, seen whole.
 *
 * A native `<dialog>` opened with `showModal()` (the TrashModal/ProviderModal shape: Escape,
 * focus containment and the browser's top layer come free), the house PLAIN panel and never
 * DaisyUI's `modal-box` — 48px wide in this Tailwind v4 setup — at the widest width token.
 *
 * It opens at FULL WIDTH: the canvas caps the figure's width, never its height, so a figure that
 * needed a horizontal slider in the 736px column is simply there, at its own size, with only
 * vertical scrolling — measured on a 1174px figure in a 95vw panel: no sideways scroll, text at
 * 1:1. `Whole figure` caps the height too, for seeing an entire tall figure on one screen, at the
 * cost of the text (measured: 1174x1594 fits at 0.27 — which is the disease the popout cures).
 *
 * Rendered through a PORTAL: the figure lives inside react-markdown's fenced-code `<pre>`, and a
 * dialog is not prose.
 */
function FigurePopout({ svg, whole, onToggleSize, onClose }: {
  svg: string;
  whole: boolean;
  onToggleSize: () => void;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const el = dialogRef.current;
    if (el && !el.open) el.showModal();
  }, []);

  return createPortal(
    <dialog
      ref={dialogRef}
      className="modal"
      aria-label="Diagram, expanded"
      onClose={onClose}
      onClick={(e) => { if (e.target === dialogRef.current) onClose(); }}
    >
      <div className="bg-base-200 rounded-lg shadow-xl w-[var(--dialog-width-full)] max-h-[92vh] p-4 flex flex-col gap-2">
        <div className="flex justify-end gap-1">
          <Tooltip
            content={whole ? 'Full width, scrolling if it is tall' : 'Scale it so the whole figure fits on one screen'}
            position="bottom"
          >
            <button
              type="button"
              className="btn btn-ghost btn-xs"
              onClick={onToggleSize}
              aria-pressed={whole}
              aria-label="Change how the expanded diagram is scaled"
            >
              {whole ? 'Full width' : 'Whole figure'}
            </button>
          </Tooltip>
          <Tooltip content="Close" position="bottom">
            <button
              type="button"
              className="btn btn-ghost btn-xs"
              onClick={onClose}
              aria-label="Close the expanded diagram"
            >
              <X size={14} />
            </button>
          </Tooltip>
        </div>
        <div
          className={`figure-canvas ${whole ? 'whole' : ''} flex-1 min-h-0`}
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      </div>
    </dialog>,
    document.body,
  );
}

function MermaidDiagram({ content: contentStr }: { content: string }) {
  const [svg, setSvg] = useState<string>('');
  const [mermaidError, setMermaidError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [wholeFigure, setWholeFigure] = useState(false);
  // THE PALETTE FOLLOWS DARKNESS, NOT THE THEME'S NAME (2026-10-10). This used to
  // read `data-theme === 'dark'`, which is true for ONE of the app's twelve dark
  // themes (black, business, coffee, dark, dim, dracula, forest, halloween, luxury,
  // night, sunset, synthwave) — the other eleven got mermaid's LIGHT palette: pale
  // nodes with dark text on a dark page. The app already answers "is this theme
  // dark?" by the resolved `--color-base-100` lightness (useTheme).
  //
  // Watch the live theme — GlobalTheme applies it in an effect that may run after
  // this component's first render, so any value read at mount can be stale.
  const [isDark, setIsDark] = useState<boolean>(() => isDarkThemeByLuminance());

  useEffect(() => {
    const sync = () => setIsDark(isDarkThemeByLuminance());
    const observer = new MutationObserver(sync);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme', 'class'],
    });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    let cancelled = false;
    const renderMermaid = async () => {
      try {
        await mermaid.initialize({
          startOnLoad: false,
          theme: isDark ? 'dark' : 'default',
          ...NO_SHRINK,
          securityLevel: 'loose',
          fontFamily: 'inherit',
        });
        const { svg: renderedSvg } = await mermaid.render(
          `mermaid-${Math.random().toString(36).substring(2, 9)}`,
          contentStr
        );
        if (!cancelled) setSvg(renderedSvg);
      } catch (err) {
        if (!cancelled) {
          const errorMsg = err instanceof Error ? err.message : 'Failed to render diagram';
          setMermaidError(errorMsg);
          frontendLoggingService.error('WikiViewer', 'Mermaid render failed', err as Error);
        }
      }
    };
    renderMermaid();
    return () => { cancelled = true; };
  }, [contentStr, isDark]);

  if (mermaidError) {
    return (
      <div className="alert alert-warning my-4">
        <div>
          <h3 className="font-bold">Diagram rendering error</h3>
          <p className="text-sm">{mermaidError}</p>
        </div>
      </div>
    );
  }

  if (!svg) {
    return (
      <div className="flex items-center justify-center my-4">
        <div className="loading loading-spinner loading-md text-primary"></div>
      </div>
    );
  }

  // `mermaid-figure` is the figure's own box: a named class rather than
  // utilities, because the stylesheet gives it the figure GROUND (the style
  // sheet's own dark blue) and the no-shrink rule — see index.css.
  //
  // The expand control sits OUTSIDE the scrolling box (in the relative wrapper),
  // or a wide figure would carry it off-screen exactly when it is wanted. It is
  // always visible, never hover-revealed.
  return (
    <div className="relative">
      <div className="absolute right-1 top-1 z-10">
        <Tooltip content="Expand" position="left">
          <button
            type="button"
            className="btn btn-ghost btn-xs"
            onClick={() => setExpanded(true)}
            aria-label="Expand the figure"
          >
            <Maximize2 size={14} />
          </button>
        </Tooltip>
      </div>
      <div className="mermaid-figure">
        <div
          className="mermaid flex justify-center"
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      </div>
      {expanded && (
        <FigurePopout
          svg={svg}
          whole={wholeFigure}
          onToggleSize={() => setWholeFigure((v) => !v)}
          onClose={() => setExpanded(false)}
        />
      )}
    </div>
  );
}

export default function WikiViewer() {
  const location = useLocation();
  const navigate = useNavigate();
  const [tree, setTree] = useState<WikiNode[]>([]);
  const [page, setPage] = useState<WikiPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const currentPath = location.pathname.replace(/^\/wiki\/?/, '') || 'Site Index';

  // Atlas mode: when viewing a page under atlas/ (ui or api), root the
  // sidebar at the atlas subtree so the main wiki navigation stays clean.
  const isAtlasPath = currentPath === 'atlas' || currentPath.startsWith('atlas/');
  const atlasRoot = isAtlasPath
    ? tree.find((n) => n.type === 'directory' && n.path === 'atlas')
    : undefined;

  // Fetch wiki tree. THE REFETCH (2026-10-12): the tree is re-read on every
  // navigation, because the corpus changes under a mounted view — a page added,
  // moved or removed left the sidebar pointing at paths that no longer answer,
  // and clicking one read as 'Page not found' until the reader reloaded. The
  // swap is in the background (the current tree keeps rendering until the new
  // one arrives), and the sidebar's collapse state is local, so the folders a
  // reader has opened survive it.
  useEffect(() => {
    let cancelled = false;
    fetch('/api/v1/wiki')
      .then((r) => r.json())
      .then((data) => { if (!cancelled) setTree(data.tree || []); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [currentPath]);

  // Fetch current page
  const [htmlContent, setHtmlContent] = useState<string | null>(null);

  // THE TAB TITLE (2026-08-30): the viewed page's title (or the
  // section 'Wiki') in the house format — 'Page | Cogitate™'.
  usePageTitle(page?.title || 'Wiki');

  const fetchPage = useCallback(async (path: string) => {
    setLoading(true);
    setError(null);
    setPage(null);
    setHtmlContent(null);
    try {
      const resp = await fetch(`/api/v1/wiki/${path}`);
      if (!resp.ok) {
        if (resp.status === 404) {
          setError(`Page not found: ${path}`);
        } else {
          setError(`Error loading page`);
        }
      } else {
        const contentType = resp.headers.get('content-type') || '';
        if (contentType.includes('text/html')) {
          // HTML diagram — render in iframe
          const html = await resp.text();
          setHtmlContent(html);
        } else {
          const data = await resp.json();
          setPage(data);
        }
      }
    } catch {
      setError('Failed to load wiki page');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPage(currentPath);
  }, [currentPath, fetchPage]);

  // Handle browser back/forward navigation
  useEffect(() => {
    const handler = () => {
      const p = window.location.pathname.replace(/^\/wiki\/?/, '') || 'Site Index';
      fetchPage(p);
    };
    window.addEventListener('popstate', handler);
    return () => window.removeEventListener('popstate', handler);
  }, [fetchPage]);

  // Convert wikilinks to /wiki/... links. Supports both forms:
  //   [[path|label]] → [label](/wiki/path)
  //   [[path]]       → [Title Cased Path](/wiki/path)

  /** Custom code block: renders mermaid fences as diagrams, others as code. */
  const CodeBlock = useCallback(({ node: _node, inline: _inline, className, children, ...props }: { node?: unknown; inline?: boolean; className?: string; children?: React.ReactNode; [key: string]: unknown }) => {
    const match = /language-(\w+)/.exec(className || '');
    const isMermaid = match && match[1] === 'mermaid';
    const contentStr = String(children).replace(/\n$/, '');

    if (isMermaid) {
      return <MermaidDiagram content={contentStr} />;
    }

    return !_inline ? (
      // react-markdown already wraps fenced blocks in <pre> — render just
      // the code so we don't get nested pre boxes (prose <pre> provides
      // the background + padding).
      <code className={className} {...props}>
        {children}
      </code>
    ) : (
      <code className="bg-base-200 px-1.5 py-0.5 rounded text-sm" {...props}>
        {children}
      </code>
    );
  }, []);

  const processContent = (content: string): string => {
    return content.replace(
      /\[\[([\w.-]+(?:\/[\w.-]+)*)(?:\|([^\]]+))?\]\]/g,
      (_match, path: string, label?: string) => {
        const text = label?.trim() || path.replace(/-/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase());
        return `[${text}](/wiki/${path})`;
      }
    );
  };

  const confidenceBadge = (level: string) => {
    const colors: Record<string, string> = {
      high: 'badge-success badge-outline',
      medium: 'badge-warning badge-outline',
      low: 'badge-error badge-outline',
    };
    return (
      <span className={`badge badge-sm ${colors[level] || 'badge-ghost'}`}>
        {level}
      </span>
    );
  };

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <WikiSidebar tree={tree} root={atlasRoot} activePath={currentPath} />

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-2">
        <div className="max-w-3xl mx-auto">
          {/* Breadcrumb */}
          <div className="text-xs breadcrumbs mb-4 text-readout">
            <ul>
              <li><a href="/wiki" onClick={(e) => { e.preventDefault(); navigate('/wiki'); }}>Wiki</a></li>
              {currentPath.split('/').map((segment, i, arr) => {
                const pathUpTo = arr.slice(0, i + 1).join('/');
                const name = segment.replace(/-/g, ' ');
                return (
                  <li key={pathUpTo}>
                    {i < arr.length - 1 ? (
                      <a href={`/wiki/${pathUpTo}`} onClick={(e) => { e.preventDefault(); navigate(`/wiki/${pathUpTo}`); }}>{name}</a>
                    ) : (
                      <span className="capitalize">{name}</span>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>

          {/* Error state */}
          {error && (
            <div className="alert alert-error mb-4">
              <span>{error}</span>
            </div>
          )}

          {/* Loading state */}
          {loading && (
            <div className="flex items-center justify-center py-16">
              <div className="inline-block w-6 h-6 border-2 border-base-content/30 border-t-primary rounded-full animate-spin" />
            </div>
          )}

          {/* Page content */}
          {!loading && page && (
            <article className="prose prose-sm max-w-none dark:prose-invert">
              {/* Frontmatter badges */}
              <div className="flex items-center gap-2 mb-4 not-prose">
                {page.frontmatter?.confidence && confidenceBadge(page.frontmatter.confidence)}
                {page.frontmatter?.tags && (
                  <span className="text-xs text-readout">
                    {page.frontmatter.tags}
                  </span>
                )}
                {page.frontmatter?.updated && (
                  <span className="text-xs text-readout ml-auto">
                    Updated: {page.frontmatter.updated}
                  </span>
                )}
              </div>

              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeHighlight]}
                components={{
                  a: ({ href, children }: { href?: string; children?: React.ReactNode }) => {
                    if (href && href.startsWith('/wiki')) {
                      return <Link to={href} className="link link-primary">{children}</Link>;
                    }
                    return <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>;
                  },
                  code: CodeBlock as never,
                }}
              >
                {processContent(page.content)}
              </ReactMarkdown>

              {/* Children links */}
              {page.children.length > 0 && (
                <div className="mt-8 pt-4 border-t border-base-300 not-prose">
                  <h3 className="text-sm font-semibold mb-2">Pages in this section:</h3>
                  <div className="flex flex-wrap gap-2">
                    {page.children.map((child) => (
                      <a
                        key={child.path}
                        href={`/wiki/${child.path}`}
                        onClick={(e) => { e.preventDefault(); navigate(`/wiki/${child.path}`); }}
                        className="badge badge-outline badge-sm hover:badge-primary cursor-pointer"
                      >
                        {child.name}
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </article>
          )}
        </div>
        {/* END max-w-3xl — breadcrumb + markdown content above */}

        {/* HTML content (diagrams) — full width, outside max-w-3lx */}
        {!loading && htmlContent && (
          <iframe
            srcDoc={htmlContent}
            className="w-full h-[calc(100vh-120px)] border-0 rounded-lg"
            title="Diagram"
            sandbox="allow-scripts"
          />
        )}
      </div>
    </div>
  );
}
