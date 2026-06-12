import { Navigate, useLocation } from 'react-router-dom';
import { useIsAuthenticated } from '../store/authStore';

export default function ProtectedRoute({ children }) {
  const isAuthenticated = useIsAuthenticated();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }
  return children;
}
