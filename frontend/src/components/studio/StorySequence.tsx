import React, { useState } from 'react';
import { contentApi } from '../../api/content';
import { ApiError } from '../../api/client';
import type { StoryFrame, StoryStickerType } from '../../types';
import './StorySequence.css';

const STICKER_LABELS: Record<StoryStickerType, string> = {
  poll: 'Encuesta',
  question: 'Caja de preguntas',
  link: 'Enlace',
  dm_cta: 'Llamada al DM',
  none: 'Sin sticker',
};

export interface StorySequenceProps {
  accountId: number | null;
}

const payloadSummary = (payload: StoryFrame['sticker_payload']): string | null => {
  if (!payload) return null;
  const question = typeof payload.question === 'string' ? payload.question : null;
  const options = Array.isArray(payload.options) ? payload.options.map(String).join(' / ') : null;
  return [question, options].filter(Boolean).join(' · ') || null;
};

export const StorySequence: React.FC<StorySequenceProps> = ({ accountId }) => {
  const [topic, setTopic] = useState('');
  const [frames, setFrames] = useState<StoryFrame[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    if (!accountId) return;
    setLoading(true);
    setError(null);
    try {
      // Sin strategy_mode: el backend usa la estrategia de la campaña del mes
      const result = await contentApi.generateStory({ account_id: accountId, topic: topic.trim() || undefined });
      setFrames(result.frames);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'No se pudieron generar las Stories.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="story-sequence">
      <div className="story-sequence-form">
        <input
          type="text"
          className="form-control form-control-sm bg-dark text-light border-secondary"
          placeholder="Tema del día (opcional)"
          aria-label="Tema de las Stories"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
        />
        <button type="button" className="btn btn-sm btn-primary text-nowrap" onClick={handleGenerate} disabled={!accountId || loading}>
          {loading ? (
            <span className="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>
          ) : (
            <i className="bi bi-phone me-1"></i>
          )}
          Generar Stories del día
        </button>
      </div>
      {!accountId && <small className="text-secondary d-block mt-2">Conecta una cuenta de Instagram para generar Stories.</small>}
      {error && <div className="text-danger small mt-2" role="alert">{error}</div>}

      {frames.length > 0 && (
        <ol className="story-frames list-unstyled" aria-label="Secuencia de Stories">
          {frames.map((frame) => {
            const summary = payloadSummary(frame.sticker_payload);
            return (
              <li key={frame.index} className="story-frame">
                <div className="story-frame-head">
                  <span className="story-frame-index">{frame.index}</span>
                  <span className={`badge story-sticker story-sticker-${frame.sticker}`}>{STICKER_LABELS[frame.sticker]}</span>
                </div>
                <p className="story-frame-text">{frame.text}</p>
                {summary && <p className="story-frame-payload">{summary}</p>}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
};

export default StorySequence;
