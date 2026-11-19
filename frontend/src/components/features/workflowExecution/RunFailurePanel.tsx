import type { WorkflowExecution } from '@/types/workflows';

interface RunFailurePanelProps {
  execution: WorkflowExecution;
  className?: string;
}

/**
 * THE RUN-LEVEL FAILURE PANEL (phase 6 group 4, Stage 3 — G4-F1).
 *
 * Before this, a failed run's only surfaces were the per-step text and a `frontendLoggingService`
 * line: the run AS A WHOLE said nothing. The panel leads with the ONE wording the log and the
 * toast carry (`failureStatement` — the provider + model the run resolved) and falls back to the
 * RAW exception when the run named nobody: a non-LLM failure has no offender to finger, so no
 * name is invented (G4-F5). The raw exception stays reachable either way (A1).
 *
 * It renders nothing while the run is not failed, so it is safe to mount unconditionally.
 */
export default function RunFailurePanel({ execution, className = '' }: RunFailurePanelProps) {
  if (execution.status !== 'failed') return null;

  const statement = (execution.failureStatement ?? '').trim();
  const rawError = (execution.error ?? '').trim();

  return (
    <div
      className={`alert alert-error items-start ${className}`}
      role="alert"
      data-testid="run-failure-panel"
    >
      <div className="w-full">
        <div className="font-semibold">Workflow run failed</div>

        {statement ? (
          <div className="mt-1 text-sm" data-testid="run-failure-statement">
            {statement}
          </div>
        ) : (
          <div
            className="mt-1 text-sm whitespace-pre-wrap break-words"
            data-testid="run-failure-raw"
          >
            {rawError || 'The run failed and recorded no error detail.'}
          </div>
        )}

        {statement && rawError && (
          <details className="mt-2">
            <summary className="cursor-pointer text-xs">
              <span
                className="tooltip tooltip-bottom"
                data-tip="The raw exception the run recorded"
              >
                Technical detail
              </span>
            </summary>
            <pre
              className="mt-1 text-xs whitespace-pre-wrap break-words"
              data-testid="run-failure-raw"
            >
              {rawError}
            </pre>
          </details>
        )}
      </div>
    </div>
  );
}
