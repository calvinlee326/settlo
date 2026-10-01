import { useEffect, useState } from 'react';
import api from '../api/axios';
import { HANDLE_RULES, isValidHandle, normalizeHandle } from '../lib/handle';

const CHECK_DELAY_MS = 400;

export default function HandleInput({ value, onChange, currentHandle, hint, autoFocus }) {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    const handle = normalizeHandle(value);
    if (!handle || handle === currentHandle) {
      setStatus(null);
      return undefined;
    }
    if (!isValidHandle(handle)) {
      setStatus({ ok: false, message: `Must be ${HANDLE_RULES}.` });
      return undefined;
    }
    setStatus({ ok: null, message: 'Checking…' });
    const controller = new AbortController();
    const timer = setTimeout(() => {
      api
        .get('/auth/handle-available', { params: { handle }, signal: controller.signal })
        .then(({ data }) =>
          setStatus(
            data.available
              ? { ok: true, message: `${data.handle} is available` }
              : { ok: false, message: data.message },
          ),
        )
        // ponytail: the live check is advisory; saving re-checks on the server.
        .catch(() => {
          if (!controller.signal.aborted) setStatus(null);
        });
    }, CHECK_DELAY_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [value, currentHandle]);

  return (
    <div>
      <input
        type="text"
        placeholder="e.g. alex.chen"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        maxLength={31}
        autoCapitalize="none"
        autoCorrect="off"
        autoFocus={autoFocus}
        aria-describedby="handle-status"
        className="input"
      />
      <p
        id="handle-status"
        role="status"
        className={`mt-1.5 text-[12px] ${status?.ok === false ? 'font-medium text-ink' : 'text-muted'}`}
      >
        {status ? `${status.ok === true ? '✓ ' : ''}${status.message}` : hint}
      </p>
    </div>
  );
}
