import React, { useState } from 'react'
import { testApi } from '../api'

export default function ConfigView({ url, setUrl, model, setModel, models, onStart, busy }) {
  const [testingStatus, setTestingStatus] = useState(null) // null, 'testing', 'success', 'error'
  const [testingMessage, setTestingMessage] = useState('')

  const handleTestApi = async () => {
    setTestingStatus('testing')
    setTestingMessage('Testing connection...')
    try {
      const res = await testApi({
        llm_type: 'huggingface',
        model: model,
        api_base: 'http://localhost:11434/v1',
        api_key: 'EMPTY'
      })
      if (res.status === 'success') {
        setTestingStatus('success')
        setTestingMessage('✓ Connection successful')
      } else {
        setTestingStatus('error')
        setTestingMessage(`✕ Connection failed: ${res.message}`)
      }
    } catch (err) {
      setTestingStatus('error')
      setTestingMessage(`✕ Connection failed: ${err.message}`)
    }
  }

  return (
    <div className="card">
      <div className="card-header">
        <h2>Generate Documentation</h2>
        <div className="helper-text" style={{ margin: 0 }}>
          Analyze a repository and automatically generate high-quality documentation.
        </div>
      </div>
      <div className="card-body">
        <div className="form-group">
          <label htmlFor="repo-url">Repository Source</label>
          <input
            id="repo-url"
            type="text"
            placeholder="https://github.com/owner/repo.git or /local/path"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            disabled={busy}
          />
          <div className="helper-text">Enter a public GitHub repository URL or a local repository path.</div>
        </div>

        <div className="form-group">
          <label>LLM Configuration</label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', background: 'var(--surface-sunken)', padding: '1rem', borderRadius: '4px', border: '1px solid var(--border)' }}>
            <div>
              <div className="helper-text" style={{ marginTop: 0, fontWeight: 600 }}>Provider:</div>
              <div>HuggingFace / Ollama</div>
            </div>
            <div>
              <div className="helper-text" style={{ marginTop: 0, fontWeight: 600 }}>API Base URL:</div>
              <div>http://localhost:11434/v1</div>
            </div>
            <div>
              <div className="helper-text" style={{ marginTop: 0, fontWeight: 600 }}>Model:</div>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                disabled={busy || models.length === 0}
                style={{ marginBottom: 0, marginTop: '0.25rem' }}
              >
                {models.length === 0 ? <option value="">Backend offline / loading...</option> : null}
                {models.map(m => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <button type="button" onClick={handleTestApi} disabled={busy || testingStatus === 'testing'}>
                {testingStatus === 'testing' ? 'Testing connection...' : 'Test API'}
              </button>
            </div>
          </div>
          {testingStatus && testingStatus !== 'testing' && (
            <div className={`helper-text ${testingStatus === 'success' ? 'success-text' : 'error-text'}`} style={{ marginTop: '0.5rem' }}>
              {testingMessage}
            </div>
          )}
        </div>



        <div style={{ marginTop: '1.5rem' }}>
          <button className="primary" onClick={onStart} disabled={busy || !url.trim()} style={{ width: '100%', padding: '0.75rem', fontSize: '1rem' }}>
            {busy ? 'Generating Documentation...' : 'Generate Documentation'}
          </button>
        </div>
      </div>
    </div>
  )
}
