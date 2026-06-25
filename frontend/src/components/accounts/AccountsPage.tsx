import React, { useEffect, useState, useCallback } from 'react';
import 'bootstrap-icons/font/bootstrap-icons.css';
import { AgentStrategyDrawer } from '../../features/agent/AgentStrategyDrawer';

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
  account_type?: string;
  sector?: string;
  purpose?: string;
  target_audience?: string;
  style_guide?: string;
  default_tone?: string;
  default_language?: string;
  posting_frequency?: string;
  best_times?: string[];
  content_pillars?: string[];
  hashtag_strategy?: string;
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
  const [drawerAccount, setDrawerAccount] = useState<InstagramAccount | null>(null);

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
        <h2 className="mb-0" style={{ color: '#e8e9ed' }}><i className="bi bi-instagram me-2 text-primary"></i>Cuentas de Instagram</h2>
        <button className="btn btn-primary" onClick={handleReconnect}>
          <i className="bi bi-plus-circle me-2"></i>Conectar cuenta
        </button>
      </div>

      {accounts.length === 0 ? (
        <div className="alert" style={{ background: 'rgba(99,102,241,0.12)', borderColor: '#667eea', color: '#e8e9ed' }}>
          <i className="bi bi-info-circle me-2" style={{ color: '#818cf8' }}></i>
          No tienes cuentas de Instagram conectadas.{' '}
          <button className="btn btn-link p-0" style={{ color: '#818cf8' }} onClick={handleReconnect}>Conectar ahora</button>
        </div>
      ) : (
        <div className="row g-3">
          {accounts.map(account => {
            const status = getTokenStatus(account.expires_at);
            return (
              <div key={account.id} className="col-12 col-md-6 col-lg-4">
                <div className="card h-100" style={{ background: '#2a3038', borderColor: '#3d444d', color: '#e8e9ed' }}>
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
                        <h6 className="mb-0 fw-bold" style={{ color: '#e8e9ed' }}>@{account.username || account.account_name || `Cuenta ${account.id}`}</h6>
                        {account.account_name && <small style={{ color: '#9ca3af' }}>{account.account_name}</small>}
                      </div>
                    </div>

                    <div className="d-flex justify-content-between align-items-center mb-3">
                      {statusBadge(status)}
                      {account.followers_count != null && (
                        <small style={{ color: '#9ca3af' }}>
                          <i className="bi bi-people me-1"></i>
                          {account.followers_count.toLocaleString()} seguidores
                        </small>
                      )}
                    </div>

                    {account.expires_at && (
                      <small className="d-block mb-3" style={{ color: '#9ca3af' }}>
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

                    <div className="mt-3 pt-3" style={{ borderTop: '1px solid #3d444d' }}>
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
                              <small className="d-block" style={{ color: '#9ca3af' }}>Send to bot:</small>
                              <code className="d-block" style={{ background: '#1a1d23', color: '#a5b4fc', padding: '4px 8px', borderRadius: 6, fontSize: '0.82rem' }}>/start {linkTokens[account.id]}</code>
                            </div>
                          )}
                        </>
                      )}
                    </div>

                    <div className="mt-3 pt-3" style={{ borderTop: '1px solid #3d444d' }}>
                      <button
                        className="btn btn-sm btn-outline-info w-100"
                        onClick={() => setDrawerAccount(account)}
                      >
                        <i className="bi bi-robot me-1"></i>Configurar Estrategia
                        {account.sector && (
                          <span className="badge bg-success ms-2" style={{ fontSize: '0.65rem' }}>Activa</span>
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <AgentStrategyDrawer
        accountId={drawerAccount?.id ?? 0}
        accountUsername={drawerAccount?.username ?? undefined}
        show={drawerAccount !== null}
        onHide={() => setDrawerAccount(null)}
        onSave={fetchAccounts}
      />
    </div>
  );
};

export default AccountsPage;
