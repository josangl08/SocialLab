import React, { createContext, useContext, useState, useEffect, useMemo } from 'react';
import type { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';

interface AuthContextType {
  token: string | null;
  login: (newToken: string) => void;
  logout: () => void;
  isAuthenticated: boolean;
  isInstagramConnected: boolean;
  setInstagramConnected: (status: boolean) => void;
  isSyncing: boolean;
  setSyncing: (status: boolean) => void;
  lastSync: Date | null;
  setLastSync: (date: Date | null) => void;
  syncCompleted: number;
  setSyncCompleted: (count: number) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const navigate = useNavigate();
  const [token, setToken] = useState<string | null>(localStorage.getItem('authToken'));
  const [isInstagramConnected, setInstagramConnected] = useState<boolean>(() => {
    return localStorage.getItem('isInstagramConnected') === 'true';
  });
  const [isSyncing, setSyncing] = useState<boolean>(false);
  const [lastSync, setLastSync] = useState<Date | null>(null);
  const [syncCompleted, setSyncCompleted] = useState<number>(0);

  useEffect(() => {
    if (token) {
      localStorage.setItem('authToken', token);
    } else {
      localStorage.removeItem('authToken');
    }
  }, [token]);

  useEffect(() => {
    localStorage.setItem('isInstagramConnected', isInstagramConnected.toString());
  }, [isInstagramConnected]);

  const login = (newToken: string) => {
    setToken(newToken);
  };

  const logout = () => {
    setToken(null);
    setInstagramConnected(false);
    setSyncing(false);
    setLastSync(null);
    setSyncCompleted(0);
  };

  const isAuthenticated = !!token;

  // Force logout + redirect on any 401 from our API, instead of leaving the
  // app silently rendering empty data with a stale/expired token.
  useEffect(() => {
    const originalFetch = window.fetch;
    window.fetch = async (...args) => {
      const response = await originalFetch(...args);
      if (response.status === 401 && localStorage.getItem('authToken')) {
        logout();
        navigate('/login', { replace: true });
      }
      return response;
    };
    return () => { window.fetch = originalFetch; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navigate]);

  const contextValue = useMemo(
    () => ({
      token,
      login,
      logout,
      isAuthenticated,
      isInstagramConnected,
      setInstagramConnected,
      isSyncing,
      setSyncing,
      lastSync,
      setLastSync,
      syncCompleted,
      setSyncCompleted,
    }),
    [
      token,
      isAuthenticated,
      isInstagramConnected,
      isSyncing,
      lastSync,
      syncCompleted,
    ]
  );

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
