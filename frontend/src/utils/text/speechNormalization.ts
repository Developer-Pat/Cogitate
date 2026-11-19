// THE SPEECH NORMALIZATION (2026-08-31, the _29 + the user's
// utility-organization ask): the markdown -> speech transform — the
// TEXT-domain's pure utilities (the ttsService imports + applies
// them at the speak chokepoint; the Exa-speaking skill imports
// them directly).
//
// The rules (the user's listen-tests):
// - the markdown: the fenced/inline code, the images, the links
//   (-> the label), the headers, the bold/italics/strikethrough
// - the EMOJIS
// - the path-names: the slashes -> 'slash', the underscores -> the
//   spaces (the speakable paths)
// - the separator characters (the bullets/middots, the pipes, the
//   en/em-dashes) -> the commas (the pauses) — the real
//   multiplication sign stays 'times'
// - the markdown TABLES -> the spoken sentences ('Metric: Q2, Q3,
//   Change. Revenue: 100K, 120K, +20%.')
// - the thousands-commas stay whole

// The variation selector (U+FE0F) rides OUTSIDE the class, as an optional
// suffix on the emoji it modifies, with its own alternative for a stray one.
// As a class MEMBER it was a combining character — the class then matched the
// selector on its own rather than 'emoji + selector' as one unit, which is
// what eslint's no-misleading-character-class flags.
const EMOJI_RE = /(?:[\p{Extended_Pictographic}\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}]\u{FE0F}?|\u{FE0F})/gu;
const PATH_RE = /(?:\/|^)([A-Za-z0-9_\-.]+\/)+[A-Za-z0-9_\-./]+/g;
const TABLE_ROW_RE = /^\|.*\|$/gm;

// THE MARKDOWN TABLES -> the spoken sentences: the header row
// becomes 'Metric: Q2, Q3, Change.' + each data row 'Revenue:
// 100K, 120K, +20%.' — the separator rows (the dashes) drop.
function tablesToSpeech(row: string): string {
  const cells = row
    .slice(1, -1)
    .split('|')
    .map((c) => c.trim())
    .filter((c) => c.length > 0)
  if (cells.length === 0) return ' '
  if (cells.every((c) => /^:?-+:?$/.test(c))) return ' '
  return cells[0] + ': ' + cells.slice(1).join(', ') + '. '
}

export function normalizeForSpeech(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/(\*\*|__)(.+?)\1/g, '$2')
    .replace(/(\*|_)([^*_]+)\1/g, '$2')
    .replace(/~~(.+?)~~/g, '$1')
    .replace(PATH_RE, (m) => m.replace(/^\/+|\/+$/g, '').replace(/\//g, ' slash ').replace(/_/g, ' '))
    .replace(TABLE_ROW_RE, tablesToSpeech)
    .replace(/[•·]/g, ', ')
    .replace(/\|/g, ', ')
    .replace(/[—–]/g, ', ')
    .replace(/×/g, ' times ')
    .replace(EMOJI_RE, ' ')
    .replace(/(?<!\d)\s*,\s*(?!\d)/g, ', ')
    .replace(/\s+/g, ' ')
    .trim();
}
