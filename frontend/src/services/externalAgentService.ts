/**
 * External agent (Hermes/OpenClaw) integration service.
 *
 * Talks to the Exa Agent backend (/api/v1/external-agent):
 * config (command/cwd), live status, restart.
 */

import { apiClient } from './apiClient';

/** One TESTED BRAIN — a model + provider + endpoint the quick-switch can activate. */
export interface ExaBrain {
  label: string;
  model: string;
  provider: string;
  base_url: string;
  /** Takes images — the vision picker lists only these entries. */
  vision: boolean;
}

export interface ExternalAgentConfig {
  /**
   * THE ACTIVATION (2026-11-18): Exa is INCLUDED and ships switched OFF — no
   * runtime, no key, nothing spawned. Turning it on is the user's decision,
   * made on the Exa page, and it is the only thing that lets a prompt reach it.
   */
  enabled?: boolean;
  command: string;
  cwd: string;
  /**
   * THE TESTED BRAINS (2026-10-10): the quick-switch list, CONFIG not bundle code.
   * Shipped as the config's own default server-side and replaceable through
   * `PUT /config`, so changing which brains the page offers needs no rebuild.
   */
  brains?: ExaBrain[];
  permission_tier?: string; // 'chat' | 'fix' | 'yolo' (2026-08-21)
  fix_mode?: boolean; // DEPRECATED compat view (the old bool)
  max_turn_seconds?: number; // 0 = unlimited (2026-08-14)
  image?: string; // the face — a /static asset path (2026-08-21)
}

export interface ExternalAgentStatus {
  connected: boolean;
  /** The user's decision — false on a fresh install. */
  enabled: boolean;
  /** Whether THIS machine can honour the decision (is the command on PATH?). */
  runnable: boolean;
  /** Why not, when `runnable` is false — shown verbatim, never guessed. */
  blocked_reason?: string | null;
  session_id?: string | null;
  command: string;
  cwd: string;
  permission_tier?: string; // 'chat' | 'fix' | 'yolo' (2026-08-21)
  fix_mode?: boolean; // DEPRECATED compat view
  max_turn_seconds?: number;
  model?: string | null;
  provider?: string | null;
  error?: string | null;
}

export async function getExternalAgentConfig(): Promise<ExternalAgentConfig> {
  const { data } = await apiClient.get<ExternalAgentConfig>('/api/v1/external-agent/config');
  return data!;
}

export async function updateExternalAgentConfig(
  patch: Partial<ExternalAgentConfig>
): Promise<ExternalAgentConfig> {
  const { data } = await apiClient.put<ExternalAgentConfig>('/api/v1/external-agent/config', patch);
  return data!;
}

export async function getExternalAgentStatus(): Promise<ExternalAgentStatus> {
  const { data } = await apiClient.get<ExternalAgentStatus>('/api/v1/external-agent/status');
  return data!;
}

export async function restartExternalAgent(): Promise<{ status: string }> {
  const { data } = await apiClient.post<{ status: string }>('/api/v1/external-agent/restart');
  return data!;
}

/** The activation decision's shape — what the box can actually do about it. */
export interface ExaActivation {
  enabled: boolean;
  runnable: boolean;
  blocked_reason?: string | null;
  /** What the activation SEEDED, line by line (only the activate answer carries it). */
  provisioned?: string[];
  /** Exa's model after activation — null until someone chooses one. */
  model?: string | null;
  provider?: string | null;
  /** True when Exa has no model of its own: it cannot answer until one is chosen. */
  needs_model?: boolean;
  /** This install's chat model, offered as the one press that fills that gap. */
  offer?: { provider: string; model: string; base_url?: string | null } | null;
}

/** How many files activation seeded into Exa's home (0 = it was already provisioned). */
export function seededFileCount(log?: string[]): number {
  const line = log?.find((l) => l.startsWith('skills seeded'));
  const m = line?.match(/\((\d+) file\(s\) added\)/);
  return m ? Number(m[1]) : 0;
}

/** THE ACTIVATION (2026-11-18): the user's decision, in one call. */
export async function activateExa(): Promise<ExaActivation> {
  const { data } = await apiClient.post<ExaActivation>('/api/v1/external-agent/activate');
  return data!;
}

/** Switch Exa off; any live session is ended by the backend. */
export async function deactivateExa(): Promise<ExaActivation> {
  const { data } = await apiClient.post<ExaActivation>('/api/v1/external-agent/deactivate');
  return data!;
}

/** THE EXA MODEL CARD (2026-08-22): the model/provider live in Exa's
 * private config file — the API is the view/editor. GET reads the
 * current brain; PUT writes it + closes the client so the next spawn
 * uses the new one. */
export async function getExaModel(): Promise<{
  model?: string
  provider?: string
  base_url?: string
  reasoning_effort?: string
  vision_model?: string
  /** THIS INSTALL'S chat answer, offered — the field names what accepting it would write. */
  offer?: { provider: string; model: string; base_url?: string | null } | null
}> {
  const { data } = await apiClient.get('/api/v1/external-agent/model');
  return data!;
}

export async function updateExaModel(patch: { model: string; provider: string; base_url?: string; reasoning_effort?: string; vision_model?: string }): Promise<{ status: string; model: string; provider: string; reasoning_effort?: string | null }> {
  const result = await apiClient.put<{ status: string; model: string; provider: string; reasoning_effort?: string | null }>('/api/v1/external-agent/model', patch);
  // THE REFUSAL (2026-10-12): the route rejects a provider nothing can dial, and the
  // client returns {error} rather than throwing. Surfacing it here is what makes the
  // refusal visible — the card used to toast SUCCESS over a save that wrote nothing.
  if (result.error) {
    throw new Error(result.error.message || 'The Exa model save was refused')
  }
  return result.data!
}

/** The YOLO button (Phase D, study 14): immediate, deliberate,
 * session-scoped fix-mode grant. Returns the new state for the badge. */
export async function setExternalAgentFixMode(on: boolean): Promise<{ fix_mode: boolean; granted: boolean }> {
  const { data } = await apiClient.post<{ fix_mode: boolean; granted: boolean }>('/api/v1/external-agent/fix-mode', { on });
  return data!;
}
