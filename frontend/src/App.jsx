import SampleSizePanel from './components/SampleSizePanel'
import AnalyzePanel from './components/AnalyzePanel'

export default function App() {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-4 md:p-8">
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-cyan-400">Axiom Stats Tester</h1>
        <p className="text-gray-500 text-sm mt-1">
          Stats engine verification · API at localhost:8000
        </p>
      </header>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 items-start">
        <SampleSizePanel />
        <AnalyzePanel />
      </div>
    </div>
  )
}
