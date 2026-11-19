import { describe, it, expect } from 'vitest'
import {
  EXA_SESSION_PLACEHOLDER,
  SESSION_PLACEHOLDERS,
  isPlaceholderTitle,
} from '../sessionTitles'

describe('the session placeholder class', () => {
  it('counts an absent title as unnamed, not as a title', () => {
    expect(isPlaceholderTitle(undefined)).toBe(true)
    expect(isPlaceholderTitle(null)).toBe(true)
    expect(isPlaceholderTitle('')).toBe(true)
    expect(isPlaceholderTitle('   ')).toBe(true)
  })

  it('counts every shape a creation path writes', () => {
    expect(isPlaceholderTitle('Untitled')).toBe(true) // the temp-commit fallback
    expect(isPlaceholderTitle('New Session')).toBe(true) // the chat path's own row
    expect(isPlaceholderTitle('New Session 17:04')).toBe(true) // ...and its timestamped shape
    // THE BUG THIS CLASS EXISTS FOR: the title service's guard read the Exa
    // panel's placeholder as a real title, so it skipped the job and an Exa
    // session could never be named.
    expect(isPlaceholderTitle(EXA_SESSION_PLACEHOLDER)).toBe(true)
  })

  it('keeps the Exa placeholder inside the class, not beside it', () => {
    expect(SESSION_PLACEHOLDERS).toContain(EXA_SESSION_PLACEHOLDER)
  })

  it('does not mistake a real title for a placeholder', () => {
    expect(isPlaceholderTitle('How Bicycles Stay Upright')).toBe(false)
    expect(isPlaceholderTitle('Local 10-Day Weather Forecast')).toBe(false)
  })

  it('accepts the known cost of the prefix rule', () => {
    // Deliberate, and the backend's gate makes the same call: a real title that
    // opens with the placeholder words counts as unnamed. The prefix rule is
    // what catches "New Session <timestamp>", and losing such a title costs one
    // extra LLM call — cheaper than the alternative, which stranded sessions
    // untitled forever.
    expect(isPlaceholderTitle('New Session Cost Accounting')).toBe(true)
  })
})
