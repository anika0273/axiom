import { Link, useNavigate } from 'react-router-dom'
import { Home, ArrowLeft } from 'lucide-react'
import Button from '../components/ui/Button'

export default function NotFound() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-deep flex items-center justify-center px-6">
      <div className="text-center max-w-md">
        <p className="font-mono text-[80px] font-medium text-subtle leading-none mb-4">
          404
        </p>
        <h1 className="font-display text-2xl font-bold text-primary mb-2">
          Page not found
        </h1>
        <p className="text-secondary text-sm leading-relaxed mb-8">
          The page you're looking for doesn't exist or has been moved.
          Check the URL or navigate back to the dashboard.
        </p>
        <div className="flex items-center justify-center gap-3">
          <Button variant="ghost" onClick={() => navigate(-1)}>
            <ArrowLeft size={15} />
            Go back
          </Button>
          <Link to="/">
            <Button>
              <Home size={15} />
              Dashboard
            </Button>
          </Link>
        </div>
      </div>
    </div>
  )
}
