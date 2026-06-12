import { Navigate, useLocation } from 'react-router-dom';
import useAuthStore from '../store/authStore';

export default function ProtectedRoute({ children }) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const refreshToken = useAuthStore((state) => state.refreshToken);
  const location = useLocation();

  if (!accessToken && !refreshToken) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }
  return children;
}
