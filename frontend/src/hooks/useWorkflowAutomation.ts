/**
 * useWorkflowAutomation Hook
 *
 * The triggered-execution model — manage triggers and monitor their
 * run history. Wraps triggerService + workflowService (the page
 * never touches raw services; this is the established
 * page → hook → service convention).
 */

import { useCallback, useEffect, useState } from 'react';
import { triggerService } from '../services/domains/llm/triggerService';
import { workflowService } from '../services/domains/llm/workflowService';
import { useNotificationStore } from '../stores/notificationStore';
import type { TriggerInfoResponse } from '../types/workflows';

export interface AutomationRun {
  id: string;
  templateId: string;
  status: string;
  startedAt?: string;
  elapsed?: number;
  /** The run completed with a failure absorbed inside it — see the executions row's `degraded`. */
  degraded?: boolean;
}

export interface UseWorkflowAutomationReturn {
  triggers: TriggerInfoResponse[];
  selectedTrigger: string;
  runs: AutomationRun[];
  loadingRuns: boolean;
  selectTrigger: (id: string) => void;
  refreshTriggers: () => Promise<void>;
}

export function useWorkflowAutomation(): UseWorkflowAutomationReturn {
  const { addError } = useNotificationStore();
  const [triggers, setTriggers] = useState<TriggerInfoResponse[]>([]);
  const [selectedTrigger, setSelectedTrigger] = useState<string>('');
  const [runs, setRuns] = useState<AutomationRun[]>([]);
  const [loadingRuns, setLoadingRuns] = useState(false);

  const refreshTriggers = useCallback(async () => {
    try {
      const resp = await triggerService.getTriggers();
      const list = (resp.data ?? []) as TriggerInfoResponse[];
      setTriggers(list);
      setSelectedTrigger((prev) => prev || (list[0]?.id ?? ''));
    } catch (err) {
      addError('Automation', 'Failed to load triggers');
      console.error('useWorkflowAutomation loadTriggers:', err);
    }
  }, [addError]);

  useEffect(() => { refreshTriggers(); }, [refreshTriggers]);

  const selectTrigger = useCallback((id: string) => {
    setSelectedTrigger(id);
  }, []);

  useEffect(() => {
    if (!selectedTrigger) return;
    let cancelled = false;
    const loadRuns = async () => {
      setLoadingRuns(true);
      try {
        const resp = await workflowService.getExecutions(undefined, selectedTrigger);
        const rows = ((resp.data as { executions?: unknown[] })?.executions ?? []) as Record<string, unknown>[];
        if (cancelled) return;
        setRuns(rows.map((r) => ({
          id: String(r.id ?? ''),
          templateId: String(r.template_id ?? ''),
          status: String(r.status ?? ''),
          startedAt: r.started_at ? String(r.started_at) : undefined,
          elapsed: typeof r.elapsed_seconds === 'number' ? r.elapsed_seconds : undefined,
          degraded: Boolean(r.degraded),
        })));
      } catch (err) {
        if (cancelled) return;
        addError('Automation', 'Failed to load run history');
        console.error('useWorkflowAutomation loadRuns:', err);
      } finally {
        if (!cancelled) setLoadingRuns(false);
      }
    };
    loadRuns();
    return () => { cancelled = true; };
  }, [selectedTrigger, addError]);

  return {
    triggers,
    selectedTrigger,
    runs,
    loadingRuns,
    selectTrigger,
    refreshTriggers,
  };
}

export default useWorkflowAutomation;
