import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../api/axios';
import Button from '../components/Button';
import ErrorMessage from '../components/ErrorMessage';
import { SkeletonList } from '../components/LoadingSpinner';
import { formatPhone } from '../lib/phone';

export default function FriendsPage() {
  const [friends, setFriends] = useState([]);
  const [requests, setRequests] = useState([]);
  const [phone, setPhone] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true);

  const load = () =>
    Promise.all([api.get('/friends'), api.get('/friends/requests')])
      .then(([f, r]) => {
        setFriends(f.data);
        setRequests(r.data);
      })
      .catch((err) =>
        setError(err.response?.data?.detail || 'Failed to load friends')
      )
      .finally(() => setLoading(false));

  useEffect(() => {
    load();
  }, []);

  const addFriend = async () => {
    setError('');
    setNotice('');
    if (!phone.trim()) return;
    let digits = phone.replace(/\D/g, '');
    if (digits.length === 11 && digits.startsWith('1')) {
      digits = digits.slice(1);
    }
    if (digits.length !== 10) {
      setError('Enter a valid 10-digit US phone number');
      return;
    }
    try {
      await api.post('/friends/requests', { phone_number: `+1${digits}` });
      setPhone('');
      setNotice('Request sent');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to send request');
    }
  };

  const respond = async (id, action) => {
    setError('');
    try {
      await api.post(`/friends/requests/${id}/${action}`);
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update request');
    }
  };

  const settle = async (friendId) => {
    setError('');
    try {
      await api.post(`/friends/${friendId}/settle`);
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to settle');
    }
  };

  const remove = async (friendId) => {
    if (!window.confirm('Remove this friend?')) return;
    setError('');
    try {
      await api.delete(`/friends/${friendId}`);
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to remove friend');
    }
  };

  if (loading) return <SkeletonList count={3} />;

  return (
    <div className="space-y-4">
      <h1 className="text-[28px] font-semibold text-ink">Friends</h1>
      <ErrorMessage message={error} />
      {notice && <p className="text-sm text-moss">{notice}</p>}

      <div className="card space-y-3 p-4">
        <p className="text-[13px] font-medium text-muted">Add a friend</p>
        <div className="flex gap-2">
          <input
            type="tel"
            inputMode="numeric"
            placeholder="909-555-0101"
            value={phone}
            onChange={(e) => setPhone(formatPhone(e.target.value))}
            onKeyDown={(e) => e.key === 'Enter' && addFriend()}
            className="min-w-0 flex-1 rounded-xl bg-sunk px-3 py-2 text-[14px] text-ink placeholder-muted outline-none"
          />
          <button
            onClick={addFriend}
            disabled={!phone.trim()}
            className="shrink-0 rounded-xl bg-slate-deep px-4 py-2 text-[14px] font-medium text-ink transition-opacity hover:opacity-80 disabled:opacity-40"
          >
            Add
          </button>
        </div>
      </div>

      {requests.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-lg font-medium text-ink">Requests</h2>
          {requests.map((r) => (
            <div
              key={r.id}
              className="card flex items-center justify-between p-4"
            >
              <span className="text-[15px] text-ink">
                {r.requester_username || 'Someone'}
              </span>
              <div className="flex gap-2">
                <Button variant="accent" onClick={() => respond(r.id, 'accept')}>
                  Accept
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => respond(r.id, 'decline')}
                >
                  Decline
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="space-y-2">
        <h2 className="text-lg font-medium text-ink">Your friends</h2>
        {friends.length === 0 ? (
          <div className="rounded-card border border-dashed border-rule bg-surface p-8 text-center">
            <p className="text-[15px] text-muted">No friends yet.</p>
          </div>
        ) : (
          friends.map((f) => (
            <div
              key={f.id}
              className="card flex items-center justify-between p-4"
            >
              <div>
                <p className="text-[15px] font-medium text-ink">
                  {f.username || f.phone_number}
                </p>
                <p
                  className={`text-sm tabular-nums ${
                    f.net_balance > 0
                      ? 'text-moss'
                      : f.net_balance < 0
                        ? 'text-clay'
                        : 'text-muted'
                  }`}
                >
                  {f.net_balance > 0
                    ? `owes you $${f.net_balance.toFixed(2)}`
                    : f.net_balance < 0
                      ? `you owe $${Math.abs(f.net_balance).toFixed(2)}`
                      : 'settled up'}
                </p>
              </div>
              <div className="flex gap-2">
                {f.net_balance !== 0 ? (
                  <Button variant="accent" onClick={() => settle(f.id)}>
                    Settle
                  </Button>
                ) : (
                  <Button variant="secondary" onClick={() => remove(f.id)}>
                    Remove
                  </Button>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      <Link
        to="/friends/expenses/new"
        aria-label="Add friend expense"
        className="fab"
      >
        +
      </Link>
    </div>
  );
}
