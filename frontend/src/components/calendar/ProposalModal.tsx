import React, { useState } from 'react';
import { Modal, Button, Badge, Spinner, Alert } from 'react-bootstrap';
import { useAuth } from '../../context/AuthContext';
import { apiClient, ApiError } from '../../api/client';
import type { ContentProposal } from '../../types';

interface ProposalModalProps {
  show: boolean;
  onHide: () => void;
  proposal: ContentProposal | null;
  onActionSuccess: (proposalId: string, status: 'approved' | 'rejected') => void;
}

const ProposalModal: React.FC<ProposalModalProps> = ({
  show,
  onHide,
  proposal,
  onActionSuccess,
}) => {
  const { token } = useAuth();
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  if (!proposal) {
    return null;
  }

  const handleAction = async (action: 'approve' | 'reject') => {
    if (!token) {
      setError('No hay token de autenticación disponible.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await apiClient.post(`/api/agent/proposals/${proposal.id}/${action}`);
      onActionSuccess(proposal.id, action === 'approve' ? 'approved' : 'rejected');
      onHide();
    } catch (err) {
      setError(err instanceof ApiError
        ? `Error al procesar la propuesta: ${err.detail}`
        : 'Error de red o servidor');
    } finally {
      setLoading(false);
    }
  };

  const getPostTypeBadgeBg = (type?: string) => {
    switch (type?.toLowerCase()) {
      case 'reel':
        return 'danger';
      case 'carousel':
        return 'primary';
      case 'story':
        return 'warning';
      default:
        return 'success';
    }
  };

  return (
    <Modal show={show} onHide={onHide} size="lg" centered className="text-light">
      <Modal.Header closeButton className="border-secondary bg-dark text-light">
        <Modal.Title>
          Propuesta de Contenido AI — Semana {proposal.week_start}
        </Modal.Title>
      </Modal.Header>
      <Modal.Body className="bg-dark text-light">
        {error && (
          <Alert variant="danger" className="mb-3 border-danger bg-danger bg-opacity-10 text-danger">
            {error}
          </Alert>
        )}

        <div className="mb-4">
          <p className="text-muted mb-2">
            El asistente AI ha programado los siguientes slots para esta semana:
          </p>
          <div className="list-group list-group-flush border-0">
            {proposal.slots && proposal.slots.length > 0 ? (
              proposal.slots.map((slot, index) => (
                <div
                  key={index}
                  className="list-group-item bg-dark text-light border-secondary px-0 py-3 d-flex align-items-start"
                >
                  <div className="me-3">
                    <Badge bg="secondary" className="px-2 py-1 text-uppercase">
                      {slot.day}
                    </Badge>
                  </div>
                  <div className="flex-grow-1">
                    <div className="d-flex align-items-center mb-1">
                      <h6 className="mb-0 me-2 text-info">{slot.theme}</h6>
                      {slot.post_type && (
                        <Badge bg={getPostTypeBadgeBg(slot.post_type)} className="text-uppercase" style={{ fontSize: '0.7em' }}>
                          {slot.post_type}
                        </Badge>
                      )}
                    </div>
                    <p className="mb-0 text-muted small" style={{ whiteSpace: 'pre-line' }}>
                      {slot.caption}
                    </p>
                  </div>
                </div>
              ))
            ) : (
              <p className="text-center text-muted py-3">No hay slots definidos para esta propuesta.</p>
            )}
          </div>
        </div>
      </Modal.Body>
      <Modal.Footer className="border-secondary bg-dark">
        <Button variant="secondary" onClick={onHide} disabled={loading}>
          Cancelar
        </Button>
        <Button
          variant="outline-danger"
          onClick={() => handleAction('reject')}
          disabled={loading}
          className="me-2"
        >
          {loading ? <Spinner size="sm" animation="border" className="me-1" /> : null}
          Rechazar
        </Button>
        <Button
          variant="primary"
          onClick={() => handleAction('approve')}
          disabled={loading}
          style={{ backgroundColor: '#667eea', borderColor: '#667eea' }}
        >
          {loading ? <Spinner size="sm" animation="border" className="me-1" /> : null}
          Aprobar
        </Button>
      </Modal.Footer>
    </Modal>
  );
};

export default ProposalModal;
