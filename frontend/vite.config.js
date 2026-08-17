import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      // Socket.IO is NOT proxied - the client connects directly to Flask's
      // origin (see frontend/src/api.js) since Vite's proxy doesn't reliably
      // relay WebSocket upgrades to Flask-SocketIO's eventlet server.
    },
  },
})
