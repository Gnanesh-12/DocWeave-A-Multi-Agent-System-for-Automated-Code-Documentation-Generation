import React, { useState } from 'react'
import { Download, AlertTriangle, FileCode2 } from 'lucide-react'
import DependencyGraph from './DependencyGraph.jsx'

function classifyLine(line) {
  if (line.startsWith('+++') || line.startsWith('---')) return 'hunk'
  if (line.startsWith('+')) return 'add'
  if (line.startsWith('-')) return 'del'
  if (line.startsWith('@@')) return 'hunk'
  return ''
}

function DiffBlock({ diffText }) {
  const lines = diffText.split('\n')
  return (
    <div className="diff-content">
      {lines.map((line, i) => {
        const type = classifyLine(line)
        const isAddedDocstring = type === 'add' && line.includes('"""')
        
        let content = line
        if (isAddedDocstring || (type === 'add' && !line.includes('def ') && !line.includes('class '))) {
          // Naive heuristic for docstring styling in diff
          content = <span className="docstring-prose">{line}</span>
        }

        return (
          <div key={i} className={`diff-line ${type}`}>
            <div className="diff-line-num">{i + 1}</div>
            <div className="diff-line-content">{content || ' '}</div>
          </div>
        )
      })}
    </div>
  )
}

export default function ResultsView({ files, progress }) {
  const [activeTab, setActiveTab] = useState('changes') // changes | graph
  const [activeFile, setActiveFile] = useState(files[0]?.file || null)

  const componentsDocumented = progress?.processed_components || 0
  const warnings = files.filter(f => f.status === 'partial').length
  const failures = files.filter(f => f.status === 'failed').length

  const selectedFileData = files.find(f => f.file === activeFile)

  return (
    <div>
      <div className="results-summary">
        <div className="summary-item">
          <span className="summary-val">{componentsDocumented}</span>
          <span className="summary-label">Components documented</span>
        </div>
        <div className="summary-item">
          <span className="summary-val">{files.length}</span>
          <span className="summary-label">Files changed</span>
        </div>
        <div className="summary-item">
          <span className="summary-val" style={{ color: warnings > 0 ? 'var(--warn)' : 'inherit' }}>{warnings}</span>
          <span className="summary-label">Warnings</span>
        </div>
        <div className="summary-item">
          <span className="summary-val" style={{ color: failures > 0 ? 'var(--err)' : 'inherit' }}>{failures}</span>
          <span className="summary-label">Failures</span>
        </div>
        <div className="summary-item" style={{ marginLeft: 'auto' }}>
          <a href="/api/download-patch" download="docweave-changes.patch" style={{ textDecoration: 'none' }}>
            <button className="primary">
              <Download size={14} /> Download all changes (.patch)
            </button>
          </a>
        </div>
      </div>

      <div className="tabs-list" role="tablist">
        <button 
          className="tab-trigger" 
          role="tab" 
          aria-selected={activeTab === 'changes'}
          onClick={() => setActiveTab('changes')}
        >
          Changes
        </button>
        <button 
          className="tab-trigger" 
          role="tab" 
          aria-selected={activeTab === 'graph'}
          onClick={() => setActiveTab('graph')}
        >
          Dependency graph
        </button>
      </div>

      <div style={{ marginTop: '24px' }}>
        {activeTab === 'changes' && (
          <div className="results-layout">
            <div className="file-list-pane">
              {files.length === 0 ? (
                <div style={{ color: 'var(--text-muted)' }}>No files changed.</div>
              ) : (
                files.map(f => (
                  <div 
                    key={f.file} 
                    className={`file-list-item ${f.file === activeFile ? 'active' : ''}`}
                    onClick={() => setActiveFile(f.file)}
                  >
                    <div style={{ paddingTop: '2px', color: f.status === 'partial' ? 'var(--warn)' : f.status === 'failed' ? 'var(--err)' : 'var(--text-muted)' }}>
                      {f.status === 'partial' || f.status === 'failed' ? <AlertTriangle size={16} /> : <FileCode2 size={16} />}
                    </div>
                    <div className="file-list-item-content">
                      <div className="file-list-item-name" title={f.file}>{f.file}</div>
                      <div className="file-list-item-meta">
                        {f.processed_components || 0} docstrings
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
            
            <div className="diff-pane">
              {selectedFileData ? (
                <>
                  <div className="diff-header">
                    <div className="diff-filename">{selectedFileData.file}</div>
                    <button className="secondary" style={{ height: '28px', fontSize: '0.75rem' }} onClick={() => navigator.clipboard.writeText(selectedFileData.diff)}>
                      <Copy size={14} /> Copy patch
                    </button>
                  </div>
                  <DiffBlock diffText={selectedFileData.diff || ''} />
                </>
              ) : (
                <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  Select a file to view changes.
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'graph' && (
          <DependencyGraph onNavigateToFile={(f) => {
            setActiveFile(f)
            setActiveTab('changes')
          }} />
        )}
      </div>
    </div>
  )
}
