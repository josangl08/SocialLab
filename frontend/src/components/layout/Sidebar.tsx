import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import './Sidebar.css'; // Para estilos específicos del sidebar

const Sidebar: React.FC = () => {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="sidebar d-flex flex-column p-3 text-white bg-dark">
      <Link to="/dashboard" className="d-flex align-items-center mb-3 mb-md-0 me-md-auto text-white text-decoration-none">
        <span className="fs-4">SocialLab</span>
      </Link>
      <hr />
      <ul className="nav nav-pills flex-column mb-auto">
        <li className="nav-item">
          <Link to="/dashboard" className="nav-link text-white" aria-current="page">
            Dashboard
          </Link>
        </li>
        <li>
          <Link to="/create-post" className="nav-link text-white">
            Crear Publicación
          </Link>
        </li>
        <li>
          <Link to="/profile" className="nav-link text-white">
            Perfil de Usuario
          </Link>
        </li>
        <li>
          <Link to="/calendar" className="nav-link text-white">
            Calendario
          </Link>
        </li>
        <li>
          <button className="nav-link text-white w-100 text-start" onClick={handleLogout} style={{ border: 'none', background: 'none' }}>
            Cerrar Sesión
          </button>
        </li>
      </ul>
      <hr />
    </div>
  );
};

export default Sidebar;
