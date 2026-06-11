import { Navigate, Route, Routes } from 'react-router-dom';
import ProtectedRoute from './components/ProtectedRoute';
import Navbar from './components/Navbar';
import LoginPage from './pages/LoginPage';
import VerifyPage from './pages/VerifyPage';
import HomePage from './pages/HomePage';
import NewGroupPage from './pages/NewGroupPage';
import GroupDetailPage from './pages/GroupDetailPage';
import NewExpensePage from './pages/NewExpensePage';
import SettlementPage from './pages/SettlementPage';
import InvitePage from './pages/InvitePage';

function Layout({ children }) {
  return (
    <div className="min-h-screen bg-slate-100">
      <Navbar />
      <main className="mx-auto max-w-md px-4 pb-24 pt-4">{children}</main>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/verify" element={<VerifyPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout>
              <HomePage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/groups/new"
        element={
          <ProtectedRoute>
            <Layout>
              <NewGroupPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/groups/:id"
        element={
          <ProtectedRoute>
            <Layout>
              <GroupDetailPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/groups/:id/expenses/new"
        element={
          <ProtectedRoute>
            <Layout>
              <NewExpensePage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/groups/:id/settle"
        element={
          <ProtectedRoute>
            <Layout>
              <SettlementPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/invite/:token"
        element={
          <ProtectedRoute>
            <Layout>
              <InvitePage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
