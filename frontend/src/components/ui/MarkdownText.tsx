/**
 * MarkdownText — markdown for the SMALL surfaces.
 *
 * Exa writes markdown, and the flyout is one of the places it lands. Rendered
 * as a plain <p> that markdown is unreadable in the literal sense: a link is
 * just characters, a list is dashes, a table is pipes. This renders it.
 *
 * WHY NOT ResponseStream: that is the chat's renderer and carries TTS, the
 * cognitive indicator, mermaid, the fold and the macro keyboard. The job here
 * is only "show what Exa wrote, and make the links work" inside a 440px panel.
 * Reusing the chat component would drag chat behaviour onto a flyout.
 *
 * STREAMING — why this splits into blocks. Text that GROWS re-parses on every
 * update, and re-parsing a whole document per token is the expensive shape
 * (the same defect the agent chat was fixed for). So the text is cut at block
 * boundaries and each block is memoized: while a reply streams, only the block
 * still being written re-parses and the finished ones are skipped entirely.
 * The splitter is CONSERVATIVE by design — a false split renders wrong, while
 * a missed split only costs time — so it refuses to split anything it is not
 * sure about and returns the whole text as one block. The rules and the test
 * corpus live in `utils/text/streamingMarkdown.ts`.
 *
 * LINKS — both halves matter:
 *   - an internal path rides the router, so the app navigates IN PLACE. That
 *     is what a clicked link should do.
 *   - anything else opens a new tab with `noopener noreferrer`.
 * A model-written link must never navigate the SPA out from under the page the
 * user was on, and must never reach window.opener.
 *
 * NO rehype-highlight on purpose: syntax colouring is a chat-surface luxury
 * and this is a compact panel. Code still renders as <pre><code>, legibly.
 * Raw HTML is NOT enabled — react-markdown escapes it, so a model cannot
 * inject markup through an answer.
 */

import { memo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Link } from 'react-router-dom';
import { splitStreamingMarkdown } from '@/utils/text/streamingMarkdown';

interface MarkdownTextProps {
  children: string;
  className?: string;
}

/** The clickable-link style the rest of the app uses. */
const LINK_CLASS = 'link link-primary';

/**
 * One markdown block. Memoized on `text`: an unchanged block re-renders to
 * nothing, which is what makes a growing reply cheap.
 */
const MarkdownBlock = memo(({ text }: { text: string }) => (
  <ReactMarkdown
    remarkPlugins={[remarkGfm]}
    components={{
      a: ({ href, children: kids }: { href?: string; children?: React.ReactNode }) => {
        const h = typeof href === 'string' ? href : '';
        if (h.startsWith('/')) {
          return (
            <Link to={h} className={LINK_CLASS}>
              {kids}
            </Link>
          );
        }
        return (
          <a href={h} target="_blank" rel="noopener noreferrer" className={LINK_CLASS}>
            {kids}
          </a>
        );
      },
    }}
  >
    {text}
  </ReactMarkdown>
));

MarkdownBlock.displayName = 'MarkdownBlock';

export function MarkdownText({ children, className }: MarkdownTextProps) {
  const blocks = splitStreamingMarkdown(children);
  return (
    <div className={className}>
      {blocks.length === 1 ? (
        <MarkdownBlock text={children} />
      ) : (
        blocks.map((b: string, i: number) => <MarkdownBlock key={i} text={b} />)
      )}
    </div>
  );
}

export default MarkdownText;
