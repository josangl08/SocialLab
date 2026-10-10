import React, { useState } from 'react';
import { contentApi } from '../../api/content';
import { ApiError } from '../../api/client';
import type { StrategyMode } from '../../types';
import type { RepurposePiece } from './RepurposePanel';
import './IdeaGenerator.css';

export interface IdeaGeneratorProps {
  accountId: number | null;
  format: 'reel' | 'carousel';
  strategyMode: StrategyMode;
  onGenerated: (piece: RepurposePiece) => void;
}

export const IdeaGenerator: React.FC<IdeaGeneratorProps> = ({ accountId, format, strategyMode, onGenerated }) => {
  const [topic, setTopic] = useState('');
  const [slides, setSlides] = useState(7);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    if (!accountId) return;
    setLoading(true);
    setError(null);
    try {
      const base = { account_id: accountId, topic: topic.trim(), strategy_mode: strategyMode };
      if (format === 'reel') {
        onGenerated({ kind: 'reel', reel: await contentApi.generateReel(base) });
      } else {
        onGenerated({ kind: 'carousel', carousel: await contentApi.generateCarousel({ ...base, slides }) });
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'No se pudo generar el contenido.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="idea-generator mb-4">
      <label htmlFor="idea-topic" className="form-label text-secondary small d-block">
        <i className="bi bi-lightbulb me-1 text-primary"></i>
        Tema del {format === 'reel' ? 'Reel' : 'carrusel'}
      </label>
      <div className="idea-generator-row">
        <input
          id="idea-topic"
          type="text"
          className="form-control form-control-sm bg-dark text-light border-secondary"
          placeholder="¿Sobre qué quieres hablar?"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
        />
        {format === 'carousel' && (
          <select
            className="form-select form-select-sm bg-dark text-light border-secondary idea-generator-slides"
            aria-label="Número de diapositivas"
            value={slides}
            onChange={(e) => setSlides(Number(e.target.value))}
          >
            {[6, 7, 8, 9, 10].map((n) => (
              <option key={n} value={n}>{n} diapositivas</option>
            ))}
          </select>
        )}
        <button
          type="button"
          className="btn btn-sm btn-primary text-nowrap"
          onClick={handleGenerate}
          disabled={!accountId || !topic.trim() || loading}
        >
          {loading ? (
            <span className="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>
          ) : (
            <i className="bi bi-magic me-1"></i>
          )}
          Generar con IA
        </button>
      </div>
      {!accountId && <small className="text-secondary d-block mt-1">Selecciona una cuenta para generar.</small>}
      {error && <div className="text-danger small mt-2" role="alert">{error}</div>}
    </div>
  );
};

export default IdeaGenerator;
