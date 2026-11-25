/**
 * The UUID that works everywhere.
 *
 * `crypto.randomUUID()` is a SECURE-CONTEXT-ONLY API: it exists on https:// and on
 * localhost, and is `undefined` on a plain-http origin such as the LAN address a
 * laptop uses to reach this app (`http://192.168.0.3:5173`). Calling it there throws
 * a TypeError inside the send path, React unmounts the tree, and the page goes blank
 * with nothing in the UI to say why.
 *
 * `crypto.getRandomValues()` carries no such restriction, so the fallback builds a
 * RFC 4122 v4 from it and the app behaves the same on every origin.
 */

export function uuidv4(): string {
  const c: Crypto | undefined = typeof globalThis !== 'undefined' ? globalThis.crypto : undefined

  if (c && typeof c.randomUUID === 'function') {
    return c.randomUUID()
  }

  const bytes = new Uint8Array(16)
  if (c && typeof c.getRandomValues === 'function') {
    c.getRandomValues(bytes)
  } else {
    // No WebCrypto at all (older embedded browsers): uniqueness still beats a throw.
    for (let i = 0; i < bytes.length; i += 1) bytes[i] = Math.floor(Math.random() * 256)
  }

  bytes[6] = (bytes[6] & 0x0f) | 0x40 // version 4
  bytes[8] = (bytes[8] & 0x3f) | 0x80 // variant 10

  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
  return [
    hex.slice(0, 8),
    hex.slice(8, 12),
    hex.slice(12, 16),
    hex.slice(16, 20),
    hex.slice(20, 32),
  ].join('-')
}
