import React from 'react';
import { Modal, Button } from 'react-bootstrap';
import type { AgentStrategyConfig } from '../../types';
import { FIELD_LABELS, formatValue, presetChanges } from './strategyOptions';
import './AccountTypeChangeModal.css';

interface AccountTypeChangeModalProps {
  show: boolean;
  newType: AgentStrategyConfig['account_type'];
  current: AgentStrategyConfig;
  onApplyPreset: () => void;
  onTypeOnly: () => void;
  onCancel: () => void;
}

export const AccountTypeChangeModal: React.FC<AccountTypeChangeModalProps> = ({
  show, newType, current, onApplyPreset, onTypeOnly, onCancel,
}) => {
  const changes = presetChanges(current, newType);
  const typeLabel = newType === 'professional' ? 'profesional' : 'personal';

  return (
    <Modal show={show} onHide={onCancel} centered className="text-light atc-modal">
      <Modal.Header closeButton className="border-secondary bg-dark text-light">
        <Modal.Title className="fs-6">Cambiar a cuenta {typeLabel}</Modal.Title>
      </Modal.Header>
      <Modal.Body className="bg-dark text-light">
        {changes.length === 0 ? (
          <p className="small mb-0">El preset {typeLabel} coincide con tu configuración actual.</p>
        ) : (
          <>
            <p className="small atc-intro">El preset {typeLabel} cambiaría estos campos:</p>
            <table className="table table-dark table-sm atc-table mb-2">
              <thead>
                <tr><th>Campo</th><th>Actual</th><th>Preset</th></tr>
              </thead>
              <tbody>
                {changes.map(c => (
                  <tr key={c.field}>
                    <td>{FIELD_LABELS[c.field] ?? c.field}</td>
                    <td className="atc-from">{formatValue(c.field, c.from)}</td>
                    <td className="atc-to">{formatValue(c.field, c.to)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="small atc-note mb-0">Los campos de Publicación quedarán como cambios sin guardar en su pestaña.</p>
          </>
        )}
      </Modal.Body>
      <Modal.Footer className="border-secondary bg-dark">
        <Button variant="outline-secondary" size="sm" onClick={onTypeOnly}>Solo cambiar el tipo</Button>
        <Button variant="primary" size="sm" onClick={onApplyPreset} disabled={changes.length === 0}>Aplicar preset</Button>
      </Modal.Footer>
    </Modal>
  );
};
