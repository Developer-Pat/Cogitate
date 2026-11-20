/**
 * Exa Agent — configuration for Exa, the external consulting agent
 * (Hermes/OpenClaw) connection backing the Agent Panel.
 *
 * Config: backend command + working directory. Status: live
 * connection + session id. Restart: close the subprocess so the
 * next panel open spawns fresh with the saved config.
 */

import { useCallback, useEffect, useState } from 'react';
import { PageBanner } from '../components/ui/PageBanner';
import { PageContainer } from '../components/ui/PageContainer';
import { HelpButton } from '../components/help';
import { usePageTitle } from '../hooks/usePageTitle';
import { useNotificationStore } from '../stores/notificationStore';
import {
  activateExa,
  deactivateExa,
  getExternalAgentConfig,
  getExternalAgentStatus,
  restartExternalAgent, getExaModel, updateExaModel, seededFileCount,
  updateExternalAgentConfig,
  type ExternalAgentConfig,
  type ExternalAgentStatus,
} from '../services/externalAgentService';

export default function AgentIntegration() {
  usePageTitle('Exa Config', 'Configure Exa — the external consulting agent');

  const [config, setConfig] = useState<ExternalAgentConfig | null>(null);
  const [status, setStatus] = useState<ExternalAgentStatus | null>(null);
  const [command, setCommand] = useState('');
  const [cwd, setCwd] = useState('');
  const [permissionTier, setPermissionTier] = useState('chat');
  const [maxTurnSeconds, setMaxTurnSeconds] = useState(300);
  const [image, setImage] = useState('');
  const [saving, setSaving] = useState(false);
  const [restarting, setRestarting] = useState(false);
  // THE ACTIVATION (2026-11-18): Exa ships switched off, and turning it on is
  // this page's decision — not a side effect of installing the app.
  const [switching, setSwitching] = useState(false);
  const active = status?.enabled ?? false;
  // THE TESTED BRAINS (2026-10-10, the service-literals arc): this list is CONFIG.
  // It used to be a `const` here, so offering a different brain meant editing and
  // rebuilding the frontend. It now ships as the external-agent config's own default
  // (backend `DEFAULT_BRAINS`) and arrives with the config this page already loads,
  // so a swap is a config write. It is Exa's own tested shortlist — NOT the provider
  // page's curated catalog, which is the app's model recommendations.
  const brains = config?.brains ?? [];

  // THE EXA MODEL CARD (2026-08-22): the model/provider live in Exa's
  // private config (.hermes/config.yaml) — the API is the view/editor.
  const [exaModel, setExaModel] = useState('');
  // The offer (2026-11-20): what THIS install answers chat with, so Exa's brain is one
  // accept instead of a second decision. Nothing is written until the button is pressed.
  const [exaOffer, setExaOffer] = useState<{ provider: string; model: string; base_url?: string | null } | null>(null);
  const [exaProvider, setExaProvider] = useState('');
  const [exaBaseUrl, setExaBaseUrl] = useState('');
  const [exaEffort, setExaEffort] = useState('medium');
  const [exaVisionModel, setExaVisionModel] = useState('');
  const [savingModel, setSavingModel] = useState(false);
  const { addNotification } = useNotificationStore();

  const load = useCallback(async () => {
    try {
      const [cfg, st] = await Promise.all([getExternalAgentConfig(), getExternalAgentStatus()]);
      setConfig(cfg);
      setStatus(st);
      setCommand(cfg.command);
      setCwd(cfg.cwd);
      setPermissionTier(cfg.permission_tier ?? (cfg.fix_mode ? 'fix' : 'chat'));
      setMaxTurnSeconds(cfg.max_turn_seconds ?? 300);
      setImage(cfg.image ?? '');
      // the model card reads Exa's private config via the model endpoint
      const m = await getExaModel();
      setExaModel(m.model ?? '');
      setExaOffer(m.offer ?? null);
      setExaProvider(m.provider ?? '');
      setExaVisionModel(m.vision_model ?? '');
      setExaBaseUrl(m.base_url ?? '');
      setExaEffort(m.reasoning_effort ?? 'medium');
    } catch (err) {
      addNotification({ type: 'error', title: 'Exa Agent', message: String(err) });
    }
  }, [addNotification]);

  useEffect(() => {
    load();
  }, [load]);

  const saveModel = useCallback(async (overrides?: Partial<{ model: string; provider: string; base_url: string; reasoning_effort: string; vision_model: string }>) => {
    setSavingModel(true);
    try {
      // OVERRIDES (2026-08-22, user): the activate-on-pick dropdowns call
      // saveModel with their NEW values — setState hasn't committed yet,
      // so the closure would send stale state. The overrides win.
      const updated = await updateExaModel({
        model: overrides?.model ?? exaModel,
        provider: overrides?.provider ?? exaProvider,
        base_url: overrides?.base_url ?? exaBaseUrl,
        reasoning_effort: overrides?.reasoning_effort ?? exaEffort,
        vision_model: overrides?.vision_model ?? exaVisionModel,
      });
      addNotification({ type: 'success', title: 'Exa Agent', message: `Model set to ${updated.model} (${updated.provider})` });
      setStatus(await getExternalAgentStatus());
    } catch (err) {
      addNotification({ type: 'error', title: 'Exa Agent', message: String(err) });
    } finally {
      setSavingModel(false);
    }
  }, [exaModel, exaProvider, exaBaseUrl, exaEffort, exaVisionModel, addNotification]);

  const save = useCallback(async () => {
    setSaving(true);
    try {
      const updated = await updateExternalAgentConfig({ command, cwd, permission_tier: permissionTier, max_turn_seconds: maxTurnSeconds, image });
      setConfig(updated);
      addNotification({ type: 'success', title: 'Exa Agent', message: 'Config saved' });
      // refresh status (restart closes the connection)
      setStatus(await getExternalAgentStatus());
    } catch (err) {
      addNotification({ type: 'error', title: 'Exa Agent', message: String(err) });
    } finally {
      setSaving(false);
    }
  }, [command, cwd, permissionTier, maxTurnSeconds, image, addNotification]);

  const restart = useCallback(async () => {
    setRestarting(true);
    try {
      await restartExternalAgent();
      addNotification({ type: 'success', title: 'Exa Agent', message: 'Agent restarted — next panel open spawns fresh' });
      setStatus(await getExternalAgentStatus());
    } catch (err) {
      addNotification({ type: 'error', title: 'Exa Agent', message: String(err) });
    } finally {
      setRestarting(false);
    }
  }, [addNotification]);

  // THE ACTIVATION (2026-11-18): the decision and its honest consequence.
  // Activating on a machine that cannot run the runtime is ALLOWED — it is the
  // user's call — but the toast carries the probe instead of promising a brain
  // that will not answer.
  const toggleActivation = useCallback(async () => {
    setSwitching(true);
    try {
      const res = active ? await deactivateExa() : await activateExa();
      setStatus((s) =>
        s ? { ...s, enabled: res.enabled, runnable: res.runnable, blocked_reason: res.blocked_reason ?? null } : s
      );
      if (res.enabled) {
        // WHAT IT SEEDED (2026-11-20): activation provisions Exa's home first, so the
        // toast can say the switch actually did something instead of promising a brain.
        const seeded = seededFileCount(res.provisioned);
        addNotification({
          type: res.runnable ? 'success' : 'warning',
          title: res.runnable ? 'Exa activated' : 'Exa activated — but it cannot run here yet',
          message: res.runnable
            ? (seeded > 0
                ? `${seeded} skill files seeded into its home. Open the Exa chat to talk to it.`
                : 'Open the Exa chat to talk to it.')
            : (res.blocked_reason ?? 'The runtime it needs is missing from this machine.'),
        });
      } else {
        addNotification({
          type: 'info',
          title: 'Exa deactivated',
          message: 'Nothing is spawned and nothing answers until you activate it again.',
        });
      }
    } catch (err) {
      addNotification({ type: 'error', title: 'Exa Agent', message: String(err) });
    } finally {
      setSwitching(false);
    }
  }, [active, addNotification]);

  // THE 3-WAY PERMISSION TIER (2026-08-21): chat (per-edit cards),
  // fix (cwd auto-approve), yolo (everything — the break button
  // bounds the runaway risk). The tier replaces the old fix_mode
  // bool; the backend maps it to the ACP edit_approval_policy.
  const TIER_META: Record<string, { label: string; desc: string; badge: string; cls: string }> = {
    chat: {
      label: 'Chat approval',
      desc: 'Exa may propose edits — EVERY one shows an Allow edit / Deny card in the chat. The granular tier.',
      badge: 'per-edit approval',
      cls: 'bg-base-200/60 border-base-300',
    },
    fix: {
      label: 'Fix mode',
      desc: 'Exa may write anywhere inside its workspace without asking. The broad-but-scoped tier.',
      badge: 'fix granted',
      cls: 'border-warning bg-warning/5',
    },
    yolo: {
      label: 'YOLO',
      desc: 'Unrestricted — Exa may write anywhere, no per-edit approval (the secret-file guard still asks). Stop it any time with the chat break button; every action is still audited.',
      badge: 'unrestricted',
      cls: 'border-error bg-error/5',
    },
  };

  const dirty = !!config && (command !== config.command || cwd !== config.cwd || permissionTier !== (config.permission_tier ?? (config.fix_mode ? 'fix' : 'chat')) || maxTurnSeconds !== (config.max_turn_seconds ?? 300) || image !== (config.image ?? ''));

  return (
    <PageContainer>
      <PageBanner
        title="Exa Agent"
        tooltip="Configure Exa — the external consulting agent"
        action={
          <HelpButton context="agent-integration" size="sm" showIcon={false} showLabel label="Help" />
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Connection status */}
        <div className="card bg-base-200/60 border border-base-300">
          <div className="card-body">
            <h2 className="card-title text-base">Connection</h2>
            {/* THE ACTIVATION STATE RIDES THE BADGE (2026-11-18): one element,
                and "inactive" is deliberately NOT "offline" — off means
                something tried and failed; inactive means nothing was ever
                meant to run. The live session is the second, separate fact. */}
            <div className="flex items-center gap-2">
              <span
                className={`badge badge-sm ${active ? (status?.connected ? 'badge-success' : 'badge-warning') : 'badge-ghost'}`}
              >
                {active ? (status?.connected ? 'active · connected' : 'active · idle') : 'inactive'}
              </span>
              {active && status?.session_id && (
                <span className="text-xs opacity-60 font-mono truncate" title={status.session_id}>
                  {status.session_id.slice(0, 13)}…
                </span>
              )}
            </div>
            <p className="text-xs opacity-60 mt-1">
              {active
                ? 'Exa starts when you open its chat, so this reads idle until then.'
                : 'Exa ships switched off. Nothing is spawned and nothing answers until you activate it.'}
            </p>
            {active && status && !status.runnable && status.blocked_reason && (
              <p className="text-xs text-warning mt-1">{status.blocked_reason}</p>
            )}
            <div className="card-actions mt-3 items-center">
              <div className="tooltip tooltip-bottom" data-tip={active ? 'Switch Exa off — any live session ends' : 'Turn Exa on. It needs an agent runtime (and a model) to answer.'}>
                <button
                  className={`btn btn-sm ${active ? 'btn-outline' : 'btn-primary'}`}
                  onClick={toggleActivation}
                  disabled={switching}
                >
                  {switching ? '…' : active ? 'Deactivate Exa' : 'Activate Exa'}
                </button>
              </div>
              <div className="tooltip tooltip-bottom" data-tip={active ? 'Close the subprocess so the next chat spawns fresh' : 'Activate Exa first — there is no process to restart'}>
                <button
                  className="btn btn-sm btn-outline"
                  onClick={restart}
                  disabled={restarting || !active}
                >
                  {restarting ? 'Restarting…' : 'Restart agent'}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* THE EXA MODEL CARD (2026-08-22): the brain — provider +
            model live in Exa's private config (.hermes/config.yaml);
            the API is the view/editor. The current brain badge makes
            the active model visible (no more config-file spelunking). */}
        <div className="card bg-base-200/60 border border-base-300">
          <div className="card-body">
            <h2 className="card-title text-base">Model</h2>
            {/* THE INSTALL'S OWN ANSWER, OFFERED (2026-11-20): by the time a user reaches
                this page they have already chosen a chat model, so Exa names it and asks for
                ONE accept. The button is the accept; nothing here writes on its own. */}
            {exaOffer && (exaOffer.model !== exaModel || exaOffer.provider !== exaProvider) && (
              <div className="alert py-2 text-sm flex items-center gap-2 bg-base-300 border border-base-300">
                <span>
                  This install answers chat with{' '}
                  <span className="font-mono">{exaOffer.model}</span> via{' '}
                  <span className="font-mono">{exaOffer.provider}</span>.
                </span>
                <button
                  type="button"
                  className="btn btn-primary btn-xs ml-auto"
                  data-tip="Write this install's chat model into Exa — one model, one key, one place"
                  disabled={savingModel}
                  onClick={() => {
                    setExaModel(exaOffer.model);
                    setExaProvider(exaOffer.provider);
                    setExaBaseUrl(exaOffer.base_url ?? '');
                    saveModel({
                      model: exaOffer.model,
                      provider: exaOffer.provider,
                      base_url: exaOffer.base_url ?? '',
                    });
                  }}
                >
                  Use this model
                </button>
              </div>
            )}
            {/* THE BRAIN QUICK-SWITCH (2026-08-22, user): a curated dropdown
                of the tested brains — pick one, it fills the fields below,
                Save applies it (the swap infra is crash-free). */}
            <div className="form-control w-full mb-2">
              <label className="label" htmlFor="exa-brain-switch">
                <span className="label-text">Quick switch (tested brains)</span>
              </label>
              <select
                id="exa-brain-switch"
                className="select select-bordered select-sm w-full"
                value=""
                onChange={(e) => {
                  // THE ACTIVATE-ON-PICK (2026-08-22, user): selecting a
                  // brain SAVES it immediately (the Save button was below
                  // the fold — the user picked models without saving).
                  // One click = activate. The fields update + the config
                  // writes + the client respawns.
                  const brain = brains.find((b) => b.model === e.target.value);
                  if (brain) {
                    setExaModel(brain.model);
                    setExaProvider(brain.provider);
                    setExaBaseUrl(brain.base_url);
                    saveModel({ model: brain.model, provider: brain.provider, base_url: brain.base_url });
                  }
                }}
              >
                <option value="" disabled>Select a tested brain…</option>
                {brains.map((brain) => (
                  <option key={brain.model} value={brain.model}>{brain.label}</option>
                ))}
              </select>
              <label className="label">
                <span className="label-text-alt opacity-60">
                  Fills the fields below — Save applies. The full curated list
                  lives on the Providers page.
                </span>
              </label>
            </div>
            {status?.model && (
              <div className="flex items-center gap-2 mb-2">
                <span className="badge badge-sm badge-outline font-mono">
                  {status.model}
                </span>
                <span className="text-xs opacity-60">
                  current brain {status.provider ? `via ${status.provider}` : ''}
                </span>
              </div>
            )}
            <div className="form-control w-full">
              <label className="label" htmlFor="exa-model">
                <span className="label-text">Model</span>
              </label>
              <input
                id="exa-model"
                type="text"
                className="input input-bordered input-sm w-full font-mono"
                value={exaModel}
                onChange={(e) => setExaModel(e.target.value)}
                placeholder="deepseek-v4-flash"
              />
            </div>
            <div className="form-control w-full mt-2">
              <label className="label" htmlFor="exa-provider">
                <span className="label-text">Provider</span>
              </label>
              <input
                id="exa-provider"
                type="text"
                className="input input-bordered input-sm w-full font-mono"
                value={exaProvider}
                onChange={(e) => setExaProvider(e.target.value)}
                placeholder="deepseek"
              />
            </div>
            <div className="form-control w-full mt-2">
              <label className="label" htmlFor="exa-base-url">
                <span className="label-text">Base URL</span>
              </label>
              <input
                id="exa-base-url"
                type="text"
                className="input input-bordered input-sm w-full font-mono"
                value={exaBaseUrl}
                onChange={(e) => setExaBaseUrl(e.target.value)}
                placeholder="https://api.deepseek.com"
              />
            </div>
            <div className="form-control w-full mt-2">
              <label className="label" htmlFor="exa-effort">
                <span className="label-text">Thinking level (reasoning effort)</span>
              </label>
              <div className="flex gap-1">
                {['none', 'low', 'medium', 'high', 'max'].map(level => (
                  <button
                    key={level}
                    type="button"
                    onClick={() => setExaEffort(level)}
                    className={`btn btn-xs flex-1 ${
                      exaEffort === level
                        ? 'btn-primary'
                        : 'btn-outline'
                    }`}
                  >
                    {level === 'none' ? 'off' : level}
                  </button>
                ))}
              </div>
              <label className="label">
                <span className="label-text-alt opacity-60">
                  How hard the model thinks. Low/off = fast + responsive; high/max
                  = deep reasoning, slower turns. Hermes forwards this to the
                  provider as the reasoning effort.
                </span>
              </label>
            </div>
            <div className="form-control w-full mt-2">
              <label className="label" htmlFor="exa-vision-model">
                <span className="label-text">Vision model (screenshot analysis)</span>
              </label>
              <select
                id="exa-vision-model"
                className="select select-bordered select-sm w-full font-mono"
                value={exaVisionModel}
                onChange={(e) => {
                  // ACTIVATE-ON-PICK (2026-08-22, user): same as the brain
                  // quick-switch — selecting the vision model saves it
                  // immediately (no forgotten Save).
                  setExaVisionModel(e.target.value);
                  saveModel({ vision_model: e.target.value });
                }}
              >
                <option value="">None (browser_vision unavailable)</option>
                {/* The vision-capable brains (the explicit vision flag —
                    verified from the OpenRouter catalog 2026-08-22: Ox
                    Alpha sees images; Nemotron Ultra does NOT, so it's
                    excluded here by design). */}
                {brains.filter((b) => b.vision).map((brain) => (
                  <option key={brain.model} value={brain.model}>{brain.label}</option>
                ))}
              </select>
              <label className="label">
                <span className="label-text-alt opacity-60">
                  The model that reads page screenshots (browser_vision → the
                  AUXILIARY_VISION_MODEL env in Exa's config). Needs a
                  vision-capable model — e.g. the V4 Flash Vision variant.
                </span>
              </label>
            </div>
            <label className="label">
              <span className="label-text-alt opacity-60">
                The model/provider in Exa's own config (the provider key must
                exist in its .env). Saving applies on the next connection.
              </span>
            </label>
            <div className="card-actions mt-2">
              <button
                className="btn btn-sm btn-primary"
                onClick={() => saveModel()}
                disabled={savingModel || !exaModel.trim() || !exaProvider.trim()}
              >
                {savingModel ? 'Saving…' : 'Save model'}
              </button>
            </div>
          </div>
        </div>

        {/* The permission tier — the 3-way selector (2026-08-21) */}
        {(() => {
          const meta = TIER_META[permissionTier] ?? TIER_META.chat;
          return (
            <div className={`card border ${meta.cls}`}>
              <div className="card-body">
                <div className="flex items-center justify-between">
                  <h2 className="card-title text-base">Permission tier</h2>
                  <span className={`badge badge-sm ${permissionTier === 'yolo' ? 'badge-error badge-outline' : permissionTier === 'fix' ? 'badge-warning badge-outline' : 'badge-ghost'}`}>
                    {meta.badge}
                  </span>
                </div>
                <p className="text-xs opacity-70">{meta.desc}</p>
                <div className="btn-group mt-2 w-full">
                  {(['chat', 'fix', 'yolo'] as const).map(tier => (
                    <button
                      key={tier}
                      className={`btn btn-sm flex-1 ${permissionTier === tier ? 'btn-active btn-selected' : 'btn-outline'}`}
                      onClick={() => setPermissionTier(tier)}
                    >
                      {TIER_META[tier].label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          );
        })()}

        {/* Configuration */}
        <div className="card bg-base-200/60 border border-base-300">
          <div className="card-body">
            <h2 className="card-title text-base">Configuration</h2>
            <div className="form-control w-full">
              <label className="label" htmlFor="agent-cmd">
                <span className="label-text">Agent command</span>
              </label>
              <input
                id="agent-cmd"
                type="text"
                className="input input-bordered input-sm w-full"
                value={command}
                onChange={(e) => setCommand(e.target.value)}
                placeholder="hermes acp"
              />
              <label className="label">
                <span className="label-text-alt opacity-60">
                  The program that runs Exa (default: hermes acp). You normally don't
                  need to change this.
                </span>
              </label>
            </div>

            <div className="form-control w-full">
              <label className="label" htmlFor="agent-cwd">
                <span className="label-text">Working directory</span>
              </label>
              <input
                id="agent-cwd"
                type="text"
                className="input input-bordered input-sm w-full"
                value={cwd}
                onChange={(e) => setCwd(e.target.value)}
                placeholder="(backend cwd — project root)"
              />
              <label className="label">
                <span className="label-text-alt opacity-60">
                  Where the agent runs. Empty uses the backend's working directory.
                </span>
              </label>
            </div>

            <div className="form-control w-full mt-3 border-t border-base-300 pt-3">
              <label className="label" htmlFor="agent-max-turn">
                <span className="label-text">Whole-turn time limit</span>
              </label>
              {/* THE MINUTES SLIDER (2026-08-22, user): the seconds
                  number input was fiddly — a slider over 1-10 minutes
                  with a tooltip showing the actual value is the
                  responsive way to set the cap. */}
              <div className="flex items-center gap-3 w-full">
                <input
                  id="agent-max-turn"
                  type="range"
                  min={1}
                  max={10}
                  step={1}
                  className="range range-sm flex-1"
                  value={Math.max(1, Math.min(10, Math.round(maxTurnSeconds / 60)))}
                  onChange={(e) => setMaxTurnSeconds(Number(e.target.value) * 60)}
                />
                <div className="tooltip tooltip-top" data-tip={`${Math.round(maxTurnSeconds / 60)} minute${Math.round(maxTurnSeconds / 60) === 1 ? '' : 's'}`}>
                  <span className="badge badge-outline badge-sm font-mono min-w-[4rem] justify-center">
                    {Math.round(maxTurnSeconds / 60)}m
                  </span>
                </div>
              </div>
              <div className="flex justify-between text-[10px] opacity-50 mt-0.5 px-1">
                <span>1m</span>
                <span>10m</span>
              </div>
              <label className="label">
                <span className="label-text-alt opacity-70">
                  How long a single run may take before Exa stops it and tells you
                  why. 1-10 minutes. The panel shows the elapsed time while working.
                </span>
              </label>
            </div>

            <div className="form-control w-full mt-3 border-t border-base-300 pt-3">
              <label className="label" htmlFor="agent-image">
                <span className="label-text">Face image</span>
              </label>
              <div className="flex items-center gap-3">
                <div className="avatar">
                  <div className="w-12 h-12 rounded-full ring ring-base-300">
                    {image ? (
                      <img src={image} alt="Exa's face" className="object-cover" />
                    ) : (
                      <div className="w-full h-full bg-base-300 flex items-center justify-center text-readout">?</div>
                    )}
                  </div>
                </div>
                <select
                  id="agent-image"
                  className="select select-bordered select-sm flex-1"
                  value={image}
                  onChange={(e) => setImage(e.target.value)}
                >
                  <option value="">(no image)</option>
                  <option value="/static/alien-01.png">alien-01</option>
                  <option value="/static/alien-rocky.png">alien-rocky</option>
                </select>
              </div>
              <label className="label">
                <span className="label-text-alt opacity-70">
                  The face shown in the agent chat. The store has more; a
                  custom PNG can be uploaded later (Canva / ComfyUI).
                </span>
              </label>
            </div>

            <div className="card-actions mt-2">
              <button className="btn btn-primary btn-sm" onClick={save} disabled={saving || !dirty}>
                {saving ? 'Saving…' : 'Save'}
              </button>
              {!dirty && <span className="text-xs opacity-50 self-center">Saved</span>}
            </div>
          </div>
        </div>
      </div>
    </PageContainer>
  );
}
