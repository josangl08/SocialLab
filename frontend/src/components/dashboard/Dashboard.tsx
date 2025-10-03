import React, { useEffect, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import PostList from '../posts/PostList';
import { useAuth } from '../../context/AuthContext';
import './Dashboard.css';

const Dashboard: React.FC = () => {
  const { 
    isInstagramConnected, 
    setInstagramConnected, 
    isSyncing, 
    setSyncing, 
    lastSync, 
    setLastSync, 
    setSyncCompleted 
  } = useAuth();
  const location = useLocation();

  const checkInstagramStatus = useCallback(async () => {
    const token = localStorage.getItem('authToken');
    if (!token) return;

    try {
      const response = await fetch('http://localhost:8000/instagram/status', {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.ok) {
        const data = await response.json();
        setInstagramConnected(data.connected);

        if (data.expired) {
          alert('Tu token de Instagram ha expirado. Por favor vuelve a conectar tu cuenta.');
        }
      }
    } catch (error) {
      console.error('Error al verificar estado de Instagram:', error);
    }
  }, [setInstagramConnected]);

  const handleSync = useCallback(async () => {
    if (isSyncing || (lastSync && new Date().getTime() - lastSync.getTime() < 5 * 60 * 1000)) {
      return;
    }

    const token = localStorage.getItem('authToken');
    if (!token) return;

    setSyncing(true);
    try {
      const response = await fetch(`http://localhost:8000/instagram/sync`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.ok) {
        setLastSync(new Date());
        setSyncCompleted(prev => prev + 1);
      } else {
        console.error('Error al sincronizar con Instagram');
        setLastSync(new Date());
      }
    } catch (error) {
      console.error('Error en la sincronización:', error);
      setLastSync(new Date());
    } finally {
      setSyncing(false);
    }
  }, [isSyncing, lastSync, setSyncing, setLastSync, setSyncCompleted]);

  useEffect(() => {
    // Verificar estado real de Instagram al montar el componente
    checkInstagramStatus();
  }, [checkInstagramStatus]);

  useEffect(() => {
    const queryParams = new URLSearchParams(location.search);
    if (queryParams.get('instagram_connected') === 'true') {
      setInstagramConnected(true);
      handleSync();
    }
  }, [location, setInstagramConnected, handleSync]);

  useEffect(() => {
    if (isInstagramConnected) {
      handleSync();
    }
  }, [isInstagramConnected, handleSync]);

  const handleConnectInstagram = async () => {
    const token = localStorage.getItem('authToken');
    if (!token) {
      alert('Debes iniciar sesión en SocialLab primero para conectar Instagram.');
      return;
    }
    try {
      window.location.href = `http://localhost:8000/instagram/login?token=${token}`;
    } catch (error) {
      console.error('Error en handleConnectInstagram:', error);
      alert('Ocurrió un error al intentar conectar con Instagram.');
    }
  };

  return (
    <div className="dashboard-container">
      <div className="container">
        <div className="row justify-content-center">
          <div className="col-12">
            <div className="card p-4 shadow-sm dashboard-card">
              <h2 className="mb-4 text-center text-primary">Bienvenido al Dashboard</h2>
              <p className="mb-4 text-center text-secondary">Aquí puedes ver tus publicaciones.</p>

              {!isInstagramConnected ? (
                <button className="btn btn-info mb-4" onClick={handleConnectInstagram}>
                  Conectar Instagram
                </button>
              ) : (
                <button className="btn btn-secondary mb-4" onClick={handleSync} disabled={isSyncing}>
                  {isSyncing ? 'Sincronizando...' : 'Sincronizar con Instagram'}
                </button>
              )}

              <PostList />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;