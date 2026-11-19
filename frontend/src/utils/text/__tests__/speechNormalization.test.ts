import { describe, expect, it } from 'vitest'
import { normalizeForSpeech } from '../speechNormalization'

describe("normalizeForSpeech (the _29 — the user's minor-issues note: the emojis, the markdown, the path-names)", () => {
  it('strips the emojis', () => {
    expect(normalizeForSpeech('Hello! 👋 Ready to help 😀')).toBe('Hello! Ready to help')
  })

  it('strips an emoji together with its variation selector (U+FE0F)', () => {
    // ❤️ is U+2764 + U+FE0F — the selector is PART of the emoji. The rule has
    // to consume the pair as one unit, or the selector survives on its own.
    expect(normalizeForSpeech('Love ❤️ this ✨')).toBe('Love this')
  })

  it('strips a stray variation selector', () => {
    expect(normalizeForSpeech('plain\uFE0Ftext')).toBe('plain text')
  })

  it('strips the markdown formatting', () => {
    expect(normalizeForSpeech('**bold** and `code` and [a link](https://x.com)')).toBe('bold and code and a link')
    expect(normalizeForSpeech('## A header\nand ~~struck~~ text')).toBe('A header and struck text')
  })

  it('makes the path-names speakable', () => {
    expect(normalizeForSpeech('the file at /home/user/Projects/cogitate/')).toBe('the file at home slash user slash Projects slash cogitate')
    expect(normalizeForSpeech('the file at /home/user/my_file.txt')).toBe('the file at home slash user slash my file.txt')
  })

  it('collapses the whitespace', () => {
    expect(normalizeForSpeech('  a   b  \n  c ')).toBe('a b c')
  })
  it('reads the real multiplication as the word', () => {
    expect(normalizeForSpeech('5 × 4 = 20')).toBe('5 times 4 = 20')
  })

  it("turns the separator characters into the pauses (the user's 'times'-read note)", () => {
    expect(normalizeForSpeech('a — b • c · d × e | f')).toBe('a, b, c, d times e, f')
  })

  it('converts the markdown tables into the spoken sentences', () => {
    const table = '| Metric | Q2 | Q3 |\n|--------|----|----|\n| Revenue | 100K | 120K |'
    expect(normalizeForSpeech(table)).toBe('Metric: Q2, Q3. Revenue: 100K, 120K.')
  })

  it("keeps the thousands-commas whole (the user's '5,000'-read)", () => {
    expect(normalizeForSpeech('The users grew to 5,000 from 6,200.')).toBe('The users grew to 5,000 from 6,200.')
  })

})
