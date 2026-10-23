import React, { useCallback, useEffect, useState } from 'react';
import { strategyApi } from '../../api/strategy';
import { ApiError } from '../../api/client';
import type { AgentStrategyConfig, AgentSuggestion } from '../../types';
import { formatValue, isFromReferences } from './strategyOptions';
import './PendingSuggestionsList.css';

interface PendingSuggestionsListProps {
  accountId: number;
  /** Tipos de sugerencia a mostrar; sin filtro, todos. */
  types?: string[];
  /** Solo las que vienen de referentes (true) o las que no (false). */
  fromReferences?: boolean;
  onAccepted: (field: keyof AgentStrategyConfig, value: unknown) => void;
  emptyText?: string;
}

const SUGGESTION_META: Record<string, { label: string; field: keyof AgentStrategyConfig; argsKey: string }> = {
  suggest_schedule_change: { label: 'Horarios', field: 'best_times', argsKey: 'suggested_best_times' },
  suggest_mix_change:      { label: 'Mix semanal', field: 'content_type_mix', argsKey: 'suggested_content_type_mix' },
  suggest_pillars_change:  { label: 'Pilares', field: 'content_pillars', argsKey: 'suggested_content_pillars' },
};

export const PendingSuggestionsList: React.FC<PendingSuggestionsListProps> = ({
  accountId, types, fromReferences, onAccepted, emptyText,
}) => {
  const [items, setItems] = useState<AgentSuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const typesKey = (types ?? []).join(',');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const all = await strategyApi.listPendingSuggestions(accountId);
      setItems(all.filter(s =>
        (!typesKey || typesKey.split(',').includes(s.decision_type))
        && (fromReferences === undefined || isFromReferences(s) === fromReferences)
      ));
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [accountId, typesKey, fromReferences]);

  useEffect(() => { void load(); }, [load]);

  const act = async (s: AgentSuggestion, action: 'accept' | 'dismiss') => {
    setBusyId(s.id);
    setError(null);
    try {
      if (action === 'accept') {
        const res = await strategyApi.acceptSuggestion(s.id);
        onAccepted(res.config_column, res.applied_value);
      } else {
        await strategyApi.dismissSuggestion(s.id);
      }
      setItems(prev => prev.filter(x => x.id !== s.id));
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'No se pudo completar la acción');
    } finally {
      setBusyId(null);
    }
  };

  if (loading) return null;
  if (items.length === 0) return emptyText ? <p className="psl-empty small mb-0">{emptyText}</p> : null;

  return (
    <div className="psl">
      {error && <div className="alert alert-danger py-2 px-3 small">{error}</div>}
      {items.map(s => {
        const meta = SUGGESTION_META[s.decision_type];
        const value = meta ? s.tool_args?.[meta.argsKey] : undefined;
        return (
          <div key={s.id} className="psl-item" data-testid="pending-suggestion">
            <div className="d-flex align-items-center gap-2 mb-1">
              <i className="bi bi-lightbulb psl-icon" />
              <span className="psl-label">{meta?.label ?? s.decision_type}</span>
              {isFromReferences(s) && <span className="badge psl-badge">Referentes</span>}
            </div>
            {s.rationale && <p className="psl-rationale small mb-1">{s.rationale}</p>}
            {meta && value !== undefined && (
              <p className="psl-value small mb-2">Propuesta: <strong>{formatValue(meta.field, value)}</strong></p>
            )}
            <div className="d-flex gap-2">
              <button type="button" className="btn btn-sm btn-success" disabled={busyId === s.id}
                onClick={() => act(s, 'accept')}>
                <i className="bi bi-check-lg me-1" />Aceptar
              </button>
              <button type="button" className="btn btn-sm btn-outline-secondary" disabled={busyId === s.id}
                onClick={() => act(s, 'dismiss')}>
                Descartar
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
};
