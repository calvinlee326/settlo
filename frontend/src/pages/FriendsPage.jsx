import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../api/axios';
import Button from '../components/Button';
import ErrorMessage from '../components/ErrorMessage';
import { SkeletonList } from '../components/LoadingSpinner';

function formatPhone(value) {
  let d = value.replace(/\D/g, '');
  if (d.length === 11 && d.startsWith('1')) d = d.slice(1);
  d = d.slice(0, 10);
  const parts = [d.slice(0, 3), d.slice(3, 6), d.slice(6, 10)].filter(Boolean);
  return parts.join('-');
}

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
      <h1 className="text-[28px] font-semibold text-white">Friends</h1>
      <ErrorMessage message={error} />
      {notice && <p className="text-sm text-emerald-400">{notice}</p>}

      <div className="glass space-y-3 p-4">
        <p className="text-[13px] font-medium text-white/55">Add a friend</p>
        <div className="flex gap-2">
          <input
            type="tel"
            placeholder="909-555-0101"
            value={phone}
            onChange={(e) => setPhone(formatPhone(e.target.value))}
            onKeyDown={(e) => e.key === 'Enter' && addFriend()}
            className="min-w-0 flex-1 rounded-xl bg-white/10 px-3 py-2 text-[14px] text-white placeholder-white/30 outline-none"
          />
          <button
            onClick={addFriend}
            disabled={!phone.trim()}
            className="shrink-0 rounded-xl bg-violet-500 px-4 py-2 text-[14px] font-medium text-white transition-opacity hover:opacity-80 disabled:opacity-40"
          >
            Add
          </button>
        </div>
      </div>

      {requests.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-lg font-medium text-white/90">Requests</h2>
          {requests.map((r) => (
            <div
              key={r.id}
              className="glass flex items-center justify-between p-4"
            >
              <span className="text-[15px] text-white/85">
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
        <h2 className="text-lg font-medium text-white/90">Your friends</h2>
        {friends.length === 0 ? (
          <div className="rounded-glass border border-dashed border-white/15 bg-white/[0.03] p-8 text-center">
            <p className="text-[15px] text-white/55">No friends yet.</p>
          </div>
        ) : (
          friends.map((f) => (
            <div
              key={f.id}
              className="glass flex items-center justify-between p-4"
            >
              <div>
                <p className="text-[15px] font-medium text-white/85">
                  {f.username || f.phone_number}
                </p>
                <p
                  className={`text-sm tabular-nums ${
                    f.net_balance > 0
                      ? 'text-emerald-400'
                      : f.net_balance < 0
                        ? 'text-red-400'
                        : 'text-white/45'
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
