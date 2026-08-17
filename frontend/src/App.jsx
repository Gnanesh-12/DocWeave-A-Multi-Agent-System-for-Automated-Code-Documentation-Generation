import { useEffect, useRef, useState } from 'react'
import RepoForm from './components/RepoForm.jsx'
import ProgressPanel from './components/ProgressPanel.jsx'
import ResultsView from './components/ResultsView.jsx'
import DependencyGraph from './components/DependencyGraph.jsx'
import { cloneRepo, getModels, startGeneration, getResults, getStatus, getSocket } from './api.js'

const MAX_LOG_LINES = 500

export default function App() {
  const [phase, setPhase] = useState('form') // 'form' | 'running' | 'results'
  const [busy, setBusy] = useState(false)
  const [busyText, setBusyText] = useState('')
  const [error, setError] = useState(null)

  const [url, setUrl] = useState('')
  const [models, setModels] = useState([])
  const [model, setModel] = useState('')

  const [agentStatus, setAgentStatus] = useState({})
  const [progress, setProgress] = useState({})
  const [logs, setLogs] = useState([])
  const [files, setFiles] = useState([])

  const phaseRef = useRef(phase)
  phaseRef.current = phase

  useEffect(() => {
    getModels().then((data) => {
      const list = data.models || []
      setModels(list)
      if (list.length > 0) setModel(list[0])
    })
  }, [])

  // Resume state on load/reconnect: a run started earlier may have already
  // finished (or still be running) server-side even if this page is fresh -
  // e.g. after a refresh, or a WebSocket drop during a long CPU-only run
  // that missed the one-shot 'complete' event. Without this, a finished job
  // would be invisible until you manually hit /api/results.
  useEffect(() => {
    async function resumeState() {
      const status = await getStatus()
      if (status.is_running) {
        setPhase('running')
        return
      }
      if (status.repo_path) {
        const result = await getResults()
        if (result.status === 'success') {
          setFiles(result.files || [])
          setPhase('results')
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
    }
    const onLogMessage = (data) => {
      setLogs((prev) => [...prev, { text: data.message, level: data.level }].slice(-MAX_LOG_LINES))
    }
    const onLogLine = (line) => {
      setLogs((prev) => [...prev, { text: line }].slice(-MAX_LOG_LINES))
    }
    const onComplete = async () => {
      const result = await getResults()
      setFiles(result.files || [])
      setBusy(false)
      setPhase('results')
    }
    const onError = (data) => {
      setError(data.message || 'Docstring generation failed')
      setBusy(false)
      setPhase('form')
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
    setBusyText('Cloning repository...')

    const cloneResult = await cloneRepo(url.trim())
    if (cloneResult.status !== 'success') {
      setError(cloneResult.message || 'Failed to clone repository')
      setBusy(false)
      return
    }

    setBusyText('Starting generation...')
    const startResult = await startGeneration(model)
    if (startResult.status !== 'success') {
      setError(startResult.message || 'Failed to start generation')
      setBusy(false)
      return
    }

    setAgentStatus({})
    setProgress({})
    setLogs([])
    setBusyText('Running...')
    setPhase('running')
  }

  function handleReset() {
    setUrl('')
    setFiles([])
    setError(null)
    setPhase('form')
  }

  return (
    <div className="app">
      <div className="eyebrow">Local · Ollama-powered</div>
      <div className="app-header">
        <div className="app-mark">DA</div>
        <h1>DocAgent</h1>
      </div>
      <p className="subtitle">Paste a public GitHub repo, generate docstrings locally with Ollama.</p>

      {error && <div className="error-banner">{error}</div>}

      {phase === 'form' && (
        <RepoForm
          url={url}
          setUrl={setUrl}
          model={model}
          setModel={setModel}
          models={models}
          busy={busy}
          busyText={busyText}
          onStart={handleStart}
        />
      )}

      {phase === 'running' && (
        <ProgressPanel agentStatus={agentStatus} progress={progress} logs={logs} />
      )}

      {phase === 'results' && (
        <>
          <button className="reset-link" onClick={handleReset}>&larr; Process another repository</button>
          <DependencyGraph />
          <ResultsView files={files} />
        </>
      )}
    </div>
  )
}
