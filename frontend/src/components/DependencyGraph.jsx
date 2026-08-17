import { useEffect, useState } from 'react'
import DependencyTree from './DependencyTree.jsx'
import DependencyForceGraph from './DependencyForceGraph.jsx'
import { getDependencyGraph } from '../api.js'

export default function DependencyGraph() {
  const [view, setView] = useState('tree')
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    getDependencyGraph().then((result) => {
      if (result.status === 'success') {
        setData(result)
      } else {
        setError(result.message || 'Failed to load dependency graph')
      }
    })
  }, [])

  return (
    <div className="card">
      <div className="dep-header">
        <h2>Dependency Graph</h2>
        {data && (
          <div className="dep-toggle">
            <button className={view === 'tree' ? 'active' : ''} onClick={() => setView('tree')}>Tree</button>
            <button className={view === 'graph' ? 'active' : ''} onClick={() => setView('graph')}>Graph</button>
          </div>
        )}
      </div>

      {error && <p className="empty-state">{error}</p>}
      {!error && !data && <p className="empty-state">Loading dependency graph...</p>}
      {data && data.nodes.length === 0 && <p className="empty-state">No components found.</p>}

      {data && data.nodes.length > 0 && (
        view === 'tree' ? (
          <DependencyTree nodes={data.nodes} edges={data.edges} />
        ) : (
          <DependencyForceGraph nodes={data.nodes} edges={data.edges} />
        )
      )}
    </div>
  )
}
