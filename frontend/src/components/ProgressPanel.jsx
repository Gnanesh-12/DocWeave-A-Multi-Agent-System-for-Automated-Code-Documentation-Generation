const AGENTS = ['Reader', 'Searcher', 'Writer', 'Verifier']

export default function ProgressPanel({ agentStatus, progress, logs }) {
  const activeAgent = (agentStatus.active_agent || '').toLowerCase()
  const total = progress.total_components || 0
  const processed = progress.processed_components || 0
  const percent = total > 0 ? Math.floor((processed / total) * 100) : 0

  return (
    <div className="card">
      <div className="agent-row">
        {AGENTS.map((agent) => (
          <div
            key={agent}
            className={`agent-pill${activeAgent.includes(agent.toLowerCase()) ? ' active' : ''}`}
          >
            {agent}
          </div>
        ))}
      </div>

      {agentStatus.status_message && (
        <div className="status-message">{agentStatus.status_message}</div>
      )}

      {agentStatus.current_component && (
        <div className="progress-text">
          Processing <strong>{agentStatus.current_component}</strong>
          {agentStatus.current_file ? ` in ${agentStatus.current_file}` : ''}
        </div>
      )}

      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${percent}%` }} />
      </div>
      <div className="progress-text">
        <strong>{processed}/{total}</strong> components processed &middot; {percent}%
      </div>

      <div className="log-panel">
        {logs.length === 0 && <div className="empty-state">Waiting for output...</div>}
        {logs.map((log, i) => (
          <div key={i} className={`log-line log-${log.level || 'info'}`}>{log.text}</div>
        ))}
      </div>
    </div>
  )
}
