/**
 * useWorkflowToasts — drains the ToastDistributor queue.
 *
 * Polls GET /workflows/toasts?since=<cursor> (localStorage cursor)
 * and shows each new product as an in-app toast with a link to the
 * Workflow Products page. Mounted once in the app shell — toasts
 * appear app-wide, not just on the Products page.
 */

import { useCallback, useEffect, useRef } from 'react';
import { workflowService } from '../services/domains/llm/workflowService';
import { useNotificationStore } from '../stores/notificationStore';
import { useWorkflowToastPreference } from '../stores/workflowToastPreference';

const CURSOR_KEY = 'workflow_toast_cursor';
const POLL_MS = 15000;

interface ToastEntry {
  product_type: string;
  title: string;
  source_template: string;
  created_at: string;
  path?: string;
}

export function useWorkflowToasts(enabled = true, intervalMs = POLL_MS) {
  const addInfo = useNotificationStore((s) => s.addInfo);
  const toastsEnabled = useWorkflowToastPreference((s) => s.toastsEnabled);
  const seenRef = useRef<string>(localStorage.getItem(CURSOR_KEY) ?? '');

  const poll = useCallback(async () => {
    if (!enabled) return;
    try {
      const resp = await workflowService.getWorkflowToasts(seenRef.current);
      const toasts = ((resp.data as { toasts?: ToastEntry[] })?.toasts ?? []) as ToastEntry[];
      if (toasts.length === 0) return;
      // newest-first from the queue; show them in order, update cursor to the newest
      const newest = toasts[0].created_at;
      // THE BACKLOG BATCH (2026-08-22, the vision report): the FIRST poll
      // (no cursor yet) returns the ENTIRE unread history (~15 items) ->
      // one toast per item = a solid blue wall. Batch it: one summary
      // toast; single new arrivals keep their per-item toast.
      const isBacklog = !seenRef.current && toasts.length > 3;
      if (isBacklog) {
        if (toastsEnabled) {
          addInfo(
            `${toasts.length} new reports since your last visit`,
            'Workflow products landed while you were away — view them on the Products page.',
            8000,
            { label: 'View reports', href: '/products' }
          );
        }
        if (newest > seenRef.current) {
          seenRef.current = newest;
          localStorage.setItem(CURSOR_KEY, newest);
        }
        return;
      }
      for (const t of [...toasts].reverse()) {
        // the folder-watcher add (Phase G, 2026-08-17): the toast
        // carries a LINK to the full-page viewer — the "do something
        // when a product lands" is now actionable
        if (toastsEnabled) {
          const basename = (t.path ?? '').split('/').pop() ?? '';
          addInfo(
            t.title,
            `${t.product_type} from ${t.source_template}`,
            8000,
            basename ? { label: 'View report', href: `/products/${encodeURIComponent(basename)}` } : undefined
          );
        }
      }
      // the cursor ALWAYS advances (even when toasts are off — no
      // backlog flood on re-enable; the queue stays drained)
      if (newest > seenRef.current) {
        seenRef.current = newest;
        localStorage.setItem(CURSOR_KEY, newest);
      }
    } catch (err) {
      // silent — polling must never spam errors
      console.warn('useWorkflowToasts poll failed:', err);
    }
  }, [enabled, addInfo, toastsEnabled]);

  useEffect(() => {
    poll();
    const id = setInterval(poll, intervalMs);
    return () => clearInterval(id);
  }, [poll, intervalMs]);
}

export default useWorkflowToasts;
