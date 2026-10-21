export function cloneRepo(url) {
  return fetch('/api/clone', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url })
  }).then(res => res.json())
}

export function startGeneration(config) {
  return fetch('/api/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config)
  }).then(res => res.json())
}

export function startOllama(model) {
  return fetch('/api/start_ollama', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model })
  }).then(res => res.json())
}

export function stopGeneration() {
  return fetch('/api/stop', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  }).then(res => res.json())
}

export function getModels() {
  return fetch('/api/models').then(res => res.json())
}

export function getStatus() {
  return fetch('/api/status').then(res => res.json())
}

export function testApi(data) {
  return fetch('/api/test_api', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  }).then(res => res.json())
}

export function getResults() {
  return fetch('/api/results').then(res => res.json())
}

export function getCompleteness() {
  return fetch('/api/completeness').then(res => res.json())
}

export function getDependencyGraph() {
  return fetch('/api/dependency-graph').then(res => res.json())
}

import { io } from 'socket.io-client'

let socket = null

export function getSocket() {
  if (!socket) {
    // Dev (Vite on :5173) talks to Flask directly. In a production build the page is served by Flask
    // itself, so connect to the page's own origin - that is what makes a shared public link work
    // (a hard-coded 127.0.0.1 would point at each visitor's own computer).
    socket = io(import.meta.env.DEV ? 'http://127.0.0.1:5000' : undefined, { path: '/socket.io' })
  }
  return socket
}
