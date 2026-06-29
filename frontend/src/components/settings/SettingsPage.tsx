import React, { useEffect, useState } from 'react';
import 'bootstrap-icons/font/bootstrap-icons.css';
import './SettingsPage.css';
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
    <div className="st-container">
      {/* Header bar */}
      <div className="st-header">
        <div className="st-header-info">
          <h2 className="st-header-title">
            <i className="bi bi-gear-fill"></i>
            Configuración
          </h2>
          <p className="st-header-subtitle">Gestiona tu cuenta y conexiones</p>
        </div>
      </div>

      <div className="st-content">
        {/* Profile panel */}
        <div className="st-panel">
          <div className="st-panel-body">
            <p className="st-section-label">Perfil</p>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
              <div className="st-avatar">{initials}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 600, fontSize: '0.95rem', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {user?.email ?? '—'}
                </div>
                {memberSince && (
                  <div className="st-meta" style={{ marginTop: 3 }}>
                    Miembro desde {memberSince}
                  </div>
                )}
              </div>
              <button
                className="st-btn st-btn-ghost"
                onClick={() => { setShowPasswordSection(p => !p); setResetStatus('idle'); }}
              >
                <i className="bi bi-key"></i>
                Contraseña
              </button>
            </div>

            {showPasswordSection && (
              <>
                <hr className="st-panel-divider" />
                {resetStatus === 'sent' ? (
                  <div className="st-success-msg" style={{ fontSize: '0.875rem' }}>
                    <i className="bi bi-check-circle-fill"></i>
                    Email enviado a <strong style={{ marginLeft: 4 }}>{user?.email}</strong>. Revisa tu bandeja de entrada.
                  </div>
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                    <span className="st-meta" style={{ flex: 1, fontSize: '0.82rem' }}>
                      Recibirás un enlace en{' '}
                      <strong style={{ color: 'var(--sl-text)', marginLeft: 3 }}>{user?.email}</strong>{' '}
                      para restablecer tu contraseña.
                    </span>
                    <button
                      className="st-btn st-btn-primary"
                      onClick={handleSendPasswordReset}
                      disabled={resetStatus === 'sending'}
                    >
                      {resetStatus === 'sending' ? (
                        <><span className="spinner-border spinner-border-sm" style={{ width: 12, height: 12 }}></span>Enviando…</>
                      ) : (
                        <><i className="bi bi-envelope"></i>Enviar email</>
                      )}
                    </button>
                    {resetStatus === 'error' && (
                      <span style={{ color: 'var(--sl-red)', fontSize: '0.78rem' }}>Error al enviar.</span>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Accounts section */}
        <AccountsPage />
      </div>
    </div>
  );
};

export default SettingsPage;
