import { createBrowserRouter, useRouteError, Link } from 'react-router-dom'
import Home from './pages/Home'
import ExperimentList from './pages/ExperimentList'
import NewExperiment from './pages/NewExperiment'
import ExperimentResults from './pages/ExperimentResults'
import StakeholderReport from './pages/StakeholderReport'
import Demo from './pages/Demo'
import DemoExperimentResults from './pages/DemoExperimentResults'
import NotFound from './pages/NotFound'

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
    element: <Home />,
    errorElement: <RouteError />,
  },
  {
    path: '/experiments',
    element: <ExperimentList />,
    errorElement: <RouteError />,
  },
  {
    path: '/experiments/new',
    element: <NewExperiment />,
    errorElement: <RouteError />,
  },
  {
    path: '/experiments/:id',
    element: <ExperimentResults />,
    errorElement: <RouteError />,
  },
  {
    path: '/experiments/:id/report',
    element: <StakeholderReport />,
    errorElement: <RouteError />,
  },
  {
    path: '/demo',
    element: <Demo />,
    errorElement: <RouteError />,
  },
  {
    path: '/demo/:name',
    element: <DemoExperimentResults />,
    errorElement: <RouteError />,
  },
  {
    path: '*',
    element: <NotFound />,
  },
])

export default router
