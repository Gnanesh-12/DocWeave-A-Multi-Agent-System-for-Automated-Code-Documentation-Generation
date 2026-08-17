export default function RepoForm({ url, setUrl, model, setModel, models, busy, busyText, onStart }) {
  return (
    <div className="card">
      <label htmlFor="repo-url">GitHub repository URL</label>
      <input
        id="repo-url"
        type="text"
        placeholder="https://github.com/owner/repo.git"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        disabled={busy}
      />

      <label htmlFor="model-select">Local Ollama model</label>
      <select
        id="model-select"
        value={model}
        onChange={(e) => setModel(e.target.value)}
        disabled={busy}
      >
        {models.map((m) => (
          <option key={m} value={m}>{m}</option>
        ))}
      </select>

      <button onClick={onStart} disabled={busy || !url.trim()}>
        {busy ? busyText : 'Generate docstrings'}
      </button>
    </div>
  )
}
