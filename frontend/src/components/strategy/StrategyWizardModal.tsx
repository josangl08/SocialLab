import React, { useEffect, useMemo, useState } from 'react';
import { Modal, Button } from 'react-bootstrap';
import { strategyApi } from '../../api/strategy';
import { ApiError } from '../../api/client';
import { HybridSelect } from '../../features/agent/HybridSelect';
import type { AgentConfigPatch, AgentStrategyConfig, StrategyWizardAnswers } from '../../types';
import { TagInput } from './TagInput';
import {
  FIELD_LABELS, MAX_REFERENCE_ACCOUNTS, TAB_FIELDS, WIZARD_OPTIONS, formatValue, sameValue,
} from './strategyOptions';
import './StrategyWizardModal.css';

interface StrategyWizardModalProps {
  show: boolean;
  accountId: number;
  current: AgentStrategyConfig;
  savedAnswers?: StrategyWizardAnswers | null;
  onClose: () => void;
  /** Aplica los campos elegidos como cambios sin guardar. */
  onApply: (patch: AgentConfigPatch) => void;
  onAnswersSaved: (answers: StrategyWizardAnswers) => void;
  /** Contenido extra bajo la propuesta (Fase C: sugerencias de referentes). */
  extraProposal?: React.ReactNode;
}

const EMPTY_ANSWERS: StrategyWizardAnswers = { dedica: [], contenido: [], objetivo: [], referentes: [] };
const EDITABLE_FIELDS = new Set<keyof AgentConfigPatch>([...TAB_FIELDS.marca, ...TAB_FIELDS.publicacion, ...TAB_FIELDS.referentes]);

interface ProposedField { field: keyof AgentConfigPatch; from: unknown; to: unknown; changed: boolean; }

export const StrategyWizardModal: React.FC<StrategyWizardModalProps> = ({
  show, accountId, current, savedAnswers, onClose, onApply, onAnswersSaved, extraProposal,
}) => {
  const [answers, setAnswers] = useState<StrategyWizardAnswers>(EMPTY_ANSWERS);
  const [generated, setGenerated] = useState<Partial<AgentStrategyConfig> | null>(null);
  const [selected, setSelected] = useState<Set<keyof AgentConfigPatch>>(new Set());
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!show) return;
    setAnswers({ ...EMPTY_ANSWERS, ...(savedAnswers ?? {}) });
    setGenerated(null);
    setError(null);
  }, [show, savedAnswers]);

  const proposal: ProposedField[] = useMemo(() => {
    if (!generated) return [];
    return (Object.entries(generated) as [keyof AgentConfigPatch, unknown][])
      .filter(([field, value]) => EDITABLE_FIELDS.has(field) && value !== undefined)
      .map(([field, to]) => ({ field, from: current[field], to, changed: !sameValue(current[field], to) }));
  }, [generated, current]);

  const generate = async () => {
    if (!answers.dedica.length && !answers.contenido.length && !answers.objetivo.length) {
      setError('Responde al menos una pregunta.');
      return;
    }
    setGenerating(true);
    setError(null);
    try {
      const result = await strategyApi.generateStrategy(accountId, answers);
      const withRefs = answers.referentes.length
        ? { ...result, reference_accounts: answers.referentes.slice(0, MAX_REFERENCE_ACCOUNTS) }
        : result;
      setGenerated(withRefs);
      setSelected(new Set(
        (Object.keys(withRefs) as (keyof AgentConfigPatch)[])
          .filter(f => EDITABLE_FIELDS.has(f) && !sameValue(current[f], withRefs[f]))
      ));
      onAnswersSaved({ ...answers, answered_at: new Date().toISOString() });
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Error al generar la estrategia');
    } finally {
      setGenerating(false);
    }
  };

  const toggle = (field: keyof AgentConfigPatch) => setSelected(prev => {
    const next = new Set(prev);
    if (next.has(field)) next.delete(field); else next.add(field);
    return next;
  });

  const apply = () => {
    if (!generated) return;
    const patch = Object.fromEntries(
      proposal.filter(p => selected.has(p.field)).map(p => [p.field, p.to])
    ) as AgentConfigPatch;
    onApply(patch);
    onClose();
  };

  return (
    <Modal show={show} onHide={onClose} size="lg" centered className="text-light swm">
      <Modal.Header closeButton className="border-secondary bg-dark text-light">
        <Modal.Title className="fs-6"><i className="bi bi-stars me-2" />Asistente de estrategia</Modal.Title>
      </Modal.Header>
      <Modal.Body className="bg-dark text-light">
        {!generated ? (
          <>
            <p className="swm-help small">Responde lo que quieras; cuantas más respuestas, más precisa será la propuesta. No se guarda nada hasta que tú lo decidas.</p>
            <div className="mb-4">
              <div className="swm-question">1. ¿A qué se dedica tu cuenta?</div>
              <HybridSelect options={WIZARD_OPTIONS.dedica} value={answers.dedica}
                onChange={v => setAnswers(p => ({ ...p, dedica: v }))} placeholder="Añadir otro..." />
            </div>
            <div className="mb-4">
              <div className="swm-question">2. ¿Qué tipo de contenido vas a publicar?</div>
              <HybridSelect options={WIZARD_OPTIONS.contenido} value={answers.contenido}
                onChange={v => setAnswers(p => ({ ...p, contenido: v }))} placeholder="Añadir otro tipo..." />
            </div>
            <div className="mb-4">
              <div className="swm-question">3. ¿Qué quieres conseguir con Instagram?</div>
              <HybridSelect options={WIZARD_OPTIONS.objetivo} value={answers.objetivo}
                onChange={v => setAnswers(p => ({ ...p, objetivo: v }))} placeholder="Añadir otro objetivo..." />
            </div>
            <div className="mb-2">
              <div className="swm-question">4. ¿Tienes cuentas referentes? (opcional)</div>
              <TagInput id="swm-refs" prefix="@" variant="info" max={MAX_REFERENCE_ACCOUNTS} values={answers.referentes}
                normalize={raw => raw.trim().replace(/^@/, '')}
                onChange={v => setAnswers(p => ({ ...p, referentes: v }))} placeholder="cuenta_referente" />
            </div>
          </>
        ) : (
          <>
            <p className="swm-help small">Marca los campos que quieres aplicar. Quedarán como cambios sin guardar en su pestaña.</p>
            <table className="table table-dark table-sm swm-table">
              <thead>
                <tr><th aria-label="Aplicar" /><th>Campo</th><th>Actual</th><th>Propuesto</th></tr>
              </thead>
              <tbody>
                {proposal.map(p => (
                  <tr key={p.field} className={p.changed ? '' : 'swm-same'}>
                    <td>
                      <input type="checkbox" className="form-check-input" aria-label={`Aplicar ${FIELD_LABELS[p.field] ?? p.field}`}
                        checked={selected.has(p.field)} onChange={() => toggle(p.field)} />
                    </td>
                    <td>{FIELD_LABELS[p.field] ?? p.field}</td>
                    <td className="swm-from">{formatValue(p.field, p.from)}</td>
                    <td className="swm-to">{formatValue(p.field, p.to)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {extraProposal}
          </>
        )}
        {error && <div className="alert alert-danger py-2 px-3 small mt-3 mb-0">{error}</div>}
      </Modal.Body>
      <Modal.Footer className="border-secondary bg-dark">
        {!generated ? (
          <Button variant="primary" size="sm" onClick={generate} disabled={generating}>
            {generating ? <><span className="spinner-border spinner-border-sm me-2" />Generando...</> : 'Generar propuesta'}
          </Button>
        ) : (
          <>
            <Button variant="outline-secondary" size="sm" onClick={() => setGenerated(null)}>Volver a las preguntas</Button>
            <Button variant="primary" size="sm" onClick={apply} disabled={selected.size === 0}>
              Aplicar seleccionados ({selected.size})
            </Button>
          </>
        )}
      </Modal.Footer>
    </Modal>
  );
};
