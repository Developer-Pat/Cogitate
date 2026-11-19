/**
 * IssueAlerts - Display detected issues from log analysis
 */

import { useState } from 'react'
import type { IssueReport } from '@/services/domain/HistoryService'

interface IssueAlertsProps {
  issueReport?: IssueReport | null
}

export default function IssueAlerts({ issueReport }: IssueAlertsProps) {
  const [expanded, setExpanded] = useState(false)

  if (!issueReport || (issueReport.frequentErrors.length === 0 && issueReport.spikes.length === 0)) {
    return null
  }

  const hasIssues = issueReport.frequentErrors.length > 0 || issueReport.spikes.length > 0

  if (!hasIssues) {
    return (
      <div className="alert alert-success">
        <svg xmlns="http://www.w3.org/2000/svg" className="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span>No issues detected in the selected time range</span>
      </div>
    )
  }

  return (
    <div className="alert alert-warning">
      <svg xmlns="http://www.w3.org/2000/svg" className="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
      <div className="flex-1">
        <div className="font-semibold">
          {issueReport.frequentErrors.length > 0 && (
            <span>{issueReport.frequentErrors.length} frequent error(s) detected</span>
          )}
          {issueReport.spikes.length > 0 && (
            <span className="ml-2">
              {issueReport.spikes.length} message spike(s) detected
            </span>
          )}
        </div>
        {expanded && (
          <div className="mt-2 text-sm space-y-2">
            {issueReport.frequentErrors.length > 0 && (
              <div>
                <div className="font-medium text-error">Frequent Errors:</div>
                <ul className="list-disc list-inside ml-4">
                  {issueReport.frequentErrors.slice(0, 5).map((error, idx) => (
                    <li key={idx} className="font-mono text-xs">
                      {error.message} ({error.count}x)
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {issueReport.spikes.length > 0 && (
              <div>
                <div className="font-medium">Message Spikes:</div>
                <ul className="list-disc list-inside ml-4">
                  {issueReport.spikes.slice(0, 5).map((spike, idx) => (
                    <li key={idx} className="font-mono text-xs">
                      {spike.message} ({spike.count}x)
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
      <button
        className="btn btn-sm btn-ghost"
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? 'Show Less' : 'Show Details'}
      </button>
    </div>
  )
}
