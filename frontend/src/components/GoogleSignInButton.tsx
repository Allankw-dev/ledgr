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

export function GoogleSignInButton({ onCredential, text = 'signin_with' }: GoogleSignInButtonProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  // Refs so the render-once effect below always calls the latest callback
  // without needing onCredential/text in its dependency array — re-running
  // renderButton on every parent re-render would flicker the button.
  const onCredentialRef = useRef(onCredential);
  const textRef = useRef(text);
  onCredentialRef.current = onCredential;
  textRef.current = text;

  useEffect(() => {
    if (!CLIENT_ID) return;
    let cancelled = false;

    function render() {
      if (cancelled || !containerRef.current || !window.google) return;
      window.google!.accounts.id.initialize({
        client_id: CLIENT_ID,
        callback: (response: { credential: string }) => onCredentialRef.current(response.credential),
      });
      window.google!.accounts.id.renderButton(containerRef.current, {
        theme: 'outline',
        size: 'large',
        width: 320,
        text: textRef.current,
      });
    }

    if (window.google) {
      render();
      return;
    }

    // The GIS script tag (index.html) loads async — poll briefly in case
    // this component mounts before it's finished.
    const interval = setInterval(() => {
      if (window.google) {
        clearInterval(interval);
        render();
      }
    }, 100);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  if (!CLIENT_ID) return null; // Google sign-in not configured — quietly omit the button

  return <div ref={containerRef} />;
}
