import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // Fail loudly instead of silently bumping to 5174/5175 if 5173 is
    // already taken by a stray dev server from an earlier session — that
    // silent drift is what was causing "my changes aren't showing up"
    // (you were looking at the old server on a different port).
    strictPort: true,
  },
})
