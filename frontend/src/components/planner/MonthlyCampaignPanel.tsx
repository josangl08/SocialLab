import React, { useEffect, useState } from 'react';
import { apiClient, ApiError } from '../../api/client';
import { CampaignChatBox } from '../../features/agent/CampaignChatBox';
import type { MonthlyCampaign } from '../../types';
import { getFirstOfDayOfMonth, withCampaignDefaults } from '../../utils/campaign';
import './MonthlyCampaignPanel.css';

interface MonthlyCampaignPanelProps {
  accountId: number | null;
  currentDate: Date;
  /** Se llama tras crear, aprobar, rechazar o editar la campaña (el banner se refresca). */
  onCampaignChanged: () => void;
}

const POLL_MS = 4000;
const POLL_TIMEOUT_MS = 45000;

/** Campaña mensual en el planner (AD-9): generar, conversar, editar y aprobar. */
export const MonthlyCampaignPanel: React.FC<MonthlyCampaignPanelProps> = ({ accountId, currentDate, onCampaignChanged }) => {
  const monthDate = getFirstOfDayOfMonth(currentDate);
  const [campaign, setCampaign] = useState<MonthlyCampaign | null>(null);
  const [open, setOpen] = useState(false);
  const [showChat, setShowChat] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedFlash, setSavedFlash] = useState(false);
  const [genStartedAt, setGenStartedAt] = useState<number | null>(null);
  const [newMilestoneDate, setNewMilestoneDate] = useState('');
  const [newMilestoneEvent, setNewMilestoneEvent] = useState('');

  useEffect(() => {
    if (!accountId) { setCampaign(null); return; }
    let cancelled = false;
    apiClient.get<Partial<MonthlyCampaign> | null>(`/api/agent/campaign?account_id=${accountId}&month_date=${monthDate}`)
      .then(data => { if (!cancelled) setCampaign(withCampaignDefaults(accountId, monthDate, data)); })
      .catch(() => { if (!cancelled) setCampaign(withCampaignDefaults(accountId, monthDate, null)); });
    setShowChat(false);
    setError(null);
    return () => { cancelled = true; };
  }, [accountId, monthDate]);

  // Hermes redacta el borrador en segundo plano: se consulta hasta que aparece
  useEffect(() => {
    if (!genStartedAt || !accountId) return;
    const poll = async () => {
      try {
        const data = await apiClient.get<Partial<MonthlyCampaign> | null>(
          `/api/agent/campaign?account_id=${accountId}&month_date=${monthDate}`
        );
        if (data?.id) {
          setCampaign(withCampaignDefaults(accountId, monthDate, data));
          setGenStartedAt(null);
          setOpen(true);
          onCampaignChanged();
        }
      } catch { /* errores transitorios: se sigue consultando hasta el timeout */ }
    };
    const interval = setInterval(poll, POLL_MS);
    const timeout = setTimeout(() => {
      setGenStartedAt(null);
      setError('Hermes no respondió a tiempo. Inténtalo de nuevo en unos segundos.');
    }, POLL_TIMEOUT_MS);
    return () => { clearInterval(interval); clearTimeout(timeout); };
  }, [genStartedAt, accountId, monthDate, onCampaignChanged]);

  if (!accountId || !campaign) return null;

  const run = async (action: () => Promise<void>, failMessage: string) => {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : failMessage);
    } finally {
      setBusy(false);
    }
  };

  const generate = () => run(async () => {
    await apiClient.post('/api/agent/campaign/trigger', { account_id: accountId, month_date: monthDate });
    setGenStartedAt(Date.now());
  }, 'Error al generar la campaña');

  const resolve = (decision: 'approve' | 'reject') => run(async () => {
    const updated = await apiClient.post<Partial<MonthlyCampaign>>(`/api/agent/campaign/${campaign.id}/${decision}`);
    setCampaign(prev => (prev ? { ...prev, ...updated } : prev));
    if (decision === 'reject') setShowChat(false);
    onCampaignChanged();
  }, decision === 'approve' ? 'Error al aprobar la campaña' : 'Error al rechazar la campaña');

  const save = () => {
    if (!campaign.title.trim()) { setError('El título es obligatorio'); return; }
    return saveCampaign();
  };

  const saveCampaign = () => run(async () => {
    const result = await apiClient.post<MonthlyCampaign>('/api/agent/campaign', { ...campaign, account_id: accountId });
    setCampaign(withCampaignDefaults(accountId, monthDate, result));
    setSavedFlash(true);
    setTimeout(() => setSavedFlash(false), 3000);
    onCampaignChanged();
  }, 'Error al guardar la campaña');

  const update = (patch: Partial<MonthlyCampaign>) => setCampaign(prev => (prev ? { ...prev, ...patch } : prev));

  const addMilestone = () => {
    const event = newMilestoneEvent.trim();
    if (!newMilestoneDate || !event) return;
    update({ milestones: [...campaign.milestones, { date: newMilestoneDate, event }].sort((a, b) => a.date.localeCompare(b.date)) });
    setNewMilestoneDate('');
    setNewMilestoneEvent('');
  };

  const canGenerate = !campaign.id || campaign.status === 'rejected';
  const generating = genStartedAt !== null;

  return (
    <div className="mcp mb-4">
      {campaign.status === 'pending_approval' && (
        <div className="mcp-pending" data-testid="campaign-pending">
          <div className="d-flex align-items-center gap-2 mb-1">
            <i className="bi bi-robot" />
            <strong>Hermes propone una campaña para este mes</strong>
          </div>
          <p className="small mcp-muted mb-2">Revísala, pide cambios en el chat o apruébala.</p>
          <div className="d-flex gap-2 flex-wrap">
            <button type="button" className="btn btn-sm btn-success" onClick={() => resolve('approve')} disabled={busy}>
              <i className="bi bi-check-lg me-1" />Aprobar
            </button>
            <button type="button" className="btn btn-sm btn-outline-danger" onClick={() => resolve('reject')} disabled={busy}>
              <i className="bi bi-x-lg me-1" />Rechazar
            </button>
            <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => setOpen(true)}>
              Revisar y editar
            </button>
          </div>
        </div>
      )}

      <div className="d-flex align-items-center gap-2 flex-wrap">
        <button type="button" className="btn btn-sm btn-outline-secondary" aria-expanded={open} onClick={() => setOpen(v => !v)}>
          <i className={`bi ${open ? 'bi-chevron-up' : 'bi-pencil-square'} me-1`} />
          {campaign.id ? 'Editar campaña del mes' : 'Crear campaña del mes'}
        </button>
        {canGenerate && (
          <button type="button" className="btn btn-sm btn-outline-primary" onClick={generate} disabled={busy || generating}>
            {generating
              ? <><span className="spinner-border spinner-border-sm me-1" />Generando...</>
              : <><i className="bi bi-robot me-1" />Generar con Hermes</>}
          </button>
        )}
        {campaign.id && (
          <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => setShowChat(v => !v)}>
            <i className="bi bi-chat-dots me-1" />Chat con Hermes
          </button>
        )}
      </div>

      {error && <div className="alert alert-danger py-2 px-3 small mt-2 mb-0">{error}</div>}

      {showChat && campaign.id && (
        <div className="mt-3">
          <CampaignChatBox
            campaignId={campaign.id}
            accountId={accountId}
            monthDate={monthDate}
            onCampaignUpdated={updated => { update(updated); onCampaignChanged(); }}
          />
        </div>
      )}

      {open && (
        <div className="mcp-form mt-3">
          <div className="mb-3">
            <span className="mcp-label">Modo de estrategia</span>
            <div className="d-flex gap-2">
              {(['commercial_campaign', 'personal_storyline'] as const).map(mode => (
                <button key={mode} type="button" aria-pressed={campaign.strategy_mode === mode}
                  className={`btn btn-sm flex-grow-1 ${campaign.strategy_mode === mode ? 'btn-primary' : 'btn-outline-secondary'}`}
                  onClick={() => update({ strategy_mode: mode })}>
                  {mode === 'commercial_campaign' ? 'Campaña comercial' : 'Hilo personal'}
                </button>
              ))}
            </div>
          </div>
          <div className="mb-3">
            <label className="mcp-label" htmlFor="mcp-title">Título</label>
            <input id="mcp-title" className="form-control form-control-sm mcp-input" value={campaign.title}
              onChange={e => update({ title: e.target.value })} placeholder="Ej: Lanzamiento Producto X / Viaje a Japón" />
          </div>
          <div className="mb-3">
            <label className="mcp-label" htmlFor="mcp-description">Descripción</label>
            <textarea id="mcp-description" className="form-control form-control-sm mcp-input" rows={2} value={campaign.description}
              onChange={e => update({ description: e.target.value })} placeholder="Ej: Foco en dar a conocer las ventajas de X..." />
          </div>
          <div className="mb-3">
            <span className="mcp-label">Hitos</span>
            {campaign.milestones.map((m, i) => (
              <div key={`${m.date}-${i}`} className="mcp-milestone">
                <span className="mcp-milestone-date">{m.date}</span>
                <span className="flex-grow-1">{m.event}</span>
                <button type="button" className="mcp-remove" aria-label={`Quitar hito ${m.event}`}
                  onClick={() => update({ milestones: campaign.milestones.filter((_, j) => j !== i) })}>
                  <i className="bi bi-trash" />
                </button>
              </div>
            ))}
            <div className="d-flex gap-2">
              <input type="date" aria-label="Fecha del hito" className="form-control form-control-sm mcp-input mcp-date"
                value={newMilestoneDate} onChange={e => setNewMilestoneDate(e.target.value)} />
              <input className="form-control form-control-sm mcp-input" aria-label="Nuevo hito" placeholder="Nuevo hito..."
                value={newMilestoneEvent} onChange={e => setNewMilestoneEvent(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addMilestone(); } }} />
              <button type="button" className="btn btn-sm btn-outline-secondary" onClick={addMilestone} aria-label="Añadir hito">
                <i className="bi bi-plus" />
              </button>
            </div>
          </div>
          <div className="mb-3">
            <span className="mcp-label">Foco por semana</span>
            {(['1', '2', '3', '4'] as const).map(week => (
              <div key={week} className="d-flex align-items-center gap-2 mb-2">
                <span className="mcp-week">Semana {week}</span>
                <input className="form-control form-control-sm mcp-input" aria-label={`Foco semana ${week}`}
                  value={campaign.weekly_focus[week] || ''} placeholder={`Foco para la semana ${week}`}
                  onChange={e => update({ weekly_focus: { ...campaign.weekly_focus, [week]: e.target.value } })} />
              </div>
            ))}
          </div>
          <div className="d-flex justify-content-end align-items-center gap-2">
            {savedFlash && <span className="small mcp-saved"><i className="bi bi-check2-circle me-1" />Guardada</span>}
            <button type="button" className="btn btn-sm btn-primary" onClick={save} disabled={busy}>Guardar campaña</button>
          </div>
        </div>
      )}
    </div>
  );
};
