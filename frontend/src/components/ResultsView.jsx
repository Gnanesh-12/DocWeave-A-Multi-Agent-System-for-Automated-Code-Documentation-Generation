function classifyLine(line) {
  if (line.startsWith('+++') || line.startsWith('---')) return 'diff-hunk'
  if (line.startsWith('+')) return 'diff-add'
  if (line.startsWith('-')) return 'diff-remove'
  if (line.startsWith('@@')) return 'diff-hunk'
  return ''
}

function DiffBlock({ diffText }) {
  const lines = diffText.split('\n')
  return (
    <div className="diff-block">
      {lines.map((line, i) => (
        <div key={i} className={`diff-line ${classifyLine(line)}`}>{line || ' '}</div>
      ))}
    </div>
  )
}

export default function ResultsView({ files }) {
  return (
    <div className="card">
      <div className="dep-header">
        <h2>Results</h2>
        {files.length > 0 && (
          <a className="download-patch-link" href="/api/download-patch" download="docagent-changes.patch">
            Download patch
          </a>
        )}
      </div>

      {files.length === 0 && (
        <p className="empty-state">
          No docstrings were changed. All components may already have been documented, or the
          repository contains no Python files.
        </p>
      )}

      {files.map((f) => (
        <div className="file-diff" key={f.file}>
          <h3>{f.file}</h3>
          <DiffBlock diffText={f.diff} />
        </div>
      ))}
    </div>
  )
}
