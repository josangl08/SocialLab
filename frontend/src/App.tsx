import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import Login from './components/auth/Login';
import Register from './components/auth/Register';
import Dashboard from './components/dashboard/Dashboard';
import PostGenerator from './components/posts/PostGenerator';
import PlannerPage from './components/planner/PlannerPage';
import Analytics from './components/analytics/Analytics';
import SettingsPage from './components/settings/SettingsPage';
import HermesMind from './components/hermes-mind/HermesMind';
import MainLayout from './components/layout/MainLayout';
import { AuthProvider, useAuth } from './context/AuthContext';
import './App.css';
import 'bootstrap/dist/css/bootstrap.min.css';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <MainLayout>{children}</MainLayout> : <Navigate to="/login" replace />;
};

export const RedirectWithQuery: React.FC<{ to: string }> = ({ to }) => {
  const location = useLocation();
  return <Navigate to={`${to}${location.search}`} replace />;
};

function App() {
  return (
    <Router>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          
          {/* Rutas protegidas dentro del MainLayout */}
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/create-post"
            element={<RedirectWithQuery to="/generate" />}
          />
          <Route
            path="/planner"
            element={
              <ProtectedRoute>
                <PlannerPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/generate"
            element={
              <ProtectedRoute>
                <PostGenerator onPostGenerated={() => { /* Refrescar si es necesario */ }} />
              </ProtectedRoute>
            }
          />
          <Route
            path="/analytics"
            element={
              <ProtectedRoute>
                <Analytics />
              </ProtectedRoute>
            }
          />
          <Route
            path="/settings"
            element={
              <ProtectedRoute>
                <SettingsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/hermes-mind"
            element={
              <ProtectedRoute>
                <HermesMind />
              </ProtectedRoute>
            }
          />
          <Route
            path="/profile"
            element={<Navigate to="/settings" replace />}
          />
          <Route
            path="/accounts"
            element={<Navigate to="/settings" replace />}
          />

          {/* Redirigir a /dashboard si está autenticado, de lo contrario a /login */}
          <Route
            path="*"
            element={
              <AuthRedirect />
            }
          />
        </Routes>
      </AuthProvider>
    </Router>
  );
}

const AuthRedirect: React.FC = () => {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <Navigate to="/dashboard" replace /> : <Navigate to="/login" replace />;
};

export default App;
