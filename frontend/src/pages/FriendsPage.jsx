import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../api/axios';
import Button from '../components/Button';
import ErrorMessage from '../components/ErrorMessage';
import { SkeletonList } from '../components/LoadingSpinner';
import { parseContact } from '../lib/handle';
import useAuthStore from '../store/authStore';

export default function FriendsPage() {
  const [friends, setFriends] = useState([]);
  const [requests, setRequests] = useState([]);
  const [contact, setContact] = useState('');
  const myHandle = useAuthStore((s) => s.user?.handle);
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
    if (!contact.trim()) return;
    const lookup = parseContact(contact);
    if (!lookup) {
      setError("Enter your friend's ID or a 10-digit US phone number");
      return;
    }
    try {
      await api.post('/friends/requests', lookup);
      setContact('');
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
      {notice && <p className="text-sm text-ink">{notice}</p>}

      <div className="card space-y-3 p-4">
        <p className="text-[13px] font-medium text-muted">Add a friend</p>
        <div className="flex gap-2">
          <input
            type="text"
            autoCapitalize="none"
            autoCorrect="off"
            placeholder="ID or phone number"
            value={contact}
            onChange={(e) => setContact(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addFriend()}
            className="min-w-0 flex-1 rounded-xl bg-sunk px-3 py-2 text-[14px] text-ink placeholder-muted outline-none"
          />
          <button
            onClick={addFriend}
            disabled={!contact.trim()}
            className="shrink-0 rounded-xl bg-ink px-4 py-2 text-[14px] font-medium text-white transition-opacity hover:opacity-80 disabled:opacity-40"
          >
            Add
          </button>
        </div>
        {myHandle && (
          <p className="text-[13px] text-muted">
            Your ID is <span className="font-medium text-ink">{myHandle}</span>.
            Share it so friends can add you.
          </p>
        )}
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
                {f.handle && <p className="text-[13px] text-muted">ID: {f.handle}</p>}
                <p
                  className={`text-sm tabular-nums ${
                    f.net_balance > 0
                      ? 'text-ink'
                      : f.net_balance < 0
                        ? 'text-ink'
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
