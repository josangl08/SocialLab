import React, { useEffect, useState } from 'react';

interface CalendarSlot {
  day: string;
  post_id: number | null;
  image_id: string | null;
  theme: string;
  caption: string;
}

interface ContentProposal {
  id: string;
  account_id: string;
  week_start: string;
  slots: CalendarSlot[];
  status: 'pending_approval' | 'approved' | 'rejected';
}

interface CalendarProposalViewProps {
  accountId: number;
}

export const CalendarProposalView: React.FC<CalendarProposalViewProps> = ({ accountId }) => {
  const [proposals, setProposals] = useState<ContentProposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem('authToken');
    fetch(`/api/agent/proposals?account_id=${accountId}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    })
      .then(r => r.json())
      .then(data => {
        setProposals(Array.isArray(data) ? data : []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [accountId]);

  const handleAction = async (proposalId: string, action: 'approve' | 'reject') => {
    setActionLoading(`${proposalId}-${action}`);
    const token = localStorage.getItem('authToken');

    setProposals(prev =>
      prev.map(p =>
        p.id === proposalId
          ? { ...p, status: action === 'approve' ? 'approved' : 'rejected' }
          : p
      )
    );

    try {
      await fetch(`/api/agent/proposals/${proposalId}/${action}`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
    } catch {
      // revert optimistic update on failure
      setProposals(prev =>
        prev.map(p => (p.id === proposalId ? { ...p, status: 'pending_approval' } : p))
      );
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="card shadow-sm mb-4">
        <div className="card-body text-center py-4">
          <div className="spinner-border text-primary spinner-border-sm" role="status" />
        </div>
      </div>
    );
  }

  if (proposals.length === 0) {
    return (
      <div className="card shadow-sm mb-4 bg-dark text-white border-secondary" data-testid="calendar-proposal-view">
        <div className="card-body text-center py-4">
          <p className="text-muted mb-0">No hay propuestas de contenido todavía. El agente generará una cada lunes.</p>
        </div>
      </div>
    );
  }

  const statusBadge = (status: ContentProposal['status']) => {
    if (status === 'approved') return <span className="badge bg-success">Aprobado</span>;
    if (status === 'rejected') return <span className="badge bg-danger">Rechazado</span>;
    return <span className="badge bg-warning text-dark">Pendiente</span>;
  };

  return (
    <div data-testid="calendar-proposal-view">
      {proposals.map(proposal => (
        <div key={proposal.id} className="card shadow-sm mb-4 bg-dark text-white border-secondary">
          <div className="card-header d-flex justify-content-between align-items-center border-secondary">
            <span className="fw-bold">
              Propuesta semanal: {proposal.week_start}
            </span>
            {statusBadge(proposal.status)}
          </div>
          <div className="card-body p-0">
            <ul className="list-group list-group-flush">
              {proposal.slots.map((slot, i) => (
                <li
                  key={i}
                  className="list-group-item bg-dark text-white border-secondary d-flex flex-column gap-1 py-3 px-3"
                >
                  <div className="d-flex justify-content-between align-items-start">
                    <span className="fw-semibold text-primary">{slot.day}</span>
                    <span className="badge bg-secondary">{slot.theme}</span>
                  </div>
                  <p className="mb-0 small text-light">{slot.caption}</p>
                </li>
              ))}
            </ul>
          </div>
          {proposal.status === 'pending_approval' && (
            <div className="card-footer border-secondary d-flex gap-2 justify-content-end">
              <button
                className="btn btn-sm btn-outline-danger"
                disabled={actionLoading !== null}
                onClick={() => handleAction(proposal.id, 'reject')}
              >
                {actionLoading === `${proposal.id}-reject` ? (
                  <span className="spinner-border spinner-border-sm me-1" />
                ) : null}
                Rechazar
              </button>
              <button
                className="btn btn-sm btn-success"
                disabled={actionLoading !== null}
                onClick={() => handleAction(proposal.id, 'approve')}
              >
                {actionLoading === `${proposal.id}-approve` ? (
                  <span className="spinner-border spinner-border-sm me-1" />
                ) : null}
                Aprobar Calendario ✅
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

export default CalendarProposalView;
