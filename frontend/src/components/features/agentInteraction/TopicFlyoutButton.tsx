/**
 * TopicFlyoutButton Component
 *
 * Displays a button that opens a flyout menu listing all available meta-topics.
 * Users select a meta-topic to drive the macro keyboard's M-key / F-key display.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { Layers, ChevronDown } from 'lucide-react';
import { useSystemMacrosStore } from '@/stores/macroSetsStore';
import type { SystemMetaTopic } from '@/types/macros';

interface TopicFlyoutButtonProps {
  className?: string;
  size?: 'sm' | 'md';
  label?: string;
  dropdownUp?: boolean;
  // THE BUILD FIX (2026-08-26, the tsc -b tail): the ChatInterface
  // passes the namespace to scope the topics.
  namespace?: string;
  // THE BANK (2026-09-03, the akeys Phase 5b): which macro bank this
  // selector drives. 'f' (default) = the F/M topic (selectMetaTopic);
  // 'a' = the ACTION-KEY source (setAKeysDefault — select IS persist,
  // no separate default step). The store's ACTIVE SURFACE scopes the
  // persisted key either way.
  bank?: 'f' | 'a';
  // ICON-ONLY (2026-09-03, the akeys Phase 5b): the keyboard-attached
  // selectors — a tiny glyph (no label pill); the tooltip carries the
  // state readout ("F topic: X" / "A source: Y").
  iconOnly?: boolean;
}

export function TopicFlyoutButton({
  className = '',
  size = 'md',
  label = 'Topic',
  dropdownUp = false,
  bank = 'f',
  iconOnly = false,
}: TopicFlyoutButtonProps) {
  const {
    metaTopics,
    isLoadingMetaTopics,
    selectedMetaTopicId,
    aKeysMetaTopicId,
    loadMetaTopics,
    selectMetaTopic,
    setAKeysDefault,
  } = useSystemMacrosStore();

  // THE BANK RESOLUTION (2026-09-03): the A-bank reads its OWN source
  // (aKeysMetaTopicId), never the F/M selection — the conflation guard
  // holds inside the selector too.
  const activeId = bank === 'a' ? aKeysMetaTopicId : selectedMetaTopicId

  const dropdownRef = useRef<HTMLDivElement>(null);

  const [flyoutOpen, setFlyoutOpen] = useState(false);

  const toggleFlyout = useCallback(() => setFlyoutOpen((prev) => !prev), []);
  const closeFlyout = useCallback(() => setFlyoutOpen(false), []);

  // Fetch meta-topics on mount
  useEffect(() => {
    if (metaTopics.length === 0 && !isLoadingMetaTopics) {
      loadMetaTopics();
    }
  }, [metaTopics.length, isLoadingMetaTopics, loadMetaTopics]);

  // Close flyout on outside click
  const handleClickOutside = useCallback(
    (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        closeFlyout();
      }
    },
    [closeFlyout]
  );

  useEffect(() => {
    if (flyoutOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    } else {
      document.removeEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [flyoutOpen, handleClickOutside]);

  // Close on Escape
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && flyoutOpen) closeFlyout();
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [flyoutOpen, closeFlyout]);

  const handleSelect = (id: number) => {
    if (bank === 'a') {
      // select IS persist — the A source is set + saved in one act
      setAKeysDefault(id);
    } else {
      selectMetaTopic(id);
    }
    closeFlyout();
  };

  const sizeClasses = size === 'sm' ? 'px-2 py-1 text-xs' : 'px-3 py-1.5 text-sm';

  // THE BANK STATE READOUT (2026-09-05, the user's redesign — "the
  // selected INTO the default"): ONE concept per bank. Picking =
  // active + persisted (the A-bank's model, now shared by the
  // F-bank); the separate starred default is gone from the UI (the
  // store's key + the load-ladder rung remain — a stale star still
  // works as the no-selection fallback, it just can't be set here).
  // The TOOLTIP = the short state readout ('F topic: X' / 'A source:
  // Y' / 'none'); the FLYOUT HEADER = the fuller state line; the
  // list = ONE marker grammar (current item highlighted + tagged).
  const activeMetaTopic = activeId
    ? metaTopics.find((mt) => mt.id === activeId) ?? null
    : null;
  const bankLabel = bank === 'a' ? 'A source' : 'F topic';
  const tipText = `${bankLabel}: ${activeMetaTopic?.name ?? 'none'}`;

  return (
    <div className={`relative inline-block ${className}`} ref={dropdownRef}>
      {/* Trigger Button */}
      <div className="tooltip tooltip-top" data-tip={tipText}>
        <button
          type="button"
          onClick={toggleFlyout}
          className={
            iconOnly
              ? [
                  'inline-flex items-center justify-center',
                  'rounded-[var(--badge-btn-radius)]',
                  'text-[var(--badge-btn-text)]',
                  'border border-[var(--badge-btn-border)]',
                  'hover:bg-[var(--badge-btn-hover-bg)]',
                  'transition-all',
                  size === 'sm' ? 'w-6 h-6' : 'w-7 h-7',
                ].join(' ')
              : [
                  'inline-flex items-center gap-1.5',
                  'rounded-[var(--badge-btn-radius)]',
                  'font-medium',
                  'bg-[var(--badge-btn-bg)]',
                  'text-[var(--badge-btn-text)]',
                  'border border-[var(--badge-btn-border)]',
                  'hover:bg-[var(--badge-btn-hover-bg)]',
                  'transition-all',
                  sizeClasses,
                ].join(' ')
          }
          aria-label={`${bankLabel}: ${activeMetaTopic?.name ?? 'none'}`}
          aria-expanded={flyoutOpen}
          aria-haspopup="listbox"
        >
          <Layers className="w-3.5 h-3.5" />
          {!iconOnly && (
            <>
              <span>{activeMetaTopic?.name || label}</span>
              <ChevronDown className={`w-3 h-3 transition-transform duration-200 ${flyoutOpen ? 'rotate-180' : ''}`} />
            </>
          )}
        </button>
      </div>

      {/* Flyout Menu */}
      {flyoutOpen && (
        <div
          className={[
            'absolute z-50',
            dropdownUp ? 'bottom-full mb-1 left-0' : 'left-0 top-full mt-1',
            'w-72 max-h-96 overflow-y-auto',
            'bg-[var(--flyout-panel-bg)]',
            'border border-[var(--flyout-panel-border)]',
            'text-[var(--flyout-panel-text)]',
            'rounded-lg shadow-lg',
            'animate-in fade-in slide-in-from-top-2 duration-200',
          ].join(' ')}
          role="listbox"
          aria-label="Meta topics"
        >
          {/* Header — THE STATE LINE (2026-09-05): just the current
              topic; the picker itself is the affordance. */}
          <div className="px-3 py-2 border-b border-base-300">
            <p className="text-xs font-semibold text-readout uppercase tracking-wider">
              {bank === 'a' ? 'A-Key Source' : 'F-Key Topic'}
            </p>
            <p className="text-xs mt-0.5 leading-relaxed">
              Current:{' '}
              {activeMetaTopic ? (
                <span className="font-medium text-base-content">{activeMetaTopic.name}</span>
              ) : (
                <span className="text-readout">none</span>
              )}
            </p>
          </div>

          {/* Loading State */}
          {isLoadingMetaTopics && (
            <div className="px-3 py-4 text-center text-sm text-readout">
              <div className="inline-block w-4 h-4 border-2 border-base-content/30 border-t-primary rounded-full animate-spin mr-2" />
              Loading meta-topics...
            </div>
          )}

          {/* Empty State */}
          {!isLoadingMetaTopics && metaTopics.length === 0 && (
            <div className="px-3 py-4 text-center text-sm text-readout">
              No meta-topics available — create one in the Macros page
            </div>
          )}

          {/* Meta-Topics List */}
          {!isLoadingMetaTopics &&
            metaTopics.map((metaTopic: SystemMetaTopic) => {
              const isSelected = activeId === metaTopic.id;
              return (
                <button
                  key={metaTopic.id}
                  type="button"
                  onClick={() => handleSelect(metaTopic.id)}
                  role="option"
                  aria-selected={isSelected}
                  className={[
                    'w-full text-left px-3 py-2.5',
                    'flex items-start gap-2.5',
                    'transition-colors duration-150',
                    'hover:bg-base-200',
                    'border-b border-base-200/50 last:border-b-0',
                    'border-l-2',
                    isSelected ? 'border-l-primary bg-primary/10' : 'border-l-transparent',
                  ].join(' ')}
                >
                  {/* Icon */}
                  <span className={['flex-shrink-0 mt-0.5', isSelected ? 'text-primary' : 'text-readout'].join(' ')}>
                    <Layers className="w-4 h-4" />
                  </span>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className={['text-sm font-medium truncate', isSelected ? 'text-primary' : 'text-base-content'].join(' ')}>
                        {metaTopic.name}
                      </span>
                      {isSelected && (
                        <span className="text-xs font-semibold text-primary">
                          {bank === 'a' ? 'Source' : 'Active'}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-readout mt-0.5 line-clamp-2">
                      {metaTopic.description}
                    </p>
                  </div>
                </button>
              );
            })}
        </div>
      )}
    </div>
  );
}

export default TopicFlyoutButton;
