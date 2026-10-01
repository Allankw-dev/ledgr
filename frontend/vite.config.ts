import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The backend (CORS), Google sign-in, saved passwords and email links all
// expect the app at http://localhost:5173 — NOT http://127.0.0.1:5173, which
// the browser treats as a different site. The server binds to 127.0.0.1
// (Node on Windows can otherwise listen on IPv6 only and the browser can't
// connect), so Vite would print the 127.0.0.1 address; this plugin makes it
// print the localhost one instead.
const printLocalhostUrl = () => ({
  name: 'print-localhost-url',
  configureServer(server: { printUrls: () => void }) {
    server.printUrls = () => {
      console.log('\n  ➜  Open the app at:  http://localhost:5173/\n')
    }
  },
})

export default defineConfig({
  plugins: [react(), tailwindcss(), printLocalhostUrl()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    // Fail loudly instead of silently bumping to 5174/5175 if 5173 is
    // already taken by a stray dev server from an earlier session — that
    // silent drift is what was causing "my changes aren't showing up"
    // (you were looking at the old server on a different port).
    strictPort: true,
  },
})
