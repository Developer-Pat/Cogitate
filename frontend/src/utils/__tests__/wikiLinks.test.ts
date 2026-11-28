import { describe, it, expect } from 'vitest';
import { wikiHref, wikiLabel, wikilinksToMarkdown } from '../wikiLinks';

describe('wikiHref', () => {
  it('percent-encodes spaces so the markdown destination does not end early', () => {
    expect(wikiHref('atlas/ui/UI Atlas')).toBe('/wiki/atlas/ui/UI%20Atlas');
  });

  it('escapes parentheses, which would otherwise close a markdown destination', () => {
    expect(wikiHref('notes/a (b)')).toBe('/wiki/notes/a%20%28b%29');
  });

  it('appends a heading as the fragment', () => {
    expect(wikiHref('help/chat', '#Sending')).toBe('/wiki/help/chat#Sending');
  });

  it('drops leading and trailing slashes (a directory link resolves to its index)', () => {
    expect(wikiHref('/atlas/ui/')).toBe('/wiki/atlas/ui');
  });
});

describe('wikiLabel', () => {
  it('title-cases a hyphenated slug', () => {
    expect(wikiLabel('concepts/cognitive-profiles')).toBe('Cognitive Profiles');
  });

  it('leaves a spaced, already-capitalised filename verbatim', () => {
    expect(wikiLabel('dev-notes/architecture/Paths and Path Resolution')).toBe(
      'Paths and Path Resolution',
    );
  });
});

describe('wikilinksToMarkdown', () => {
  it('converts alias, bare and heading forms', () => {
    const out = wikilinksToMarkdown('a [[help/tools|Tool Management]] b [[chat]] c [[help/chat#Sending]]');
    expect(out).toBe(
      'a [Tool Management](/wiki/help/tools) b [Chat](/wiki/chat) c [Chat](/wiki/help/chat#Sending)',
    );
  });

  it('leaves text without wikilinks untouched', () => {
    expect(wikilinksToMarkdown('see [docs](https://example.com)')).toBe(
      'see [docs](https://example.com)',
    );
  });
});
