import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import useAuthStore from './store/authStore';
import { initializeSession } from './api/axios';
import './index.css';

initializeSession();

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
    <BrowserRouter>
      <SessionApp />
    </BrowserRouter>
  </React.StrictMode>
);
