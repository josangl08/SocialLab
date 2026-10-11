import React, { useState } from 'react';
import { contentApi } from '../../api/content';
import { ApiError } from '../../api/client';
import type { ProspectCommentItem, StrategyMode } from '../../types';
import './ProspectComments.css';

export interface ProspectCommentsProps {
  accountId: number | null;
  strategyMode: StrategyMode;
}

export const ProspectComments: React.FC<ProspectCommentsProps> = ({ accountId, strategyMode }) => {
  const [open, setOpen] = useState(false);
  const [postText, setPostText] = useState('');
  const [suggestions, setSuggestions] = useState<ProspectCommentItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedType, setCopiedType] = useState<number | null>(null);

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await contentApi.generateProspectComments({
        target_post_text: postText.trim(),
        strategy_mode: strategyMode,
        ...(accountId ? { account_id: accountId } : {}),
      });
      setSuggestions(res.suggestions);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'No se pudieron generar los comentarios.');
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = async (item: ProspectCommentItem) => {
    try {
      await navigator.clipboard.writeText(item.text);
      setCopiedType(item.type);
      setTimeout(() => setCopiedType(null), 2000);
    } catch {
      // Portapapeles no disponible
    }
  };

  return (
    <div className="prospect-comments mt-4">
      <button
        type="button"
        className="prospect-comments-toggle"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span>
          <i className="bi bi-chat-quote me-2 text-primary"></i>Comentarios de prospección
        </span>
        <i className={`bi ${open ? 'bi-chevron-up' : 'bi-chevron-down'}`}></i>
      </button>

      {open && (
        <div className="prospect-comments-body">
          <label htmlFor="prospect-post-text" className="form-label text-secondary small">
            Pega el texto de una publicación de otra cuenta del sector:
          </label>
          <textarea
            id="prospect-post-text"
            className="form-control form-control-sm bg-dark text-light border-secondary"
            rows={4}
            maxLength={5000}
            value={postText}
            onChange={(e) => setPostText(e.target.value)}
          />
          <div className="d-flex justify-content-end mt-2">
            <button
              type="button"
              className="btn btn-sm btn-primary"
              onClick={handleGenerate}
              disabled={!postText.trim() || loading}
            >
              {loading ? (
                <span className="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>
              ) : (
                <i className="bi bi-magic me-1"></i>
              )}
              Sugerir comentarios
            </button>
          </div>
          {error && <div className="text-danger small mt-2" role="alert">{error}</div>}

          {suggestions.length > 0 && (
            <ul className="prospect-comments-list">
              {suggestions.map((item) => (
                <li key={item.type} className="prospect-comment-card">
                  <div className="d-flex justify-content-between align-items-center mb-1">
                    <span className="badge bg-secondary">{item.type_name}</span>
                    <button
                      type="button"
                      className="btn btn-sm prospect-copy-btn"
                      onClick={() => handleCopy(item)}
                      aria-label={`Copiar comentario ${item.type_name}`}
                    >
                      {copiedType === item.type ? (
                        <span className="text-success"><i className="bi bi-check-lg me-1"></i>Copiado</span>
                      ) : (
                        <><i className="bi bi-clipboard me-1"></i>Copiar</>
                      )}
                    </button>
                  </div>
                  <p className="mb-0 small">{item.text}</p>
                </li>
              ))}
            </ul>
          )}
          <small className="text-secondary d-block mt-2">
            Son sugerencias para copiar. Nada se publica de forma automática en Instagram.
          </small>
        </div>
      )}
    </div>
  );
};

export default ProspectComments;
