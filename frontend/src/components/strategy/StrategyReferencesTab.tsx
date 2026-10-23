import React, { useCallback, useEffect, useState } from 'react';
import { strategyApi } from '../../api/strategy';
import type { AgentConfigPatch, AgentStrategyConfig, ReferenceAnalysis } from '../../types';
import { TagInput } from './TagInput';
import { PendingSuggestionsList } from './PendingSuggestionsList';
import { MAX_REFERENCE_ACCOUNTS, sameValue } from './strategyOptions';
import './StrategyReferencesTab.css';

interface StrategyReferencesTabProps {
  accountId: number;
  draft: AgentStrategyConfig;
  savedReferences: string[];
  onChange: (patch: AgentConfigPatch) => void;
  onSuggestionAccepted: (field: keyof AgentStrategyConfig, value: unknown) => void;
}

const FORMAT_LABELS: Record<string, string> = { REELS: 'Reels', CAROUSEL_ALBUM: 'Carruseles', IMAGE: 'Fotos' };

const STATUS_HELP: Record<Exclude<ReferenceAnalysis['status'], 'ok'>, string> = {
  not_professional: 'No es una cuenta profesional: Instagram solo permite analizar cuentas de empresa o creador.',
  not_found: 'No existe ninguna cuenta con ese nombre (o no es profesional).',
  error: 'No se pudo analizar ahora mismo.',
};

const formatNumber = (n?: number | null) => (n == null ? '—' : new Intl.NumberFormat('es-ES').format(n));

export const StrategyReferencesTab: React.FC<StrategyReferencesTabProps> = ({
  accountId, draft, savedReferences, onChange, onSuggestionAccepted,
}) => {
  const [analysis, setAnalysis] = useState<ReferenceAnalysis[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestionsKey, setSuggestionsKey] = useState(0);
  const savedKey = savedReferences.join(',');
  const pendingSave = !sameValue(draft.reference_accounts, savedReferences);

  const load = useCallback(async (refresh: boolean) => {
    if (!savedKey) { setAnalysis([]); return; }
    setLoading(true);
    setError(null);
    try {
      const res = await strategyApi.getReferences(accountId, refresh);
      setAnalysis(res.references);
      if (res.refreshed) setSuggestionsKey(k => k + 1);
    } catch {
      setError('No se pudo cargar el análisis de tus referentes.');
    } finally {
      setLoading(false);
    }
  }, [accountId, savedKey]);

  useEffect(() => { void load(false); }, [load]);

  return (
    <div className="srt">
      <section className="stg-section">
        <div className="d-flex align-items-center justify-content-between">
          <h3 className="stg-section-title"><i className="bi bi-at" />Cuentas de referencia</h3>
          <span className="srt-count">{draft.reference_accounts.length}/{MAX_REFERENCE_ACCOUNTS}</span>
        </div>
        <p className="srt-help small">Cuentas que te inspiran o con las que compites. Hermes analiza qué publican y qué les funciona.</p>
        <TagInput id="srt-refs" prefix="@" variant="info" max={MAX_REFERENCE_ACCOUNTS}
          values={draft.reference_accounts}
          normalize={raw => raw.trim().replace(/^@/, '')}
          onChange={v => onChange({ reference_accounts: v })}
          placeholder="cuenta_referente" />
        {pendingSave && <p className="srt-pending small mt-2 mb-0">Guarda los cambios para analizar la nueva lista.</p>}
      </section>

      {savedReferences.length > 0 && (
        <section className="stg-section">
          <div className="d-flex align-items-center justify-content-between">
            <h3 className="stg-section-title"><i className="bi bi-graph-up" />Qué les funciona</h3>
            <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => load(true)} disabled={loading}>
              {loading ? <span className="spinner-border spinner-border-sm" /> : <><i className="bi bi-arrow-clockwise me-1" />Actualizar</>}
            </button>
          </div>
          {error && <div className="alert alert-danger py-2 px-3 small">{error}</div>}
          {loading && analysis.length === 0 && <p className="srt-help small mb-0">Analizando referentes…</p>}
          <div className="srt-cards">
            {analysis.map(ref => (
              <article key={ref.username} className={`srt-card ${ref.status === 'ok' ? '' : 'is-invalid'}`}
                data-testid={`reference-${ref.username}`}>
                <header className="d-flex align-items-center justify-content-between mb-2">
                  <a className="srt-username" href={`https://instagram.com/${ref.username}`} target="_blank" rel="noopener noreferrer">
                    @{ref.username}
                  </a>
                  {ref.status === 'ok' && <span className="srt-followers">{formatNumber(ref.followers)} seguidores</span>}
                </header>
                {ref.status !== 'ok' ? (
                  <p className="srt-warning small mb-0">
                    <i className="bi bi-exclamation-triangle me-1" />
                    {STATUS_HELP[ref.status]}{ref.status === 'error' && ref.error_message ? ` ${ref.error_message}` : ''}
                  </p>
                ) : (
                  <>
                    <dl className="srt-metrics">
                      <div><dt>Frecuencia</dt><dd>{ref.posts_per_week ?? '—'} posts/semana</dd></div>
                      <div>
                        <dt>Formatos</dt>
                        <dd>
                          {Object.entries(ref.format_mix ?? {})
                            .filter(([, v]) => v > 0)
                            .map(([k, v]) => `${FORMAT_LABELS[k] ?? k} ${v}%`).join(' · ') || '—'}
                        </dd>
                      </div>
                      <div><dt>Ganchos</dt><dd>{ref.hook_formulas?.join(', ') || 'Sin fórmula clara'}</dd></div>
                    </dl>
                    {(ref.top_posts?.length ?? 0) > 0 && (
                      <ol className="srt-top">
                        {ref.top_posts?.map((p, i) => (
                          <li key={p.permalink ?? i}>
                            {p.permalink
                              ? <a href={p.permalink} target="_blank" rel="noopener noreferrer">{p.caption_first_line || 'Sin texto'}</a>
                              : p.caption_first_line || 'Sin texto'}
                            <span className="srt-rate">{p.engagement_rate}%</span>
                          </li>
                        ))}
                      </ol>
                    )}
                  </>
                )}
              </article>
            ))}
          </div>
        </section>
      )}

      <section className="stg-section">
        <h3 className="stg-section-title"><i className="bi bi-lightbulb" />Sugerencias a partir de tus referentes</h3>
        <PendingSuggestionsList
          key={suggestionsKey}
          accountId={accountId}
          fromReferences
          onAccepted={onSuggestionAccepted}
          emptyText="No hay sugerencias pendientes de tus referentes."
        />
      </section>
    </div>
  );
};
