/**
 * The ONE wikilink converter.
 *
 * Two surfaces render wiki pages — the viewer (`pages/WikiViewer.tsx`) and the
 * help modal (`components/help/HelpModal.tsx`) — and each used to carry its own
 * copy of this regex. They drifted: the viewer accepted `[[path|label]]` but
 * refused any target with a space, the modal did the opposite. 66 pages in this
 * corpus have a space in the filename ("UI Atlas.md", "Paths and Path
 * Resolution.md"), so ~35 links rendered as literal `[[...]]` text.
 *
 * The rules, once, for both:
 *   [[path]]            → link labelled with the last path segment
 *   [[path|label]]      → link labelled `label`
 *   [[path#heading]]    → link to the page, fragment appended
 *
 * The destination is PERCENT-ENCODED: a markdown link destination ends at the
 * first whitespace, so a raw space would truncate the URL mid-path and leave
 * "Atlas)" as body text.
 */

const WIKILINK_RE = /\[\[([^\]|#]+)(#[^\]|]*)?(?:\|([^\]]+))?\]\]/g

/** Encode one path segment. `encodeURIComponent` leaves `!'()*` alone, and `(`
 *  would end a markdown destination early, so those are escaped by hand. */
function encodeSegment(segment: string): string {
  return encodeURIComponent(segment).replace(
    /[!'()*]/g,
    (c) => `%${c.charCodeAt(0).toString(16).toUpperCase()}`,
  );
}

/** `/wiki/<encoded path>` plus an optional `#fragment`. */
export function wikiHref(target: string, heading?: string): string {
  const path = target.trim().replace(/^\/+/, '').replace(/\/+$/, '');
  const base = '/wiki/' + path.split('/').filter(Boolean).map(encodeSegment).join('/');
  if (!heading) return base;
  const fragment = heading.replace(/^#/, '');
  return `${base}#${encodeURIComponent(fragment)}`;
}

/** The label for a link with no alias: the page's own name, as Obsidian shows it.
 *  A slug (`cognitive-profiles`) is title-cased for display; a filename that
 *  already carries spaces and capitals ("Paths and Path Resolution") is used
 *  verbatim — capitalising its words would turn "and" into "And". */
export function wikiLabel(target: string): string {
  const segments = target.trim().split('/').filter(Boolean);
  const last = segments.length ? segments[segments.length - 1] : target.trim();
  if (/\s/.test(last)) return last;
  return last.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Convert every `[[...]]` in the text to a markdown link. */
export function wikilinksToMarkdown(text: string): string {
  return text.replace(
    WIKILINK_RE,
    (_match, target: string, heading: string | undefined, label: string | undefined) => {
      const title = label?.trim() || wikiLabel(target);
      return `[${title}](${wikiHref(target, heading)})`;
    },
  );
}
