import React, { useState, useEffect, useRef } from 'react'
import { FileText, Folder, Check, X, AlertTriangle, Circle, ArrowDownToLine, Copy } from 'lucide-react'

const AGENTS = ['Reader', 'Searcher', 'Writer', 'Verifier']

function AgentTrack({ activeAgent, lastMessage, currentDraft }) {
  const activeLower = (activeAgent || '').toLowerCase()
  
  return (
    <div style={{ marginBottom: '32px' }}>
      <div className="agent-track">
        <div className="agent-track-line"></div>
        {AGENTS.map((agent, i) => {
          const activeIndex = AGENTS.findIndex(a => activeLower.includes(a.toLowerCase()))
          
          let state = 'waiting'
          let stateText = 'Waiting'
          
          if (activeIndex === i) {
            state = 'active'
            stateText = 'Working'
          } else if (activeIndex > i || activeLower.includes('complete')) {
            state = 'done'
            stateText = 'Done'
          }

          return (
            <div key={agent} className={`agent-node ${state}`}>
              <div className="agent-node-icon">
                {state === 'done' ? <Check size={14} /> : <Circle size={14} fill={state === 'active' ? 'currentColor' : 'none'} />}
              </div>
              <div className="agent-node-name">{agent}</div>
              <div className="agent-node-state">{stateText}</div>
            </div>
          )
        })}
      </div>
      
      {lastMessage && (
        <div className="agent-msg">
          {lastMessage}
        </div>
      )}

      {currentDraft && (
        <div className="draft-code">
          <pre style={{ margin: 0 }}>
            <span className="docstring-prose" style={{ color: 'var(--accent)' }}>{currentDraft}</span>
          </pre>
        </div>
      )}
    </div>
  )
}

function LogPanel({ logs }) {
  const [height, setHeight] = useState(250)
  const [autoScroll, setAutoScroll] = useState(true)
  const [filter, setFilter] = useState('All')
  const containerRef = useRef(null)

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [logs, autoScroll])

  const handleScroll = () => {
    if (!containerRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 10

    if (isAtBottom && !autoScroll) setAutoScroll(true)
    else if (!isAtBottom && autoScroll) setAutoScroll(false)
  }

  const filteredLogs = logs.filter(l => {
    if (filter === 'All') return true
    if (filter === 'Info') return l.level === 'INFO'
    if (filter === 'Warnings') return l.level === 'WARN' || l.level === 'WARNING'
    if (filter === 'Errors') return l.level === 'ERROR'
    return true
  })

  return (
    <div className="log-panel" style={{ height: `${height}px` }}>
      <div 
        style={{ height: '4px', cursor: 'ns-resize', background: 'transparent', position: 'absolute', top: '-2px', left: 0, right: 0, zIndex: 10 }}
        onMouseDown={(e) => {
          const startY = e.clientY
          const startHeight = height
          const onMouseMove = (moveEvent) => {
            const newHeight = startHeight + (startY - moveEvent.clientY)
            setHeight(Math.max(160, Math.min(newHeight, window.innerHeight - 100)))
          }
          const onMouseUp = () => {
            document.removeEventListener('mousemove', onMouseMove)
            document.removeEventListener('mouseup', onMouseUp)
          }
          document.addEventListener('mousemove', onMouseMove)
          document.addEventListener('mouseup', onMouseUp)
        }}
      />
      <div className="log-panel-header">
        <div className="segmented-control">
          <button aria-selected={filter === 'All'} onClick={() => setFilter('All')}>All</button>
          <button aria-selected={filter === 'Info'} onClick={() => setFilter('Info')}>Info</button>
          <button aria-selected={filter === 'Warnings'} onClick={() => setFilter('Warnings')}>Warnings</button>
          <button aria-selected={filter === 'Errors'} onClick={() => setFilter('Errors')}>Errors</button>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          {!autoScroll && (
            <button className="secondary" style={{ height: '28px', fontSize: '0.75rem' }} onClick={() => {
              setAutoScroll(true)
              if (containerRef.current) containerRef.current.scrollTop = containerRef.current.scrollHeight
            }}>
              Jump to latest
            </button>
          )}
          <button className="icon-btn" aria-label="Copy logs">
            <Copy size={14} />
          </button>
        </div>
      </div>
      <div className="log-panel-content" ref={containerRef} onScroll={handleScroll}>
        {filteredLogs.map((log, i) => {
          let lvl = (log.level || 'INFO').toUpperCase()
          if (lvl === 'WARNING') lvl = 'WARN'
          const text = log.message || log.text || ''
          return (
            <div key={i} className="log-line">
              <div className="log-line-num">{i + 1}</div>
              <div className="log-line-time">{log.time}</div>
              <div className={`log-line-lvl ${lvl.toLowerCase()}`}>{lvl}</div>
              <div className="log-line-msg">{text}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function TreeSidebar({ filesList, activeFile }) {
  const [filter, setFilter] = useState('')

  const displayedFiles = filesList.filter(f => {
    if (!filter) return true
    return (f.file || f.name || '').toLowerCase().includes(filter.toLowerCase())
  })

  return (
    <div className="tree-sidebar">
      <div className="tree-filter">
        <input 
          type="text" 
          placeholder="Filter files..." 
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      </div>
      <div className="tree-nodes">
        {displayedFiles.map(f => {
          const name = f.file || f.name || 'Unknown'
          const isActive = name === activeFile
          
          let icon = <Circle size={14} className="status-mark pending" />
          if (f.status === 'completed' || f.status === 'complete') icon = <Check size={14} className="status-mark done" />
          else if (f.status === 'processing' || f.status === 'in_progress') icon = <Circle size={14} fill="currentColor" className="status-mark processing" />
          else if (f.status === 'failed') icon = <X size={14} className="status-mark error" />
          else if (f.status === 'partial') icon = <AlertTriangle size={14} className="status-mark warning" />

          return (
            <div key={name} className={`tree-node ${isActive ? 'active' : ''}`}>
              {icon}
              <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{name}</div>
            </div>
          )
        })}
        {displayedFiles.length === 0 && <div style={{ color: 'var(--text-muted)', padding: '8px' }}>No files found.</div>}
      </div>
    </div>
  )
}

export default function DashboardView({ agentStatus, progress, repoStructure, logs, status, onStop }) {
  const total = progress.total_components || 0
  const processed = progress.processed_components || 0
  const perc = total > 0 ? (processed / total) * 100 : 0

  let filesList = []
  if (progress && progress.file_progress) {
    filesList = Object.values(progress.file_progress)
  } else if (repoStructure && repoStructure.tree) {
    const collectFiles = (node) => {
      if (node.type === 'file') filesList.push(node)
      if (node.children) node.children.forEach(collectFiles)
    }
    collectFiles(repoStructure.tree)
  }
  
  filesList.sort((a, b) => (a.file || a.name).localeCompare(b.file || b.name))

  const warnings = filesList.filter(f => f.status === 'partial').length
  const failures = filesList.filter(f => f.status === 'failed').length

  const isCompleted = status === 'complete' || (total > 0 && processed === total)

  // Find most recent meaningful message
  const recentMsg = logs.slice().reverse().find(l => l.level === 'INFO' && l.message && !l.message.includes('Status update'))?.message

  if (isCompleted) {
    return null // Handled in App.jsx to render completion strip
  }

  return (
    <>
      <div className="status-strip">
        <div className="status-strip-inner">
          <div className="status-strip-main">
            <div className="status-large-num">{processed} / {total} components</div>
            <div className="status-stats">
              {warnings > 0 && (
                <div className="stat">
                  <span className="stat-val" style={{ color: 'var(--warn)' }}>{warnings}</span>
                  Warnings
                </div>
              )}
              {failures > 0 && (
                <div className="stat">
                  <span className="stat-val" style={{ color: 'var(--err)' }}>{failures}</span>
                  Failures
                </div>
              )}
            </div>
          </div>
          {onStop && status === 'running' && (
            <button className="danger" onClick={onStop}>Stop</button>
          )}
        </div>
        <div className="status-strip-inner">
          <div className="progress-bar-thin">
            <div className="progress-bar-thin-fill" style={{ width: `${perc}%` }}></div>
          </div>
        </div>
      </div>

      <div className="dashboard-layout">
        <TreeSidebar filesList={filesList} activeFile={agentStatus.current_file} />
        
        <div className="dashboard-center">
          <div className="current-work-header">
            <div className="current-work-name">
              {agentStatus.current_component || 'Waiting for component...'}
              {agentStatus.current_component && <span className="chip">Component</span>}
            </div>
            <div className="current-work-file">
              {agentStatus.current_file || ''}
            </div>
          </div>

          <AgentTrack 
            activeAgent={agentStatus.active_agent} 
            lastMessage={recentMsg} 
            currentDraft={agentStatus.current_draft} 
          />
        </div>
      </div>

      <LogPanel logs={logs} />
    </>
  )
}
