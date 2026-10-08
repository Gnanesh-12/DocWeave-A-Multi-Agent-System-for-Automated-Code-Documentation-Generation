import React, { useEffect, useState } from 'react'
import DependencyTree from './DependencyTree.jsx'
import DependencyForceGraph from './DependencyForceGraph.jsx'
import { getDependencyGraph } from '../api.js'

export default function DependencyGraph({ onNavigateToFile }) {
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
    }).catch(err => {
      setError(err.message || 'Failed to load dependency graph')
    })
  }, [])

  if (error) {
    return <div style={{ color: 'var(--err)', padding: '24px' }}>{error}</div>
  }

  if (!data) {
    return <div style={{ color: 'var(--text-muted)', padding: '24px' }}>Loading dependency graph...</div>
  }

  if (data.nodes.length === 0) {
    return <div style={{ color: 'var(--text-muted)', padding: '24px' }}>No components found.</div>
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div className="segmented-control">
          <button aria-selected={view === 'tree'} onClick={() => setView('tree')}>Tree view</button>
          <button aria-selected={view === 'graph'} onClick={() => setView('graph')}>Graph view</button>
        </div>
        
        <div style={{ display: 'flex', gap: '16px', fontSize: '0.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--ok)' }}></div>
            Documented
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--err)' }}></div>
            Undocumented / Failed
          </div>
        </div>
      </div>

      <div className="graph-container">
        {view === 'tree' ? (
          <DependencyTree nodes={data.nodes} edges={data.edges} onNavigateToFile={onNavigateToFile} />
        ) : (
          <DependencyForceGraph nodes={data.nodes} edges={data.edges} onNavigateToFile={onNavigateToFile} />
        )}
      </div>
    </div>
  )
}
