import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', // Ensure it listens on all interfaces within the container
    port: 5173,
    strictPort: true,
    hmr: {
      // protocol: 'ws',
      // host: 'localhost',
      // port: 80
      clientPort: 80
    },
    // --- ADD THIS ---
    // Allow requests from the 'frontend' service name within Docker
    // and from localhost (your browser via Nginx)
    allowedHosts: ['localhost', 'frontend']
    // ---------------
  }
})