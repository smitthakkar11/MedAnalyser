import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Google Identity Services integration.
 *
 * The GIS script is loaded on demand (not on every page) and only when a client
 * id is configured. It returns an ID token, which is then verified
 * *server-side* — the browser's word about who the user is counts for nothing.
 */

const GIS_SRC = 'https://accounts.google.com/gsi/client';

interface GoogleCredentialResponse {
  credential?: string;
}

interface GoogleAccountsId {
  initialize: (config: {
    client_id: string;
    callback: (response: GoogleCredentialResponse) => void;
    ux_mode?: 'popup' | 'redirect';
  }) => void;
  prompt: () => void;
}

declare global {
  interface Window {
    google?: { accounts?: { id?: GoogleAccountsId } };
  }
}

export const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? '';

/** True when the deployment has Google sign-in configured. */
export const googleSignInConfigured = GOOGLE_CLIENT_ID.length > 0;

function loadGisScript(): Promise<void> {
  if (window.google?.accounts?.id) return Promise.resolve();

  return new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${GIS_SRC}"]`);
    if (existing) {
      existing.addEventListener('load', () => resolve(), { once: true });
      existing.addEventListener('error', () => reject(new Error('load failed')), { once: true });
      return;
    }
    const script = document.createElement('script');
    script.src = GIS_SRC;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('Could not load Google sign-in.'));
    document.head.appendChild(script);
  });
}

interface UseGoogleSignInOptions {
  onCredential: (idToken: string) => void | Promise<void>;
  onError: (message: string) => void;
}

export function useGoogleSignIn({ onCredential, onError }: UseGoogleSignInOptions) {
  const [pending, setPending] = useState(false);
  const handlers = useRef({ onCredential, onError });

  useEffect(() => {
    handlers.current = { onCredential, onError };
  }, [onCredential, onError]);

  const start = useCallback(async () => {
    if (!googleSignInConfigured) {
      handlers.current.onError('Google sign-in is not configured for this deployment.');
      return;
    }

    setPending(true);
    try {
      await loadGisScript();
      const identity = window.google?.accounts?.id;
      if (!identity) throw new Error('Google sign-in is unavailable.');

      identity.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: (response) => {
          if (!response.credential) {
            handlers.current.onError('Google did not return a credential.');
            setPending(false);
            return;
          }
          void Promise.resolve(handlers.current.onCredential(response.credential)).finally(() =>
            setPending(false),
          );
        },
      });
      identity.prompt();
    } catch {
      handlers.current.onError('Could not start Google sign-in. Please try again.');
      setPending(false);
    }
  }, []);

  return { start, pending, configured: googleSignInConfigured };
}
