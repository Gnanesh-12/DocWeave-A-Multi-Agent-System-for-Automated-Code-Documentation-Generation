import React, { useState, useEffect, useRef } from 'react'

const AGENTS = ['Reader', 'Searcher', 'Writer', 'Verifier']

function AgentPipeline({ activeAgent }) {
  const activeLower = (activeAgent || '').toLowerCase()
  return (
    <div className="card">
      <div className="card-header">
        <h2>Agent Pipeline</h2>
      </div>
      <div className="card-body">
        <div className="agent-pipeline">
          {AGENTS.map((agent, i) => {
            const activeIndex = AGENTS.findIndex(a => activeLower.includes(a.toLowerCase()))

            let statusClass = 'waiting'
            let icon = '○'
            let isActive = false

            if (activeIndex === i) {
              statusClass = 'active'
              icon = '●'
              isActive = true
            } else if (activeIndex > i || activeLower.includes('complete')) {
              statusClass = 'completed'
              icon = '✓'
            }

            return (
              <div key={agent} className={`agent-row ${isActive ? 'active' : ''}`}>
                <div className="agent-name">{agent}</div>
                <div className={`agent-status-icon ${statusClass}`}>{icon}</div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function LogViewer({ logs }) {
  const containerRef = useRef(null)
  const [autoScroll, setAutoScroll] = useState(true)

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [logs, autoScroll])

  const handleScroll = () => {
    if (!containerRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 10

    if (isAtBottom && !autoScroll) {
      setAutoScroll(true)
    } else if (!isAtBottom && autoScroll) {
      setAutoScroll(false)
    }
  }

  const formatTime = () => {
    const d = new Date()
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
  }

  return (
    <div className="card log-viewer-card">
      <div className="log-toolbar">
        <div>Logs</div>
        {!autoScroll && (
          <button style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem' }} onClick={() => {
            setAutoScroll(true)
            if (containerRef.current) {
              containerRef.current.scrollTop = containerRef.current.scrollHeight
            }
          }}>
            Jump to latest ↓
          </button>
        )}
      </div>
      <div className="log-scroll-area" ref={containerRef} onScroll={handleScroll}>
        {logs.length === 0 ? (
          <div style={{ color: '#858585', padding: '1rem' }}>Waiting for output...</div>
        ) : null}
        {logs.map((log, i) => {
          let lvl = (log.level || 'INFO').toUpperCase()
          if (lvl === 'WARNING') lvl = 'WARN'
          // Some logs from socket might just be strings in log.text
          const text = log.message || log.text || ''
          return (
            <div key={i} className="log-line">
              <div className="log-time">{log.time || formatTime()}</div>
              <div className={`log-level ${lvl}`}>{lvl}</div>
              <div className="log-msg">{text}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function RepoStructure({ repoStructure }) {
  if (!repoStructure || !repoStructure.tree) return null

  const renderTree = (node, depth = 0) => {
    if (!node) return null
    if (depth > 2) return null // Limit initial depth for perf
    return (
      <div key={node.path} style={{ paddingLeft: `${depth}rem` }}>
        <div className="tree-item">
          <div className="icon">{node.type === 'dir' ? '▾' : '📄'}</div>
          <div>{node.name}</div>
        </div>
        {node.children && node.children.map(c => renderTree(c, depth + 1))}
      </div>
    )
  }

  return (
    <div className="card">
      <div className="card-header">
        <h2>Repository Structure</h2>
      </div>
      <div className="card-body" style={{ padding: '0.5rem' }}>
        <div className="repo-tree-container">
          {renderTree(repoStructure.tree)}
        </div>
      </div>
    </div>
  )
}

function FileTable({ files }) {
  return (
    <div className="card">
      <div className="card-header">
        <h2>File Status</h2>
      </div>
      <div className="file-table-container">
        <table className="file-table">
          <thead>
            <tr>
              <th>File</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {files && files.slice(0, 20).map(f => (
              <tr key={f.file}>
                <td className="file-name">{f.file}</td>
                <td>
                  {f.status === 'complete' ? '✓' : f.status === 'in_progress' ? '●' : '—'}
                </td>
              </tr>
            ))}
            {(!files || files.length === 0) && (
              <tr><td colSpan="2" style={{ color: 'var(--text-muted)' }}>No files processed yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function DashboardView({ agentStatus, progress, repoStructure, logs, status }) {
  const total = progress.total_components || 0
  const processed = progress.processed_components || 0
  const percentNum = total > 0 ? (processed / total) * 100 : 0
  const percentStr = percentNum.toFixed(2).replace(/\.00$/, '') // e.g., 0.95 or 100 or 54.5

  let dashboardState = 'ANALYZING'
  let stateMessage = 'Analyzing source code...'

  if (status === 'error' || status === 'cancelled') {
    dashboardState = status === 'error' ? 'FAILED' : 'CANCELLED'
    stateMessage = status === 'error' ? 'Generation failed' : 'Generation stopped'
  } else if (status === 'complete') {
    dashboardState = 'COMPLETED'
    stateMessage = 'Documentation generation completed'
  } else if (total > 0 && processed === total) {
    dashboardState = 'COMPLETED'
    stateMessage = 'Documentation generation completed'
  } else if (agentStatus.status_message?.toLowerCase().includes('clone') || agentStatus.status_message?.toLowerCase().includes('cloning')) {
    dashboardState = 'CLONING'
    stateMessage = 'Cloning repository...'
  } else if (total > 0 && processed < total) {
    dashboardState = 'GENERATING'
    stateMessage = 'Generating documentation...'
  }

  // Extract file list from progress.component_status or repoStructure
  let filesList = []
  if (repoStructure && repoStructure.tree) {
    const collectFiles = (node) => {
      if (node.type === 'file') filesList.push(node)
      if (node.children) node.children.forEach(collectFiles)
    }
    collectFiles(repoStructure.tree)
  }

  return (
    <div className="dashboard-grid">
      <div className="dashboard-main">
        <div className="card progress-card">
          <div className="progress-header">
            <div className="progress-title">Generation Progress</div>
            <div className="progress-status">{stateMessage}</div>
          </div>

          <div className="progress-bar-container" role="progressbar" aria-valuenow={percentNum} aria-valuemin="0" aria-valuemax="100">
            <div className="progress-bar-fill" style={{ width: `${percentNum}%`, background: dashboardState === 'FAILED' || dashboardState === 'CANCELLED' ? 'var(--danger)' : 'var(--accent)' }} />
          </div>

          <div className="progress-stats">
            <div>
              <span style={{ fontWeight: 600, color: 'var(--text)' }}>{percentStr}%</span> complete
            </div>
            <div>
              Processed: <span style={{ fontWeight: 600, color: 'var(--text)' }}>{processed}</span> / {total} components
            </div>
          </div>

          <div className="processing-panel">
            <div className="processing-label">Currently Processing</div>
            <div className="processing-item">
              <div className="label">Component:</div>
              <div className="value">{agentStatus.current_component || 'N/A'}</div>
            </div>
            <div className="processing-item">
              <div className="label">File:</div>
              <div className="value">{agentStatus.current_file || 'N/A'}</div>
            </div>
            <div className="processing-item" style={{ marginTop: '0.5rem' }}>
              <div className="label">Status:</div>
              <div className="value" style={{ color: 'var(--accent)' }}>{agentStatus.status_message || 'Waiting...'}</div>
            </div>
          </div>
        </div>

        <LogViewer logs={logs} />
      </div>

      <div className="dashboard-sidebar">
        <AgentPipeline activeAgent={agentStatus.active_agent} />
        <RepoStructure repoStructure={repoStructure} />
        <FileTable files={filesList} />
      </div>
    </div>
  )
}
