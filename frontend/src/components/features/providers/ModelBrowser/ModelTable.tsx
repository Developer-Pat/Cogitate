/**
 * Model Table Component
 *
 * Displays models in a paginated table with expandable rows for details.
 */

import React, { useState } from 'react'
import type { ModelInfo, ModelCapabilityBadge } from '@/services/domains/providers/modelBrowserService'
import { Pagination } from '@/components/ui/tables/Pagination'

interface ModelTableProps {
  models: ModelInfo[]
  loading: boolean
  error: string | null
  currentPage: number
  totalPages: number
  pageSize: number
  totalItems: number
  onPageChange: (page: number) => void
  onPageSizeChange: (size: number) => void
  onSelectModel: (model: ModelInfo) => void
}

/**
 * Model Table Component
 */
const ModelTable: React.FC<ModelTableProps> = ({
  models,
  loading,
  error,
  currentPage,
  totalPages,
  pageSize,
  totalItems,
  onPageChange,
  onPageSizeChange,
  onSelectModel,
}) => {
  const [expandedModelId, setExpandedModelId] = useState<string | null>(null)

  /**
   * Toggle model row expansion
   */
  const handleToggleExpand = (modelId: string) => {
    setExpandedModelId(expandedModelId === modelId ? null : modelId)
  }

  /**
   * Get badge styling
   */
  const getCapabilityBadgeStyle = (badge: ModelCapabilityBadge) => {
    const colorMap: Record<string, string> = {
      blue: 'bg-blue-100 text-blue-800 border-blue-300',
      purple: 'bg-purple-100 text-purple-800 border-purple-300',
      green: 'bg-green-100 text-green-800 border-green-300',
      orange: 'bg-orange-100 text-orange-800 border-orange-300',
      pink: 'bg-pink-100 text-pink-800 border-pink-300',
      gray: 'bg-gray-100 text-gray-800 border-gray-300',
    }

    return colorMap[badge.color] || colorMap.gray
  }

  /**
   * Format context length
   */
  const formatContextLength = (tokens?: number) => {
    if (!tokens) return 'N/A'
    if (tokens >= 1000000) return `${(tokens / 1000000).toFixed(0)}M`
    if (tokens >= 1000) return `${(tokens / 1000).toFixed(0)}K`
    return tokens.toString()
  }

  /**
   * The price for one side of a model, from whichever shape the provider sent.
   *
   * The payload is NOT uniform: openrouter carries only the nested `pricing: {prompt, completion}`,
   * while deepseek carries both that and flat `pricing_prompt`/`pricing_completion`. Reading only the
   * flat fields left openrouter's entire column as `N/A`.
   */
  const priceOf = (model: ModelInfo, side: 'prompt' | 'completion') =>
    model.pricing?.[side] ?? (side === 'prompt' ? model.pricing_prompt : model.pricing_completion)

  /**
   * Format a price.
   *
   * The stored figure is PER TOKEN; people read per MILLION, so the column shows per 1M with the unit
   * spelled out (`$2.50 / 1M`). The old `$price.toFixed(4)` printed every real price as `$0.0000`.
   * A NEGATIVE price is not a number: openrouter uses `-1` to mean "variable / not published", which
   * the old formatter rendered as `$-1.0000`.
   */
  const formatPrice = (price?: number | null) => {
    if (price === undefined || price === null) return 'N/A'
    if (price === 0) return 'Free'
    if (price < 0) return 'Variable'
    const perMillion = price * 1_000_000
    return perMillion >= 1 ? `$${perMillion.toFixed(2)} / 1M` : `$${perMillion.toFixed(3)} / 1M`
  }

  if (error) {
    return (
      <div className="alert alert-error">
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
        <span>{error}</span>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <span className="loading loading-spinner loading-lg text-primary"></span>
      </div>
    )
  }

  if (models.length === 0) {
    return (
      <div className="text-center py-12">
        <svg className="mx-auto h-12 w-12 text-readout" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <h3 className="mt-2 text-sm font-medium text-base-content">No models found</h3>
        <p className="mt-1 text-sm text-readout">
          Try adjusting your search or filters
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Models Table */}
      <div className="overflow-x-auto">
        <table className="table table-zebra w-full">
          <thead>
            <tr>
              <th className="w-10"></th>
              <th>Model</th>
              <th>Provider</th>
              <th>Context</th>
              <th>Pricing</th>
              <th>Capabilities</th>
              <th className="text-right">Action</th>
            </tr>
          </thead>
          <tbody>
            {models.map((model) => (
              <React.Fragment key={model.id}>
                {/* Main Row */}
                <tr className="hover">
                  <td>
                    <button
                      onClick={() => handleToggleExpand(model.id)}
                      className="btn btn-ghost btn-xs"
                    >
                      {expandedModelId === model.id ? (
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                      ) : (
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      )}
                    </button>
                  </td>
                  <td>
                    <div className="font-medium flex items-center gap-1.5 flex-wrap">
                      {model.display_name || model.name}
                      {model.curated?.is_curated && (
                        <>
                          {model.curated.verified && (
                            <span className="tooltip tooltip-top" data-tip="Verified — confirmed in the provider catalog">
                              <span className="badge badge-xs badge-success badge-outline">Verified</span>
                            </span>
                          )}
                        </>
                      )}
                    </div>
                    {model.description && (
                      <div className="text-xs text-readout truncate max-w-xs">
                        {model.description}
                      </div>
                    )}
                  </td>
                  <td>
                    <span className="text-sm">{model.top_provider || 'Unknown'}</span>
                  </td>
                  <td>
                    <span className={`badge ${model.context_category === 'ultra_long' ? 'badge-success badge-outline' : model.context_category === 'very_long' ? 'badge-info badge-outline' : 'badge-ghost'}`}>
                      {formatContextLength(model.context_length)}
                    </span>
                  </td>
                  <td>
                    <div className="flex flex-col text-sm">
                      <span>Prompt: {formatPrice(priceOf(model, 'prompt'))}</span>
                      <span>Completion: {formatPrice(priceOf(model, 'completion'))}</span>
                    </div>
                  </td>
                  <td>
                    <div className="flex flex-wrap gap-1">
                      {model.capability_badges?.slice(0, 3).map((badge) => (
                        <span
                          key={badge.id}
                          className={`badge badge-xs border ${getCapabilityBadgeStyle(badge)}`}
                          title={badge.label}
                        >
                          {badge.icon}
                        </span>
                      ))}
                      {(model.capability_badges?.length || 0) > 3 && (
                        <span className="badge badge-xs badge-ghost">
                          +{model.capability_badges!.length - 3}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="text-right">
                    <button
                      onClick={() => onSelectModel(model)}
                      className="btn btn-sm btn-primary btn-outline"
                    >
                      Select
                    </button>
                  </td>
                </tr>

                {/* Expanded Details Row */}
                {expandedModelId === model.id && (
                  <tr>
                    <td colSpan={7} className="p-4 bg-base-200">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* Left Column */}
                        <div>
                          <h4 className="font-semibold mb-2">Model Details</h4>
                          <dl className="space-y-1 text-sm">
                            <div>
                              <dt className="text-readout">ID:</dt>
                              <dd className="font-mono text-xs">{model.id}</dd>
                            </div>
                            {model.architecture && (
                              <div>
                                <dt className="text-readout">Architecture:</dt>
                                <dd>{model.architecture}</dd>
                              </div>
                            )}
                            {model.modality && (
                              <div>
                                <dt className="text-readout">Modality:</dt>
                                <dd>{model.modality}</dd>
                              </div>
                            )}
                          </dl>
                        </div>

                        {/* Right Column */}
                        <div>
                          <h4 className="font-semibold mb-2">Capabilities</h4>
                          <div className="flex flex-wrap gap-2">
                            {model.capability_badges?.map((badge) => (
                              <span
                                key={badge.id}
                                className={`badge border ${getCapabilityBadgeStyle(badge)}`}
                              >
                                {badge.icon} {badge.label}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>

                      {model.description && (
                        <div className="mt-4 pt-4 border-t border-base-300">
                          <h4 className="font-semibold mb-2">Description</h4>
                          <p className="text-sm text-readout">{model.description}</p>
                        </div>
                      )}

                      <div className="mt-4 flex justify-end">
                        <button
                          onClick={() => onSelectModel(model)}
                          className="btn btn-primary btn-sm"
                        >
                          Select This Model
                        </button>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center">
          <Pagination
            currentPage={currentPage}
            totalPages={totalPages}
            totalItems={totalItems}
            pageSize={pageSize}
            onPageChange={onPageChange}
            onPageSizeChange={onPageSizeChange}
            showPageSizeOptions={true}
            pageSizeOptions={[10, 25, 50, 100]}
            showTotalItems={true}
          />
        </div>
      )}
    </div>
  )
}

export default ModelTable
