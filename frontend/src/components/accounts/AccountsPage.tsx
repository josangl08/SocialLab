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

function extractDriveFolderId(input: string): string {
  const match = input.match(/\/folders\/([a-zA-Z0-9_-]+)/);
  return match ? match[1] : input.trim();
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
  const [driveSaving, setDriveSaving] = useState<number | null>(null);
  const [driveUnlinking, setDriveUnlinking] = useState<number | null>(null);
  const [driveInputs, setDriveInputs] = useState<Record<number, string>>({});
  const [driveSuccess, setDriveSuccess] = useState<Record<number, boolean>>({});

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

  const handleDriveSave = async (accountId: number, input: string) => {
    const folderId = extractDriveFolderId(input);
    if (!folderId) return;
    const token = localStorage.getItem('authToken');
    if (!token) return;
    setDriveSaving(accountId);
    try {
      const res = await fetch(`http://localhost:8000/instagram/accounts/${accountId}/config`, {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ drive_folder_id: folderId })
      });
      if (!res.ok) throw new Error('Error al vincular carpeta');
      setAccounts(prev => prev.map(a => a.id === accountId ? { ...a, drive_folder_id: folderId } : a));
      setDriveInputs(prev => { const next = { ...prev }; delete next[accountId]; return next; });
      setDriveSuccess(prev => ({ ...prev, [accountId]: true }));
      setTimeout(() => setDriveSuccess(prev => { const next = { ...prev }; delete next[accountId]; return next; }), 3000);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setDriveSaving(null);
    }
  };

  const handleDriveUnlink = async (accountId: number) => {
    const token = localStorage.getItem('authToken');
    if (!token) return;
    setDriveUnlinking(accountId);
    try {
      const res = await fetch(`http://localhost:8000/instagram/accounts/${accountId}/config`, {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ drive_folder_id: null })
      });
      if (!res.ok) throw new Error('Error al desvincular carpeta');
      setAccounts(prev => prev.map(a => a.id === accountId ? { ...a, drive_folder_id: null } : a));
    } catch (e: any) {
      alert(e.message);
    } finally {
      setDriveUnlinking(null);
    }
  };

  const handleReconnect = () => {
    const token = localStorage.getItem('authToken');
    if (token) window.location.href = `http://localhost:8000/instagram/login?token=${token}`;
  };

  const statusBadge = (status: TokenStatus) => {
    if (status === 'valid') return (
      <span className="st-badge st-badge-success">
        <i className="bi bi-check-circle"></i>Conectada
      </span>
    );
    if (status === 'expiring') return (
      <span className="st-badge st-badge-warning">
        <i className="bi bi-exclamation-triangle"></i>Expira pronto
      </span>
    );
    return (
      <span className="st-badge st-badge-danger">
        <i className="bi bi-x-circle"></i>Reconectar
      </span>
    );
  };

  const spinner = <span className="spinner-border spinner-border-sm" role="status" style={{ width: 12, height: 12 }}></span>;

  if (loading) return (
    <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
      <div className="spinner-border" style={{ color: 'var(--sl-indigo)' }} role="status"></div>
    </div>
  );

  if (error) return (
    <div style={{ background: 'rgba(252,165,165,0.08)', border: '1px solid rgba(252,165,165,0.2)', borderRadius: 12, padding: '12px 16px', color: 'var(--sl-red)', fontSize: 14 }}>
      {error}
    </div>
  );

  return (
    <>
      {/* Accounts header */}
      <div className="st-accounts-header">
        <h3 className="st-accounts-title">
          <i className="bi bi-instagram"></i>
          Cuentas de Instagram
        </h3>
        <button className="st-btn st-btn-primary st-btn-sm" onClick={handleReconnect}>
          <i className="bi bi-plus-circle"></i>Conectar cuenta
        </button>
      </div>

      {accounts.length === 0 ? (
        <div className="st-empty">
          <i className="bi bi-instagram"></i>
          No tienes cuentas de Instagram conectadas.
          <br />
          <button className="st-btn st-btn-ghost st-btn-sm" style={{ marginTop: 12 }} onClick={handleReconnect}>
            Conectar ahora
          </button>
        </div>
      ) : (
        <div className="st-accounts-grid">
          {accounts.map(account => {
            const status = getTokenStatus(account.expires_at);
            return (
              <div key={account.id} className="st-account-card">
                {/* Profile row */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
                  {account.profile_picture_url ? (
                    <img
                      src={account.profile_picture_url}
                      alt={account.username || ''}
                      style={{ width: 44, height: 44, borderRadius: '50%', objectFit: 'cover', flexShrink: 0 }}
                    />
                  ) : (
                    <div style={{
                      width: 44, height: 44, borderRadius: '50%', flexShrink: 0,
                      background: 'var(--sl-surface-2)', border: '1px solid var(--sl-border-2)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center'
                    }}>
                      <i className="bi bi-person" style={{ color: 'var(--sl-muted)', fontSize: 18 }}></i>
                    </div>
                  )}
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: '0.9rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      @{account.username || account.account_name || `Cuenta ${account.id}`}
                    </div>
                    {account.account_name && (
                      <div className="st-meta">{account.account_name}</div>
                    )}
                  </div>
                </div>

                {/* Status + followers */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                  {statusBadge(status)}
                  {account.followers_count != null && (
                    <span className="st-meta">
                      <i className="bi bi-people"></i>
                      {account.followers_count.toLocaleString()}
                    </span>
                  )}
                </div>

                {/* Expiry */}
                {account.expires_at && (
                  <div className="st-meta" style={{ marginBottom: 12 }}>
                    <i className="bi bi-clock"></i>
                    Expira: {new Date(account.expires_at).toLocaleDateString('es-ES')}
                  </div>
                )}

                {/* Actions */}
                <div style={{ display: 'flex', gap: 8 }}>
                  {status !== 'valid' && (
                    <button className="st-btn st-btn-accent st-btn-sm" style={{ flex: 1 }} onClick={handleReconnect}>
                      <i className="bi bi-arrow-repeat"></i>Reconectar
                    </button>
                  )}
                  <button
                    className="st-btn st-btn-danger st-btn-sm"
                    onClick={() => handleDisconnect(account.id, account.username)}
                    disabled={disconnecting === account.id}
                  >
                    {disconnecting === account.id ? spinner : <><i className="bi bi-trash"></i>Desconectar</>}
                  </button>
                </div>

                {/* Telegram */}
                <div className="st-card-row">
                  <div className="st-card-row-label">
                    <i className="bi bi-telegram" style={{ color: '#29b6f6' }}></i>
                    Telegram
                  </div>
                  {account.telegram_chat_id ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span className="st-badge st-badge-success">Vinculado</span>
                      <button
                        className="st-btn st-btn-ghost st-btn-sm"
                        onClick={() => handleTelegramUnlink(account.id)}
                        disabled={telegramUnlinking === account.id}
                      >
                        {telegramUnlinking === account.id ? spinner : 'Unlink'}
                      </button>
                    </div>
                  ) : (
                    <>
                      <button
                        className="st-btn st-btn-ghost st-btn-sm"
                        onClick={() => handleTelegramLink(account.id)}
                        disabled={telegramLinking === account.id}
                      >
                        {telegramLinking === account.id ? spinner : <><i className="bi bi-telegram"></i>Link Telegram</>}
                      </button>
                      {linkTokens[account.id] && (
                        <div style={{ marginTop: 8 }}>
                          <div className="st-meta">Envía al bot:</div>
                          <code className="st-code">/start {linkTokens[account.id]}</code>
                        </div>
                      )}
                    </>
                  )}
                </div>

                {/* Google Drive */}
                <div className="st-card-row">
                  <div className="st-card-row-label">
                    <i className="bi bi-google" style={{ color: '#ea4335' }}></i>
                    Google Drive
                  </div>
                  {account.drive_folder_id ? (
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span className="st-badge st-badge-success">Vinculado</span>
                        <button
                          className="st-btn st-btn-ghost st-btn-sm"
                          onClick={() => handleDriveUnlink(account.id)}
                          disabled={driveUnlinking === account.id}
                        >
                          {driveUnlinking === account.id ? spinner : 'Unlink'}
                        </button>
                      </div>
                      {driveSuccess[account.id] && (
                        <div className="st-success-msg">
                          <i className="bi bi-check-circle-fill"></i>
                          Carpeta sincronizada correctamente
                        </div>
                      )}
                    </div>
                  ) : (
                    <div>
                      <div style={{ display: 'flex', gap: 8 }}>
                        <input
                          className="st-input"
                          type="text"
                          placeholder="URL o ID de carpeta de Google Drive"
                          value={driveInputs[account.id] ?? ''}
                          onChange={e => setDriveInputs(prev => ({ ...prev, [account.id]: e.target.value }))}
                        />
                        <button
                          className="st-btn st-btn-ghost st-btn-sm"
                          style={{ flexShrink: 0 }}
                          onClick={() => handleDriveSave(account.id, driveInputs[account.id] ?? '')}
                          disabled={driveSaving === account.id || !driveInputs[account.id]?.trim()}
                        >
                          {driveSaving === account.id ? spinner : <><i className="bi bi-folder-symlink"></i>Vincular</>}
                        </button>
                      </div>
                      <div className="st-meta" style={{ marginTop: 5 }}>
                        Puedes pegar la URL completa de la carpeta
                      </div>
                    </div>
                  )}
                </div>

                {/* Strategy */}
                <div className="st-card-row">
                  <button
                    className="st-btn st-btn-accent"
                    style={{ width: '100%', justifyContent: 'center' }}
                    onClick={() => setDrawerAccount(account)}
                  >
                    <i className="bi bi-robot"></i>
                    Configurar Estrategia
                    {account.sector && (
                      <span className="st-badge st-badge-success" style={{ fontSize: '0.65rem', marginLeft: 4 }}>
                        Activa
                      </span>
                    )}
                  </button>
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
    </>
  );
};

export default AccountsPage;
