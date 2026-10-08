// Helpers for classifying the log lines streamed from the generation process.
//
// The backend forwards raw subprocess output, e.g.
//   2026-10-05 22:53:24,385 - src.agent.writer - WARNING - Error parsing ...
// so the level has to be read out of the text. Without this every line was tagged INFO and
// the Warnings / Errors tabs could never show anything.

const ANSI = /\u001b?\[[0-9;]*m/g // colour codes such as ESC[93m (the ESC byte is often already stripped)
const LEVEL_IN_LINE = /\s-\s(DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL)\s-\s/
const ERROR_HINT = /^Traceback \(most recent call last\)|^\s*File ".*", line \d+|^\w*(Error|Exception)\b[^\n]*:|Error generating|Failed to |No docstring generated|Could not find/
const WARN_HINT = /\bwarning\b|deprecat/i

// 'warning' | 'Warn' | 'ERROR' -> 'WARN' | 'ERROR' | 'INFO' | 'DEBUG'
export function normalizeLevel(level) {
  const l = String(level || 'INFO').toUpperCase()
  if (l === 'WARNING' || l === 'WARN') return 'WARN'
  if (l === 'ERROR' || l === 'CRITICAL' || l === 'FATAL') return 'ERROR'
  if (l === 'DEBUG') return 'DEBUG'
  return 'INFO'
}

export function stripAnsi(text) {
  return String(text).replace(ANSI, '')
}

// Level of one raw line. `previousLevel` lets indented continuation lines (traceback frames,
// wrapped messages) stay with the entry they belong to.
export function detectLevel(line, previousLevel = 'INFO') {
  const explicit = LEVEL_IN_LINE.exec(line)
  if (explicit) return normalizeLevel(explicit[1])
  if (ERROR_HINT.test(line)) return 'ERROR'
  if (/^\s+\S/.test(line) && (previousLevel === 'ERROR' || previousLevel === 'WARN')) return previousLevel
  if (WARN_HINT.test(line)) return 'WARN'
  return 'INFO'
}

export function makeLogEntry(rawLine, previousLevel) {
  const message = stripAnsi(rawLine)
  return {
    message,
    level: detectLevel(message, previousLevel),
    time: new Date().toLocaleTimeString('en-US', { hour12: false }),
  }
}
