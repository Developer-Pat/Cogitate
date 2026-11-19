/**
 * THE RUN-LEVEL FAILURE PANEL — and the runner that mounts it (phase 6 group 4, Stage 3).
 *
 * Two halves, because the panel proves the RENDER and the runner proves the WIRING: a panel
 * nobody mounts is a complete, tested feature that is completely inert. The runner test mocks its
 * two hooks and asserts the panel reaches the DOM for a failed run.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@/test/test-utils';
import type { WorkflowExecution, WorkflowTemplate } from '@/types/workflows';
import RunFailurePanel from '../RunFailurePanel';

const STATEMENT =
  'Deepseek V4 Flash (deepseek) is not functioning properly — the provider reported: boom. ' +
  'You can have Exa attempt diagnosis (ask Exa).';

const base: WorkflowExecution = {
  id: 'wf-1',
  templateId: 'tpl',
  status: 'failed',
  inputs: {},
  stepExecutions: [],
  logs: [],
};

// ── the panel ─────────────────────────────────────────────────────────────────────────────────

describe('RunFailurePanel', () => {
  it('renders nothing while the run is not failed', () => {
    render(<RunFailurePanel execution={{ ...base, status: 'running' }} />);
    expect(screen.queryByTestId('run-failure-panel')).toBeNull();
  });

  it('leads with the ONE wording and keeps the raw exception reachable', () => {
    render(
      <RunFailurePanel
        execution={{ ...base, failureStatement: STATEMENT, error: 'litellm.APIConnectionError: boom' }}
      />,
    );

    expect(screen.getByTestId('run-failure-statement').textContent).toBe(STATEMENT);
    // A1: the raw exception stays recoverable, beside the statement
    expect(screen.getByTestId('run-failure-raw').textContent).toContain(
      'litellm.APIConnectionError: boom',
    );
  });

  it('shows the raw error and invents no name when the run named nobody', () => {
    render(<RunFailurePanel execution={{ ...base, error: 'KeyError: no such node' }} />);

    expect(screen.queryByTestId('run-failure-statement')).toBeNull();
    expect(screen.getByTestId('run-failure-raw').textContent).toContain('KeyError: no such node');
  });
});

// ── the runner mounts it ──────────────────────────────────────────────────────────────────────

const FAILED: WorkflowExecution = {
  ...base,
  failureStatement: STATEMENT,
  error: 'litellm.APIConnectionError: boom',
};

vi.mock('@/hooks/useWorkflowExecution', () => ({
  useWorkflowExecution: () => ({
    executeWorkflow: vi.fn(),
    cancelExecution: vi.fn(),
    selectedExecution: FAILED,
    loading: false,
    error: null,
    setSSEDisconnect: vi.fn(),
    disconnectSSE: vi.fn(),
  }),
}));

vi.mock('@/hooks/useSSE', () => ({
  useWorkflowProgress: () => ({ data: null, status: 'idle', disconnect: vi.fn() }),
}));

const template: WorkflowTemplate = {
  id: 'tpl',
  name: 'T',
  description: '',
  category: 'Custom',
  version: '1',
  author: 'System',
  tags: [],
  steps: [],
  inputs: [],
  outputs: [],
  metadata: {
    complexity: 'simple',
    estimatedDuration: 0,
    requiredCapabilities: [],
    dependencies: [],
    supportedAgents: [],
  },
  createdAt: '2026-10-04T00:00:00Z',
  updatedAt: '2026-10-04T00:00:00Z',
  isPublic: false,
  isCustomizable: true,
  executionCount: 0,
  successRate: 0,
  averageExecutionTime: 0,
};

describe('WorkflowRunner — the run-level panel', () => {
  beforeEach(() => {
    // the runner logs the failure through frontendLoggingService; keep it off the network
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: true, json: async () => ({}) })));
  });
  afterEach(() => vi.unstubAllGlobals());

  it('renders the failure panel for a failed run', async () => {
    const { default: WorkflowRunner } = await import('../WorkflowRunner');

    render(<WorkflowRunner template={template} onExecutionError={vi.fn()} />);

    expect(screen.getByTestId('run-failure-panel')).toBeTruthy();
    expect(screen.getByTestId('run-failure-statement').textContent).toBe(STATEMENT);
  });
});
