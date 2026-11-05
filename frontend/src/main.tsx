import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import * as Sentry from '@sentry/react'
// Fonts are bundled with the app (SIL Open Font License 1.1: free to embed and redistribute), so opening Ledgr
// sends nothing to Google Fonts. Latin subset only.
import '@fontsource/space-grotesk/latin-400.css'
import '@fontsource/space-grotesk/latin-500.css'
import '@fontsource/space-grotesk/latin-600.css'
import '@fontsource/space-grotesk/latin-700.css'
import '@fontsource/ibm-plex-sans/latin-400.css'
import '@fontsource/ibm-plex-sans/latin-500.css'
import '@fontsource/ibm-plex-sans/latin-600.css'
import '@fontsource/ibm-plex-sans/latin-700.css'
import '@fontsource/ibm-plex-mono/latin-400.css'
import '@fontsource/ibm-plex-mono/latin-500.css'
import '@fontsource/ibm-plex-mono/latin-600.css'
import App from './App.tsx'
import './index.css'

// Error tracking is off unless VITE_SENTRY_DSN is set (Vercel env var). Errors only —
// no tracing/session replay, and no personal data is sent.
const sentryDsn = import.meta.env.VITE_SENTRY_DSN as string | undefined
if (sentryDsn) {
  Sentry.init({
    dsn: sentryDsn,
    environment: import.meta.env.MODE,
    // Flaky mobile networks and browser quirks aren't bugs in Ledgr.
    ignoreErrors: ['Network Error', 'Request aborted', 'ResizeObserver loop'],
  })
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Sentry.ErrorBoundary
      fallback={
        <div style={{ padding: '3rem 1.5rem', textAlign: 'center', fontFamily: 'sans-serif' }}>
          <h1 style={{ fontSize: '1.25rem', marginBottom: '0.5rem' }}>Something went wrong</h1>
          <p style={{ fontSize: '0.9rem', color: '#555' }}>Please refresh the page. If it keeps happening, tell the school office.</p>
        </div>
      }
    >
      <App />
    </Sentry.ErrorBoundary>
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
