/**
 * MessagePreviewCard — the dashboard's Message Center card
 * (2026-08-25, the roadmap's Phase 3): the recent 5 messages +
 * the unread count + the "View all" link to the /messages page.
 */
import { useNavigate } from 'react-router-dom'
import { useMessageStore, selectUnreadCount, type SystemMessage } from '@/stores/messageStore'

function fmtTime(ts: number): string {
  const d = new Date(ts)
  return d.toLocaleString(undefined, { hour: '2-digit', minute: '2-digit' })
}

const TYPE_DOT: Record<string, string> = {
  info: 'bg-info',
  success: 'bg-success',
  warning: 'bg-warning',
  error: 'bg-error',
}

export default function MessagePreviewCard() {
  const messages = useMessageStore((s) => s.messages)
  const unreadCount = useMessageStore(selectUnreadCount)
  const navigate = useNavigate()

  const recent = messages.slice(0, 5)

  return (
    <div className="card bg-base-200 shadow-sm">
      <div className="card-body p-4">
        <div className="flex items-center justify-between mb-2">
          <h2 className="card-title text-sm">
            Messages
            {unreadCount > 0 && (
              <span className="badge badge-error badge-outline badge-sm">{unreadCount} unread</span>
            )}
          </h2>
          <button
            className="btn btn-outline btn-xs"
            onClick={() => navigate('/messages')}
          >
            View all
          </button>
        </div>

        {recent.length === 0 ? (
          <p className="text-xs text-readout py-2">
            No messages yet — the system notifications land here.
          </p>
        ) : (
          <ul className="space-y-1.5">
            {recent.map((m: SystemMessage) => (
              <li
                key={m.id}
                className={`flex items-center gap-2 text-xs ${m.read ? 'opacity-60' : ''}`}
              >
                <span className={`w-2 h-2 rounded-full flex-shrink-0 ${TYPE_DOT[m.type] ?? 'bg-base-content/30'}`} />
                <span className="font-medium truncate flex-1">{m.title}</span>
                <span className="text-readout whitespace-nowrap">{fmtTime(m.timestamp)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
