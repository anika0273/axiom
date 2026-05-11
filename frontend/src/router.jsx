import { lazy, Suspense } from 'react'
import { createBrowserRouter, useRouteError, Link } from 'react-router-dom'
import LoadingSpinner from './components/ui/LoadingSpinner'

const Home = lazy(() => import('./pages/Home'))
const ExperimentList = lazy(() => import('./pages/ExperimentList'))
const NewExperiment = lazy(() => import('./pages/NewExperiment'))
const ExperimentResults = lazy(() => import('./pages/ExperimentResults'))
const StakeholderReport = lazy(() => import('./pages/StakeholderReport'))
const Demo = lazy(() => import('./pages/Demo'))
const DemoExperimentResults = lazy(() => import('./pages/DemoExperimentResults'))
const NotFound = lazy(() => import('./pages/NotFound'))

function PageFallback() {
  return (
    <div
      className="min-h-screen flex items-center justify-center"
      style={{ backgroundColor: 'var(--color-bg-deep)' }}
    >
      <LoadingSpinner size={32} />
    </div>
  )
}

function RouteError() {
  const error = useRouteError()
  const message =
    error?.statusText ?? error?.message ?? 'An unexpected error occurred.'

  return (
    <div className="min-h-screen bg-deep flex items-center justify-center px-6">
      <div className="text-center max-w-md">
        <p className="font-mono text-4xl font-medium text-subtle mb-4">Error</p>
        <h1 className="font-display text-xl font-bold text-primary mb-2">
          Something went wrong
        </h1>
        <p className="text-secondary text-sm mb-8">{message}</p>
        <Link
          to="/"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-blue text-white text-sm font-medium hover:brightness-110 transition-all shadow-glow"
        >
          Back to Dashboard
        </Link>
      </div>
    </div>
  )
}

const router = createBrowserRouter([
  {
    path: '/',
    element: <Suspense fallback={<PageFallback />}><Home /></Suspense>,
    errorElement: <RouteError />,
  },
  {
    path: '/experiments',
    element: <Suspense fallback={<PageFallback />}><ExperimentList /></Suspense>,
    errorElement: <RouteError />,
  },
  {
    path: '/experiments/new',
    element: <Suspense fallback={<PageFallback />}><NewExperiment /></Suspense>,
    errorElement: <RouteError />,
  },
  {
    path: '/experiments/:id',
    element: <Suspense fallback={<PageFallback />}><ExperimentResults /></Suspense>,
    errorElement: <RouteError />,
  },
  {
    path: '/experiments/:id/report',
    element: <Suspense fallback={<PageFallback />}><StakeholderReport /></Suspense>,
    errorElement: <RouteError />,
  },
  {
    path: '/demo',
    element: <Suspense fallback={<PageFallback />}><Demo /></Suspense>,
    errorElement: <RouteError />,
  },
  {
    path: '/demo/:name',
    element: <Suspense fallback={<PageFallback />}><DemoExperimentResults /></Suspense>,
    errorElement: <RouteError />,
  },
  {
    path: '*',
    element: <Suspense fallback={<PageFallback />}><NotFound /></Suspense>,
  },
])

export default router
