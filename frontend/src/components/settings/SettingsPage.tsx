import React, { useEffect, useState } from 'react';
import 'bootstrap-icons/font/bootstrap-icons.css';
import AccountsPage from '../accounts/AccountsPage';

interface User {
  id: string;
  email: string;
  created_at: string;
}

type ResetStatus = 'idle' | 'sending' | 'sent' | 'error';

const SettingsPage: React.FC = () => {
  const [user, setUser] = useState<User | null>(null);
  const [showPasswordSection, setShowPasswordSection] = useState(false);
  const [resetStatus, setResetStatus] = useState<ResetStatus>('idle');

  useEffect(() => {
    const token = localStorage.getItem('authToken');
    if (!token) return;
    fetch('http://localhost:8000/users/me', {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => (r.ok ? r.json() : null))
      .then(data => { if (data) setUser(data); })
      .catch(() => {});
  }, []);

  const handleSendPasswordReset = async () => {
    const token = localStorage.getItem('authToken');
    if (!token) return;
    setResetStatus('sending');
    try {
      const res = await fetch('http://localhost:8000/users/me/send-password-reset', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      setResetStatus(res.ok ? 'sent' : 'error');
    } catch {
      setResetStatus('error');
    }
  };

  const initials = user?.email?.[0]?.toUpperCase() ?? '?';
  const memberSince = user?.created_at
    ? new Date(user.created_at).toLocaleDateString('es-ES', { month: 'long', year: 'numeric' })
    : '';

  return (
    <div style={{ padding: '24px 20px', maxWidth: 960, margin: '0 auto' }}>
      <h2 style={{ color: '#e8e9ed', fontWeight: 700, marginBottom: 24 }}>
        <i className="bi bi-gear-fill me-2 text-primary"></i>Settings
      </h2>

      {/* Profile header */}
      <div style={{
        background: '#2a3038',
        borderRadius: 12,
        padding: '20px 24px',
        marginBottom: 24,
        border: '1px solid #3d444d',
      }}>
        <div className="d-flex align-items-center gap-3 flex-wrap">
          {/* Avatar */}
          <div style={{
            width: 52, height: 52, borderRadius: '50%', flexShrink: 0,
            background: 'linear-gradient(135deg, #667eea, #764ba2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#fff', fontWeight: 700, fontSize: '1.35rem',
          }}>
            {initials}
          </div>

          {/* Info */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ color: '#e8e9ed', fontWeight: 600, fontSize: '0.95rem', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {user?.email ?? '—'}
            </div>
            {memberSince && (
              <div style={{ color: '#9ca3af', fontSize: '0.78rem', marginTop: 2 }}>
                Miembro desde {memberSince}
              </div>
            )}
          </div>

          {/* Password toggle */}
          <button
            className={`btn btn-sm ${showPasswordSection ? 'btn-secondary' : 'btn-outline-secondary'}`}
            onClick={() => { setShowPasswordSection(p => !p); setResetStatus('idle'); }}
            style={{ flexShrink: 0 }}
          >
            <i className="bi bi-key me-1"></i>Contraseña
          </button>
        </div>

        {/* Password reset section */}
        {showPasswordSection && (
          <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid #3d444d' }}>
            {resetStatus === 'sent' ? (
              <div style={{ color: '#10b981', fontSize: '0.875rem', display: 'flex', alignItems: 'center', gap: 8 }}>
                <i className="bi bi-check-circle-fill"></i>
                Email enviado a <strong style={{ marginLeft: 4 }}>{user?.email}</strong>. Revisa tu bandeja de entrada.
              </div>
            ) : (
              <div className="d-flex align-items-center gap-3 flex-wrap">
                <span style={{ color: '#9ca3af', fontSize: '0.82rem', flex: 1 }}>
                  Recibirás un enlace en{' '}
                  <strong style={{ color: '#e8e9ed' }}>{user?.email}</strong>{' '}
                  para restablecer tu contraseña.
                </span>
                <button
                  className="btn btn-sm btn-primary"
                  onClick={handleSendPasswordReset}
                  disabled={resetStatus === 'sending'}
                  style={{ flexShrink: 0 }}
                >
                  {resetStatus === 'sending' ? (
                    <><span className="spinner-border spinner-border-sm me-1" style={{ width: 12, height: 12 }}></span>Enviando…</>
                  ) : (
                    <><i className="bi bi-envelope me-1"></i>Enviar email</>
                  )}
                </button>
                {resetStatus === 'error' && (
                  <span style={{ color: '#ef4444', fontSize: '0.78rem' }}>Error al enviar.</span>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Accounts section */}
      <AccountsPage />
    </div>
  );
};

export default SettingsPage;
