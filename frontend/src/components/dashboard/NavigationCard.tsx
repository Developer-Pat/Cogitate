import { Link } from 'react-router-dom'

interface NavigationCardProps {
  icon: React.ReactNode
  title: string
  description: string
  to: string
}

export default function NavigationCard({ icon, title, description, to }: NavigationCardProps) {
  return (
    <Link
      to={to}
      className="card bg-base-100 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)] hover:shadow-xl transition-all duration-[var(--button-transition)] hover:-translate-y-1 group"
    >
      <div className="card-body gap-[var(--card-gap)]">
        <div className="w-14 h-14 rounded-full flex items-center justify-center bg-primary/10 text-primary mb-3 group-hover:bg-primary/20 transition-colors duration-[var(--button-transition)]">
          {icon}
        </div>
        <h3 className="card-title text-lg">{title}</h3>
        <p className="text-sm text-readout leading-relaxed">{description}</p>
        <div className="card-actions justify-end mt-2">
          <span className="btn btn-ghost btn-sm rounded-[var(--button-radius)] gap-1 text-primary group-hover:gap-2 transition-all duration-[var(--button-transition)]">
            Open
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </span>
        </div>
      </div>
    </Link>
  )
}
