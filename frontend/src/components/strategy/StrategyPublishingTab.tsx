import React, { useState } from 'react';
import { apiClient } from '../../api/client';
import { HASHTAG_LEVELS } from '../../types';
import type { AgentConfigPatch, AgentStrategyConfig, ContentTypeMix } from '../../types';
import { TagInput } from './TagInput';
import { PendingSuggestionsList } from './PendingSuggestionsList';
import { CONTENT_TYPES, DAYS } from './strategyOptions';
import './StrategyPublishingTab.css';

interface StrategyPublishingTabProps {
  accountId: number;
  draft: AgentStrategyConfig;
  onChange: (patch: AgentConfigPatch) => void;
  onSuggestionAccepted: (field: keyof AgentStrategyConfig, value: unknown) => void;
}

// Al desactivar "Usar mis datos" sin horarios previos
const FALLBACK_BEST_TIMES = ['09:00', '19:00'];
const TIME_RE = /^\d{2}:\d{2}$/;

export const StrategyPublishingTab: React.FC<StrategyPublishingTabProps> = ({
  accountId, draft, onChange, onSuggestionAccepted,
}) => {
  const [lastBestTimes, setLastBestTimes] = useState<string[]>([]);
  const [suggestingTimes, setSuggestingTimes] = useState(false);
  const total = Object.values(draft.content_type_mix).reduce((s, n) => s + n, 0);
  const useHistoricalTimes = draft.best_times.length === 0;

  const setMix = (key: keyof ContentTypeMix, value: number) =>
    onChange({ content_type_mix: { ...draft.content_type_mix, [key]: Math.max(0, Math.min(7, value)) } });

  const toggleDay = (day: string) => onChange({
    preferred_days: draft.preferred_days.includes(day)
      ? draft.preferred_days.filter(d => d !== day)
      : [...draft.preferred_days, day],
  });

  const toggleHistoricalTimes = () => {
    if (useHistoricalTimes) {
      onChange({ best_times: lastBestTimes.length ? lastBestTimes : FALLBACK_BEST_TIMES });
    } else {
      setLastBestTimes(draft.best_times);
      onChange({ best_times: [] });
    }
  };

  const suggestTimes = async () => {
    setSuggestingTimes(true);
    try {
      const d = await apiClient.post<{ best_times?: string[] }>('/api/agent/suggest-times', {
        sector: draft.sector, target_audience: draft.target_audience,
        default_tone: draft.default_tone, account_type: draft.account_type, account_id: accountId,
      });
      if (d.best_times?.length) onChange({ best_times: d.best_times });
    } catch { /* sin sugerencia: se mantiene lo que hay */ }
    finally { setSuggestingTimes(false); }
  };

  return (
    <div className="spt">
      <section className="stg-section">
        <h3 className="stg-section-title"><i className="bi bi-lightbulb" />Sugerencias de Hermes</h3>
        <PendingSuggestionsList
          accountId={accountId}
          types={['suggest_schedule_change', 'suggest_mix_change']}
          onAccepted={onSuggestionAccepted}
          emptyText="Hermes no tiene sugerencias pendientes sobre horarios ni mix."
        />
      </section>

      <section className="stg-section">
        <div className="d-flex align-items-center justify-content-between">
          <h3 className="stg-section-title"><i className="bi bi-layout-three-columns" />Piezas por tipo y semana</h3>
          <span className="spt-total">{total} por semana</span>
        </div>
        <div className="spt-mix">
          {CONTENT_TYPES.map(ct => (
            <div key={ct.key} className="spt-mix-row">
              <span className="spt-mix-icon">{ct.icon}</span>
              <div className="flex-grow-1">
                <div className="spt-mix-label">{ct.label}</div>
                <div className="spt-mix-desc">{ct.desc}</div>
              </div>
              <div className="d-flex align-items-center gap-1">
                <button type="button" className="spt-counter" aria-label={`Menos ${ct.label}`}
                  onClick={() => setMix(ct.key, draft.content_type_mix[ct.key] - 1)}>−</button>
                <span className="spt-count" data-testid={`mix-${ct.key}`}>{draft.content_type_mix[ct.key]}</span>
                <button type="button" className="spt-counter" aria-label={`Más ${ct.label}`}
                  onClick={() => setMix(ct.key, draft.content_type_mix[ct.key] + 1)}>+</button>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="stg-section">
        <h3 className="stg-section-title"><i className="bi bi-shuffle" />Distribución semanal</h3>
        <div className="d-flex gap-2 mb-3">
          {([
            { value: 'flexible' as const, icon: 'bi-shuffle',   label: 'Flexible',         desc: 'Hermes reparte los días' },
            { value: 'fixed'    as const, icon: 'bi-calendar3', label: 'Días específicos', desc: 'Solo publica en los días que elijas' },
          ]).map(m => (
            <button key={m.value} type="button" aria-pressed={draft.scheduling_mode === m.value}
              className={`stg-option-card flex-grow-1 ${draft.scheduling_mode === m.value ? 'is-active' : ''}`}
              onClick={() => onChange({ scheduling_mode: m.value })}>
              <i className={`bi ${m.icon} d-block mb-1`} />
              <span className="stg-option-title">{m.label}</span>
              <span className="stg-option-desc">{m.desc}</span>
            </button>
          ))}
        </div>
        <span className="stg-label">{draft.scheduling_mode === 'fixed' ? 'Días de publicación' : 'Días preferidos (orientativos)'}</span>
        <div className="d-flex gap-2">
          {DAYS.map(d => {
            const on = draft.preferred_days.includes(d.key);
            return (
              <button key={d.key} type="button" title={d.label} aria-label={d.label} aria-pressed={on}
                className={`spt-day ${on ? 'is-active' : ''}`} onClick={() => toggleDay(d.key)}>
                {d.short}
              </button>
            );
          })}
        </div>
      </section>

      <section className="stg-section">
        <div className="d-flex align-items-center justify-content-between">
          <h3 className="stg-section-title"><i className="bi bi-clock" />Horarios</h3>
          {!useHistoricalTimes && (
            <button type="button" className="spt-link" onClick={suggestTimes} disabled={suggestingTimes}>
              {suggestingTimes ? <span className="spinner-border spinner-border-sm spt-spinner" /> : <i className="bi bi-stars" />}
              Sugerir con IA
            </button>
          )}
        </div>
        <div className="form-check form-switch mb-2">
          <input className="form-check-input" type="checkbox" role="switch" id="spt-historical"
            checked={useHistoricalTimes} onChange={toggleHistoricalTimes} />
          <label className="form-check-label small" htmlFor="spt-historical">
            Usar mis datos <span className="spt-hint">— Hermes elige la hora con tu histórico</span>
          </label>
        </div>
        {!useHistoricalTimes && (
          <TagInput id="spt-times" inputType="time" variant="info" values={draft.best_times}
            normalize={raw => (TIME_RE.test(raw) ? raw : '')}
            onChange={v => onChange({ best_times: [...v].sort() })} />
        )}
      </section>

      <section className="stg-section">
        <h3 className="stg-section-title"><i className="bi bi-hash" />Hashtags por post</h3>
        <div className="d-flex gap-2">
          {HASHTAG_LEVELS.map(o => (
            <button key={o.value} type="button" aria-pressed={draft.hashtag_strategy === o.value}
              className={`btn btn-sm flex-grow-1 ${draft.hashtag_strategy === o.value ? 'btn-primary' : 'btn-outline-secondary'}`}
              onClick={() => onChange({ hashtag_strategy: o.value })}>
              {o.label}<span className="stg-btn-sub">{o.range}</span>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
};
