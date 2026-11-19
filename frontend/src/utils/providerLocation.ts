/**
 * The provider class seam (2026-09-08, the A1 split) — mirrors the
 * backend's provider_classes.py. The API carries `location` when the
 * new backend is live; this fallback keeps the UI class-aware even
 * against a stale backend (and drives the local dev).
 */
const CLOUD_TYPES = new Set(['openai', 'anthropic', 'openrouter', 'deepseek', 'groq', 'ollama_cloud'])

export type ProviderLocation = 'cloud' | 'local'

function isLoopback(baseUrl?: string | null): boolean {
  if (!baseUrl) return false
  const host = baseUrl.split('://').slice(-1)[0].split('/')[0].split(':')[0].toLowerCase()
  return host === 'localhost' || host === '127.0.0.1' || host === '0.0.0.0' || host === '::1'
}

export function providerLocationOf(provider: {
  location?: 'cloud' | 'local'
  provider_type: string
  base_url?: string | null
}): ProviderLocation {
  if (provider.location === 'cloud' || provider.location === 'local') return provider.location
  // Type-first, then the loopback tiebreaker: llama.cpp registers as
  // an 'openai' type pointed at 127.0.0.1 — that is LOCAL.
  if (!CLOUD_TYPES.has(provider.provider_type)) return 'local'
  return isLoopback(provider.base_url) ? 'local' : 'cloud'
}
