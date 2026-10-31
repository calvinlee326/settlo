import React, { useEffect } from 'react';
import ReactDOM from 'react-dom/client';
import { createBrowserRouter, RouterProvider, ScrollRestoration } from 'react-router-dom';
import { SWRConfig, useSWRConfig } from 'swr';
import App from './App';
import useAuthStore from './store/authStore';
import { fetcher, initializeSession } from './api/axios';
import { savedData, saveSnapshot } from './lib/snapshot';
import './index.css';

initializeSession();

// Screens render from cache and refetch in the background; on open, the cache
// starts from the data saved last time (fallback). keepPreviousData holds a
// screen's data while a write refetches it (it would also hold a stale group
// if one page instance switched :id, which no link does). Errors are not
// retried: they are mostly 4xx, and focus/navigation refetch anyway.
const swrConfig = { fetcher, keepPreviousData: true, shouldRetryOnError: false, fallback: savedData };

function SessionApp() {
  const status = useAuthStore((s) => s.sessionStatus);
  const hasUser = useAuthStore((s) => Boolean(s.user));
  const { cache } = useSWRConfig();

  // Save when the app goes to the background: on phones it may be closed
  // from there without another event.
  useEffect(() => {
    const save = () => {
      if (document.visibilityState === 'hidden') saveSnapshot(useAuthStore.getState().user, cache);
    };
    document.addEventListener('visibilitychange', save);
    return () => document.removeEventListener('visibilitychange', save);
  }, [cache]);

  // A returning user skips the spinner and error screens: the app shows saved
  // data while the session restores, and pages show their own load errors.
  // The spinner fades in after 400ms, so a quick restore goes straight to the app.
  if (status === 'loading' && !hasUser) return (
    <div
      role="status"
      className="page-enter flex min-h-screen items-center justify-center"
      style={{ animationDelay: '400ms' }}
    >
      <div className="spinner-ring" />
      <span className="sr-only">Restoring your session…</span>
    </div>
  );
  if (status === 'error' && !hasUser) return (
    <div className="p-8">
      <p role="alert">Could not connect to Settlo. Your session has not been cleared.</p>
      <button className="mt-4 underline" onClick={initializeSession}>Try again</button>
    </div>
  );
  return <App />;
}

// A data router only for <ScrollRestoration>: a new page opens at the top and
// Back returns to where you were. App still declares its routes in <Routes>.
const router = createBrowserRouter([
  {
    path: '*',
    element: (
      <>
        <ScrollRestoration />
        <SessionApp />
      </>
    ),
  },
]);

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <SWRConfig value={swrConfig}>
      <RouterProvider router={router} />
    </SWRConfig>
  </React.StrictMode>
);
