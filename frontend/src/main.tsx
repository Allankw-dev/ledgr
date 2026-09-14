import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

// Service workers must never run during local development — once a URL
// is cached, this strategy serves it cache-first forever, which makes a
// dev server's saved changes invisible no matter how many times the file
// is edited. That's exactly what happened here: registering unconditionally
// earlier caused localhost to get stuck serving whatever was cached on
// first visit. Now it only registers on a real deployed origin.
//
// The isLocalhost check also actively unregisters and clears the caches
// of anything already stuck from before this fix, so reloading with this
// code is enough to self-heal — no manual DevTools steps needed.
const isLocalhost = ['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname);

if ('serviceWorker' in navigator) {
  if (isLocalhost) {
    navigator.serviceWorker.getRegistrations().then((registrations) => {
      registrations.forEach((registration) => registration.unregister());
    });
    if ('caches' in window) {
      caches.keys().then((keys) => keys.forEach((key) => caches.delete(key)));
    }
  } else {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js').catch(() => {
        // Non-fatal — the app works fine without it, just without the
        // installability/offline-shell benefits.
      });
    });
  }
}
