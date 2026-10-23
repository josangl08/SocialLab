import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Modal, Button } from 'react-bootstrap';
import { apiClient, ApiError } from '../../api/client';
import { strategyApi } from '../../api/strategy';
import type {
  AgentConfigPatch, AgentStrategyConfig, InstagramAccount, StrategyTab, StrategyWizardAnswers,
} from '../../types';
import { StrategyBrandTab } from './StrategyBrandTab';
import { StrategyPublishingTab } from './StrategyPublishingTab';
import { StrategyReferencesTab } from './StrategyReferencesTab';
import { StrategyDiagnosticsTab } from './StrategyDiagnosticsTab';
import { StrategyWizardModal } from './StrategyWizardModal';
import { PendingSuggestionsList } from './PendingSuggestionsList';
import {
  DEFAULT_CONFIG, STRATEGY_TABS, TAB_FIELDS, isStrategyTab, isTabDirty, pickFields,
} from './strategyOptions';
import './StrategyPage.css';

interface PendingConfirm {
  message: string;
  onConfirm: () => void;
}

const EDITABLE_TABS: StrategyTab[] = ['marca', 'publicacion', 'referentes'];

const StrategyPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [accounts, setAccounts] = useState<InstagramAccount[] | null>(null);
  const [saved, setSaved] = useState<AgentStrategyConfig>(DEFAULT_CONFIG);
  const [draft, setDraft] = useState<AgentStrategyConfig>(DEFAULT_CONFIG);
  const [loadingConfig, setLoadingConfig] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedFlash, setSavedFlash] = useState(false);
  const [diagnosticsKey, setDiagnosticsKey] = useState(0);
  const [pendingConfirm, setPendingConfirm] = useState<PendingConfirm | null>(null);
  const [wizardOpen, setWizardOpen] = useState(false);

  const tabParam = searchParams.get('tab');
  const tab: StrategyTab = isStrategyTab(tabParam) ? tabParam : 'marca';
  const accountParam = Number(searchParams.get('account'));
  const account = accounts?.find(a => a.id === accountParam) ?? accounts?.[0] ?? null;
  const accountId = account?.id ?? null;

  const anyDirty = EDITABLE_TABS.some(t => isTabDirty(t, draft, saved));
  const currentDirty = isTabDirty(tab, draft, saved);

  useEffect(() => {
    apiClient.get<InstagramAccount[]>('/instagram/accounts')
      .then(setAccounts)
      .catch(() => setAccounts([]));
  }, []);

  // URL canónica: cuenta válida y pestaña conocida
  useEffect(() => {
    if (accountId === null) return;
    if (accountParam !== accountId || tabParam !== tab) {
      setSearchParams({ account: String(accountId), tab }, { replace: true });
    }
  }, [accountId, accountParam, tab, tabParam, setSearchParams]);

  useEffect(() => {
    if (accountId === null) return;
    let cancelled = false;
    setLoadingConfig(true);
    setLoadError(null);
    strategyApi.getConfig(accountId)
      .then(cfg => {
        if (cancelled) return;
        const merged = { ...DEFAULT_CONFIG, ...cfg };
        setSaved(merged);
        setDraft(merged);
      })
      .catch(() => { if (!cancelled) setLoadError('No se pudo cargar la estrategia de esta cuenta.'); })
      .finally(() => { if (!cancelled) setLoadingConfig(false); });
    return () => { cancelled = true; };
  }, [accountId]);

  useEffect(() => {
    if (!anyDirty) return;
    const onBeforeUnload = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [anyDirty]);

  const guard = (dirty: boolean, message: string, action: () => void) => {
    if (dirty) setPendingConfirm({ message, onConfirm: action });
    else action();
  };

  const discardTab = (t: StrategyTab) =>
    setDraft(d => ({ ...d, ...pickFields(saved, TAB_FIELDS[t]) }));

  const goToTab = (next: StrategyTab) => {
    if (next === tab || accountId === null) return;
    guard(currentDirty, 'Tienes cambios sin guardar en esta pestaña. ¿Quieres descartarlos?', () => {
      discardTab(tab);
      setSearchParams({ account: String(accountId), tab: next });
    });
  };

  const goToAccount = (id: number) => {
    if (id === accountId) return;
    guard(anyDirty, 'Tienes cambios sin guardar. Si cambias de cuenta se descartarán.', () => {
      setSearchParams({ account: String(id), tab });
    });
  };

  const goTo = (path: string) =>
    guard(anyDirty, 'Tienes cambios sin guardar. Si sales de la página se descartarán.', () => navigate(path));

  const updateDraft = useCallback((patch: AgentConfigPatch) => {
    setDraft(d => ({ ...d, ...patch }));
    setSavedFlash(false);
  }, []);

  const save = async () => {
    if (accountId === null) return;
    setSaving(true);
    setSaveError(null);
    try {
      const fields = TAB_FIELDS[tab];
      const result = { ...DEFAULT_CONFIG, ...(await strategyApi.patchConfig(accountId, pickFields(draft, fields))) };
      setSaved(result);
      // Solo se sincronizan los campos de esta pestaña: el resto conserva sus cambios
      setDraft(d => ({ ...d, ...pickFields(result, fields) }));
      setDiagnosticsKey(k => k + 1);
      setSavedFlash(true);
    } catch (e) {
      setSaveError(e instanceof ApiError ? e.detail : 'Error al guardar');
    } finally {
      setSaving(false);
    }
  };

  const onSuggestionAccepted = useCallback((field: keyof AgentStrategyConfig, value: unknown) => {
    setSaved(s => ({ ...s, [field]: value }));
    setDraft(d => ({ ...d, [field]: value }));
    setDiagnosticsKey(k => k + 1);
  }, []);

  const onAnswersSaved = useCallback((answers: StrategyWizardAnswers) => {
    setSaved(s => ({ ...s, strategy_wizard_answers: answers }));
    setDraft(d => ({ ...d, strategy_wizard_answers: answers }));
  }, []);

  if (accounts === null) {
    return <div className="d-flex justify-content-center py-5"><div className="spinner-border text-primary" role="status" /></div>;
  }

  if (accounts.length === 0 || accountId === null) {
    return (
      <div className="stg-page">
        <h1 className="stg-title">Estrategia del agente</h1>
        <p className="stg-muted">Conecta una cuenta de Instagram para definir su estrategia.</p>
        <Link to="/settings" className="btn btn-sm btn-primary">Ir a Ajustes</Link>
      </div>
    );
  }

  return (
    <div className="stg-page">
      <header className="stg-header">
        <div>
          <span className="stg-eyebrow">Estrategia del agente</span>
          <div className="d-flex align-items-center gap-2 flex-wrap">
            <h1 className="stg-title">@{account?.username ?? `cuenta_${accountId}`}</h1>
            {accounts.length > 1 && (
              <select className="form-select form-select-sm stg-account-select" aria-label="Cuenta"
                value={accountId} onChange={e => goToAccount(Number(e.target.value))}>
                {accounts.map(a => <option key={a.id} value={a.id}>@{a.username ?? a.id}</option>)}
              </select>
            )}
          </div>
        </div>
        <div className="d-flex align-items-center gap-2 flex-wrap">
          <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => goTo('/planner')}>
            <i className="bi bi-calendar3-range me-1" />Campaña del mes → planner
          </button>
          <button type="button" className="btn btn-sm stg-wizard-btn" onClick={() => setWizardOpen(true)}
            disabled={loadingConfig}>
            <i className="bi bi-stars me-1" />Asistente IA
          </button>
        </div>
      </header>

      <nav className="nav stg-tabs" role="tablist">
        {STRATEGY_TABS.map(t => {
          const dirty = EDITABLE_TABS.includes(t.key) && isTabDirty(t.key, draft, saved);
          return (
            <button key={t.key} type="button" role="tab" aria-selected={tab === t.key}
              className={`stg-tab ${tab === t.key ? 'is-active' : ''}`} onClick={() => goToTab(t.key)}>
              <i className={`bi ${t.icon} me-1`} />{t.label}
              {dirty && <span className="stg-dirty-dot" aria-label="cambios sin guardar" />}
            </button>
          );
        })}
      </nav>

      <div className="stg-body">
        {loadingConfig ? (
          <div className="d-flex justify-content-center py-5"><div className="spinner-border text-primary" role="status" /></div>
        ) : loadError ? (
          <div className="alert alert-danger small">{loadError}</div>
        ) : (
          <>
            {tab === 'marca' && <StrategyBrandTab draft={draft} onChange={updateDraft} />}
            {tab === 'publicacion' && (
              <StrategyPublishingTab accountId={accountId} draft={draft} onChange={updateDraft}
                onSuggestionAccepted={onSuggestionAccepted} />
            )}
            {tab === 'referentes' && (
              <StrategyReferencesTab accountId={accountId} draft={draft} savedReferences={saved.reference_accounts}
                onChange={updateDraft} onSuggestionAccepted={onSuggestionAccepted} />
            )}
            {tab === 'diagnostico' && (
              <StrategyDiagnosticsTab accountId={accountId} refreshKey={diagnosticsKey} onGoToTab={goToTab} />
            )}

            {EDITABLE_TABS.includes(tab) && (
              <footer className="stg-footer">
                {saveError && <span className="stg-save-error small">{saveError}</span>}
                {savedFlash && !currentDirty && <span className="stg-saved small"><i className="bi bi-check2-circle me-1" />Guardado</span>}
                {currentDirty && <span className="stg-unsaved small">Cambios sin guardar</span>}
                <button type="button" className="btn btn-primary btn-sm" onClick={save} disabled={saving || !currentDirty}>
                  {saving ? <><span className="spinner-border spinner-border-sm me-2" />Guardando...</> : 'Guardar'}
                </button>
              </footer>
            )}
          </>
        )}
      </div>

      <StrategyWizardModal
        show={wizardOpen}
        accountId={accountId}
        current={draft}
        savedAnswers={saved.strategy_wizard_answers}
        onClose={() => setWizardOpen(false)}
        onApply={updateDraft}
        onAnswersSaved={onAnswersSaved}
        extraProposal={(
          <div className="mt-3">
            <h4 className="stg-section-title"><i className="bi bi-search" />Sugerencias de tus referentes</h4>
            <PendingSuggestionsList accountId={accountId} fromReferences onAccepted={onSuggestionAccepted}
              emptyText="No hay sugerencias pendientes de tus referentes." />
          </div>
        )}
      />

      <Modal show={pendingConfirm !== null} onHide={() => setPendingConfirm(null)} centered className="text-light">
        <Modal.Header closeButton className="border-secondary bg-dark text-light">
          <Modal.Title className="fs-6">Cambios sin guardar</Modal.Title>
        </Modal.Header>
        <Modal.Body className="bg-dark text-light small">{pendingConfirm?.message}</Modal.Body>
        <Modal.Footer className="border-secondary bg-dark">
          <Button variant="outline-secondary" size="sm" onClick={() => setPendingConfirm(null)}>Seguir editando</Button>
          <Button variant="danger" size="sm" onClick={() => { pendingConfirm?.onConfirm(); setPendingConfirm(null); }}>
            Descartar cambios
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
};

export default StrategyPage;
