import React, { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import './Register.css'; // Importar el archivo CSS

const Register: React.FC = () => {
  const [email, setEmail] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [instagramHandle, setInstagramHandle] = useState<string>('');
  const [message, setMessage] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false); // Nuevo estado de carga
  const navigate = useNavigate();

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setMessage(''); // Limpiar mensajes anteriores
    setLoading(true); // Iniciar carga

    try {
      const response = await fetch('http://localhost:8000/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email,
          password,
          instagram_handle: instagramHandle,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setMessage('Registro exitoso! Usuario: ' + data.email + '. Redirigiendo a login...');
        setTimeout(() => {
          navigate('/login'); // Redirigir al login después de un registro exitoso
        }, 2000); // Redirigir después de 2 segundos
      } else {
        const errorData = await response.json();
        setMessage('Error al registrar: ' + (errorData.detail || 'Error desconocido'));
      }
    } catch (error) {
      setMessage('Error de red o servidor');
      console.error('Error de red o servidor:', error);
    } finally {
      setLoading(false); // Finalizar carga
    }
  };

  return (
    <div className="register-container bg-light">
      <div className="container">
        <div className="row justify-content-center">
          <div className="col-12 col-sm-10 col-md-8 col-lg-6 col-xl-5">
            <div className="card p-4 shadow-sm register-card">
              <h2 className="mb-4 text-center text-dark">Registro</h2>
              <form onSubmit={handleSubmit}>
                <div className="mb-3">
                  <input
                    type="email"
                    className="form-control"
                    placeholder="Email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    disabled={loading}
                  />
                </div>
                <div className="mb-3">
                  <input
                    type="password"
                    className="form-control"
                    placeholder="Contraseña"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    disabled={loading}
                  />
                </div>
                <div className="mb-3">
                  <input
                    type="text"
                    className="form-control"
                    placeholder="Usuario de Instagram"
                    value={instagramHandle}
                    onChange={(e) => setInstagramHandle(e.target.value)}
                    required
                    disabled={loading}
                  />
                </div>
                <button type="submit" className="btn btn-success w-100" disabled={loading}>
                  {loading ? (
                    <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                  ) : (
                    'Registrarse'
                  )}
                </button>
              </form>
              {message && (
                <p className={`mt-3 text-center ${message.startsWith('Error') ? 'text-danger' : 'text-success'}`}>
                  {message}
                </p>
              )}
              <p className="mt-3 text-center">
                ¿Ya tienes cuenta? <a href="/login" className="text-decoration-none">Inicia sesión aquí</a>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Register;