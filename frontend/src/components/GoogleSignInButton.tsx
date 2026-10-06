import { useEffect, useRef } from 'react';

interface GoogleSignInButtonProps {
  onCredential: (credential: string) => void;
  text?: 'signin_with' | 'signup_with' | 'continue_with';
}

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: Record<string, unknown>) => void;
          renderButton: (el: HTMLElement, options: Record<string, unknown>) => void;
        };
      };
    };
  }
}

const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;

// Google only accepts a button width between 200 and 400 px. We cap at 320 so it lines up
// with the form fields on desktop, and otherwise use whatever room the card really has.
const MIN_WIDTH = 200;
const MAX_WIDTH = 320;

export function GoogleSignInButton({ onCredential, text = 'signin_with' }: GoogleSignInButtonProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  // Refs so the effect below always calls the latest callback without needing
  // onCredential/text in its dependency array — re-running renderButton on every parent
  // re-render would flicker the button.
  const onCredentialRef = useRef(onCredential);
  const textRef = useRef(text);
  onCredentialRef.current = onCredential;
  textRef.current = text;

  useEffect(() => {
    if (!CLIENT_ID) return;
    const host = containerRef.current;
    if (!host) return;
    // The wrapper around us is as wide as the form column, so its width is the room we have.
    const measured = host.parentElement ?? host;
    let cancelled = false;
    let renderedWidth = 0;

    function render() {
      if (cancelled || !window.google) return;
      // clientWidth, not getBoundingClientRect(): on desktop the sign-in card is scaled down with
      // CSS zoom to fit short windows, and the bounding rect would report that shrunken size.
      const available = measured.clientWidth;
      if (available <= 0) {
        // Hidden (the other tab of the sign in / sign up card on a phone). Forget what we drew
        // so it is drawn again, at the right size, the moment it becomes visible.
        renderedWidth = 0;
        return;
      }
      // A fixed 320 px button was wider than the card on phones (a 360 px phone has ~280 px of
      // room), which stretched the whole form past the screen edge. Fit the room instead.
      const width = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, available));
      if (width === renderedWidth) return;
      renderedWidth = width;
      // Google keeps ONE global callback — the last initialize() wins — so (re)initialize
      // right before drawing, so a button that just became visible calls its own handler.
      window.google.accounts.id.initialize({
        client_id: CLIENT_ID,
        callback: (response: { credential: string }) => onCredentialRef.current(response.credential),
      });
      host!.replaceChildren();
      window.google.accounts.id.renderButton(host!, {
        theme: 'outline',
        size: 'large',
        width,
        text: textRef.current,
        // Google otherwise follows the browser language (it showed "Inloggen met Google"
        // on a Dutch-language browser). The whole app is English, so pin the button to English.
        locale: 'en',
      });
    }

    // Redraw when the room changes: rotating the phone, resizing, or the tab becoming visible.
    const observer = new ResizeObserver(render);
    observer.observe(measured);

    // The GIS script tag (index.html) loads async — poll briefly in case
    // this component mounts before it's finished.
    let interval: ReturnType<typeof setInterval> | undefined;
    if (window.google) {
      render();
    } else {
      interval = setInterval(() => {
        if (window.google) {
          clearInterval(interval);
          render();
        }
      }, 100);
    }

    return () => {
      cancelled = true;
      observer.disconnect();
      if (interval) clearInterval(interval);
    };
  }, []);

  if (!CLIENT_ID) return null; // Google sign-in not configured — quietly omit the button

  // max-w-full + overflow-hidden: whatever Google draws can never push the card wider.
  return <div ref={containerRef} className="max-w-full overflow-hidden" />;
}
