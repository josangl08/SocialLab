import React, { useEffect, useState } from 'react';
import { strategyApi } from '../../api/strategy';
import type { StrategyDiagnostics, StrategyIssue, StrategyTab } from '../../types';
import { ProfileAudit } from '../studio/ProfileAudit';
import { STRATEGY_TABS } from './strategyOptions';
import './StrategyDiagnosticsTab.css';

interface StrategyDiagnosticsTabProps {
  accountId: number;
  /** Cambia tras cada guardado para volver a pedir el diagnóstico. */
  refreshKey: number;
  onGoToTab: (tab: StrategyTab) => void;
}

const SEVERITIES: { key: StrategyIssue['severity']; label: string; icon: string }[] = [
  { key: 'error',   label: 'Errores',      icon: 'bi-x-octagon' },
  { key: 'warning', label: 'Avisos',       icon: 'bi-exclamation-triangle' },
  { key: 'info',    label: 'Información',  icon: 'bi-info-circle' },
];

export const StrategyDiagnosticsTab: React.FC<StrategyDiagnosticsTabProps> = ({ accountId, refreshKey, onGoToTab }) => {
  const [data, setData] = useState<StrategyDiagnostics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [showAudit, setShowAudit] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);
    strategyApi.getDiagnostics(accountId)
      .then(d => { if (!cancelled) setData(d); })
      .catch(() => { if (!cancelled) setError(true); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [accountId, refreshKey]);

  if (loading) {
    return <div className="d-flex justify-content-center py-5"><div className="spinner-border text-primary" role="status" /></div>;
  }
  if (error || !data) {
    return <div className="alert alert-danger small">No se pudo cargar el diagnóstico.</div>;
  }

  const tabLabel = (tab: StrategyTab) => STRATEGY_TABS.find(t => t.key === tab)?.label ?? tab;

  return (
    <div className="sdt">
      <section className="stg-section">
        <h3 className="stg-section-title"><i className="bi bi-clipboard2-pulse" />Coherencia de la estrategia</h3>
        {data.issues.length === 0 ? (
          <p className="sdt-ok small mb-0"><i className="bi bi-check2-circle me-2" />No hay problemas en tu estrategia.</p>
        ) : SEVERITIES.map(sev => {
          const issues = data.issues.filter(i => i.severity === sev.key);
          if (issues.length === 0) return null;
          return (
            <div key={sev.key} className="mb-3">
              <div className={`sdt-sev sdt-sev--${sev.key}`}><i className={`bi ${sev.icon} me-1`} />{sev.label}</div>
              <ul className="sdt-issues">
                {issues.map(i => (
                  <li key={i.code} className={`sdt-issue sdt-issue--${i.severity}`} data-testid={`issue-${i.code}`}>
                    <span>{i.message}</span>
                    <button type="button" className="sdt-fix" onClick={() => onGoToTab(i.tab)}>
                      Ir a {tabLabel(i.tab)} →
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </section>

      <section className="stg-section">
        <h3 className="stg-section-title"><i className="bi bi-chat-square-text" />Cómo te entiende Hermes</h3>
        <p className="sdt-help small">Este es el perfil que recibe el agente en cada sesión.</p>
        <pre className="sdt-preview" data-testid="context-preview">{data.context_preview}</pre>
      </section>

      <section className="stg-section">
        <div className="d-flex align-items-center justify-content-between">
          <h3 className="stg-section-title"><i className="bi bi-shield-check" />Auditoría del perfil</h3>
          <span className="sdt-score">{data.profile_audit.score}/100</span>
        </div>
        <ul className="sdt-audit">
          {data.profile_audit.items.map(item => (
            <li key={item.id} className={item.passed ? 'is-passed' : 'is-failed'}>
              <i className={`bi ${item.passed ? 'bi-check-circle' : 'bi-circle'} me-2`} />
              {item.label}
              {!item.passed && <span className="sdt-tip"> — {item.tip}</span>}
            </li>
          ))}
        </ul>
        <button type="button" className="btn btn-sm btn-outline-info" onClick={() => setShowAudit(true)}>
          Auditoría completa con bio sugerida
        </button>
      </section>

      <ProfileAudit accountId={accountId} isOpen={showAudit} onClose={() => setShowAudit(false)} />
    </div>
  );
};
