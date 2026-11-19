/**
 * The RAG page — the two answers about the embedding service, and the sentence when they disagree.
 *
 * This is the surface of the embedding-configuration ruling, **option C** (2026-10-12): the RAG
 * vector stores capture the resolved embedding service at FIRST CONSTRUCTION, so a change made on the
 * Capabilities page waits for a restart — and a WIDTH change cannot be fixed by one at all, because
 * the index keeps the width it was created at. The page therefore shows the configured model, the
 * index's own width, what the running process is using, and the backend's `note` as an alert.
 *
 * Copy nobody asserts is copy the next edit can drop — and this copy is the whole point of the
 * ruling, so it is asserted here.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@/test/test-utils'
import RagIndex from '../RagIndex'

const { getStatus, getIngestJobStatus, triggerIngest } = vi.hoisted(() => ({
  getStatus: vi.fn(),
  getIngestJobStatus: vi.fn(),
  triggerIngest: vi.fn(),
}))

vi.mock('@/services/ragService', () => ({
  ragService: { getStatus, getIngestJobStatus, triggerIngest },
}))

/** The health payload as the API shapes it — with the four embedding fields the ruling added. */
const statusWith = (config: Record<string, unknown>) => ({
  data: {
    indexed_documents: 506,
    total_chunks: 3527,
    last_indexed: '2026-08-19T11:01:29',
    database_path: 'data/system_docs_vector.db',
    database_size_bytes: 55508992,
    config: {
      ingestion_dirs: ['wiki/entities'],
      embedding_model: null,
      ollama_base_url: null,
      index_width: 768,
      running_model: null,
      running_address: null,
      note: null,
      ...config,
    },
  },
})

describe('RagIndex — the embedding configuration vs the running process', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getIngestJobStatus.mockResolvedValue({ data: null })
  })

  it('shows the index’s own width and what the running process is using', async () => {
    getStatus.mockResolvedValue(statusWith({}))
    render(<RagIndex />)

    expect(await screen.findByText(/768 — what the index was built at/)).toBeTruthy()
    expect(screen.getByText(/nothing loaded in this process yet/)).toBeTruthy()
  })

  it('shows the backend’s note when a saved model cannot fit the index', async () => {
    getStatus.mockResolvedValue(
      statusWith({
        embedding_model: 'mxbai-embed-large',
        note: 'the index is 768 wide and \u2018mxbai-embed-large\u2019 is 1024 — re-run the ingest to rebuild the index (nothing was changed)',
      }),
    )
    render(<RagIndex />)

    expect(await screen.findByText(/re-run the ingest to rebuild the index/)).toBeTruthy()
  })

  it('shows no note when the model and the index agree', async () => {
    getStatus.mockResolvedValue(statusWith({ note: null }))
    render(<RagIndex />)

    await screen.findByText(/what the index was built at/)
    expect(screen.queryByText(/after a restart/)).toBeNull()
    expect(screen.queryByText(/re-run the ingest/)).toBeNull()
  })
})
