import React from 'react'

export default function Header({ status, isRunning, onStop }) {
  let indicatorClass = 'ready'
  let indicatorText = 'System Ready'

  if (status === 'error') {
    indicatorClass = 'error'
    indicatorText = 'Connection Error'
  } else if (isRunning) {
    indicatorClass = 'active'
    indicatorText = 'Processing'
  } else if (status === 'complete') {
    indicatorClass = 'ready'
    indicatorText = 'Generation Complete'
  } else if (status === 'cancelled') {
    indicatorClass = 'error'
    indicatorText = 'Generation Stopped'
  }

  return (
    <header className="app-header">
      <div className="header-left">
        <div className="app-mark">DA</div>
        <div className="header-title">
          <h1>DocAgent</h1>
          <span className="header-subtitle">Automated Code Documentation</span>
        </div>
      </div>
      <div className="header-right">
        {isRunning && (
          <button className="danger" onClick={onStop}>
            Stop Generation
          </button>
        )}
        <div className="status-indicator">
          <div className={`status-dot ${indicatorClass}`} />
          {indicatorText}
        </div>
      </div>
    </header>
  )
}
