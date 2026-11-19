/** SchedulerModal — the workflow trigger's schedule editor (2026-08-18).

Opened from the TriggerManagement rows ('Schedule'). Presets for
the common cadences + a validated custom cron. Save → PUT
/triggers/{id} with the new cron (the existing timezone kept).
DaisyUI modal (the Sessions/products pattern).
*/

import { useState } from 'react';

export interface SchedulerModalProps {
  trigger: { id: string; name: string; cron?: string; timezone?: string };
  onClose: () => void;
  onSaved: (cron: string) => void;
}

const PRESETS: { label: string; cron: string }[] = [
  { label: 'Hourly (at :00)', cron: '0 * * * *' },
  { label: 'Daily at 9 AM', cron: '0 9 * * *' },
  { label: 'Weekly (Mon 9 AM)', cron: '0 9 * * 1' },
];

const isValidCron = (v: string) => v.trim().split(/\s+/).length === 5;

/** The cron → plain English preview (2026-08-18: the editor was
 *  cryptic — '0 9 * * *' means nothing to a user. This parses the
 *  5 fields into a readable cadence; presets get exact phrasing,
 *  anything else falls back to the field-by-field readout. */
function cronToHuman(expr: string): string {
  const p = expr.trim().split(/\s+/);
  if (p.length !== 5) return '';
  const [min, hour, dom, mon, dow] = p;
  const nums = (s: string) => /^\d+$/.test(s);
  const any = (s: string) => s === '*';
  const isEveryMin = min === '*' && hour === '*' && dom === '*' && mon === '*' && dow === '*';
  if (isEveryMin) return 'Every minute';
  const h = nums(hour) && any(dom) && any(mon) && any(dow);
  const time = (hh: string) => {
    const n = parseInt(hh, 10) % 24;
    return n === 0 ? 'midnight' : n === 12 ? 'noon' : `${n}:00`;
  };
  if (min === '0' && h) return `Every day at ${time(hour)}`;
  if (min === '0' && h && nums(dow) && any(dom) && any(mon)) {
    const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    const d = parseInt(dow, 10);
    return `Every ${days[d % 7]} at ${time(hour)}`;
  }
  if (nums(min) && nums(hour) && any(dom) && any(mon) && any(dow)) {
    return `Every day at ${time(hour)} past ${parseInt(min, 10)} minute${min === '1' ? '' : 's'}`;
  }
  if (nums(min) && nums(hour) && nums(dow) && any(dom) && any(mon)) {
    const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    return `Every ${days[parseInt(dow, 10) % 7]} at ${time(hour)} past ${parseInt(min, 10)}`;
  }
  return `${p.join(' ')} — minute hour day-of-month month weekday`;
}

export default function SchedulerModal({ trigger, onClose, onSaved }: SchedulerModalProps) {
  const [cron, setCron] = useState(trigger.cron || '0 * * * *');
  const [saving, setSaving] = useState(false);
  // THE ERROR SLOT (2026-08-26, the tsc -b tail — the earlier
  // unused-removal left [setError] destructuring the STATE as the
  // setter! The empty-first keeps the setter working.)
  const [, setError] = useState<string | null>(null);

  const valid = isValidCron(cron);

  const save = async () => {
    if (!valid) return;
    setSaving(true);
    setError(null);
    try {
      const { triggerService } = await import('@/services/domains/llm/triggerService');
      await triggerService.updateTrigger(trigger.id, { config: { cron: cron.trim() } });
      onSaved(cron.trim());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save the schedule');
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/50" onClick={() => !saving && onClose()}>
      <div
        className="bg-base-200 rounded-lg shadow-xl max-h-[90vh] overflow-y-auto p-6"
        style={{ width: 'min(var(--dialog-width-md), 95vw)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="font-bold text-lg">Schedule — {trigger.name}</h3>
        <p className="py-2 text-sm text-readout">
          Set the cron expression. Presets cover the common cadences; the custom field
          accepts any 5-part cron ({'{minute} {hour} {day} {month} {weekday}'}).
        </p>

        {/* Presets */}
        <div className="grid grid-cols-3 gap-2 my-3">
          {PRESETS.map((p) => (
            <button
              key={p.cron}
              className={`btn btn-sm ${cron === p.cron ? 'btn-active btn-selected' : 'btn-outline'}`}
              onClick={() => setCron(p.cron)}
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* Custom cron */}
        <div className="flex flex-col gap-1">
          <label className="text-xs uppercase tracking-wide text-readout">Cron expression</label>
          <input
            type="text"
            value={cron}
            onChange={(e) => setCron(e.target.value)}
            placeholder="0 9 * * *"
            className={`input input-bordered input-sm font-mono ${!valid && cron ? 'input-error' : ''}`}
          />
          {valid && (
            <span className="text-sm font-medium text-primary">
              ↳ {cronToHuman(cron)}
            </span>
          )}
          {!valid && cron && (
            <span className="text-xs text-error">Cron must have 5 parts (minute hour day month weekday).</span>
          )}
        </div>

        <div className="modal-action">
          <button className="btn btn-neutral btn-ghost" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn btn-primary" onClick={save} disabled={!valid || saving}>
            {saving ? 'Saving…' : 'Save Schedule'}
          </button>
        </div>
      </div>
    </div>
  );
}
