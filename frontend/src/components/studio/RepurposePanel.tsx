import React, { useState } from 'react';
import { contentApi } from '../../api/content';
import { ApiError } from '../../api/client';
import type { CarouselOut, ReelOut, RepurposeOut, StrategyMode } from '../../types';
import './RepurposePanel.css';

export const MAX_TRANSCRIPT_CHARS = 30000;

export type RepurposePiece =
  | { kind: 'reel'; reel: ReelOut }
  | { kind: 'carousel'; carousel: CarouselOut };

export interface RepurposePanelProps {
  accountId: number | null;
  strategyMode: StrategyMode;
  onOpenPiece: (piece: RepurposePiece) => void;
}

export const RepurposePanel: React.FC<RepurposePanelProps> = ({ accountId, strategyMode, onOpenPiece }) => {
  const [transcript, setTranscript] = useState('');
  const [result, setResult] = useState<RepurposeOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const tooLong = transcript.length > MAX_TRANSCRIPT_CHARS;
  const canGenerate = Boolean(accountId) && transcript.trim().length > 0 && !tooLong && !loading;

  const handleGenerate = async () => {
    if (!accountId) return;
    setLoading(true);
    setError(null);
    try {
      setResult(await contentApi.generateRepurpose({ account_id: accountId, transcript, strategy_mode: strategyMode }));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'No se pudo reciclar el contenido.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="repurpose-panel mb-4">
      <label htmlFor="repurpose-transcript" className="form-label text-secondary small d-block">
        <i className="bi bi-recycle me-1 text-primary"></i>Transcripción o texto largo
      </label>
      <textarea
        id="repurpose-transcript"
        className="form-control bg-dark text-light border-secondary"
        rows={6}
        value={transcript}
        onChange={(e) => setTranscript(e.target.value)}
        placeholder="Pega aquí la transcripción de un podcast, vídeo o artículo..."
      />
      <div className="d-flex justify-content-between align-items-center mt-2">
        <span className={`small ${tooLong ? 'text-danger' : 'text-secondary'}`} data-testid="transcript-count">
          {transcript.length.toLocaleString('es-ES')} / {MAX_TRANSCRIPT_CHARS.toLocaleString('es-ES')}
          {tooLong && ' · Acorta el texto para poder reciclarlo'}
        </span>
        <button type="button" className="btn btn-sm btn-primary" onClick={handleGenerate} disabled={!canGenerate}>
          {loading ? (
            <span className="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>
          ) : (
            <i className="bi bi-magic me-1"></i>
          )}
          Generar 5 piezas
        </button>
      </div>
      {!accountId && <small className="text-secondary d-block mt-1">Selecciona una cuenta para reciclar.</small>}
      {error && <div className="text-danger small mt-2" role="alert">{error}</div>}

      {result && (
        <ul className="repurpose-pieces list-unstyled mt-3 mb-0" aria-label="Piezas recicladas">
          {result.reels.map((reel, idx) => (
            <li key={`reel-${idx}`} className="repurpose-piece">
              <span className="badge bg-primary me-2">Reel {idx + 1}</span>
              <span className="repurpose-piece-text">{reel.hooks[0]?.text || reel.caption}</span>
              <button
                type="button"
                className="btn btn-sm btn-outline-light ms-auto"
                onClick={() => onOpenPiece({ kind: 'reel', reel })}
                aria-label={`Abrir Reel ${idx + 1}`}
              >
                Abrir
              </button>
            </li>
          ))}
          {result.carousels.map((carousel, idx) => (
            <li key={`carousel-${idx}`} className="repurpose-piece">
              <span className="badge bg-info text-dark me-2">Carrusel {idx + 1}</span>
              <span className="repurpose-piece-text">{carousel.slides[0]?.text || carousel.caption}</span>
              <button
                type="button"
                className="btn btn-sm btn-outline-light ms-auto"
                onClick={() => onOpenPiece({ kind: 'carousel', carousel })}
                aria-label={`Abrir Carrusel ${idx + 1}`}
              >
                Abrir
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default RepurposePanel;
