import React, { useState } from 'react'

export default function ConfigView({ url, setUrl, model, setModel, models, onStart, busy }) {
  const [urlError, setUrlError] = useState('')

  const validateUrl = () => {
    if (!url) {
      setUrlError('')
      return true
    }
    const val = url.trim()
    if (!val.startsWith('http') && !val.startsWith('/') && !val.startsWith('C:\\') && !val.startsWith('c:\\')) {
      setUrlError("That doesn't look like a Git URL or an absolute path")
      return false
    }
    setUrlError('')
    return true
  }

  const handleStart = () => {
    if (validateUrl()) {
      onStart()
    }
  }

  return (
    <div className="config-layout">
      <div className="config-form">
        <h1 style={{ marginBottom: '8px' }}>Document a repository</h1>
        <p className="helper-text" style={{ marginBottom: '32px' }}>
          DocWeave reads your code locally and writes docstrings in dependency order. Nothing leaves this machine.
        </p>

        <div className="form-group">
          <label htmlFor="repo-url">Repository</label>
          <input
            id="repo-url"
            type="text"
            className={urlError ? 'input-error' : ''}
            placeholder="https://github.com/owner/repo.git or /local/path"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onBlur={validateUrl}
            disabled={busy}
          />
          {urlError && <div className="input-error-text">{urlError}</div>}
        </div>

        <div className="form-group">
          <label htmlFor="model-select">Model</label>
          {models.length === 0 ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <select id="model-select" disabled>
                <option>Loading models...</option>
              </select>
              <div className="helper-text">
                No Ollama models found. Run <code className="mono">ollama pull qwen2.5-coder:7b</code>, then refresh.
              </div>
            </div>
          ) : (
            <select
              id="model-select"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              disabled={busy}
            >
              {models.map(m => (
                <option key={m} value={m}>{m.startsWith('claude-') ? `${m} (hosted, uses your API key)` : m}</option>
              ))}
            </select>
          )}
          {model.startsWith('claude-') && (
            <div className="helper-text" style={{ marginTop: '8px' }}>
              This model runs on Anthropic&apos;s servers: your code is sent to the Anthropic API and each
              component is billed to your API key. Use it for open-source or non-sensitive code.
            </div>
          )}
        </div>

        <button
          className="primary"
          onClick={handleStart}
          disabled={busy || !url.trim() || !!urlError || models.length === 0}
          style={{ width: '100%', height: '40px', marginTop: '16px' }}
        >
          {busy ? (
            <>
              <span className="icon">↻</span> Cloning repository...
            </>
          ) : (
            'Start generating'
          )}
        </button>
      </div>

      <div className="config-info">
        <h3 style={{ marginBottom: '8px' }}>What happens next</h3>
        <ul className="config-info-list">
          <li>
            <span className="config-info-list-num">1.</span>
            <span>Navigator maps dependencies so each component is documented after the code it relies on.</span>
          </li>
          <li>
            <span className="config-info-list-num">2.</span>
            <span>Reader extracts the source code for the component.</span>
          </li>
          <li>
            <span className="config-info-list-num">3.</span>
            <span>Searcher gathers context from related files.</span>
          </li>
          <li>
            <span className="config-info-list-num">4.</span>
            <span>Writer produces a draft docstring.</span>
          </li>
          <li>
            <span className="config-info-list-num">5.</span>
            <span>Verifier reviews it for accuracy and requests changes if needed.</span>
          </li>
        </ul>

        <div style={{ marginTop: '24px' }}>
          <pre style={{ margin: 0, border: '1px solid var(--border)' }}>
            <span style={{ color: 'var(--text-muted)' }}>def</span> calculate_tax(amount):<br />
            <span className="docstring-prose" style={{ color: 'var(--accent)' }}>    """<br />    Calculates the 20% value-added tax for a given amount.<br />    """</span><br />
            <span style={{ color: 'var(--text-muted)' }}>return</span> amount * <span style={{ color: 'var(--ok)' }}>0.2</span>
          </pre>
        </div>
      </div>
    </div>
  )
}
