/**
 * ModelTable's **Pricing column**.
 *
 * Guards the three things the column got wrong — see
 * `local/issues/unit-blind-pricing-readers-2026-10-09.md`:
 *   1. it read only the FLAT `pricing_prompt`, so openrouter's nested-only rows showed `N/A`;
 *   2. it printed per-token figures through `toFixed(4)`, so every real price read `$0.0000`;
 *   3. it rendered the `-1` "variable / not published" sentinel as `$-1.0000`.
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import ModelTable from '../ModelBrowser/ModelTable'
import type { ModelInfo } from '@/services/domains/providers/modelBrowserService'

const model = (over: Partial<ModelInfo>): ModelInfo => ({ id: 'm', name: 'm', ...over })

const renderOne = (m: ModelInfo) =>
  render(
    <ModelTable
      models={[m]}
      loading={false}
      error={null}
      currentPage={1}
      totalPages={1}
      pageSize={10}
      totalItems={1}
      onPageChange={() => {}}
      onPageSizeChange={() => {}}
      onSelectModel={() => {}}
    />,
  )

describe('ModelTable — the Pricing column', () => {
  it('reads the NESTED pricing shape and shows per 1M', () => {
    // openrouter's rows carry ONLY `pricing: {prompt, completion}` — no flat fields.
    renderOne(model({ id: 'nested', pricing: { prompt: 2.5e-6, completion: 1e-5 } }))

    expect(screen.getByText(/Prompt: \$2\.50 \/ 1M/)).toBeTruthy()
    expect(screen.getByText(/Completion: \$10\.00 \/ 1M/)).toBeTruthy()
  })

  it('still reads the FLAT fields deepseek sends beside the nested shape', () => {
    renderOne(model({ id: 'flat', pricing_prompt: 1.4e-7, pricing_completion: 2.8e-7 }))

    expect(screen.getByText(/Prompt: \$0\.140 \/ 1M/)).toBeTruthy()
    expect(screen.getByText(/Completion: \$0\.280 \/ 1M/)).toBeTruthy()
  })

  it('renders the -1 sentinel as Variable, never as a negative price', () => {
    renderOne(model({ id: 'variable', pricing: { prompt: -1, completion: -1 } }))

    expect(screen.getByText(/Prompt: Variable/)).toBeTruthy()
    expect(screen.getByText(/Completion: Variable/)).toBeTruthy()
    expect(screen.queryByText(/\$-1/)).toBeNull()
  })

  it('says Free for a zero price, and N/A when neither shape carries one', () => {
    renderOne(model({ id: 'free', pricing: { prompt: 0, completion: 0 } }))
    expect(screen.getByText(/Prompt: Free/)).toBeTruthy()
  })

  it('says N/A when no price arrived at all', () => {
    renderOne(model({ id: 'absent' }))
    expect(screen.getByText(/Prompt: N\/A/)).toBeTruthy()
  })
})
