import React, { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import 'bootstrap-icons/font/bootstrap-icons.css';
import './Login.css';

const Login: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [message, setMessage] = useState('');
  const [isError, setIsError] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorKey, setErrorKey] = useState(0);

  const navigate = useNavigate();
  const { login } = useAuth();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setMessage('');
    setLoading(true);

    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    try {
      const response = await fetch('http://localhost:8000/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData.toString(),
      });

      if (response.ok) {
        const data = await response.json();
        login(data.access_token);
        navigate('/dashboard');
      } else {
        const err = await response.json();
        setIsError(true);
        setMessage(err.detail || 'Credenciales inválidas');
        setErrorKey(k => k + 1);
      }
    } catch (error: unknown) {
      setIsError(true);
      setMessage('Error de conexión con el servidor');
      setErrorKey(k => k + 1);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      {/* Background — Aurora Galáctica */}
      <div className="login-stars-sm" />
      <div className="login-stars-md" />
      <div className="login-stars-lg" />
      <div className="login-conic" />
      <div className="login-glow-a" />
      <div className="login-glow-b" />
      <div className="login-beam login-beam-1" />
      <div className="login-beam login-beam-2" />
      <div className="login-beam login-beam-3" />
      <div className="login-vignette" />

      {/* Card */}
      <div
        className="login-card"
        style={{
          width: '100%',
          maxWidth: 420,
          background: '#161b22',
          borderRadius: 18,
          border: '1px solid rgba(255,255,255,0.07)',
          boxShadow: '0 32px 80px rgba(0,0,0,0.5)',
          padding: '40px 36px',
          position: 'relative',
          zIndex: 1,
        }}
      >
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div
            className="login-logo-icon"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 56,
              height: 56,
              borderRadius: 16,
              background: 'linear-gradient(135deg, #667eea, #764ba2)',
              boxShadow: '0 8px 28px rgba(102,126,234,0.4)',
              marginBottom: 18,
            }}
          >
            <i className="bi bi-grid-3x3-gap-fill" style={{ color: '#fff', fontSize: '1.45rem' }} />
          </div>
          <h1 style={{ color: '#e8e9ed', fontSize: '1.55rem', fontWeight: 700, margin: 0 }}>
            SocialLab
          </h1>
          <p style={{ color: '#4b5563', fontSize: '0.82rem', marginTop: 6, marginBottom: 0 }}>
            Planifica y automatiza tu contenido
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit}>
          {/* Email */}
          <div style={{ position: 'relative', marginBottom: 14 }}>
            <i
              className="bi bi-envelope"
              style={{
                position: 'absolute', left: 14, top: '50%',
                transform: 'translateY(-50%)',
                color: '#4b5563', fontSize: '0.9rem', pointerEvents: 'none',
              }}
            />
            <input
              type="email"
              className="login-input"
              placeholder="Email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              disabled={loading}
              autoComplete="email"
            />
          </div>

          {/* Password */}
          <div style={{ position: 'relative', marginBottom: 24 }}>
            <i
              className="bi bi-lock"
              style={{
                position: 'absolute', left: 14, top: '50%',
                transform: 'translateY(-50%)',
                color: '#4b5563', fontSize: '0.9rem', pointerEvents: 'none',
              }}
            />
            <input
              type={showPassword ? 'text' : 'password'}
              className="login-input"
              placeholder="Contraseña"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              disabled={loading}
              autoComplete="current-password"
              style={{ paddingRight: 44 }}
            />
            <button
              type="button"
              onClick={() => setShowPassword(p => !p)}
              style={{
                position: 'absolute', right: 12, top: '50%',
                transform: 'translateY(-50%)',
                background: 'none', border: 'none', padding: 4,
                color: '#4b5563', cursor: 'pointer', lineHeight: 1,
                transition: 'color 0.15s',
              }}
              onMouseEnter={e => (e.currentTarget.style.color = '#818cf8')}
              onMouseLeave={e => (e.currentTarget.style.color = '#4b5563')}
              tabIndex={-1}
            >
              <i className={`bi bi-eye${showPassword ? '-slash' : ''}`} style={{ fontSize: '0.9rem' }} />
            </button>
          </div>

          {/* Error / success message */}
          {message && (
            <div
              key={errorKey}
              className={isError ? 'login-error' : ''}
              style={{
                marginBottom: 16,
                padding: '10px 14px',
                borderRadius: 8,
                fontSize: '0.82rem',
                background: isError ? 'rgba(239,68,68,0.1)' : 'rgba(16,185,129,0.1)',
                border: `1px solid ${isError ? 'rgba(239,68,68,0.25)' : 'rgba(16,185,129,0.25)'}`,
                color: isError ? '#fca5a5' : '#6ee7b7',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}
            >
              <i className={`bi bi-${isError ? 'exclamation-circle' : 'check-circle'}`} />
              {message}
            </div>
          )}

          {/* Submit */}
          <button type="submit" className="login-btn" disabled={loading}>
            {loading ? (
              <>
                <span
                  className="spinner-border spinner-border-sm me-2"
                  role="status"
                  style={{ width: 14, height: 14, borderWidth: 2 }}
                />
                Iniciando sesión…
              </>
            ) : (
              'Iniciar sesión'
            )}
          </button>
        </form>

        {/* Register link */}
        <p style={{ textAlign: 'center', marginTop: 24, marginBottom: 0, fontSize: '0.83rem', color: '#4b5563' }}>
          ¿No tienes cuenta?{' '}
          <a
            href="/register"
            style={{ color: '#818cf8', textDecoration: 'none', fontWeight: 500 }}
            onMouseEnter={e => (e.currentTarget.style.color = '#a5b4fc')}
            onMouseLeave={e => (e.currentTarget.style.color = '#818cf8')}
          >
            Regístrate aquí
          </a>
        </p>
      </div>
    </div>
  );
};

export default Login;
