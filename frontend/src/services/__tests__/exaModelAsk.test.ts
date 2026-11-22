/**
 * THE ACTIVATION'S MODEL READING (2026-11-22, measured on the release run).
 *
 * Activating on a box with no chat model is a legitimate answer — but "activated" is not "able to
 * answer". On the v0.1.1 release run the Exa chat page pressed Activate, told the user to say
 * something, and the first turn came back as an opaque `RequestError: Internal error`: that page
 * read `needs_model` nowhere. The integrations page did read it, which is exactly how two doors
 * drift. `modelAskFrom` is the one reading both call.
 */

import { describe, expect, it } from 'vitest';

import { modelAskFrom, type ExaActivation } from '../externalAgentService';

const activation = (over: Partial<ExaActivation> = {}): ExaActivation => ({
  enabled: true,
  runnable: true,
  blocked_reason: null,
  model: null,
  provider: null,
  needs_model: true,
  offer: { provider: 'deepseek', model: 'deepseek/deepseek-flash', base_url: 'https://api.deepseek.com' },
  ...over,
});

describe('modelAskFrom', () => {
  it('asks, with the offer, when the home has no model', () => {
    const { needsModel, offer } = modelAskFrom(activation());
    expect(needsModel).toBe(true);
    expect(offer?.model).toBe('deepseek/deepseek-flash');
  });

  it('asks with nothing to offer when the install itself has no chat model', () => {
    const { needsModel, offer } = modelAskFrom(activation({ offer: null }));
    expect(needsModel).toBe(true);
    expect(offer).toBeNull();
  });

  it('does not ask when the home already carries a model — and offers nothing to overwrite', () => {
    const { needsModel, offer } = modelAskFrom(
      activation({ needs_model: false, model: 'deepseek/x', provider: 'deepseek' })
    );
    expect(needsModel).toBe(false);
    expect(offer).toBeNull();
  });

  it('an answer that turned Exa OFF never asks', () => {
    const { needsModel } = modelAskFrom(activation({ enabled: false }));
    expect(needsModel).toBe(false);
  });
});
