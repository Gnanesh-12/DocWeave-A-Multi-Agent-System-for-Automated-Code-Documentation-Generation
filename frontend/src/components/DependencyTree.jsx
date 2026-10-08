import React from 'react'

const TYPE_LABELS = { class: 'class', method: 'method', function: 'func', constructor: 'ctor' }

function groupByFile(nodes) {
  const groups = {}
  for (const n of nodes) {
    if (!groups[n.file]) groups[n.file] = []
    groups[n.file].push(n)
  }
  return groups
}

export default function DependencyTree({ nodes, edges, onNavigateToFile }) {
  const groups = groupByFile(nodes)
  const nodeById = new Map(nodes.map((n) => [n.id, n]))
  const depsFor = (id) =>
    edges
      .filter((e) => e.source === id)
      .map((e) => nodeById.get(e.target))
      .filter(Boolean)

  return (
    <div style={{ maxHeight: '600px', overflowY: 'auto', padding: '24px' }}>
      {Object.entries(groups).map(([file, fileNodes]) => (
        <div key={file} style={{ marginBottom: '32px' }}>
          <h4 
            style={{ 
              fontFamily: '"IBM Plex Mono", monospace', 
              fontSize: '0.8125rem', 
              color: 'var(--text-muted)', 
              borderBottom: '1px solid var(--border)', 
              paddingBottom: '8px', 
              marginBottom: '16px',
              cursor: 'pointer'
            }}
            onClick={() => onNavigateToFile && onNavigateToFile(file)}
            title="View in changes"
          >
            {file}
          </h4>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
            {fileNodes.map((n) => {
              const deps = depsFor(n.id)
              return (
                <li key={n.id} style={{ marginBottom: '12px', fontSize: '0.875rem' }}>
                  <span className="chip" style={{ marginRight: '8px', verticalAlign: 'middle' }}>
                    {TYPE_LABELS[n.type] || n.type}
                  </span>
                  <span style={{ 
                    fontFamily: '"IBM Plex Mono", monospace',
                    fontWeight: 500,
                    color: n.has_docstring ? 'var(--text)' : 'var(--err)',
                    verticalAlign: 'middle'
                  }}>
                    {n.label}
                  </span>
                  {deps.length > 0 && (
                    <ul style={{ 
                      listStyle: 'none', 
                      margin: '8px 0 0 24px', 
                      padding: 0, 
                      borderLeft: '1px solid var(--border)',
                      paddingLeft: '12px'
                    }}>
                      {deps.map((d) => (
                        <li key={d.id} style={{ 
                          fontFamily: '"IBM Plex Mono", monospace', 
                          fontSize: '0.8125rem', 
                          color: 'var(--text-muted)',
                          marginBottom: '4px'
                        }}>
                          <span style={{ color: 'var(--border-strong)', marginRight: '8px' }}>↳</span>
                          {d.label}
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              )
            })}
          </ul>
        </div>
      ))}
    </div>
  )
}
