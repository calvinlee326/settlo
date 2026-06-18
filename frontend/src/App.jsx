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
import FriendsPage from './pages/FriendsPage';
import NewDirectExpensePage from './pages/NewDirectExpensePage';

function Layout({ children }) {
  return (
    <div className="min-h-screen">
      <Navbar />
      <main
        className="page-enter mx-auto max-w-[480px] px-4 pt-[76px]"
        style={{ paddingBottom: 'calc(7rem + env(safe-area-inset-bottom))' }}
      >
        {children}
      </main>
    </div>
  );
}

function AmbientBackground() {
  return (
    <>
      <div className="ambient-blob blob-1" />
      <div className="ambient-blob blob-2" />
      <div className="ambient-blob blob-3" />
    </>
  );
}

export default function App() {
  return (
    <>
      <AmbientBackground />
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
      <Route
        path="/friends"
        element={
          <ProtectedRoute>
            <Layout>
              <FriendsPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/friends/expenses/new"
        element={
          <ProtectedRoute>
            <Layout>
              <NewDirectExpensePage />
            </Layout>
          </ProtectedRoute>
        }
      />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
