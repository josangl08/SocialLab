import React, { useEffect, useState } from 'react';
import { useAuth } from '../../context/AuthContext'; // Ruta corregida
import { Link } from 'react-router-dom';
import './UserProfile.css'; // Importar el archivo CSS

interface User {
  id: string;
  email: string;
  created_at: string;
}

const UserProfile: React.FC = () => {
  const { token } = useAuth();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchUserProfile = async () => {
      if (!token) {
        setError('No hay token de autenticación disponible.');
        setLoading(false);
        return;
      }

      try {
        const response = await fetch('http://localhost:8000/users/me', {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });

        if (response.ok) {
          const data: User = await response.json();
          setUser(data);
        } else {
          const errorData = await response.json();
          setError('Error al cargar el perfil: ' + (errorData.detail || 'Error desconocido'));
        }
      } catch (err) {
        setError('Error de red o servidor: ' + err.message);
        console.error('Error de red o servidor:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchUserProfile();
  }, [token]);

  if (loading) {
    return <p className="text-center text-primary">Cargando perfil...</p>;
  }

  if (error) {
    return <p className="text-danger text-center">{error}</p>;
  }

  if (!user) {
    return <p className="text-center">No se pudo cargar la información del usuario.</p>;
  }

  return (
    <div className="user-profile-container bg-info bg-opacity-10">
      <div className="container">
        <div className="row justify-content-center">
          <div className="col-12 col-sm-10 col-md-8 col-lg-6 col-xl-5">
            <div className="card p-4 shadow-sm user-profile-card">
              <h2 className="mb-4 text-center text-primary">Perfil de Usuario</h2>
              <div className="mb-3">
                <p className="card-text"><strong className="text-dark">ID de Usuario:</strong> {user.id}</p>
              </div>
              <div className="mb-3">
                <p className="card-text"><strong className="text-dark">Email:</strong> {user.email}</p>
              </div>
              <div className="mb-3">
                <p className="card-text"><strong className="text-dark">Miembro desde:</strong> {new Date(user.created_at).toLocaleString()}</p>
              </div>
              <div className="text-center mt-4">
                <Link to="/dashboard" className="btn btn-secondary">Volver al Dashboard</Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UserProfile;