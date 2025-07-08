import React, { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext'; // Ruta corregida
import './Login.css'; // Importar el archivo CSS

const Login: React.FC = () => {
  const [email, setEmail] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [message, setMessage] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false); // Nuevo estado de carga
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setMessage(''); // Limpiar mensajes anteriores
    setLoading(true); // Iniciar carga

    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    try {
      const response = await fetch('http://localhost:8000/token', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData.toString(),
      });

      if (response.ok) {
        const data = await response.json();
        login(data.access_token); // Guardar el token en el contexto y localStorage
        setMessage('Login exitoso!');
        navigate('/dashboard'); // Redirigir al dashboard
      } else {
        const errorData = await response.json();
        setMessage('Error al iniciar sesión: ' + (errorData.detail || 'Credenciales inválidas'));
      }
    } catch (error) {
      setMessage('Error de red o servidor: ' + error.message);
      console.error('Error de red o servidor:', error);
    } finally {
      setLoading(false); // Finalizar carga
    }
  };

  return (
    <div className="login-container bg-light">
      <div className="container">
        <div className="row justify-content-center">
          <div className="col-12 col-sm-10 col-md-8 col-lg-6 col-xl-5">
            <div className="card p-4 shadow-sm login-card">
              <h2 className="mb-4 text-center text-dark">Login</h2>
              <form onSubmit={handleSubmit}>
                <div className="mb-3">
                  <input
                    type="email"
                    className="form-control"
                    placeholder="Email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    disabled={loading} // Deshabilitar durante la carga
                  />
                </div>
                <div className="mb-3">
                  <input
                    type="password"
                    className="form-control"
                    placeholder="Password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    disabled={loading} // Deshabilitar durante la carga
                  />
                </div>
                <button type="submit" className="btn btn-primary w-100" disabled={loading}>
                  {loading ? (
                    <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                  ) : (
                    'Login'
                  )}
                </button>
              </form>
              {message && (
                <p className={`mt-3 text-center ${message.startsWith('Error') ? 'text-danger' : 'text-success'}`}>
                  {message}
                </p>
              )}
              <p className="mt-3 text-center">
                ¿No tienes cuenta? <a href="/register" className="text-decoration-none">Regístrate aquí</a>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
