import React, { useState, useEffect } from 'react';
import { contentApi } from '../../api/content';
import type {
  CommentTriageItem,
  CommentTriageSource,
  CommentTriageUnavailableReason,
  StrategyMode,
} from '../../types';
import './CommentTriage.css';

interface CommentTriageProps {
  postId: number;
  strategyMode?: StrategyMode;
}

const UNAVAILABLE_MESSAGES: Record<CommentTriageUnavailableReason, string> = {
  not_published: 'Este post aún no está publicado en Instagram, así que no tiene comentarios que leer.',
  story: 'Las Stories no tienen comentarios en Instagram: las respuestas llegan como mensajes directos.',
  collaboration: 'Este post es una colaboración publicada desde otra cuenta: Instagram solo deja leer los comentarios de los posts propios.',
  api_error: 'No se pudieron leer los comentarios de Instagram. Si vuelve a pasar, reconecta la cuenta desde Cuentas.',
};

const LABEL_LABELS: Record<string, { text: string; className: string }> = {
  lead:      { text: 'Lead',      className: 'triage-badge-lead' },
  question:  { text: 'Pregunta',  className: 'triage-badge-question' },
  objection: { text: 'Objeción',  className: 'triage-badge-objection' },
  support:   { text: 'Soporte',   className: 'triage-badge-support' },
  noise:     { text: 'Ruido',     className: 'triage-badge-noise' },
};

export const CommentTriage: React.FC<CommentTriageProps> = ({ postId, strategyMode }) => {
  const [source, setSource] = useState<CommentTriageSource | null>(null);
  const [unavailableReason, setUnavailableReason] = useState<CommentTriageUnavailableReason>('api_error');
  const [comments, setComments] = useState<CommentTriageItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Manual paste state
  const [showManualPaste, setShowManualPaste] = useState<boolean>(false);
  const [manualInput, setManualInput] = useState<string>('');
  const [manualLoading, setManualLoading] = useState<boolean>(false);

  // Copy feedback tracking
  const [copiedId, setCopiedId] = useState<string | number | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);

    contentApi
      .getCommentsTriage(postId)
      .then((res) => {
        if (!mounted) return;
        setSource(res.source);
        setComments(res.comments || []);
        setUnavailableReason(res.unavailable_reason ?? 'api_error');
        if (res.source === 'unavailable') {
          setShowManualPaste(true);
        }
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : 'Error cargando comentarios');
        setSource('unavailable');
        setShowManualPaste(true);
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [postId]);

  const handleCopy = async (item: CommentTriageItem) => {
    try {
      await navigator.clipboard.writeText(item.suggested_reply);
      setCopiedId(item.id);
      setTimeout(() => {
        setCopiedId(null);
      }, 2000);
    } catch {
      // Fallback si falla el portapapeles
    }
  };

  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const lines = manualInput
      .split('\n')
      .map((l) => l.trim())
      .filter(Boolean);

    if (lines.length === 0) return;

    setManualLoading(true);
    setError(null);
    try {
      const res = await contentApi.triageManualComments({
        comments: lines,
        strategy_mode: strategyMode,
      });
      setSource(res.source);
      setComments(res.comments);
      setShowManualPaste(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error analizando comentarios pegados');
    } finally {
      setManualLoading(false);
    }
  };

  return (
    <div className="comment-triage-container" data-testid="comment-triage-panel">
      <div className="comment-triage-header">
        <div className="d-flex justify-content-between align-items-center">
          <h5 className="mb-0">
            <i className="bi bi-chat-left-text me-2"></i>Triaje de Comentarios
          </h5>
          {source !== 'unavailable' && (
            <button
              type="button"
              className="btn btn-sm btn-outline-secondary"
              onClick={() => setShowManualPaste(!showManualPaste)}
            >
              {showManualPaste ? 'Ver comentarios API' : 'Pegar manualmente'}
            </button>
          )}
        </div>
        <p className="triage-disclaimer text-muted small mt-1 mb-0">
          <i className="bi bi-shield-check me-1"></i>
          Las respuestas son sugerencias. Nada se publica de forma automática en Instagram.
        </p>
      </div>

      {error && <div className="alert alert-danger py-2 mt-2">{error}</div>}

      {loading && (
        <div className="text-center py-4">
          <div className="spinner-border spinner-border-sm text-primary" role="status"></div>
          <p className="small text-muted mt-2">Consultando comentarios...</p>
        </div>
      )}

      {!loading && source === 'unavailable' && (
        <div className="alert alert-warning py-2 mt-3" data-testid="unavailable-notice">
          <i className="bi bi-exclamation-triangle me-1"></i>
          {UNAVAILABLE_MESSAGES[unavailableReason]} Puedes pegar los comentarios manualmente para
          analizarlos.
        </div>
      )}

      {!loading && (showManualPaste || source === 'unavailable') && (
        <form onSubmit={handleManualSubmit} className="triage-manual-form mt-3">
          <label className="form-label small fw-semibold">
            Pegar comentarios para analizar (uno por línea):
          </label>
          <textarea
            className="form-control triage-textarea"
            rows={4}
            placeholder="¿Cuánto cuesta el servicio?&#10;Excelente publicación, muy útil&#10;Me interesa contratarlo..."
            value={manualInput}
            onChange={(e) => setManualInput(e.target.value)}
          />
          <div className="d-flex justify-content-end mt-2">
            <button
              type="submit"
              className="btn btn-primary btn-sm"
              disabled={manualLoading || !manualInput.trim()}
            >
              {manualLoading ? (
                <>
                  <span className="spinner-border spinner-border-sm me-1" role="status"></span>
                  Analizando...
                </>
              ) : (
                <>
                  <i className="bi bi-magic me-1"></i>Analizar comentarios
                </>
              )}
            </button>
          </div>
        </form>
      )}

      {!loading && !showManualPaste && comments.length === 0 && (
        <div className="text-center py-4 text-muted">
          <i className="bi bi-chat-square-dots fs-3"></i>
          <p className="small mt-2">No se encontraron comentarios en esta publicación.</p>
        </div>
      )}

      {!loading && !showManualPaste && comments.length > 0 && (
        <div className="triage-comments-list mt-3">
          {comments.map((item) => {
            const badgeMeta = LABEL_LABELS[item.label] || {
              text: item.label,
              className: 'triage-badge-default',
            };
            const isCopied = copiedId === item.id;

            return (
              <div key={item.id} className="triage-item-card" data-testid="triage-item">
                <div className="d-flex justify-content-between align-items-start mb-1">
                  <div className="d-flex align-items-center gap-2">
                    {item.username && (
                      <span className="triage-username">@{item.username}</span>
                    )}
                    <span className={`triage-badge ${badgeMeta.className}`}>
                      {badgeMeta.text}
                    </span>
                  </div>
                </div>

                <p className="triage-comment-text mb-2">{item.text}</p>

                <div className="triage-reply-box">
                  <div className="d-flex justify-content-between align-items-center mb-1">
                    <span className="triage-reply-label">Respuesta sugerida:</span>
                    <button
                      type="button"
                      className="btn btn-sm triage-copy-btn"
                      onClick={() => handleCopy(item)}
                      aria-label="Copiar respuesta sugerida"
                    >
                      {isCopied ? (
                        <>
                          <i className="bi bi-check-lg text-success me-1"></i>
                          <span className="text-success">Copiado</span>
                        </>
                      ) : (
                        <>
                          <i className="bi bi-clipboard me-1"></i>Copiar
                        </>
                      )}
                    </button>
                  </div>
                  <p className="triage-reply-text mb-0">{item.suggested_reply}</p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default CommentTriage;
