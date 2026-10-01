import { useEffect, useRef, useState } from 'react';
import ErrorMessage from './ErrorMessage';

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;
const GSI_SRC = 'https://accounts.google.com/gsi/client';
const GSI_MAX_WIDTH = 400;

let gsiPromise = null;

function loadGsi() {
  if (!gsiPromise) {
    gsiPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = GSI_SRC;
      script.async = true;
      script.onload = resolve;
      script.onerror = () => {
        gsiPromise = null;
        reject(new Error('Could not load Google sign-in. Try again later.'));
      };
      document.head.appendChild(script);
    });
  }
  return gsiPromise;
}

export const isGoogleEnabled = Boolean(GOOGLE_CLIENT_ID);

export default function GoogleButton({ onCredential, text = 'continue_with' }) {
  const containerRef = useRef(null);
  const callbackRef = useRef(onCredential);
  const [error, setError] = useState('');
  callbackRef.current = onCredential;

  useEffect(() => {
    let cancelled = false;
    loadGsi()
      .then(() => {
        if (cancelled || !containerRef.current) return;
        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: (response) => callbackRef.current(response.credential),
        });
        window.google.accounts.id.renderButton(containerRef.current, {
          theme: 'outline',
          size: 'large',
          text,
          width: Math.min(GSI_MAX_WIDTH, containerRef.current.offsetWidth),
        });
      })
      .catch((err) => setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [text]);

  return (
    <>
      <div ref={containerRef} className="flex min-h-[44px] justify-center" />
      <ErrorMessage message={error} />
    </>
  );
}
