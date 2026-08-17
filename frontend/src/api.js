import { io } from 'socket.io-client'

async function postJson(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return res.json()
}

async function getJson(url) {
  const res = await fetch(url)
  return res.json()
}

export function cloneRepo(url) {
  return postJson('/api/clone', { url })
}

export function getModels() {
  return getJson('/api/models')
}

export function startGeneration(model) {
  return postJson('/api/start_ollama', { model })
}

export function getResults() {
  return getJson('/api/results')
}

export function getDependencyGraph() {
  return getJson('/api/dependency-graph')
}

export function getStatus() {
  return getJson('/api/status')
}

// A single shared socket, connected on demand. The backend emits (see
// src/web/process_handler.py and visualization_handler.py for the exact
// payload shapes this listens for):
//   status_update  -> { status: {active_agent, status_message, current_component, current_file},
//                        progress: {total_components, processed_components, ...} }
//   log_message    -> { level, message }
//   log_line       -> "<raw line>"
//   docstring_updated -> { component }
//   complete       -> { message }
//   error          -> { message }
let socket = null

export function getSocket() {
  if (!socket) {
    // Connect directly to the Flask origin rather than through Vite's dev
    // proxy - Vite's Node-based proxy doesn't reliably relay the WebSocket
    // upgrade to Flask-SocketIO's eventlet server (falls back to constant
    // ECONNRESET). Flask-SocketIO already allows cross-origin connections
    // (cors_allowed_origins="*"), so connecting directly works cleanly.
    socket = io('http://localhost:5000', { path: '/socket.io' })
  }
  return socket
}
