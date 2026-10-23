import React, { useState } from 'react';
import type { AgentConfigPatch, AgentStrategyConfig } from '../../types';
import { TagInput } from './TagInput';
import { AccountTypeChangeModal } from './AccountTypeChangeModal';
import { ACCOUNT_TYPE_PRESETS, CAPTION_VOICE_OPTS, TONES } from './strategyOptions';
import './StrategyBrandTab.css';

interface StrategyBrandTabProps {
  draft: AgentStrategyConfig;
  onChange: (patch: AgentConfigPatch) => void;
}

const ACCOUNT_TYPES: { value: AgentStrategyConfig['account_type']; icon: string; label: string; desc: string }[] = [
  { value: 'personal',     icon: 'bi-person',    label: 'Personal',    desc: 'Creador, 1ª persona, audio trending' },
  { value: 'professional', icon: 'bi-briefcase', label: 'Profesional', desc: 'Marca, funnel de conversión, cadencia fija' },
];

export const StrategyBrandTab: React.FC<StrategyBrandTabProps> = ({ draft, onChange }) => {
  const [pendingType, setPendingType] = useState<AgentStrategyConfig['account_type'] | null>(null);

  const requestTypeChange = (value: AgentStrategyConfig['account_type']) => {
    if (value !== draft.account_type) setPendingType(value);
  };

  return (
    <div className="sbt">
      <section className="stg-section">
        <h3 className="stg-section-title"><i className="bi bi-grid-1x2" />Tipo de cuenta</h3>
        <div className="d-flex gap-3">
          {ACCOUNT_TYPES.map(opt => (
            <button key={opt.value} type="button" aria-pressed={draft.account_type === opt.value}
              className={`stg-option-card flex-grow-1 ${draft.account_type === opt.value ? 'is-active' : ''}`}
              onClick={() => requestTypeChange(opt.value)}>
              <i className={`bi ${opt.icon} d-block mb-1`} />
              <span className="stg-option-title">{opt.label}</span>
              <span className="stg-option-desc">{opt.desc}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="stg-section">
        <h3 className="stg-section-title"><i className="bi bi-tag" />Identidad</h3>
        <div className="mb-3">
          <label className="stg-label" htmlFor="sbt-sector">Sector / Nicho</label>
          <input id="sbt-sector" className="form-control form-control-sm stg-input" value={draft.sector}
            onChange={e => onChange({ sector: e.target.value })} placeholder="Ej: Deporte profesional, Fotografía, Fitness" />
        </div>
        <div className="mb-3">
          <label className="stg-label" htmlFor="sbt-purpose">Objetivo principal</label>
          <input id="sbt-purpose" className="form-control form-control-sm stg-input" value={draft.purpose}
            onChange={e => onChange({ purpose: e.target.value })} placeholder="Ej: Inspirar y compartir mi pasión" />
        </div>
        <div>
          <label className="stg-label" htmlFor="sbt-audience">Audiencia objetivo</label>
          <textarea id="sbt-audience" className="form-control form-control-sm stg-input" rows={2} value={draft.target_audience}
            onChange={e => onChange({ target_audience: e.target.value })}
            placeholder="Ej: Jóvenes aficionados al fútbol y la fotografía, 18-30 años" />
        </div>
      </section>

      <section className="stg-section">
        <h3 className="stg-section-title"><i className="bi bi-mic" />Voz</h3>
        <div className="mb-3">
          <span className="stg-label">Tono</span>
          <div className="d-flex flex-wrap gap-2">
            {TONES.map(t => (
              <button key={t.value} type="button" aria-pressed={draft.default_tone === t.value}
                className={`stg-pill ${draft.default_tone === t.value ? 'is-active' : ''}`}
                onClick={() => onChange({ default_tone: t.value })}>
                {t.emoji} {t.label}
              </button>
            ))}
          </div>
        </div>
        <div className="mb-3">
          <span className="stg-label">Idioma de los captions</span>
          <div className="d-flex gap-2">
            {(['es', 'en'] as const).map(lang => (
              <button key={lang} type="button" aria-pressed={draft.default_language === lang}
                className={`btn btn-sm ${draft.default_language === lang ? 'btn-primary' : 'btn-outline-secondary'}`}
                onClick={() => onChange({ default_language: lang })}>
                {lang === 'es' ? 'Español' : 'Inglés'}
              </button>
            ))}
          </div>
        </div>
        <div className="mb-3">
          <label className="stg-label" htmlFor="sbt-style">Guía de estilo</label>
          <textarea id="sbt-style" className="form-control form-control-sm stg-input" rows={3} value={draft.style_guide}
            onChange={e => onChange({ style_guide: e.target.value })}
            placeholder="Ej: Tono cercano e inspirador, combinar fútbol con fotografía y viajes" />
        </div>
        <div>
          <span className="stg-label">Estilo de caption</span>
          <div className="d-flex gap-2">
            {CAPTION_VOICE_OPTS.map(o => (
              <button key={o.label} type="button" aria-pressed={draft.caption_voice === o.value}
                className={`btn btn-sm flex-grow-1 ${draft.caption_voice === o.value ? 'btn-primary' : 'btn-outline-secondary'}`}
                onClick={() => onChange({ caption_voice: o.value })}>
                {o.label}<span className="stg-btn-sub">{o.desc}</span>
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="stg-section">
        <h3 className="stg-section-title"><i className="bi bi-collection" />Pilares de contenido</h3>
        <TagInput id="sbt-pillars" values={draft.content_pillars} onChange={v => onChange({ content_pillars: v })}
          placeholder="Ej: Fotografía de viajes, Día de partido" />
      </section>

      <section className="stg-section">
        <h3 className="stg-section-title"><i className="bi bi-shield-slash" />Filtro anti-slop</h3>
        <div className="form-check form-switch mb-3">
          <input className="form-check-input" type="checkbox" role="switch" id="sbt-humanizer"
            checked={draft.humanizer_enabled} onChange={e => onChange({ humanizer_enabled: e.target.checked })} />
          <label className="form-check-label small" htmlFor="sbt-humanizer">Limpieza automática de lenguaje sintético</label>
        </div>
        <label className="stg-label" htmlFor="sbt-banned">Términos vetados</label>
        <TagInput id="sbt-banned" values={draft.banned_phrases} onChange={v => onChange({ banned_phrases: v })}
          placeholder="Nuevo término vetado..." variant="danger" />
      </section>

      {pendingType && (
        <AccountTypeChangeModal
          show
          newType={pendingType}
          current={draft}
          onCancel={() => setPendingType(null)}
          onTypeOnly={() => { onChange({ account_type: pendingType }); setPendingType(null); }}
          onApplyPreset={() => {
            onChange({ account_type: pendingType, ...ACCOUNT_TYPE_PRESETS[pendingType] });
            setPendingType(null);
          }}
        />
      )}
    </div>
  );
};
