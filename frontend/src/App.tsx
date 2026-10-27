import { RequestError } from './components/ui/RequestError';
import { UnsubscribePage } from './pages/UnsubscribePage';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './lib/auth';
import { Layout } from './components/layout/Layout';
import { LandingPage } from './pages/LandingPage';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { DashboardPage } from './pages/DashboardPage';
import { OpportunitiesPage } from './pages/OpportunitiesPage';
import { OpportunityDetailPage } from './pages/OpportunityDetailPage';
import { ApplicationsPage } from './pages/ApplicationsPage';
import { ProfilePage } from './pages/ProfilePage';
import { DigestPage } from './pages/DigestPage';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading, sessionError, retrySession, logout } = useAuth();
  if (loading) return <div className="flex items-center justify-center min-h-screen"><div className="animate-spin w-8 h-8 border-4 border-brand-500 border-t-transparent rounded-full" /></div>;
  if (sessionError) return <div className="max-w-lg mx-auto p-8"><RequestError message={sessionError} onRetry={retrySession} /><button className="btn-secondary mt-4" onClick={logout}>Sign out</button></div>;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { user, loading, sessionError, retrySession, logout } = useAuth();
  if (loading) return null;
  if (sessionError) return <div className="max-w-lg mx-auto p-8"><RequestError message={sessionError} onRetry={retrySession} /><button className="btn-secondary mt-4" onClick={logout}>Sign out</button></div>;
  if (user) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/unsubscribe" element={<UnsubscribePage />} />
      <Route path="/" element={<PublicRoute><LandingPage /></PublicRoute>} />
      <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
      <Route path="/register" element={<PublicRoute><RegisterPage /></PublicRoute>} />
      <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/opportunities" element={<OpportunitiesPage />} />
        <Route path="/opportunities/:id" element={<OpportunityDetailPage />} />
        <Route path="/applications" element={<ApplicationsPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/digest" element={<DigestPage />} />
      </Route>
    </Routes>
  );
}
