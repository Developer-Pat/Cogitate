/**
 * HelpModal Component — Right-drawer overlay.
 *
 * Loads help content from the wiki API (wiki/help/ markdown files).
 * Converts from center-modal to right-drawer layout.
 * Context-sensitive: opens help for the page the user is on.
 *
 * Features:
 * - Right-drawer overlay (slides in from right)
 * - Markdown rendering with Mermaid support
 * - Help index grouped by category
 * - Back button with navigation history
 * - Related topics navigation
 */

import { useState, useEffect, useCallback } from 'react';
import { X, HelpCircle, ChevronRight, ChevronDown, Book } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import mermaid from 'mermaid';
import { frontendLoggingService } from '@/services/frontendLoggingService';

// Initialize Mermaid
mermaid.initialize({
  startOnLoad: false,
  theme: 'default',
  securityLevel: 'loose',
  fontFamily: 'inherit',
});

interface WikiHelpPage {
  slug: string;
  title: string;
  category: string;
  subtopic: string;
  order: number;
  content: string;
  summary: string;
  frontmatter: Record<string, unknown>;
}

export interface HelpModalProps {
  isOpen?: boolean;
  onClose?: () => void;
  initialContext?: string;
}

interface ModalEventData {
  context: string;
  documentTitle: string;
  timestamp: string;
}

/** Convert [[wikilinks]] to markdown links matching wiki viewer behavior */
function processWikilinks(text: string): string {
  return text.replace(/\[\[([\w.-]+(?:\/[\w.-]+)*)\]\]/g, (_match, name: string) => {
    const title = name
      .split('/')
      .pop()!
      .replace(/-/g, ' ')
      .replace(/\b\w/g, (c: string) => c.toUpperCase());
    return `[${title}](/wiki/${name})`;
  });
}

export function HelpModal({
  isOpen: _controlledIsOpen,
  onClose,
  initialContext,
}: HelpModalProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [context, setContext] = useState<string>(initialContext || 'help_page');
  const [content, setContent] = useState<string>('');
  const [title, setTitle] = useState<string>('Help');
  const [currentPage, setCurrentPage] = useState<WikiHelpPage | null>(null);
  const [allPages, setAllPages] = useState<WikiHelpPage[]>([]);
  const [relatedPages, setRelatedPages] = useState<WikiHelpPage[]>([]);
  const [groupedPages, setGroupedPages] = useState<Map<string, WikiHelpPage[]>>(new Map());
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showIndex, setShowIndex] = useState(false);
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());
  const [navigationHistory, setNavigationHistory] = useState<string[]>([]);

  /**
   * Custom code component for Mermaid diagrams.
   */
  const CodeComponent = useCallback(({ node: _node, inline: _inline, className, children, ...props }: { node?: unknown; inline?: boolean; className?: string; children?: React.ReactNode; [key: string]: unknown }) => {
    const match = /language-(\w+)/.exec(className || '');
    const isMermaid = match && match[1] === 'mermaid';
    const contentStr = String(children).replace(/\n$/, '');

    if (isMermaid) {
      return <MermaidDiagram content={contentStr} />;
    }

    return !_inline ? (
      <pre className="bg-base-200 rounded-lg p-4 overflow-x-auto">
        <code className={className} {...props}>
          {children}
        </code>
      </pre>
    ) : (
      <code className="bg-base-200 px-1.5 py-0.5 rounded text-sm" {...props}>
        {children}
      </code>
    );
  }, []);

  function MermaidDiagram({ content: contentStr }: { content: string }) {
    const [svg, setSvg] = useState<string>('');
    const [mermaidError, setMermaidError] = useState<string | null>(null);

    useEffect(() => {
      const renderMermaid = async () => {
        try {
          const { svg: renderedSvg } = await mermaid.render(
            `mermaid-${Math.random().toString(36).substring(2, 9)}`,
            contentStr
          );
          setSvg(renderedSvg);
        } catch (err) {
          const errorMsg = err instanceof Error ? err.message : 'Failed to render diagram';
          setMermaidError(errorMsg);
          frontendLoggingService.error('HelpModal', 'Mermaid render failed', err as Error);
        }
      };
      renderMermaid();
    }, [contentStr]);

    if (mermaidError) {
      return (
        <div className="alert alert-warning my-4">
          <svg xmlns="http://www.w3.org/2000/svg" className="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
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
          <div className="flex flex-col items-center gap-2">
            <div className="loading loading-spinner loading-md text-primary"></div>
            <p className="text-sm text-readout">Rendering diagram...</p>
          </div>
        </div>
      );
    }

    return (
      <div className="my-6 overflow-x-auto">
        <div
          className="mermaid flex justify-center"
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      </div>
    );
  }

  /**
   * Load all help pages from the wiki API for the index view.
   */
  const loadAllPages = useCallback(async () => {
    try {
      const response = await fetch('/api/v1/wiki');
      const indexData = await response.json();
      
      if (indexData.tree) {
        const helpDir = indexData.tree.find((n: { name: string; type: string }) => n.name === 'help' && n.type === 'directory');
        if (helpDir?.children) {
          const pagePromises = helpDir.children
            .filter((c: { type: string }) => c.type === 'file')
            .map(async (c: { path: string }) => {
              try {
                const res = await fetch(`/api/v1/wiki/${c.path}`);
                if (res.ok) {
                  const data = await res.json();
                  return {
                    slug: data.path.split('/').pop() || data.path,
                    title: data.title,
                    category: data.frontmatter?.category || 'other',
                    subtopic: data.frontmatter?.subtopic || 'General',
                    order: parseInt(data.frontmatter?.order || '99'),
                    content: data.content,
                    summary: data.frontmatter?.summary || '',
                    frontmatter: data.frontmatter,
                  } as WikiHelpPage;
                }
              } catch {
                // skip failed fetches
              }
              return null;
            });
          
          const pages = (await Promise.all(pagePromises)).filter((p): p is WikiHelpPage => p !== null);
          setAllPages(pages);

          const grouped = new Map<string, WikiHelpPage[]>();
          pages.forEach(page => {
            const cat = page.category;
            if (!grouped.has(cat)) {
              grouped.set(cat, []);
            }
            grouped.get(cat)!.push(page);
          });
          
          grouped.forEach((catPages, _key) => {
            catPages.sort((a, b) => a.order - b.order);
          });
          
          setGroupedPages(grouped);
        }
      }
    } catch (err) {
      frontendLoggingService.error('HelpModal', 'Failed to load help index', err as Error);
    }
  }, []);

  /**
   * Open a specific help page by slug.
   */
  const handleOpenPage = useCallback(async (slug: string, addToHistory: boolean = true) => {
    setShowIndex(false);
    setIsLoading(true);
    setError(null);

    try {
      if (addToHistory && currentPage) {
        setNavigationHistory(prev => [...prev, currentPage.slug]);
      }

      const response = await fetch(`/api/v1/wiki/help?context=${slug}`);
      if (!response.ok) {
        throw new Error(`Failed to load page: ${slug}`);
      }
      
      const data = await response.json();
      const page = data.pages?.[0];

      if (page) {
        setContent(page.content);
        setTitle(page.title);
        setCurrentPage(page);

        const related = allPages.filter(p => p.category === page.category && p.slug !== page.slug);
        setRelatedPages(related);
      } else {
        setError('Help page not found');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMessage);
      frontendLoggingService.error('HelpModal', 'Failed to load help page', err as Error);
    } finally {
      setIsLoading(false);
    }
  }, [currentPage, allPages]);

  /**
   * Load the first help page for a given context.
   */
  const loadContextPage = useCallback(async (contextSlug: string) => {
    try {
      const response = await fetch(`/api/v1/wiki/help?context=${contextSlug}`);
      if (response.ok) {
        const data = await response.json();
        if (data.pages && data.pages.length > 0) {
          const firstPage = data.pages[0];
          setContent(firstPage.content);
          setTitle(firstPage.title);
          setCurrentPage(firstPage);

          const related = allPages.filter(p => p.category === firstPage.category && p.slug !== firstPage.slug);
          setRelatedPages(related);
          return;
        }
      }
      setShowIndex(true);
      setExpandedCategories(prev => {
        const next = new Set(prev);
        next.add(contextSlug);
        return next;
      });
    } catch (err) {
      frontendLoggingService.error('HelpModal', 'Failed to load context page', err as Error);
      setShowIndex(true);
    }
  }, [allPages]);

  /**
   * Handle open-help-modal events.
   */
  useEffect(() => {
    const handleOpenModal = (event: CustomEvent<ModalEventData>) => {
      const incomingContext = event.detail.context;

      setContext(incomingContext);
      setIsOpen(true);

      if (incomingContext && incomingContext !== 'help_page') {
        loadContextPage(incomingContext);
        loadAllPages();
      } else {
        setShowIndex(true);
        loadAllPages();
      }
    };

    window.addEventListener('open-help-modal' as string, handleOpenModal as EventListener);
    return () => {
      window.removeEventListener('open-help-modal' as string, handleOpenModal as EventListener);
    };
  }, [loadAllPages, loadContextPage]);

  /**
   * Go back to previous page.
   */
  const handleGoBack = useCallback(async () => {
    if (navigationHistory.length === 0) return;

    const previousSlug = navigationHistory[navigationHistory.length - 1];
    setNavigationHistory(prev => prev.slice(0, -1));

    try {
      const response = await fetch(`/api/v1/wiki/help?context=${previousSlug}`);
      if (response.ok) {
        const data = await response.json();
        const page = data.pages?.[0];
        if (page) {
          setContent(page.content);
          setTitle(page.title);
          setCurrentPage(page);
          const related = allPages.filter(p => p.category === page.category && p.slug !== page.slug);
          setRelatedPages(related);
        }
      }
    } catch (err) {
      frontendLoggingService.error('HelpModal', 'Failed to go back', err as Error);
    }
  }, [navigationHistory, allPages]);

  const toggleCategory = useCallback((category: string) => {
    setExpandedCategories(prev => {
      const next = new Set(prev);
      if (next.has(category)) {
        next.delete(category);
      } else {
        next.add(category);
      }
      return next;
    });
  }, []);

  const handleOpenIndex = useCallback(() => {
    setShowIndex(true);
  }, []);

  // Stable identity, and DECLARED FIRST: the Escape-key effect below lists it as
  // a dependency (the rule is right — the listener closes over it), and a dep
  // array is evaluated during render, so a later declaration would be a TDZ
  // error. Plain setters + the onClose prop are all it touches.
  const handleClose = useCallback(() => {
    setIsOpen(false);
    setShowIndex(false);
    setNavigationHistory([]);
    setContent('');
    setCurrentPage(null);
    onClose?.();
  }, [onClose]);

  /**
   * Handle Escape key press.
   */
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && isOpen) {
        handleClose();
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, handleClose]);

  /**
   * Handle Backspace/Alt+Left for back navigation.
   */
  useEffect(() => {
    const handleBackNavigation = (event: KeyboardEvent) => {
      const isBackspace = event.key === 'Backspace';
      const isAltLeft = event.altKey && event.key === 'ArrowLeft';
      if ((isBackspace || isAltLeft) && isOpen && navigationHistory.length > 0 && !showIndex) {
        event.preventDefault();
        handleGoBack();
      }
    };
    document.addEventListener('keydown', handleBackNavigation);
    return () => document.removeEventListener('keydown', handleBackNavigation);
  }, [isOpen, navigationHistory, showIndex, handleGoBack]);

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={handleClose}
        aria-hidden="true"
      />

      {/* Drawer */}
      <div
        className="relative bg-base-100 shadow-xl w-[560px] max-w-[90vw] h-full overflow-hidden flex flex-col"
        role="dialog"
        aria-modal="true"
        aria-labelledby="help-modal-title"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-base-300 flex-shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            {showIndex ? (
              <>
                <Book size={24} className="text-primary flex-shrink-0" />
                <h2 id="help-modal-title" className="text-xl font-semibold text-base-content truncate">
                  Help Index
                </h2>
              </>
            ) : (
              <>
                {navigationHistory.length > 0 && (
                  <span className="tooltip tooltip-top" data-tip="Go back to previous document">
                <button
                    onClick={handleGoBack}
                    className="btn btn-ghost btn-sm rounded-lg p-1 flex-shrink-0"
                    aria-label="Go back"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="m15 18-6-6 6-6"/>
                    </svg>
                  </button>
                  </span>
                )}
                <HelpCircle size={24} className="text-primary flex-shrink-0" />
                <h2 id="help-modal-title" className="text-xl font-semibold text-base-content truncate">
                  {title}
                </h2>
              </>
            )}
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            {!showIndex && (
              <span className="tooltip tooltip-top" data-tip="View all help topics">
              <button onClick={handleOpenIndex} className="btn btn-outline btn-sm rounded-lg gap-2" aria-label="View all help topics">
                <Book size={16} />
                <span className="hidden sm:inline">All Topics</span>
              </button>
              </span>
            )}
            <button onClick={handleClose} className="btn btn-ghost btn-sm rounded-lg" aria-label="Close help">
              <X size={20} />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="flex flex-col items-center gap-4">
                <div className="loading loading-spinner loading-lg text-primary"></div>
                <p className="text-readout">Loading help content...</p>
              </div>
            </div>
          ) : error ? (
            <div className="alert alert-error">
              <svg xmlns="http://www.w3.org/2000/svg" className="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div>
                <h3 className="font-bold">Error loading help</h3>
                <p className="text-sm">{error}</p>
              </div>
            </div>
          ) : showIndex ? (
            /* Help Index View */
            <div className="space-y-6">
              {Array.from(groupedPages.entries())
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([category, pages]) => {
                  const isExpanded = expandedCategories.has(category);
                  const isActiveContext = context && context !== 'help_page' && category === context;
                  return (
                    <div key={category} className={`card shadow-sm ${isActiveContext ? 'bg-primary/5 border border-primary/30' : 'bg-base-200'}`}>
                      <div className="card-body p-5">
                        <button onClick={() => toggleCategory(category)} className="flex items-center justify-between w-full mb-4 text-left" aria-expanded={isExpanded}>
                          <h3 className="card-title text-xl capitalize text-primary flex items-center gap-2">
                            {isExpanded ? <ChevronDown size={24} /> : <ChevronRight size={24} />}
                            {category}
                            {isActiveContext && <span className="badge badge-accent badge-outline badge-sm ml-2">Current Page</span>}
                          </h3>
                          <span className="badge badge-primary badge-outline badge-sm">
                            {pages.length} {pages.length === 1 ? 'doc' : 'docs'}
                          </span>
                        </button>

                        {isExpanded && (
                          <div className="space-y-1 ml-8">
                            {pages.map(page => (
                              <button
                                key={page.slug}
                                onClick={() => handleOpenPage(page.slug)}
                                className={`w-full text-left p-3 rounded-lg transition-colors ${currentPage?.slug === page.slug ? 'bg-primary text-primary-content' : 'hover:bg-base-300'}`}
                              >
                                <div className="flex items-center justify-between">
                                  <span className="font-medium">{page.title}</span>
                                  <ChevronRight size={16} />
                                </div>
                                {page.summary && (
                                  <p className="text-sm opacity-70 mt-1 line-clamp-1">{page.summary}</p>
                                )}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              {groupedPages.size === 0 && !isLoading && (
                <div className="text-center py-12 text-readout">
                  <Book size={48} className="mx-auto mb-4 opacity-30" />
                  <p>No help topics available.</p>
                </div>
              )}
            </div>
          ) : (
            /* Document Content View */
            <div className="space-y-6">
              {currentPage && (
                <div>
                  <nav className="flex items-center gap-2 text-sm text-readout mb-4 flex-wrap" aria-label="Breadcrumb">
                    <button onClick={handleOpenIndex} className="hover:text-primary transition-colors flex items-center gap-1 flex-shrink-0">
                      <Book size={14} />
                      Help
                    </button>
                    <ChevronRight size={14} className="opacity-50 flex-shrink-0" />
                    <span className="capitalize hover:text-primary transition-colors">{currentPage.category}</span>
                    {currentPage.subtopic && (
                      <>
                        <ChevronRight size={14} className="opacity-50 flex-shrink-0" />
                        <span className="capitalize">{currentPage.subtopic}</span>
                      </>
                    )}
                    <ChevronRight size={14} className="opacity-50 flex-shrink-0" />
                    <span className="font-medium text-base-content truncate max-w-[200px]">{title}</span>
                  </nav>
                </div>
              )}

              <div className="help-content prose prose-sm dark:prose-invert prose-a:text-primary prose-a:no-underline hover:prose-a:underline prose-a:font-medium">
                {/* eslint-disable @typescript-eslint/no-explicit-any -- legacy-any: the type-debt backlog (the tsc -b sweep 2026-08-26) */}
                {/* remark-gfm: the help pages' TABLES. This drawer was the one markdown surface in the app
                    without it (MarkdownText, MessageBubble, ReportViewer and WorkflowProducts all pass it),
                    so every table in wiki/help rendered as a row of literal pipes. On this page that was
                    two tables the reader needs — the eight capabilities and the rungs that can answer. */}
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ code: CodeComponent } as any}>
                  {processWikilinks(content)}
                {/* eslint-enable @typescript-eslint/no-explicit-any */}
                </ReactMarkdown>
              </div>

              {relatedPages.length > 0 && <div className="divider"></div>}

              {relatedPages.length > 0 && (
                <div className="card bg-primary/10 border border-primary/20">
                  <div className="card-body p-5">
                    <h3 className="card-title text-base font-semibold text-primary mb-3 flex items-center gap-2">
                      <Book size={18} />
                      Related Topics
                    </h3>
                    <div className="space-y-2">
                      {relatedPages.map(page => (
                        <button
                          key={page.slug}
                          onClick={() => handleOpenPage(page.slug)}
                          className="w-full text-left p-3 rounded-lg hover:bg-primary hover:text-primary-content transition-all flex items-center gap-3 group"
                        >
                          <ChevronRight size={18} className="group-hover:translate-x-1 transition-transform" />
                          <span className="font-medium">{page.title}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {groupedPages.size > 0 && (
                <div className="text-center pt-6 pb-2">
                  <button onClick={handleOpenIndex} className="btn btn-outline btn-primary gap-2">
                    <Book size={18} />
                    View All Help Topics
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-base-300 flex justify-end flex-shrink-0">
          <button onClick={handleClose} className="btn btn-primary rounded-lg">
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

export default HelpModal;
