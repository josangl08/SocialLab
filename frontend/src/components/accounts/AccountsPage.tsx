import React, { useEffect, useState, useCallback } from 'react';
import 'bootstrap-icons/font/bootstrap-icons.css';

interface InstagramAccount {
  id: number;
  username: string | null;
  account_name: string | null;
  profile_picture_url: string | null;
  followers_count: number | null;
  expires_at: string | null;
  is_active: boolean;
  telegram_chat_id: string | null;
  drive_folder_id: string | null;
}

type TokenStatus = 'valid' | 'expiring' | 'expired';

function getTokenStatus(expiresAt: string | null): TokenStatus {
  if (!expiresAt) return 'expired';
  const exp = new Date(expiresAt);
  const now = new Date();
  const diffDays = (exp.getTime() - now.getTime()) / (1000 * 60 * 60 * 24);
  if (diffDays < 0) return 'expired';
  if (diffDays < 7) return 'expiring';
  return 'valid';
}

const AccountsPage: React.FC = () => {
  const [accounts, setAccounts] = useState<InstagramAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [disconnecting, setDisconnecting] = useState<number | null>(null);
  const [telegramLinking, setTelegramLinking] = useState<number | null>(null);
  const [telegramUnlinking, setTelegramUnlinking] = useState<number | null>(null);
  const [linkTokens, setLinkTokens] = useState<Record<number, string>>({});

  const fetchAccounts = useCallback(async () => {
    const token = localStorage.getItem('authToken');
    if (!token) return;
    try {
      const res = await fetch('http://localhost:8000/instagram/accounts', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!res.ok) throw new Error('Error al cargar cuentas');
      setAccounts(await res.json());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAccounts(); }, [fetchAccounts]);

  const handleDisconnect = async (accountId: number, username: string | null) => {
    if (!confirm(`¿Desconectar la cuenta @${username || accountId}? Esta acción eliminará los datos de autenticación.`)) return;
    const token = localStorage.getItem('authToken');
    if (!token) return;
    setDisconnecting(accountId);
    try {
      const res = await fetch(`http://localhost:8000/instagram/accounts/${accountId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!res.ok) throw new Error('Error al desconectar');
      setAccounts(prev => prev.filter(a => a.id !== accountId));
    } catch (e: any) {
      alert(e.message);
    } finally {
      setDisconnecting(null);
    }
  };

  const handleTelegramLink = async (accountId: number) => {
    const token = localStorage.getItem('authToken');
    if (!token) return;
    setTelegramLinking(accountId);
    try {
      const res = await fetch('http://localhost:8000/api/telegram/generate-link-token', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!res.ok) throw new Error('Error al generar token');
      const data = await res.json();
      setLinkTokens(prev => ({ ...prev, [accountId]: data.token }));
    } catch (e: any) {
      alert(e.message);
    } finally {
      setTelegramLinking(null);
    }
  };

  const handleTelegramUnlink = async (accountId: number) => {
    const token = localStorage.getItem('authToken');
    if (!token) return;
    setTelegramUnlinking(accountId);
    try {
      const res = await fetch(`http://localhost:8000/instagram/accounts/${accountId}/config`, {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ telegram_chat_id: null })
      });
      if (!res.ok) throw new Error('Error al desvincular');
      setAccounts(prev => prev.map(a => a.id === accountId ? { ...a, telegram_chat_id: null } : a));
      setLinkTokens(prev => { const next = { ...prev }; delete next[accountId]; return next; });
    } catch (e: any) {
      alert(e.message);
    } finally {
      setTelegramUnlinking(null);
    }
  };

  const handleReconnect = () => {
    const token = localStorage.getItem('authToken');
    if (token) window.location.href = `http://localhost:8000/instagram/login?token=${token}`;
  };

  const statusBadge = (status: TokenStatus) => {
    if (status === 'valid') return <span className="badge bg-success"><i className="bi bi-check-circle me-1"></i>Conectada</span>;
    if (status === 'expiring') return <span className="badge bg-warning text-dark"><i className="bi bi-exclamation-triangle me-1"></i>Expira pronto</span>;
    return <span className="badge bg-danger"><i className="bi bi-x-circle me-1"></i>Reconectar</span>;
  };

  if (loading) return <div className="d-flex justify-content-center p-5"><div className="spinner-border text-primary" role="status"></div></div>;
  if (error) return <div className="alert alert-danger m-4">{error}</div>;

  return (
    <div className="container-fluid p-4">
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2 className="mb-0"><i className="bi bi-instagram me-2"></i>Cuentas de Instagram</h2>
        <button className="btn btn-primary" onClick={handleReconnect}>
          <i className="bi bi-plus-circle me-2"></i>Conectar cuenta
        </button>
      </div>

      {accounts.length === 0 ? (
        <div className="alert alert-info">
          <i className="bi bi-info-circle me-2"></i>
          No tienes cuentas de Instagram conectadas.{' '}
          <button className="btn btn-link p-0 alert-link" onClick={handleReconnect}>Conectar ahora</button>
        </div>
      ) : (
        <div className="row g-3">
          {accounts.map(account => {
            const status = getTokenStatus(account.expires_at);
            return (
              <div key={account.id} className="col-12 col-md-6 col-lg-4">
                <div className="card h-100 shadow-sm">
                  <div className="card-body">
                    <div className="d-flex align-items-center mb-3">
                      {account.profile_picture_url ? (
                        <img
                          src={account.profile_picture_url}
                          alt={account.username || ''}
                          className="rounded-circle me-3"
                          style={{ width: 48, height: 48, objectFit: 'cover' }}
                        />
                      ) : (
                        <div className="rounded-circle bg-secondary me-3 d-flex align-items-center justify-content-center" style={{ width: 48, height: 48 }}>
                          <i className="bi bi-person text-white fs-5"></i>
                        </div>
                      )}
                      <div>
                        <h6 className="mb-0 fw-bold">@{account.username || account.account_name || `Cuenta ${account.id}`}</h6>
                        {account.account_name && <small className="text-muted">{account.account_name}</small>}
                      </div>
                    </div>

                    <div className="d-flex justify-content-between align-items-center mb-3">
                      {statusBadge(status)}
                      {account.followers_count != null && (
                        <small className="text-muted">
                          <i className="bi bi-people me-1"></i>
                          {account.followers_count.toLocaleString()} seguidores
                        </small>
                      )}
                    </div>

                    {account.expires_at && (
                      <small className="text-muted d-block mb-3">
                        <i className="bi bi-clock me-1"></i>
                        Expira: {new Date(account.expires_at).toLocaleDateString('es-ES')}
                      </small>
                    )}

                    <div className="d-flex gap-2">
                      {status !== 'valid' && (
                        <button className="btn btn-sm btn-outline-primary flex-grow-1" onClick={handleReconnect}>
                          <i className="bi bi-arrow-repeat me-1"></i>Reconectar
                        </button>
                      )}
                      <button
                        className="btn btn-sm btn-outline-danger"
                        onClick={() => handleDisconnect(account.id, account.username)}
                        disabled={disconnecting === account.id}
                      >
                        {disconnecting === account.id
                          ? <span className="spinner-border spinner-border-sm" role="status"></span>
                          : <><i className="bi bi-trash me-1"></i>Desconectar</>
                        }
                      </button>
                    </div>

                    <div className="mt-3 pt-3 border-top">
                      {account.telegram_chat_id ? (
                        <div className="d-flex align-items-center gap-2">
                          <span className="badge bg-success">Linked ✅</span>
                          <button
                            className="btn btn-sm btn-outline-secondary"
                            onClick={() => handleTelegramUnlink(account.id)}
                            disabled={telegramUnlinking === account.id}
                          >
                            {telegramUnlinking === account.id
                              ? <span className="spinner-border spinner-border-sm" role="status"></span>
                              : 'Unlink'
                            }
                          </button>
                        </div>
                      ) : (
                        <>
                          <button
                            className="btn btn-sm btn-outline-primary"
                            onClick={() => handleTelegramLink(account.id)}
                            disabled={telegramLinking === account.id}
                          >
                            {telegramLinking === account.id
                              ? <span className="spinner-border spinner-border-sm" role="status"></span>
                              : <><i className="bi bi-telegram me-1"></i>Link Telegram</>
                            }
                          </button>
                          {linkTokens[account.id] && (
                            <div className="mt-2">
                              <small className="text-muted d-block">Send to bot:</small>
                              <code className="d-block">/start {linkTokens[account.id]}</code>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default AccountsPage;
