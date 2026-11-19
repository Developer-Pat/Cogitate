import { Link } from 'react-router-dom'
import { usePageTitle } from '../hooks/usePageTitle'

export default function NotFound() {
  usePageTitle('Not Found', 'Page not found')
  
  return (
    <div className="hero min-h-screen bg-base-200">
      <div className="hero-content text-center">
        <div className="max-w-md">
          <div className="text-9xl font-bold text-primary mb-4">404</div>
          <h1 className="text-5xl font-bold mb-4">Page Not Found</h1>
          <p className="mb-6">
            Sorry, the page you are looking for doesn't exist or has been moved.
          </p>
          <div className="flex gap-4 justify-center">
            <Link to="/" className="btn btn-primary rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]">
              Go Home
            </Link>
            <Link to="/logs" className="btn btn-outline rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]">
              View Logs
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
