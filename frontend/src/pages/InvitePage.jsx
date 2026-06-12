import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../api/axios';
import Button from '../components/Button';
import ErrorMessage from '../components/ErrorMessage';
import LoadingSpinner from '../components/LoadingSpinner';

export default function InvitePage() {
  const { token } = useParams();
  const navigate = useNavigate();
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [joining, setJoining] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api
      .get(`/groups/join/${token}`)
      .then(({ data }) => setPreview(data))
      .catch((err) =>
        setError(err.response?.data?.detail || 'Invalid invite link')
      )
      .finally(() => setLoading(false));
  }, [token]);

  const handleJoin = async () => {
    setJoining(true);
    setError('');
    try {
      const { data } = await api.post(`/groups/join/${token}`);
      navigate(`/groups/${data.id}`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to join group');
      setJoining(false);
    }
  };

  if (loading) return <LoadingSpinner />;
  if (!preview) return <ErrorMessage message={error || 'Invalid invite link'} />;

  return (
    <div className="space-y-4">
      <div className="glass-strong p-8 text-center">
        <p className="text-[15px] text-white/55">
          You have been invited to join
        </p>
        <h1 className="mt-2 text-[28px] font-semibold text-white">
          {preview.name}
        </h1>
        {preview.description && (
          <p className="mt-2 text-[15px] text-white/55">{preview.description}</p>
        )}
        <p className="mt-4 text-[13px] text-white/30">
          {preview.member_count} of {preview.max_members} members
          {preview.created_by_username &&
            ` · created by ${preview.created_by_username}`}
        </p>
        <ErrorMessage message={error} />
        <div className="mt-6">
          {preview.is_member ? (
            <Button
              className="w-full"
              onClick={() => navigate(`/groups/${preview.group_id}`)}
            >
              You are already a member — open group
            </Button>
          ) : (
            <Button
              variant="accent"
              className="w-full"
              onClick={handleJoin}
              disabled={joining}
            >
              {joining ? 'Joining…' : 'Join Group'}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
