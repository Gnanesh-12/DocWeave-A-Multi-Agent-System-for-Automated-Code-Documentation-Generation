const TYPE_LABELS = { class: 'class', method: 'method', function: 'func' }

function groupByFile(nodes) {
  const groups = {}
  for (const n of nodes) {
    if (!groups[n.file]) groups[n.file] = []
    groups[n.file].push(n)
  }
  return groups
}

export default function DependencyTree({ nodes, edges }) {
  const groups = groupByFile(nodes)
  const nodeById = new Map(nodes.map((n) => [n.id, n]))
  const depsFor = (id) =>
    edges
      .filter((e) => e.source === id)
      .map((e) => nodeById.get(e.target))
      .filter(Boolean)

  return (
    <div className="dep-tree">
      {Object.entries(groups).map(([file, fileNodes]) => (
        <div className="dep-file-group" key={file}>
          <h4>{file}</h4>
          <ul>
            {fileNodes.map((n) => {
              const deps = depsFor(n.id)
              return (
                <li key={n.id}>
                  <span className={`dep-type-badge dep-type-${n.type}`}>{TYPE_LABELS[n.type] || n.type}</span>
                  <span className={n.has_docstring ? 'dep-documented' : 'dep-undocumented'}>{n.label}</span>
                  {deps.length > 0 && (
                    <ul className="dep-deps">
                      {deps.map((d) => (
                        <li key={d.id}>&rarr; {d.label}</li>
                      ))}
                    </ul>
                  )}
                </li>
              )
            })}
          </ul>
        </div>
      ))}
    </div>
  )
}
