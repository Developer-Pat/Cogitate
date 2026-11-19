import type { LogEntry } from '@/types'
import { frontendLoggingService } from '@/services/frontendLoggingService'
import { getLevelBadge } from './levelBadge'

interface LogDetailsModalProps {
  selectedLog: LogEntry | null
  onClose: () => void
}

export default function LogDetailsModal({
  selectedLog,
  onClose
}: LogDetailsModalProps) {
  if (!selectedLog) return null

  const copyToClipboard = async (text: string, label: string) => {
    try {
      await navigator.clipboard.writeText(text)
      frontendLoggingService.info('LogDetailsModal', `${label} copied`)
    } catch (err) {
      frontendLoggingService.error('LogDetailsModal', 'Failed to copy', err as Error)
    }
  }


  return (
    <div className="modal modal-open" onClick={onClose}>
      <div className="modal-box max-w-3xl bg-base-100 text-base-content" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-start mb-6 pb-4 border-b border-base-200">
          <h3 className="font-bold text-xl text-base-content">Log Details</h3>
          <button className="btn btn-ghost btn-sm btn-circle text-base-content hover:bg-base-200 transition-all duration-[var(--button-transition)]" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="space-y-4">
          {/* Level & Source */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-label uppercase">Level</label>
              <div className={`badge ${getLevelBadge(selectedLog.level).cls} mt-1`}>
                {selectedLog.level.toUpperCase()}
              </div>
            </div>
            <div>
              <label className="text-xs font-semibold text-label uppercase">Source</label>
              <p className="font-medium mt-1 text-base-content">{selectedLog.source}</p>
            </div>
          </div>

          {/* Timestamp */}
          <div>
            <label className="text-xs font-semibold text-label uppercase">Timestamp</label>
            <div className="flex items-center gap-2 mt-1">
              <code className="text-sm bg-base-200 text-base-content px-3 py-2 rounded font-mono">
                {new Date(selectedLog.timestamp).toLocaleString()}
              </code>
              <div className="tooltip tooltip-top" data-tip="Copy to clipboard">
                <button
                  className="btn btn-outline btn-xs rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                  onClick={() => copyToClipboard(selectedLog.timestamp, 'Timestamp')}
                >
                  📋 Copy
                </button>
              </div>
            </div>
          </div>

          {/* Message */}
          <div>
            <label className="text-xs font-semibold text-label uppercase">Message</label>
            <div className="flex items-start gap-2 mt-1">
              <div className="bg-base-200 text-base-content p-3 rounded flex-1">
                <p className="font-medium">{selectedLog.message}</p>
              </div>
              <div className="tooltip tooltip-top" data-tip="Copy to clipboard">
                <button
                  className="btn btn-outline btn-sm shrink-0 rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                  onClick={() => copyToClipboard(selectedLog.message, 'Message')}
                >
                  📋 Copy
                </button>
              </div>
            </div>
          </div>

          {/* Metadata */}
          {selectedLog.trace_id && (
            <div>
              <label className="text-xs font-semibold text-label uppercase">Trace ID</label>
              <div className="flex items-center gap-2 mt-1">
                <code className="text-sm bg-base-200 text-base-content px-3 py-2 rounded font-mono flex-1">
                  {selectedLog.trace_id}
                </code>
                <div className="tooltip tooltip-top" data-tip="Copy to clipboard">
                  <button
                    className="btn btn-outline btn-xs rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                    onClick={() => copyToClipboard(selectedLog.trace_id || '', 'Trace ID')}
                  >
                    📋 Copy
                  </button>
                </div>
              </div>
            </div>
          )}

          {selectedLog.sessionId && (
            <div>
              <label className="text-xs font-semibold text-label uppercase">Session ID</label>
              <div className="flex items-center gap-2 mt-1">
                <code className="text-sm bg-base-200 text-base-content px-3 py-2 rounded font-mono flex-1">
                  {selectedLog.sessionId}
                </code>
                <div className="tooltip tooltip-top" data-tip="Copy to clipboard">
                  <button
                    className="btn btn-outline btn-xs rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                    onClick={() => copyToClipboard(selectedLog.sessionId || '', 'Session ID')}
                  >
                    📋 Copy
                  </button>
                </div>
              </div>
            </div>
          )}

          {selectedLog.url && (
            <div>
              <label className="text-xs font-semibold text-label uppercase">URL</label>
              <div className="flex items-start gap-2 mt-1">
                <code className="text-xs bg-base-200 text-base-content px-3 py-2 rounded flex-1 break-all font-mono">
                  {selectedLog.url}
                </code>
                <div className="tooltip tooltip-top" data-tip="Copy to clipboard">
                  <button
                    className="btn btn-outline btn-xs shrink-0 rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                    onClick={() => copyToClipboard(selectedLog.url || '', 'URL')}
                  >
                    📋 Copy
                  </button>
                </div>
              </div>
            </div>
          )}

          {selectedLog.user_agent && (
            <div>
              <label className="text-xs font-semibold text-label uppercase">User Agent</label>
              <p className="text-xs bg-base-200 text-base-content p-3 rounded mt-1 font-mono">{selectedLog.user_agent}</p>
            </div>
          )}

          {/* Context */}
          {selectedLog.context && Object.keys(selectedLog.context).length > 0 && (
            <div>
              <label className="text-xs font-semibold text-label uppercase">Context</label>
              <div className="flex gap-2 mt-1">
                <pre className="text-xs bg-base-200 text-base-content p-3 rounded flex-1 max-h-64 overflow-y-auto font-mono">
                  {JSON.stringify(selectedLog.context, null, 2)}
                </pre>
                <div className="tooltip tooltip-top" data-tip="Copy to clipboard">
                  <button
                    className="btn btn-outline btn-sm self-start rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                    onClick={() => copyToClipboard(JSON.stringify(selectedLog.context, null, 2), 'Context')}
                  >
                    📋 Copy
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="modal-action mt-6 pt-4 border-t border-base-200">
          <button className="btn btn-primary rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  )
}
