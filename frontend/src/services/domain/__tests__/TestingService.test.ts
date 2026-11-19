/**
 * TestingService — the run endpoints the page calls.
 *
 * C2 wired four things the page had no method for: start, cancel, delete, and the
 * SSE URL. What matters in each is not that a URL is built, but that the ARGUMENT
 * goes where the runner expects it (`run_path` verbatim), that the id is encoded
 * (it arrives from a table row), and that a refusal is RETURNED as an error rather
 * than thrown — the page reads `{error}` and shows the lock's own sentence.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { apiClient } from '@/services/apiClient';
import { testingService } from '../TestingService';

vi.mock('@/services/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
  API_BASE_URL: 'http://localhost:8000',
}));

const mocked = apiClient as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('retireRuns — the batch, and its answers', () => {
  it('posts the names as a LIST — never a rule the server would have to interpret', async () => {
    mocked.post.mockResolvedValue({
      data: { retired: [{ name: 'a', moved_to: 'trash/test-runs/a', contents: [] }], refused: [], missing: [] },
    });
    await testingService.retireRuns(['a', 'b']);
    expect(mocked.post).toHaveBeenCalledWith(
      '/api/v1/testing/runs/retire',
      { runs: ['a', 'b'] },
      // No retries: a retry would re-send names that have already moved, and the
      // server answers those as `missing` — which would then read as an error.
      { retries: 0 },
    );
  });

  it('returns the per-run answer whole, so a refusal can be shown by name', async () => {
    const answer = {
      retired: [],
      refused: [{ name: 'a', reason: 'a run is in progress: a (pid 7, origin page)' }],
      missing: ['gone'],
    };
    mocked.post.mockResolvedValue({ data: answer });
    const res = await testingService.retireRuns(['a', 'gone']);
    expect(res.data).toEqual(answer);
  });
});

describe('the diff and save endpoints', () => {
  it('asks for the diff of one run, with the name encoded', async () => {
    mocked.get.mockResolvedValue({
      data: { run: 'x y', fingerprint: 'abc', baseline: null, reason: 'nothing comparable', added: [], removed: [], newly_failing: [], fixed: [], baseline_counts: {} },
    });
    await testingService.getDiff('x y');
    expect(mocked.get).toHaveBeenCalledWith('/api/v1/testing/runs/x%20y/diff');
  });

  it('saves with the destination the person chose', async () => {
    mocked.post.mockResolvedValue({ data: { saved: true, name: 'r', saved_to: 'kept/r', files: [] } });
    await testingService.saveRun('r', '  kept/r  ');
    expect(mocked.post).toHaveBeenCalledWith(
      '/api/v1/testing/runs/r/save',
      { destination: 'kept/r' },          // trimmed, because a pasted path has spaces
      // The start's patience, not the client's default: a big run's XML is
      // megabytes and a copy that SUCCEEDED must not be reported as failed.
      { timeout: 30000, retries: 0 },
    );
  });

  it('sends NULL for an empty destination — the server\'s default, not an empty path', async () => {
    mocked.post.mockResolvedValue({ data: { saved: true, name: 'r', saved_to: 'data/test-reports/r', files: [] } });
    await testingService.saveRun('r', '   ');
    expect(mocked.post).toHaveBeenCalledWith(
      '/api/v1/testing/runs/r/save',
      { destination: null },
      { timeout: 30000, retries: 0 },
    );
  });

  it('returns a save refusal as an error, with the server\'s own sentence', async () => {
    mocked.post.mockResolvedValue({
      error: { code: 'HTTP_409', message: 'r is already saved at /tmp/x — move or rename that copy first' },
    });
    const res = await testingService.saveRun('r');
    expect(res.error?.code).toBe('HTTP_409');
    expect(res.data).toBeUndefined();
  });
});

describe('startRun', () => {
  it('posts the files and the run id the page will watch', async () => {
    mocked.post.mockResolvedValue({ data: { run_id: 'page-20260101-000000' } });
    await testingService.startRun({
      files: ['tests/unit/test_run_lock.py'],
      run_id: 'page-20260101-000000',
    });
    expect(mocked.post).toHaveBeenCalledWith(
      '/api/v1/testing/runs',
      {
        files: ['tests/unit/test_run_lock.py'],
        run_id: 'page-20260101-000000',
      },
      // THE PATIENCE MATCHES THE SERVER'S, and this is a defect that was measured,
      // not guessed: the spawn waits up to 20s for the runner's lock, so the
      // client's 10s default aborted starts that had actually succeeded. No
      // retries: a second POST would collide with the lock the first one took.
      { timeout: 30000, retries: 0 },
    );
  });

  it('returns the refusal as an error — the lock\'s sentence is what the page shows', async () => {
    mocked.post.mockResolvedValue({
      error: { code: 'HTTP_409', message: 'a run is in progress: run 20260101-000000 (pid 42, origin terminal)' },
    });
    const res = await testingService.startRun({ files: ['tests/unit/x.py'] });
    expect(res.error?.code).toBe('HTTP_409');
    expect(res.error?.message).toContain('a run is in progress');
  });
});

describe('cancelRun', () => {
  it('posts to the run\'s cancel route, with the id ENCODED and time for the kill', async () => {
    mocked.post.mockResolvedValue({ data: { cancelled: true, survivors: [] } });
    const res = await testingService.cancelRun('20260101-000000');
    expect(mocked.post).toHaveBeenCalledWith(
      '/api/v1/testing/runs/20260101-000000/cancel',
      undefined,
      // The group kill is TERM → wait → KILL → reap → verify: up to ~16s of real
      // work. At the 10s default the browser aborted mid-kill and the page
      // reported "Could not cancel" over a run that had already died.
      { timeout: 30000, retries: 0 },
    );
    expect(res.data?.survivors).toEqual([]);
  });

  it('a refused cancel is data, not an error — the run was not this page\'s to stop', async () => {
    mocked.post.mockResolvedValue({
      data: { cancelled: false, reason: 'this run was started outside the page (terminal)' },
    });
    const res = await testingService.cancelRun('20260101-000000');
    expect(res.data?.cancelled).toBe(false);
    expect(res.data?.reason).toContain('outside the page');
  });
});

describe('deleteRun', () => {
  it('DELETEs the run and returns where it went', async () => {
    mocked.delete.mockResolvedValue({
      data: {
        deleted: true,
        name: '20260101-000000',
        moved_to: 'trash/test-runs/20260101-000000',
        contents: ['events.jsonl', 'report.md', 'report.xml'],
      },
    });
    const res = await testingService.deleteRun('20260101-000000');
    expect(mocked.delete).toHaveBeenCalledWith('/api/v1/testing/runs/20260101-000000');
    expect(res.data?.moved_to).toBe('trash/test-runs/20260101-000000');
  });
});

describe('runEventsUrl', () => {
  it('points at the run\'s own events, and can skip the replay', () => {
    expect(testingService.runEventsUrl('20260101-000000'))
      .toBe('http://localhost:8000/api/v1/testing/runs/20260101-000000/events');
    expect(testingService.runEventsUrl('20260101-000000', { tail: true }))
      .toBe('http://localhost:8000/api/v1/testing/runs/20260101-000000/events?tail=true');
  });
});
