/**
 * Teams Table Component
 *
 * Displays teams in a table format with name, members, tools, and actions.
 */

import React from 'react'
import type { Collection } from '@/types/collections'

interface TeamsTableProps {
  teams: Collection[]
  onOpen: (id: string) => void
  onEdit: (team: Collection) => void
  onDelete: (team: Collection) => void
}

export const TeamsTable: React.FC<TeamsTableProps> = ({
  teams,
  onOpen,
  onEdit,
  onDelete,
}) => {
  return (
    <div className="overflow-x-auto bg-base-100 border border-base-300 rounded-lg">
      <table className="table table-zebra w-full">
        <thead>
          <tr>
            <th className="w-10"></th>
            <th>Name</th>
            <th>Description</th>
            <th className="w-24">Members</th>
            <th className="w-24">Updated</th>
            <th className="w-40 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {teams.map((team) => (
            <tr
              key={team.id}
              className="hover:bg-base-200 cursor-pointer"
              onClick={() => onOpen(team.id)}
            >
              <td className="text-2xl">{team.icon}</td>
              <td>
                <div className="font-medium">{team.name}</div>
              </td>
              <td className="text-sm text-readout">
                {team.description || <span className="text-readout">—</span>}
              </td>
              <td>
                <span className="badge badge-ghost badge-sm">
                  {team.item_count}
                </span>
              </td>
              <td className="text-sm text-readout">
                {new Date(team.updated_at).toLocaleDateString()}
              </td>
              <td className="text-right">
                <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                  <button
                    onClick={() => onOpen(team.id)}
                    className="btn btn-ghost btn-xs"
                    data-tip="Open"
                  >
                    Open
                  </button>
                  <button
                    onClick={() => onEdit(team)}
                    className="btn btn-ghost btn-xs"
                    data-tip="Edit"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                  </button>
                  <button
                    onClick={() => onDelete(team)}
                    className="btn btn-ghost btn-xs text-error"
                    data-tip="Delete"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
