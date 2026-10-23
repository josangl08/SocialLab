import React from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import 'bootstrap-icons/font/bootstrap-icons.css';
import './Sidebar.css';

const Sidebar: React.FC = () => {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const menuItems = [
    { path: '/dashboard', label: 'Dashboard', icon: 'bi-speedometer2' },
    { path: '/planner', label: 'Planner', icon: 'bi-calendar-event' },
    { path: '/generate', label: 'Content Studio', icon: 'bi-palette2' },
    { path: '/analytics', label: 'Analytics', icon: 'bi-bar-chart-line' },
    { path: '/hermes-mind', label: 'Hermes Mind', icon: 'bi-cpu' },
    { path: '/strategy', label: 'Estrategia', icon: 'bi-compass' },
    { path: '/settings', label: 'Settings', icon: 'bi-gear' },
  ];

  return (
    <nav className="sidebar d-flex flex-column p-3 text-white bg-dark" aria-label="Navegación principal">
      <Link
        to="/dashboard"
        className="d-flex align-items-center mb-2 mb-md-0 me-md-auto text-white text-decoration-none"
      >
        <i className="bi bi-grid-3x3-gap-fill me-2" style={{ fontSize: '1.25rem' }}></i>
        <span className="fs-4 fw-bold">SocialLab</span>
      </Link>
      <hr />

      <ul className="nav nav-pills flex-column mb-auto">
        {menuItems.map((item) => (
          <li key={item.path} className="nav-item">
            <Link
              to={item.path}
              className={`nav-link text-white d-flex align-items-center ${
                location.pathname === item.path ? 'active' : ''
              }`}
            >
              <i className={`bi ${item.icon} me-3 fs-5`}></i>
              <span>{item.label}</span>
            </Link>
          </li>
        ))}
      </ul>

      <hr />

      <div className="dropdown">
        <button
          className="nav-link text-white w-100 text-start d-flex align-items-center"
          onClick={handleLogout}
          style={{ border: 'none', background: 'none' }}
        >
          <i className="bi bi-box-arrow-right me-3 fs-5"></i>
          <span>Cerrar Sesión</span>
        </button>
      </div>
    </nav>
  );
};

export default Sidebar;
