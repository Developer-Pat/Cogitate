/**
 * TriggerManagement — workflow trigger control panel
 *
 * Monitor + activate/deactivate workflow triggers (schedule,
 * webhook, database). Backed by /api/v1/triggers. Shows active
 * state, cron config, and next run time (from the scheduler).
 */

import { useCallback, useEffect, useState } from 'react';
import { triggerService } from '@/services/domains/llm/triggerService';
import { useNotificationStore } from '@/stores/notificationStore';
import SchedulerModal from './SchedulerModal';
import type {
  TriggerInfoResponse,
  ScheduleListResponse
} from '@/types/workflows';

interface TriggerManagementProps {
  refreshKey?: number;
  onRefresh?: () => void;
}

interface TriggerRow {
  id: string;
  workflowId: string;
  triggerType: string;
  isActive: boolean;
  name: string;
  cron?: string;
  nextRun?: string;
}

export default function TriggerManagement({ refreshKey, onRefresh }: TriggerManagementProps) {
  const [triggers, setTriggers] = useState<TriggerRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  // the scheduler modal (2026-08-18): the row being scheduled
  const [scheduling, setScheduling] = useState<TriggerRow | null>(null);
  const { addSuccess, addError } = useNotificationStore();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [trigResp, schedResp] = await Promise.all([
        triggerService.getTriggers(),
        triggerService.getSchedules(),
      ]);
      const list = (trigResp.data ?? []) as TriggerInfoResponse[];
      const schedules = (schedResp.data ?? []) as ScheduleListResponse[];
      const schedByTrigger = new Map(
        schedules.map((s) => [s.trigger_id, s])
      );
      const rows: TriggerRow[] = list.map((t) => {
        const sched = schedByTrigger.get(t.id);
        const cfg = (t.config ?? {}) as { cron?: string };
        return {
          id: t.id,
          workflowId: t.workflow_id,
          triggerType: t.trigger_type,
          isActive: t.is_active,
          name: t.name ?? t.id,
          cron: sched?.cron ?? cfg.cron,
          nextRun: sched?.next_run_time,
        };
      });
      rows.sort((a, b) => Number(b.isActive) - Number(a.isActive));
      setTriggers(rows);
    } catch (err) {
      addError('Triggers', 'Failed to load workflow triggers');
      console.error('TriggerManagement load:', err);
    } finally {
      setLoading(false);
    }
  }, [addError]);

  useEffect(() => { load(); }, [load]);
  // the shared refresh (2026-08-18): when the Exa panel sets a cron,
  // the table reloads so the new schedule shows
  useEffect(() => { if (refreshKey) load(); }, [refreshKey, load]);

  const toggle = async (row: TriggerRow) => {
    setBusy(row.id);
    try {
      if (row.isActive) {
        await triggerService.deactivateTrigger(row.id);
        addSuccess('Trigger deactivated', row.name + ' will no longer fire.');
      } else {
        await triggerService.activateTrigger(row.id);
        addSuccess('Trigger activated', row.name + ' is now scheduled.');
      }
      await load();
      onRefresh?.();
    } catch (err) {
      addError('Trigger', 'Failed to ' + (row.isActive ? 'deactivate' : 'activate') + ' ' + row.name);
      console.error('TriggerManagement toggle:', err);
    } finally {
      setBusy(null);
    }
  };

  const handleScheduled = async (cron: string) => {
    await load();
    onRefresh?.();
    if (scheduling) addSuccess('Schedule saved', `${scheduling.name} → ${cron}`);
    setScheduling(null);
  };

  const typeLabel = (t: string) =>
    t === 'schedule' ? 'Scheduled' : t === 'webhook' ? 'Webhook' : 'Database';

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Workflow Triggers</h3>
        <button
          onClick={() => load()}
          className="rounded-md border border-base-300 px-3 py-1.5 text-sm text-readout hover:bg-base-200/60"
        >
          Refresh
        </button>
      </div>

      {loading ? (
        <p className="text-sm text-readout">Loading triggers…</p>
      ) : triggers.length === 0 ? (
        <p className="text-sm text-readout">No triggers configured.</p>
      ) : (
        <div className="overflow-hidden rounded-lg border border-base-300 dark:border-base-300">
          <table className="w-full text-sm">
            <thead className="bg-base-200/60">
              <tr className="text-left text-xs uppercase tracking-wide text-readout ">
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Workflow</th>
                <th className="px-3 py-2">Type</th>
                <th className="px-3 py-2">Schedule</th>
                <th className="px-3 py-2">Next Run</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-base-300">
              {triggers.map((row) => (
                <tr key={row.id} className="hover:bg-base-200/60">
                  <td className="px-3 py-2 font-medium">{row.name}</td>
                  <td className="px-3 py-2 text-readout">{row.workflowId}</td>
                  <td className="px-3 py-2">{typeLabel(row.triggerType)}</td>
                  <td className="px-3 py-2 font-mono text-xs">{row.cron ?? '—'}</td>
                  <td className="px-3 py-2 text-xs text-readout">
                    {row.nextRun ? new Date(row.nextRun).toLocaleString() : '—'}
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={
                        row.isActive
                          ? 'inline-flex items-center rounded-full bg-success/10 px-2 py-0.5 text-xs font-medium text-success'
                          : 'inline-flex items-center rounded-full bg-base-content/10 px-2 py-0.5 text-xs font-medium text-disabled'
                      }
                    >
                      {row.isActive ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-1">
                      {/* the media play/stop toggle + the calendar (2026-08-18):
                          icon-only buttons with descriptive DaisyUI tooltips */}
                      <div
                        className="tooltip"
                        data-tip={row.isActive ? 'Stop' : 'Start'}
                      >
                        <button
                          onClick={() => toggle(row)}
                          disabled={busy === row.id}
                          aria-label={row.isActive ? 'Stop trigger' : 'Start trigger'}
                          className={
                            'btn btn-circle btn-xs ' +
                            (row.isActive
                              ? 'btn-error'
                              : 'btn-success')
                          }
                        >
                          {busy === row.id ? (
                            <span className="loading loading-spinner loading-xs"></span>
                          ) : row.isActive ? (
                            <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="1" /></svg>
                          ) : (
                            <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>
                          )}
                        </button>
                      </div>
                      {row.triggerType === 'schedule' && (
                        <div className="tooltip tooltip-bottom-left" data-tip="Schedule">
                          <button
                            onClick={() => setScheduling(row)}
                            aria-label="Edit schedule"
                            className="btn btn-circle btn-xs btn-ghost"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" /></svg>
                          </button>
                        </div>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* The scheduler modal (2026-08-18) */}
      {scheduling && (
        <SchedulerModal
          trigger={{ id: scheduling.id, name: scheduling.name, cron: scheduling.cron, timezone: undefined }}
          onClose={() => setScheduling(null)}
          onSaved={handleScheduled}
        />
      )}
    </div>
  );
}
