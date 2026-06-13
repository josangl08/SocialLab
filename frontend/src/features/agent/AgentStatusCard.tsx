import React, { useEffect, useState } from 'react';

interface AgentStatus {
  last_run_at: string | null;
  images_scanned: number;
  images_analyzed: number;
  posts_drafted: number;
}

interface AgentStatusCardProps {
  accountId: number;
}

export const AgentStatusCard: React.FC<AgentStatusCardProps> = ({ accountId }) => {
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [countdown, setCountdown] = useState<string>('');

  useEffect(() => {
    const fetchAgentStatus = async () => {
      const token = localStorage.getItem('authToken');
      if (!token) return;

      try {
        const res = await fetch(`http://localhost:8000/api/agent/proposals?account_id=${accountId}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
          const proposals = await res.json();
          if (proposals.length > 0) {
            const latest = proposals[0];
            setStatus({
              last_run_at: latest.created_at || new Date().toISOString(),
              images_scanned: latest.slots?.length || 0,
              images_analyzed: latest.slots?.length || 0,
              posts_drafted: latest.slots?.length || 0
            });
          }
        }
      } catch (err) {
        console.error('Error fetching agent status:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchAgentStatus();
  }, [accountId]);

  useEffect(() => {
    const calculateCountdown = () => {
      const now = new Date();
      const nextMonday = new Date();
      nextMonday.setUTCDate(now.getUTCDate() + ((1 + 7 - now.getUTCDay()) % 7 || 7));
      nextMonday.setUTCHours(8, 0, 0, 0);

      if (nextMonday.getTime() <= now.getTime()) {
        nextMonday.setUTCDate(nextMonday.getUTCDate() + 7);
      }

      const diffMs = nextMonday.getTime() - now.getTime();
      const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
      const diffHours = Math.floor((diffMs % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
      const diffMins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));

      setCountdown(`${diffDays}d ${diffHours}h ${diffMins}m`);
    };

    calculateCountdown();
    const timer = setInterval(calculateCountdown, 60000);
    return () => clearInterval(timer);
  }, []);

  if (loading) {
    return (
      <div className="card shadow-sm mb-4">
        <div className="card-body text-center py-4">
          <div className="spinner-border text-primary spinner-border-sm" role="status"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="card shadow-sm mb-4 bg-dark text-white border-secondary" data-testid="agent-status-card">
      <div className="card-body">
        <h5 className="card-title fw-bold mb-3 d-flex align-items-center justify-content-between">
          <span><i className="bi bi-robot text-primary me-2"></i>Estado del Agente</span>
          <span className="badge bg-primary small">Activo</span>
        </h5>
        
        <div className="row text-center g-2 my-2">
          <div className="col-4">
            <div className="p-2 bg-secondary bg-opacity-25 rounded">
              <small className="text-muted d-block small">Escaneadas</small>
              <span className="fw-bold fs-5">{status?.images_scanned || 0}</span>
            </div>
          </div>
          <div className="col-4">
            <div className="p-2 bg-secondary bg-opacity-25 rounded">
              <small className="text-muted d-block small">Redactados</small>
              <span className="fw-bold fs-5">{status?.posts_drafted || 0}</span>
            </div>
          </div>
          <div className="col-4">
            <div className="p-2 bg-secondary bg-opacity-25 rounded">
              <small className="text-muted d-block small">Siguiente Ejecución</small>
              <span className="fw-bold fs-6 d-block text-warning" style={{ marginTop: '4px' }}>{countdown}</span>
            </div>
          </div>
        </div>

        {status?.last_run_at && (
          <div className="mt-3 pt-2 border-top border-secondary text-muted small">
            <i className="bi bi-clock-history me-1"></i>
            Última ejecución: {new Date(status.last_run_at).toLocaleDateString('es-ES', {
              day: 'numeric',
              month: 'short',
              hour: '2-digit',
              minute: '2-digit'
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default AgentStatusCard;
