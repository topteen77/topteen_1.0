import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Build for Django: output under static/game/ so collectstatic and /game/ view can serve the SPA
// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/static/game/',
  build: {
    outDir: '../../static/game',
    emptyOutDir: true,
  },
})
