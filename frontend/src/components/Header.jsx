import React, { useEffect, useState } from 'react'
import { Moon, Sun, Check } from 'lucide-react'

export default function Header({ status, phase, model }) {
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'light')

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('theme', theme)
  }, [theme])

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light')
  }

  const phases = [
    { id: 'form', label: 'Configure' },
    { id: 'running', label: 'Generate' },
    { id: 'results', label: 'Review' }
  ]
  const currentIndex = phases.findIndex(p => p.id === phase)

  let connText = 'Disconnected'
  let dotClass = 'error'
  if (status === 'ready' || status === 'complete') { connText = 'Ollama connected'; dotClass = 'done' }
  else if (status === 'running') { connText = 'Ollama connected'; dotClass = 'processing' }
  else if (status === 'error' || status === 'cancelled') { connText = 'Disconnected'; dotClass = 'error' }

  return (
    <header className="top-bar">
      <div style={{ display: 'flex', alignItems: 'center', gap: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 8l16 8M4 16l16-8" />
          </svg>
          <span style={{ fontFamily: '"IBM Plex Sans", sans-serif', fontWeight: 600, fontSize: '1rem', letterSpacing: '-0.02em' }}>
            DocWeave
          </span>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {phases.map((p, i) => {
            const isPast = i < currentIndex
            const isCurrent = i === currentIndex
            
            let color = 'var(--text-faint)'
            if (isCurrent) color = 'var(--text)'
            else if (isPast) color = 'var(--text-muted)'

            return (
              <React.Fragment key={p.id}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color, fontWeight: isCurrent ? 600 : 400 }}>
                  {p.label}
                  {isPast && <Check size={14} />}
                </div>
                {i < phases.length - 1 && <span style={{ color: 'var(--text-faint)' }}>›</span>}
              </React.Fragment>
            )
          })}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8125rem' }}>
          <div className={`status-mark ${dotClass}`} style={{ borderRadius: '50%', width: '8px', height: '8px', backgroundColor: 'currentColor' }}></div>
          <span style={{ color: 'var(--text-muted)' }}>{connText}</span>
        </div>
        
        {model && (
          <div className="mono" style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
            {model}
          </div>
        )}

        <button className="icon-btn" onClick={toggleTheme} aria-label="Toggle theme" title="Toggle theme">
          {theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}
        </button>
      </div>
    </header>
  )
}
