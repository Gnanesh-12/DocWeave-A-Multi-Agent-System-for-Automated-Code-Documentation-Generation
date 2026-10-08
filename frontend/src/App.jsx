import React, { useEffect, useRef, useState } from 'react'
import Header from './components/Header.jsx'
import ConfigView from './components/ConfigView.jsx'
import DashboardView from './components/DashboardView.jsx'
import ResultsView from './components/ResultsView.jsx'
import { cloneRepo, getModels, startOllama, stopGeneration, getResults, getStatus, getSocket } from './api.js'
import { AlertCircle, Copy, RotateCcw } from 'lucide-react'

const MAX_LOG_LINES = 5000

export default function App() {
  const [phase, setPhase] = useState('form') // 'form' | 'running' | 'results'
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [appStatus, setAppStatus] = useState('ready') // 'ready', 'running', 'complete', 'error', 'cancelled'

  const [url, setUrl] = useState('')
  const [models, setModels] = useState([])
  const [model, setModel] = useState('')

  const [agentStatus, setAgentStatus] = useState({})
  const [progress, setProgress] = useState({})
  const [repoStructure, setRepoStructure] = useState({})
  const [logs, setLogs] = useState([])
  const [files, setFiles] = useState([])
  const [metrics, setMetrics] = useState(null)

  useEffect(() => {
    getModels()
      .then((data) => {
        const list = data.models || []
        setModels(list)
        if (list.length > 0) setModel(list[0])
      })
      .catch((err) => {
        console.error("Failed to fetch models from backend:", err)
        setError("Couldn't reach Ollama at localhost:11434. Make sure Ollama is running, then try again.")
        setAppStatus("error")
      })
  }, [])

  useEffect(() => {
    async function resumeState() {
      const status = await getStatus()
      if (status.is_running) {
        setPhase('running')
        setAppStatus('running')
        return
      }
      if (status.repo_path) {
        const result = await getResults()
        if (result.status === 'success') {
          setFiles(result.files || [])
          setPhase('results')
          setAppStatus('complete')
        }
      }
    }
    resumeState()
  }, [])

  useEffect(() => {
    const socket = getSocket()

    const onStatusUpdate = (data) => {
      if (data.status) setAgentStatus(data.status)
      if (data.progress) setProgress(data.progress)
      if (data.repo_structure) setRepoStructure(data.repo_structure)
    }
    const onLogMessage = (data) => {
      setLogs((prev) => [...prev, { message: data.message, level: data.level, time: new Date().toLocaleTimeString('en-US', { hour12: false }) }].slice(-MAX_LOG_LINES))
    }
    const onLogLine = (line) => {
      setLogs((prev) => [...prev, { message: line, level: 'INFO', time: new Date().toLocaleTimeString('en-US', { hour12: false }) }].slice(-MAX_LOG_LINES))
    }
    const onComplete = async () => {
      const result = await getResults()
      setFiles(result.files || [])
      setBusy(false)
      setAppStatus('complete')
    }
    const onError = (data) => {
      if (data.message && data.message.toLowerCase().includes('stopped')) {
        setAppStatus('cancelled')
      } else {
        setError(data.message || 'Docstring generation failed')
        setAppStatus('error')
      }
      setBusy(false)
    }

    socket.on('status_update', onStatusUpdate)
    socket.on('log_message', onLogMessage)
    socket.on('log_line', onLogLine)
    socket.on('complete', onComplete)
    socket.on('error', onError)

    return () => {
      socket.off('status_update', onStatusUpdate)
      socket.off('log_message', onLogMessage)
      socket.off('log_line', onLogLine)
      socket.off('complete', onComplete)
      socket.off('error', onError)
    }
  }, [])

  async function handleStart() {
    setError(null)
    setBusy(true)
    setAppStatus('running')

    try {
      const cloneResult = await cloneRepo(url.trim())
      if (cloneResult.status !== 'success') {
        setError(cloneResult.message || 'Failed to clone repository')
        setBusy(false)
        setAppStatus('error')
        return
      }

      const startResult = await startOllama(model)
      if (startResult.status !== 'success') {
        setError(startResult.message || 'Failed to start generation')
        setBusy(false)
        setAppStatus('error')
        return
      }

      setAgentStatus({})
      setProgress({})
      setLogs([])
      setPhase('running')
    } catch (err) {
      setError(err.message || 'A network error occurred while communicating with the backend.')
      setBusy(false)
      setAppStatus('error')
    }
  }

  async function handleStop() {
    await stopGeneration()
    setBusy(false)
    setAppStatus('cancelled')
  }

  function handleReset() {
    setUrl('')
    setFiles([])
    setError(null)
    setAppStatus('ready')
    setPhase('form')
  }

  return (
    <div className="app">
      <Header status={appStatus} phase={phase} model={phase !== 'form' ? model : null} />

      {error && (
        <div className="error-banner" role="alert">
          <div className="error-banner-content">
            <div className="error-banner-title">
              <AlertCircle size={16} className="icon" />
              Generation halted
            </div>
            <div className="error-banner-details">
              {error}
            </div>
            <div className="error-banner-actions">
              <button className="danger" onClick={handleReset}>Start over</button>
              <button className="secondary" onClick={() => navigator.clipboard.writeText(error)}>
                <Copy size={14} /> Copy error details
              </button>
            </div>
          </div>
        </div>
      )}

      {phase === 'form' && (
        <main className="main-content narrow">
          <ConfigView
            url={url}
            setUrl={setUrl}
            model={model}
            setModel={setModel}
            models={models}
            busy={busy}
            onStart={handleStart}
          />
        </main>
      )}

      {phase === 'running' && (
        <>
          {appStatus === 'complete' ? (
            <div className="status-strip">
              <div className="status-strip-inner" style={{ alignItems: 'center' }}>
                <div style={{ fontSize: '1rem', color: 'var(--text)' }}>
                  Documented {progress.processed_components || 0} components.
                </div>
                <div style={{ display: 'flex', gap: '16px' }}>
                  <button className="primary" onClick={() => setPhase('results')}>Review changes</button>
                  <button className="secondary" onClick={handleReset}>Start over</button>
                </div>
              </div>
            </div>
          ) : (appStatus === 'cancelled' || appStatus === 'error') ? (
            <div className="status-strip">
              <div className="status-strip-inner">
                <div style={{ fontSize: '1rem', color: 'var(--text)' }}>
                  Process stopped.
                </div>
                <button className="primary" onClick={handleReset}>
                  <RotateCcw size={14} /> Start over
                </button>
              </div>
            </div>
          ) : (
            <DashboardView
              agentStatus={agentStatus}
              progress={progress}
              repoStructure={repoStructure}
              logs={logs}
              status={appStatus}
              onStop={handleStop}
            />
          )}
        </>
      )}

      {phase === 'results' && (
        <main className="main-content">
          <div style={{ marginBottom: '24px' }}>
            <button className="ghost" onClick={handleReset}>&larr; Process another repository</button>
          </div>
          <ResultsView files={files} progress={progress} />
        </main>
      )}
    </div>
  )
}
