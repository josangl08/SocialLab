import React, { useState, useEffect } from 'react';
import { contentApi } from '../../api/content';
import type { SwipeFileResponse } from '../../types';
import './SwipeFile.css';

interface SwipeFileProps {
  accountId: number;
}

export const SwipeFile: React.FC<SwipeFileProps> = ({ accountId }) => {
  const [data, setData] = useState<SwipeFileResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);

    contentApi
      .getSwipeFile(accountId)
      .then((res) => {
        if (mounted) setData(res);
      })
      .catch((err) => {
        if (mounted) setError(err.message || 'Error cargando Swipe File');
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [accountId]);

  if (loading) {
    return (
      <div className="swipe-file-container text-center py-5">
        <div className="spinner-border text-primary" role="status"></div>
        <p className="mt-2 text-muted">Cargando Swipe File...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="swipe-file-container">
        <div className="alert alert-danger">{error}</div>
      </div>
    );
  }

  if (!data || data.items.length === 0) {
    return (
      <div className="swipe-file-container text-center py-5">
        <i className="bi bi-bookmark-star fs-1 text-muted"></i>
        <p className="mt-2 text-muted">No hay ganchos registrados en el Swipe File.</p>
      </div>
    );
  }

  return (
    <div className="swipe-file-container" data-testid="swipe-file-panel">
      <div className="swipe-file-header">
        <h4>Swipe File</h4>
        <p className="text-muted small">
          Ganchos con mejor Outlier Multiple clasificados por fórmula.
        </p>
      </div>

      {data.by_formula.length > 0 && (
        <div className="swipe-file-formula-badges" aria-label="Rendimiento por fórmula">
          {data.by_formula.map((f) => (
            <span key={f.formula_id} className="swipe-file-badge">
              {f.formula_name || `Fórmula ${f.formula_id}`} · {f.count} posts ·{' '}
              {f.avg_outlier != null ? `${f.avg_outlier}×` : '—'}
            </span>
          ))}
        </div>
      )}

      <table className="swipe-file-table">
        <thead>
          <tr>
            <th>Gancho</th>
            <th>Fórmula</th>
            <th>Outlier</th>
            <th>Sends/Reach</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((item) => (
            <tr key={item.post_id}>
              <td className="swipe-file-hook">
                {item.hook_text}
                {item.is_trial && (
                  <span className="swipe-file-trial">
                    Trial Reel
                    {item.reels_skip_rate != null && ` · salto 3 s: ${item.reels_skip_rate}%`}
                  </span>
                )}
              </td>
              <td className="text-muted small">{item.formula_name || 'Sin fórmula'}</td>
              <td>
                {item.outlier_multiple != null ? (
                  <span className="badge bg-primary">{item.outlier_multiple}×</span>
                ) : (
                  <span className="text-muted small">Datos insuficientes</span>
                )}
              </td>
              <td className="text-muted small">
                {item.sends_per_reach != null
                  ? `${(item.sends_per_reach * 100).toFixed(1)}%`
                  : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
