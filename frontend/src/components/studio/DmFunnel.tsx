import React, { useState } from 'react';
import { contentApi } from '../../api/content';
import type { DmFunnelResponse, StrategyMode } from '../../types';
import './DmFunnel.css';

interface DmFunnelProps {
  strategyMode?: StrategyMode;
  accountId?: number;
}

export const DmFunnel: React.FC<DmFunnelProps> = ({ strategyMode, accountId }) => {
  const [keyword, setKeyword] = useState<string>('');
  const [resourceDescription, setResourceDescription] = useState<string>('');
  const [funnel, setFunnel] = useState<DmFunnelResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedSection, setCopiedSection] = useState<string | null>(null);

  // Requirement: En cuentas personales, el bloque de embudo de DM no se muestra
  if (strategyMode === 'personal_storyline') {
    return null;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!keyword.trim() || !resourceDescription.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const res = await contentApi.generateDmFunnel({
        keyword: keyword.trim(),
        resource_description: resourceDescription.trim(),
        account_id: accountId,
      });
      setFunnel(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error generando embudo de DM');
    } finally {
      setLoading(false);
    }
  };

  const copyText = async (text: string, sectionKey: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedSection(sectionKey);
      setTimeout(() => {
        setCopiedSection(null);
      }, 2000);
    } catch {
      // Fallback
    }
  };

  return (
    <div className="dm-funnel-container" data-testid="dm-funnel-panel">
      <div className="dm-funnel-header mb-3">
        <h5 className="mb-1">
          <i className="bi bi-envelope-paper me-2"></i>Embudo de DM por Palabra Clave
        </h5>
        <p className="text-muted small mb-0">
          Genera el mensaje de entrega del recurso y 2 mensajes de seguimiento para copiar manualmente.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="dm-funnel-form mb-3">
        <div className="row g-2 mb-2">
          <div className="col-12 col-md-5">
            <label className="form-label small fw-semibold">Palabra clave a comentar:</label>
            <input
              type="text"
              className="form-control form-control-sm"
              placeholder="Ej: GUIA, SISTEMA, PLANTILLA"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              required
            />
          </div>
          <div className="col-12 col-md-7">
            <label className="form-label small fw-semibold">Descripción del recurso:</label>
            <input
              type="text"
              className="form-control form-control-sm"
              placeholder="Ej: Plantilla de Notion para calendario de contenidos"
              value={resourceDescription}
              onChange={(e) => setResourceDescription(e.target.value)}
              required
            />
          </div>
        </div>

        <div className="d-flex justify-content-end">
          <button
            type="submit"
            className="btn btn-primary btn-sm"
            disabled={loading || !keyword.trim() || !resourceDescription.trim()}
          >
            {loading ? (
              <>
                <span className="spinner-border spinner-border-sm me-1" role="status"></span>
                Generando embudo...
              </>
            ) : (
              <>
                <i className="bi bi-stars me-1"></i>Generar mensajes
              </>
            )}
          </button>
        </div>
      </form>

      {error && <div className="alert alert-danger py-2">{error}</div>}

      {funnel && (
        <div className="dm-funnel-results mt-3">
          <div className="dm-funnel-card mb-2">
            <div className="d-flex justify-content-between align-items-center mb-1">
              <span className="dm-funnel-card-title">
                <i className="bi bi-box-arrow-up-right me-1 text-primary"></i>Mensaje de entrega (Inmediato)
              </span>
              <button
                type="button"
                className="btn btn-sm dm-funnel-copy-btn"
                onClick={() => copyText(funnel.delivery_dm, 'delivery')}
                aria-label="Copiar mensaje de entrega"
              >
                {copiedSection === 'delivery' ? (
                  <>
                    <i className="bi bi-check-lg text-success me-1"></i>
                    <span className="text-success">Copiado</span>
                  </>
                ) : (
                  <>
                    <i className="bi bi-clipboard me-1"></i>Copiar
                  </>
                )}
              </button>
            </div>
            <p className="dm-funnel-text mb-0">{funnel.delivery_dm}</p>
          </div>

          {funnel.follow_ups.map((fu, idx) => (
            <div key={idx} className="dm-funnel-card mb-2">
              <div className="d-flex justify-content-between align-items-center mb-1">
                <span className="dm-funnel-card-title">
                  <i className="bi bi-clock-history me-1 text-info"></i>Seguimiento #{idx + 1}
                </span>
                <button
                  type="button"
                  className="btn btn-sm dm-funnel-copy-btn"
                  onClick={() => copyText(fu, `fu_${idx}`)}
                  aria-label={`Copiar seguimiento ${idx + 1}`}
                >
                  {copiedSection === `fu_${idx}` ? (
                    <>
                      <i className="bi bi-check-lg text-success me-1"></i>
                      <span className="text-success">Copiado</span>
                    </>
                  ) : (
                    <>
                      <i className="bi bi-clipboard me-1"></i>Copiar
                    </>
                  )}
                </button>
              </div>
              <p className="dm-funnel-text mb-0">{fu}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default DmFunnel;
