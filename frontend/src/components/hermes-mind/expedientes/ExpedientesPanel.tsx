import React from 'react';
import './ExpedientesPanel.css';
import { ExpedienteCard } from './ExpedienteCard';
import { SourceChip } from '../shared/SourceChip';
import type { DecisionSummary, Source } from '../shared/types';

interface ExpedientesPanelProps {
  decisions: DecisionSummary[];
  /** resolve a decision's applied rules → source chips */
  sourcesFor: (d: DecisionSummary) => Source[];
  token: string | null;
  selectedId: number | null;
  onSelect: (id: number) => void;
  loading: boolean;
  error: boolean;
  activeSource: Source | null;
  onClearFilter: () => void;
}

export const ExpedientesPanel: React.FC<ExpedientesPanelProps> = ({
  decisions,
  sourcesFor,
  token,
  selectedId,
  onSelect,
  loading,
  error,
  activeSource,
  onClearFilter,
}) => {
  return (
    <section className="hm-panel stream-panel hm-col">
      <div className="stream-head">
        <span className="hm-panel-label">Decisiones</span>
        {activeSource && (
          <span className="stream-filter">
            <SourceChip label={activeSource.label} kind={activeSource.kind} conflict={activeSource.conflict} />
            <button type="button" className="stream-clear" onClick={onClearFilter}>
              quitar filtro ×
            </button>
          </span>
        )}
      </div>
      <div className="stream-scroll">
        {loading && decisions.length === 0 ? (
          <div className="hm-state">
            <div className="hm-spinner" />
            <p>Cargando decisiones…</p>
          </div>
        ) : error && decisions.length === 0 ? (
          <div className="hm-state">
            <i className="bi bi-exclamation-circle" />
            <p>No se pudieron cargar las decisiones.</p>
          </div>
        ) : decisions.length === 0 ? (
          <div className="hm-state">
            <i className="bi bi-cpu" />
            <p>
              {activeSource
                ? 'Ninguna decisión coincide con ese filtro en la propuesta seleccionada.'
                : 'Hermes aún no ha tomado decisiones para esta cuenta.'}
            </p>
          </div>
        ) : (
          decisions.map((d) => (
            <ExpedienteCard
              key={d.id}
              decision={d}
              sources={sourcesFor(d)}
              token={token}
              selected={d.id === selectedId}
              onSelect={onSelect}
            />
          ))
        )}
      </div>
    </section>
  );
};
