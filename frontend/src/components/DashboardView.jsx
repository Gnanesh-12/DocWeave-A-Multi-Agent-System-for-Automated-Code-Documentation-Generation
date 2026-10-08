import React, { useState, useEffect, useRef } from 'react'
import { FileText, Folder, Check, X, AlertTriangle, Circle, ArrowDownToLine, Copy } from 'lucide-react'
import { normalizeLevel } from '../logUtils.js'

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

  const [copied, setCopied] = useState(false)

  // Keep each entry's original line number so numbering stays stable while filtering.
  const entries = logs.map((log, idx) => ({ log, idx, level: normalizeLevel(log.level) }))
  const counts = {
    All: entries.length,
    Info: entries.filter(e => e.level === 'INFO' || e.level === 'DEBUG').length,
    Warnings: entries.filter(e => e.level === 'WARN').length,
    Errors: entries.filter(e => e.level === 'ERROR').length,
  }
  const filteredLogs = entries.filter(e => {
    if (filter === 'Info') return e.level === 'INFO' || e.level === 'DEBUG'
    if (filter === 'Warnings') return e.level === 'WARN'
    if (filter === 'Errors') return e.level === 'ERROR'
    return true
  })

  const copyLogs = async () => {
    const text = filteredLogs.map(e => `${e.log.time || ''} ${e.level} ${e.log.message || e.log.text || ''}`).join('\n')
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // Clipboard can be blocked (non-secure context); nothing useful to do.
    }
  }

  const emptyText = {
    All: 'Waiting for output...',
    Info: 'No info messages yet.',
    Warnings: 'No warnings so far.',
    Errors: 'No errors so far.',
  }[filter]

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
        <div className="segmented-control" role="tablist">
          {['All', 'Info', 'Warnings', 'Errors'].map(tab => (
            <button key={tab} role="tab" aria-selected={filter === tab} onClick={() => setFilter(tab)}>
              {tab}
              <span className={`tab-count ${tab === 'Errors' && counts[tab] > 0 ? 'has-errors' : ''} ${tab === 'Warnings' && counts[tab] > 0 ? 'has-warnings' : ''}`}>
                {counts[tab]}
              </span>
            </button>
          ))}
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
          <button className="icon-btn" aria-label="Copy logs" title={copied ? 'Copied' : 'Copy shown logs'} onClick={copyLogs}>
            {copied ? <Check size={14} /> : <Copy size={14} />}
          </button>
        </div>
      </div>
      <div className="log-panel-content" ref={containerRef} onScroll={handleScroll}>
        {filteredLogs.length === 0 && (
          <div style={{ color: 'var(--text-muted)', padding: '12px 16px' }}>{emptyText}</div>
        )}
        {filteredLogs.map(({ log, idx, level }) => (
          <div key={idx} className="log-line">
            <div className="log-line-num">{idx + 1}</div>
            <div className="log-line-time">{log.time}</div>
            <div className={`log-line-lvl ${level.toLowerCase()}`}>{level}</div>
            <div className="log-line-msg">{log.message || log.text || ''}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

// Compare paths regardless of case or slash direction: file names arrive as Windows paths
// (src\main\...) but people type src/main.
const normPath = (s) => String(s || '').replace(/\\/g, '/').toLowerCase()

function TreeSidebar({ filesList, activeFile }) {
  const [filter, setFilter] = useState('')

  const query = normPath(filter.trim())
  const displayedFiles = filesList.filter(f => !query || normPath(f.file || f.name).includes(query))
  const active = normPath(activeFile)

  return (
    <div className="tree-sidebar">
      <div className="tree-filter">
        <div className="tree-filter-box">
          <input
            type="text"
            placeholder="Filter files..."
            aria-label="Filter files"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Escape') setFilter('') }}
          />
          {filter && (
            <button className="tree-filter-clear" aria-label="Clear filter" onClick={() => setFilter('')}>
              <X size={14} />
            </button>
          )}
        </div>
        {query && (
          <div className="tree-filter-count">{displayedFiles.length} of {filesList.length} files</div>
        )}
      </div>
      <div className="tree-nodes">
        {displayedFiles.map(f => {
          const name = f.file || f.name || 'Unknown'
          const normName = normPath(name)
          const isActive = !!active && (normName === active || normName.endsWith('/' + active) || active.endsWith('/' + normName))
          const slash = Math.max(name.lastIndexOf('/'), name.lastIndexOf('\\'))
          const base = name.slice(slash + 1)
          const dir = slash >= 0 ? name.slice(0, slash) : ''

          let icon = <Circle size={14} className="status-mark pending" />
          if (f.status === 'completed' || f.status === 'complete') icon = <Check size={14} className="status-mark done" />
          else if (f.status === 'processing' || f.status === 'in_progress') icon = <Circle size={14} fill="currentColor" className="status-mark processing" />
          else if (f.status === 'failed') icon = <X size={14} className="status-mark error" />
          else if (f.status === 'partial') icon = <AlertTriangle size={14} className="status-mark warning" />

          return (
            <div key={name} className={`tree-node ${isActive ? 'active' : ''}`} title={name}>
              {icon}
              <div className="tree-node-text">
                <div className="tree-node-name">{base}</div>
                {dir && <div className="tree-node-dir">{dir}</div>}
              </div>
            </div>
          )
        })}
        {displayedFiles.length === 0 && (
          <div style={{ color: 'var(--text-muted)', padding: '8px' }}>
            {query ? `No files match "${filter.trim()}".` : 'Waiting for files...'}
          </div>
        )}
      </div>
    </div>
  )
}

export default function DashboardView({ agentStatus, progress, repoStructure, logs, status, onStop, onReview, onReset }) {
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

  // The dashboard stays on screen once generation ends, so the progress, per-file status
  // and logs can still be inspected (especially after a failure). Only the banner changes.
  const isComplete = status === 'complete'
  const isStopped = status === 'cancelled' || status === 'error'
  const isFinished = isComplete || isStopped

  // Find most recent meaningful message
  const recentMsg = logs.slice().reverse().find(l => l.level === 'INFO' && l.message && !l.message.includes('Status update'))?.message

  let headline = `${processed} / ${total} components`
  if (isComplete) headline = `Documented ${processed || total} components`
  else if (isStopped) headline = `Stopped at ${processed} / ${total} components`

  let workName = agentStatus.current_component || 'Waiting for component...'
  let workFile = agentStatus.current_file || ''
  if (isComplete) {
    workName = 'All components documented'
    workFile = 'Open the review to see exactly what changed in each file.'
  } else if (isStopped) {
    workName = 'Generation stopped'
    workFile = 'Progress and logs are kept below. Start over to try again.'
  }

  return (
    <>
      <div className="status-strip">
        <div className="status-strip-inner">
          <div className="status-strip-main">
            <div className="status-large-num">{headline}</div>
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
          <div style={{ display: 'flex', gap: '12px' }}>
            {onStop && !isFinished && (
              <button className="danger" onClick={onStop}>Stop</button>
            )}
            {isComplete && onReview && (
              <button className="primary" onClick={onReview}>Review changes</button>
            )}
            {isFinished && onReset && (
              <button className="secondary" onClick={onReset}>Start over</button>
            )}
          </div>
        </div>
        <div className="status-strip-inner">
          <div className="progress-bar-thin">
            <div className="progress-bar-thin-fill" style={{ width: `${isComplete ? 100 : perc}%` }}></div>
          </div>
        </div>
      </div>

      <div className="dashboard-layout">
        <TreeSidebar filesList={filesList} activeFile={isFinished ? null : agentStatus.current_file} />

        <div className="dashboard-center">
          <div className="current-work-header">
            <div className="current-work-name">
              {workName}
              {!isFinished && agentStatus.current_component && <span className="chip">Component</span>}
            </div>
            <div className="current-work-file">
              {workFile}
            </div>
          </div>

          <AgentTrack
            activeAgent={isComplete ? 'complete' : isStopped ? null : agentStatus.active_agent}
            lastMessage={recentMsg}
            currentDraft={isFinished ? null : agentStatus.current_draft}
          />
        </div>
      </div>

      <LogPanel logs={logs} />
    </>
  )
}
