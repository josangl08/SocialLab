import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext'; // Ruta corregida
import PostList from '../posts/PostList';
import CreatePost from '../posts/CreatePost';
import { Link } from 'react-router-dom'; // Importar Link
import './Dashboard.css'; // Importar el archivo CSS

const Dashboard: React.FC = () => {
  const { logout } = useAuth();
  const [refreshPosts, setRefreshPosts] = useState<boolean>(false);

  const handlePostCreated = () => {
    setRefreshPosts(prev => !prev); // Cambiar el estado para forzar la recarga de PostList
  };

  return (
    <div className="dashboard-container bg-info bg-opacity-10">
      <div className="container">
        <div className="row justify-content-center">
          <div className="col-12 col-md-10 col-lg-9 col-xl-8">
            <div className="card p-4 shadow-sm dashboard-card">
              <h2 className="mb-4 text-center text-primary">Bienvenido al Dashboard</h2>
              <p className="mb-4 text-center text-secondary">Has iniciado sesión correctamente.</p>
              <div className="d-flex justify-content-center mb-4">
                <Link to="/profile" className="btn btn-info me-2">Ver Perfil</Link> {/* Enlace al perfil */}
                <button
                  onClick={logout}
                  className="btn btn-danger"
                >
                  Cerrar Sesión
                </button>
              </div>

              {/* Componente para crear publicaciones */}
              <CreatePost onPostCreated={handlePostCreated} />

              {/* Aquí se mostrará la lista de publicaciones */}
              <PostList key={refreshPosts ? 'refresh' : 'no-refresh'} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
