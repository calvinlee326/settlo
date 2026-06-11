import { Navigate, useLocation } from 'react-router-dom';
import useAuthStore from '../store/authStore';

export default function ProtectedRoute({ children }) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const location = useLocation();

  if (!accessToken) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }
  return children;
}
