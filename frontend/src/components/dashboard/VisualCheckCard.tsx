import { Link } from 'react-router-dom'

/**
 * VISUAL CHECK LINKS (2026-09-07, the token-vocabulary arc): the pages
 * whose look changed in the text-role + token work — the spot-check list
 * for the human eye (the Component Gallery, the info-blue depth chip,
 * the readout/disabled tiers, the semantic status chips, the primary
 * idioms). State-only, no dates.
 */
const CHECK_PAGES: { name: string; to: string; note: string }[] = [
  {
    name: 'Component Gallery',
    to: '/components',
    note: 'the whole vocabulary: controls, badges, the text roles, the theme palette — switch themes and it re-samples',
  },
  {
    name: 'Agent Profiles',
    to: '/agent-profiles',
    note: 'the depth chip = the info-blue outline for EVERY depth value (the text carries the depth)',
  },
  {
    name: 'Workflow Automation',
    to: '/workflow-automation',
    note: 'the Inactive pill = text-disabled at the dimmest tier; the row metadata = text-readout',
  },
  {
    name: 'Provider Dashboard',
    to: '/provider-dashboard',
    note: 'the status dots + pills on the semantic tokens, the DaisyUI spinners, the readout stats',
  },
  {
    name: 'Image Management',
    to: '/images',
    note: 'the metadata readouts (counts, sizes) on the named text-readout tier',
  },
  {
    name: 'Collections',
    to: '/collections',
    note: 'the selection rings + the icon-picker selected state on the primary idiom',
  },
  {
    name: 'Sounds',
    to: '/sounds',
    note: 'the size readouts on the text-readout tier',
  },
  {
    name: 'Workflow Templates',
    to: '/workflow-templates',
    note: 'the focus rings on ring-primary, the card chrome tokenized',
  },
]

export default function VisualCheckCard() {
  return (
    <div className="card bg-base-200 shadow-sm">
      <div className="card-body p-4">
        <h2 className="card-title text-sm">
          Visual Check Links
          <span
            className="tooltip tooltip-top"
            data-tip="The pages the 2026-09-07 token-vocabulary arc changed — spot-check them"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-3.5 w-3.5 text-readout"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          </span>
        </h2>
        <ul className="mt-1 space-y-1.5">
          {CHECK_PAGES.map((p) => (
            <li key={p.to} className="flex items-baseline gap-2 text-sm">
              <Link to={p.to} className="link link-primary link-hover shrink-0 font-medium">
                {p.name}
              </Link>
              <span className="text-xs text-readout truncate">{p.note}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
