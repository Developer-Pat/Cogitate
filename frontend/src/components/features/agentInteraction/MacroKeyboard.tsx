/**
 * MacroKeyboard Component
 * Compact keyboard-style buttons for F-keys (topic macros), A-keys (actions), and M-keys (topics).
 * Uses topic selector data — independent from the old chatMacrosStore.
 */

import { useState, useRef, useEffect } from 'react'
import type { SystemMetaTopic, SystemMacroSet } from '@/types/macros'
import { TopicFlyoutButton } from './TopicFlyoutButton'

interface MacroKeyboardProps {
  onMacroSelect: (value: string) => void
  disabled?: boolean
  compact?: boolean
  metaTopics: SystemMetaTopic[]
  selectedMetaTopicId: number | null
  selectMetaTopic: (id: number) => void
  macros?: SystemMacroSet[]
  // THE A-KEY SOURCE (2026-09-03, the akeys roadmap Phase 2): the
  // resolved meta-topic feeding the A1-A5 flyouts (the store's
  // aKeysMetaTopicId). null = deactivated (no source configured).
  aKeysMetaTopicId?: number | null
  // THE AFTER-A-KEYS SLOT (2026-09-03, the user's ask): the Exa page
  // renders its ACP trio (commands doc + ACP + history) right after
  // the A selector — passed in, spaced by the caller.
  afterAKeys?: React.ReactNode
}


const F_KEYS = ['F1', 'F2', 'F3', 'F4', 'F5'] as const

/** The topic_mappings' union-narrowing (2026-08-26, the tsc -b —
 * the mappings can be a plain string OR {topic, slot_start} OR a
 * SystemMetaTopic; the property access needs the guard). */
function mappingTopic(m: unknown): string {
  if (typeof m === 'string') return m
  if (m && typeof m === 'object' && 'topic' in m) return String((m as { topic?: unknown }).topic ?? '')
  if (m && typeof m === 'object' && 'name' in m) return String((m as { name?: unknown }).name ?? '')
  return ''
}


export default function MacroKeyboard({
  onMacroSelect,
  disabled = false,
  compact = false,
  metaTopics,
  selectedMetaTopicId,
  selectMetaTopic,
  macros = [],
  aKeysMetaTopicId = null,
  afterAKeys,
}: MacroKeyboardProps) {
  const [topicMappingIndex, setTopicMappingIndex] = useState(0)
  // Reset topic mapping index when meta-topic changes
  const prevMetaTopicIdRef = useRef(selectedMetaTopicId)
  useEffect(() => {
    if (prevMetaTopicIdRef.current !== selectedMetaTopicId) {
      setTopicMappingIndex(0)
      prevMetaTopicIdRef.current = selectedMetaTopicId
    }
  }, [selectedMetaTopicId])

  const selectedTopic = selectedMetaTopicId
    ? metaTopics.find((mt) => mt.id === selectedMetaTopicId) ?? null
    : null

  // Get macro values from the selected topic's macro sets
  const getTopicMacro = (fIndex: number): string | null => {
    if (!selectedTopic || !selectedTopic.topic_mappings) return null
    const topicMappings = selectedTopic.topic_mappings
    if (topicMappings.length === 0) return null
    const mapping = topicMappings[topicMappingIndex] || topicMappings[0]
    if (!mapping) return null
    const macroSet = macros.find((m) => m.topic === mappingTopic(mapping))
    if (!macroSet) return null
    const key = `f${fIndex + 1}_macro` as keyof SystemMacroSet
    return (macroSet[key] as string) || null
  }

  // THE A-KEY SOURCE (2026-09-03, the akeys roadmap Phase 2): the
  // A-source meta-topic (the store's aKeysMetaTopicId — its OWN
  // default, never the F/M selection). A1-A5 each = one of the
  // source's first-5 mapped macro sets; the flyout items = that
  // set's non-empty macros. Empty set / missing source = the slot
  // (or the whole row) deactivates — never arbitrary content.
  const aSourceTopic = aKeysMetaTopicId
    ? metaTopics.find((mt) => mt.id === aKeysMetaTopicId) ?? null
    : null

  interface AKeySlot {
    key: string
    /** The mapped topic name (the flyout's label) — '' = no mapping */
    label: string
    /** The prompts for this slot's flyout (non-empty macros) */
    items: string[]
  }

  const getAKeySlots = (): AKeySlot[] => {
    const slots: AKeySlot[] = []
    for (let i = 0; i < 5; i += 1) {
      const key = `A${i + 1}`
      if (!aSourceTopic?.topic_mappings) {
        slots.push({ key, label: '', items: [] })
        continue
      }
      const mapping = aSourceTopic.topic_mappings[i]
      if (!mapping) {
        slots.push({ key, label: '', items: [] })
        continue
      }
      const label = mappingTopic(mapping)
      const macroSet = macros.find((m) => m.topic === label)
      if (!macroSet) {
        slots.push({ key, label, items: [] })
        continue
      }
      const items = ['f1_macro', 'f2_macro', 'f3_macro', 'f4_macro', 'f5_macro']
        .map((k) => (macroSet[k as keyof SystemMacroSet] as string) || '')
        .filter((v) => v.trim() !== '')
      slots.push({ key, label, items })
    }
    return slots
  }

  const aKeySlots = getAKeySlots()
  const aSourceMissing = aKeysMetaTopicId === null || aSourceTopic === null

  if (compact) {
    return (
      <div className="flex items-center gap-2 flex-wrap">
        {/* Function Keys */}
        <div className="flex gap-0.5">
          {F_KEYS.map((key, i) => {
            const macroValue = getTopicMacro(i)
            return (
              <div key={key} className="tooltip tooltip-top" data-tip={macroValue || `${key}: Empty`}>
                <button
                  type="button"
                  onClick={() => {
                    if (macroValue && !disabled) onMacroSelect(macroValue)
                  }}
                  disabled={disabled}
                  className={`w-7 h-7 text-xs font-bold rounded border border-base-400 bg-base-200 hover:bg-base-300 active:bg-base-400 transition-colors flex items-center justify-center ${disabled || !macroValue ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                >
                  {key}
                </button>
              </div>
            )
          })}
        </div>

        {/* M Keys — topic/mapping selectors */}
        <div className="flex gap-0.5">
          {Array.from({ length: 5 }, (_, i) => {
            const mappings = selectedTopic?.topic_mappings?.length ? selectedTopic.topic_mappings : metaTopics.filter(mt => mt.namespace === 'agent')
            const mapping = mappings[i] || null
            const topicName = mapping
              ? mappingTopic(mapping)
              : ''
            const isActive = mapping && (selectedTopic?.topic_mappings?.length
              ? topicMappingIndex === i
              : selectedMetaTopicId === (mapping as any).id) // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
            const handleClick = () => {
              if (!mapping) return
              if (selectedTopic?.topic_mappings?.length) {
                setTopicMappingIndex(i)
              } else {
                selectMetaTopic((mapping as any).id) // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
              }
            }
            return (
              <div key={i} className="tooltip tooltip-top" data-tip={topicName || 'Empty slot'}>
                <button
                  type="button"
                  onClick={handleClick}
                  className={`px-1.5 py-0.5 text-xs font-semibold rounded transition-colors ${
                    isActive
                      ? 'bg-primary text-primary-content'
                      : topicName
                        ? 'bg-base-300 text-base-content hover:bg-base-400'
                        : 'bg-base-200 text-disabled cursor-default'
                  } ${disabled || !topicName ? 'opacity-50 cursor-not-allowed' : ''}`}
                  disabled={disabled || !topicName}
                >
                  M{i + 1}
                </button>
              </div>
            )
          })}
        </div>

        {/* THE F SELECTOR (2026-09-03, the akeys Phase 5b): direct
            selection for the F/M bank — the tiny icon after the M
            group; the tooltip reads the current F topic. Select =
            the new topic, persisted for this surface. */}
        <TopicFlyoutButton size="sm" bank="f" iconOnly={true} dropdownUp={true} />

        {/* A Keys — the ACTION-KEY BANK (2026-09-03, the akeys Phase 2):
            data-driven flyouts from the A-source meta-topic (the
            store's aKeysMetaTopicId). No source -> the row
            deactivates with the reason (never arbitrary content).
            THE A-UNIT (2026-09-03, the user's ask): the A keys + the
            A selector + the afterAKeys slot (the Exa ACP trio) wrap
            as ONE non-breaking group — the trio sits right after the
            A selector, never orphaned on its own line. */}
        <div className="flex items-center gap-1">
          <div className="flex gap-0.5">
          {aSourceMissing ? (
            <>
              <div
                className="tooltip tooltip-top"
                data-tip="No Action-key source — set one on the Macros page"
              >
                <button
                  type="button"
                  disabled
                  className="px-1.5 py-0.5 text-xs font-semibold rounded bg-base-200 text-disabled cursor-not-allowed"
                  aria-label="Action keys disabled — no source configured"
                >
                  A-keys
                </button>
              </div>
              {/* the visible reason — never a silent deactivation */}
              <span className="text-xs text-readout italic">
                No Action-key source — set one on the Macros page
              </span>
            </>
          ) : (
            aKeySlots.map((slot) => {
              const hasItems = slot.items.length > 0
              const hasMapping = slot.label !== ''
              return (
                <div key={slot.key} className={`dropdown dropdown-top dropdown-end ${hasItems ? '' : 'pointer-events-none'}`}>
                  <div
                    className="tooltip tooltip-top"
                    data-tip={hasMapping ? `${slot.label} (${slot.key})` : hasItems ? slot.key : `${slot.key}: Empty`}
                  >
                    <button
                      tabIndex={0}
                      type="button"
                      disabled={disabled || !hasItems}
                      className={`px-1.5 py-0.5 text-xs font-semibold rounded transition-colors ${
                        hasItems && !disabled
                          ? 'cursor-pointer'
                          : 'cursor-not-allowed opacity-50'
                      }`}
                      style={
                        hasItems && !disabled
                          ? {
                              backgroundColor: 'var(--highlight-bg)',
                              color: 'var(--highlight-text)',
                            }
                          : undefined
                      }
                      onMouseEnter={(e) => {
                        if (!hasItems || disabled) return
                        ;(e.currentTarget as HTMLElement).style.backgroundColor = 'color-mix(in oklch, var(--color-info) 35%, transparent)'
                      }}
                      onMouseLeave={(e) => {
                        if (!hasItems || disabled) return
                        ;(e.currentTarget as HTMLElement).style.backgroundColor = 'var(--highlight-bg)'
                      }}
                    >
                      {slot.key}
                    </button>
                  </div>
                  {hasItems && (
                    <ul tabIndex={0} className="dropdown-content z-[1] menu p-2 shadow bg-base-100 rounded-box w-64 max-h-72 overflow-y-auto">
                      {slot.items.map((item, itemIndex) => (
                        <li key={itemIndex}>
                          <a
                            onClick={() => {
                              onMacroSelect(item)
                              ;(document.activeElement as HTMLElement)?.blur()
                            }}
                          >
                            {item}
                          </a>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )
            })
          )}
          </div>
          {/* THE A SELECTOR (2026-09-03, the akeys Phase 5b): direct
              selection for the A-bank — the tiny icon beside the A
              keys; the tooltip reads the current A source. Select =
              the new source, persisted for this surface. */}
          <TopicFlyoutButton size="sm" bank="a" iconOnly={true} dropdownUp={true} />
          {/* THE AFTER-A-KEYS SLOT (2026-09-03, the user's ask): the
              caller's trailing controls (the Exa ACP trio) with a
              little space after the A selector. */}
          {afterAKeys && <div className="ml-1.5 flex items-center gap-1">{afterAKeys}</div>}
        </div>
      </div>
    )
  }

  // Full layout
  return (
    <div className="flex flex-col gap-3 p-3">
      {/* Function Keys */}
      <div>
        <div className="text-xs font-semibold text-readout uppercase mb-2">Function Keys (F1-F5)</div>
        <div className="grid grid-cols-5 gap-2">
          {F_KEYS.map((key, i) => {
            const macroValue = getTopicMacro(i)
            return (
              <div key={key} className="flex flex-col gap-1">
                <button
                  type="button"
                  onClick={() => {
                    console.log('F-key clicked', { i, macroValue })
                    if (macroValue) onMacroSelect(macroValue)
                  }}
                  disabled={disabled || !macroValue}
                  className={`btn btn-sm h-auto min-h-fit py-2 px-2 text-xs font-bold ${
                    disabled ? 'btn-disabled' : macroValue ? 'btn-outline' : 'btn-disabled opacity-50'
                  }`}
                  title={macroValue ? `Click to use\n${macroValue}` : `${key}: Empty`}
                >
                  {key}
                </button>
                <div className="text-xs text-readout line-clamp-2 px-1">
                  {macroValue || '(empty)'}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* A Keys — the ACTION-KEY BANK (2026-09-03, the akeys Phase 2):
          the same data-driven flyouts as the compact layout — one
          source, both layouts agree. */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <div className="text-xs font-semibold text-readout uppercase">Action Keys (A1-A5)</div>
          {/* THE A SELECTOR (Phase 5b): direct selection for the A-bank */}
          <TopicFlyoutButton size="sm" bank="a" iconOnly={true} dropdownUp={true} />
        </div>
        {aSourceMissing ? (
          <div className="text-xs text-readout italic">
            No Action-key source — set one on the Macros page.
          </div>
        ) : (
          <div className="grid grid-cols-5 gap-2">
            {aKeySlots.map((slot) => {
              const hasItems = slot.items.length > 0
              return (
                <div key={slot.key} className="flex flex-col gap-1">
                  <div className={`dropdown dropdown-top dropdown-end ${hasItems ? '' : 'pointer-events-none'}`}>
                    <button
                      tabIndex={0}
                      type="button"
                      disabled={disabled || !hasItems}
                      className={`btn btn-sm h-auto min-h-fit py-2 px-2 text-xs font-bold ${
                        hasItems && !disabled ? 'btn-accent btn-outline' : 'btn-disabled opacity-50'
                      }`}
                      title={hasItems ? `${slot.label} (${slot.key})` : `${slot.key}: Empty`}
                    >
                      {slot.key}
                    </button>
                    {hasItems && (
                      <ul tabIndex={0} className="dropdown-content z-[1] menu p-2 shadow bg-base-100 rounded-box w-64 max-h-72 overflow-y-auto">
                        {slot.items.map((item, itemIndex) => (
                          <li key={itemIndex}>
                            <a
                              onClick={() => {
                                onMacroSelect(item)
                                ;(document.activeElement as HTMLElement)?.blur()
                              }}
                            >
                              {item}
                            </a>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <div className="text-xs text-readout line-clamp-2 px-1">
                    {slot.label || '(empty)'}
                  </div>
                </div>
              )
            })}
          </div>
        )}
        {afterAKeys && <div className="mt-2 flex items-center gap-1">{afterAKeys}</div>}
      </div>

      {/* M Keys — topic mapping selectors */}
      <div>
        <div className="text-xs font-semibold text-readout uppercase mb-2">Topic Keys (M1-M5)</div>
        <div className="flex gap-2 flex-wrap">
          {Array.from({ length: 5 }, (_, i) => {
            const mappings = selectedTopic?.topic_mappings?.length ? selectedTopic.topic_mappings : metaTopics.filter(mt => mt.namespace === 'agent')
            const mapping = mappings[i] || null
            const topicName = mapping
              ? mappingTopic(mapping)
              : ''
            const isActive = mapping && (selectedTopic?.topic_mappings?.length
              ? topicMappingIndex === i
              : selectedMetaTopicId === (mapping as any).id) // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
            const handleClick = () => {
              if (!mapping) return
              if (selectedTopic?.topic_mappings?.length) {
                setTopicMappingIndex(i)
              } else {
                selectMetaTopic((mapping as any).id) // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
              }
            }
            return (
            <button
              key={i}
              type="button"
              onClick={handleClick}
              className={`px-3 py-1.5 text-xs font-semibold rounded transition-colors ${
                isActive
                  ? 'bg-primary text-primary-content'
                  : 'bg-base-300 text-base-content hover:bg-base-400'
              } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
              disabled={disabled}
              title={topicName || 'Empty slot'}
            >
              M{i + 1}
            </button>
            )
          })}
        </div>
        {/* THE F SELECTOR (Phase 5b): direct selection for the F/M bank */}
        <div className="flex items-center gap-1.5 mt-2">
          <TopicFlyoutButton size="sm" bank="f" iconOnly={true} dropdownUp={true} />
          <span className="text-xs text-readout">change the F/M topic</span>
        </div>
      </div>
    </div>
  )
}
