import React from 'react';
import PostList from '../posts/PostList';
import './Dashboard.css'; // Importar el archivo CSS

const Dashboard: React.FC = () => {
  const handleConnectInstagram = async () => {
    const token = localStorage.getItem('authToken'); // Usar la clave correcta

    if (!token) {
      alert('Debes iniciar sesión en SocialLab primero para conectar Instagram.');
      return;
    }

    try {
      console.log("Attempting to connect to Instagram...");
      // Redirigir directamente al endpoint del backend que inicia el flujo de OAuth
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

              <button className="btn btn-info mb-4" onClick={handleConnectInstagram}>
                Conectar Instagram
              </button>

              {/* Aquí se mostrará la lista de publicaciones */}
              <PostList />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
