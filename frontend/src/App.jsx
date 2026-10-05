import React, { useEffect, useRef, useState } from 'react'
import Header from './components/Header.jsx'
import ConfigView from './components/ConfigView.jsx'
import DashboardView from './components/DashboardView.jsx'
import ResultsView from './components/ResultsView.jsx'
import DependencyGraph from './components/DependencyGraph.jsx'
import { cloneRepo, getModels, startOllama, stopGeneration, getResults, getStatus, getSocket } from './api.js'

const MAX_LOG_LINES = 1000

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

  const phaseRef = useRef(phase)
  phaseRef.current = phase

  useEffect(() => {
    getModels()
      .then((data) => {
        const list = data.models || []
        setModels(list)
        if (list.length > 0) setModel(list[0])
      })
      .catch((err) => {
        console.error("Failed to fetch models from backend:", err)
        setError("Failed to connect to the backend server. Is it running?")
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
      // Only transition to results if we want. For now, keep dashboard visible but complete.
      // setPhase('results')
    }
    const onError = (data) => {
      // If stopped manually
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
      <Header status={appStatus} isRunning={busy} onStop={handleStop} />

      <main className="main-content">
        {error && (
          <div className="error-banner">
            <h3>Error</h3>
            <p>{error}</p>
          </div>
        )}

        {phase === 'form' && (
          <ConfigView
            url={url}
            setUrl={setUrl}
            model={model}
            setModel={setModel}
            models={models}
            busy={busy}
            onStart={handleStart}
          />
        )}

        {phase === 'running' && (
          <>
            <DashboardView
              agentStatus={agentStatus}
              progress={progress}
              repoStructure={repoStructure}
              logs={logs}
              status={appStatus}
            />
            {appStatus === 'complete' && (
              <div style={{ marginTop: '1.5rem', display: 'flex', gap: '1rem' }}>
                <button className="primary" onClick={() => setPhase('results')}>View Results & Diff</button>
                <button onClick={handleReset}>Process Another Repository</button>
              </div>
            )}
            {(appStatus === 'cancelled' || appStatus === 'error') && (
              <div style={{ marginTop: '1.5rem' }}>
                <button onClick={handleReset}>Start Over</button>
              </div>
            )}
          </>
        )}

        {phase === 'results' && (
          <>
            <button style={{ marginBottom: '1rem' }} onClick={handleReset}>&larr; Process another repository</button>
            <DependencyGraph />
            <ResultsView files={files} />
          </>
        )}
      </main>
    </div>
  )
}
