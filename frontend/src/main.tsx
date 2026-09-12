import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

// Registered after load so it never competes with the initial page load
// for bandwidth/priority — installability and the offline shell only
// matter on the SECOND visit anyway.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {
      // Non-fatal — the app works fine without it, just without the
      // installability/offline-shell benefits.
    });
  });
}
