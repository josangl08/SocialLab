import React, { useState, useEffect } from 'react';
import { RadialBarChart, RadialBar, PolarAngleAxis } from 'recharts';
import { contentApi } from '../../api/content';
import type { ProfileAuditResponse } from '../../types';
import './ProfileAudit.css';

interface ProfileAuditProps {
  accountId: number;
  isOpen: boolean;
  onClose: () => void;
}

export const ProfileAudit: React.FC<ProfileAuditProps> = ({ accountId, isOpen, onClose }) => {
  const [loading, setLoading] = useState<boolean>(false);
  const [data, setData] = useState<ProfileAuditResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;

    let mounted = true;
    setLoading(true);
    setError(null);

    contentApi
      .auditProfile({ account_id: accountId })
      .then((res) => {
        if (mounted) setData(res);
      })
      .catch((err) => {
        if (mounted) setError(err.message || 'Error al auditar perfil');
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [isOpen, accountId]);

  if (!isOpen) return null;

  return (
    <div className="profile-audit-modal" data-testid="profile-audit-modal">
      <div className="profile-audit-card">
        <div className="profile-audit-header">
          <h4 className="m-0">
            <i className="bi bi-shield-check me-2"></i>Auditoría de Perfil
          </h4>
          <button
            type="button"
            className="btn-close btn-close-white"
            aria-label="Cerrar"
            onClick={onClose}
          ></button>
        </div>

        {loading && (
          <div className="text-center py-4">
            <div className="spinner-border text-primary" role="status"></div>
            <p className="mt-2 text-muted">Evaluando perfil frente a la rúbrica...</p>
          </div>
        )}

        {error && (
          <div className="alert alert-danger" role="alert">
            {error}
          </div>
        )}

        {data && !loading && (
          <div>
            <div className="profile-audit-score">
              <div className="profile-audit-gauge">
                <RadialBarChart
                  width={160}
                  height={160}
                  innerRadius="78%"
                  outerRadius="100%"
                  data={[{ value: data.score }]}
                  startAngle={90}
                  endAngle={-270}
                >
                  <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
                  <RadialBar dataKey="value" cornerRadius={8} background fill="#6366f1" />
                </RadialBarChart>
                <div className="profile-audit-score-num">{data.score}/100</div>
              </div>
              <p className="text-muted">Puntuación de optimización del perfil</p>
            </div>

            <h6 className="mt-3">Puntos de la rúbrica ({(data.items ?? []).length})</h6>
            <ul className="profile-audit-items">
              {(data.items ?? []).map((item) => (
                <li key={item.id} className="profile-audit-item">
                  <i
                    className={`bi ${
                      item.passed
                        ? 'bi-check-circle-fill profile-audit-item-passed'
                        : 'bi-x-circle-fill profile-audit-item-failed'
                    }`}
                  ></i>
                  <div className="flex-grow-1">
                    <div className="d-flex justify-content-between">
                      <span style={{ fontWeight: 600 }}>{item.label}</span>
                      <small className="text-muted">{item.weight} pts</small>
                    </div>
                    {!item.passed && item.tip && (
                      <small className="text-warning d-block mt-1">{item.tip}</small>
                    )}
                  </div>
                </li>
              ))}
            </ul>

            {data.bio_rewrite && (
              <div className="profile-audit-bio-box">
                <div className="d-flex justify-content-between align-items-center mb-1">
                  <strong>Bio sugerida</strong>
                  <button
                    className="btn btn-sm btn-outline-light"
                    onClick={() => navigator.clipboard.writeText(data.bio_rewrite || '')}
                  >
                    Copiar
                  </button>
                </div>
                <p className="small mb-0" style={{ whiteSpace: 'pre-wrap' }}>
                  {data.bio_rewrite}
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
