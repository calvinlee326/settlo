import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { SWRConfig } from 'swr';
import App from './App';
import useAuthStore from './store/authStore';
import { fetcher, initializeSession } from './api/axios';
import './index.css';

initializeSession();

// Screens render from cache and refetch in the background. keepPreviousData
// holds a screen's data while a write refetches it (it would also hold a stale
// group if one page instance switched :id, which no link does). Errors are not
// retried: they are mostly 4xx, and focus/navigation refetch anyway.
const swrConfig = { fetcher, keepPreviousData: true, shouldRetryOnError: false };

function SessionApp() {
  const status = useAuthStore((s) => s.sessionStatus);
  if (status === 'loading') return <p role="status" className="p-8">Restoring your session…</p>;
  if (status === 'error') return (
    <div className="p-8">
      <p role="alert">Could not connect to Settlo. Your session has not been cleared.</p>
      <button className="mt-4 underline" onClick={initializeSession}>Try again</button>
    </div>
  );
  return <App />;
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <SWRConfig value={swrConfig}>
      <BrowserRouter>
        <SessionApp />
      </BrowserRouter>
    </SWRConfig>
  </React.StrictMode>
);
