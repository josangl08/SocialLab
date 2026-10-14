import React, { useState, useEffect } from 'react';
import { contentApi } from '../../api/content';
import type { HookFormula, StrategyMode, ContentFormat } from '../../types';
import ScheduleZoneHint from '../posts/ScheduleZoneHint';
import { browserTimezone, fromDatetimeLocalValue } from '../../utils/timezone';
import './FormatEditor.css';

export interface SavePostPayload {
  status: 'draft' | 'scheduled';
  scheduledAt?: string | null;
  notifyTelegram: boolean;
  /** Trial Reel (AD-10): solo se envía en Reels */
  trialGraduation?: TrialGraduation | null;
}

export type TrialGraduation = 'MANUAL' | 'SS_PERFORMANCE';

export interface FormatEditorProps {
  format: Exclude<ContentFormat, 'story'>;
  onFormatChange: (format: Exclude<ContentFormat, 'story'>) => void;
  caption: string;
  onCaptionChange: (caption: string) => void;
  mediaFile: File | null;
  onMediaFileChange: (file: File | null) => void;
  mediaUrl: string | null;
  scheduledAt: string;
  onScheduledAtChange: (date: string) => void;
  /** Zona en la que se lee el campo de fecha (la de la cuenta; por defecto, la del navegador) */
  timezone?: string;
  secondaryTimezone?: string | null;
  strategyMode: StrategyMode;
  hasTelegram: boolean;
  onSave: (payload: SavePostPayload) => Promise<void>;
  loading?: boolean;
}

export const FormatEditor: React.FC<FormatEditorProps> = ({
  format,
  onFormatChange,
  caption,
  onCaptionChange,
  mediaFile,
  onMediaFileChange,
  mediaUrl,
  scheduledAt,
  onScheduledAtChange,
  timezone,
  secondaryTimezone,
  strategyMode,
  hasTelegram,
  onSave,
  loading = false,
}) => {
  const tz = timezone ?? browserTimezone();
  const [formulas, setFormulas] = useState<HookFormula[]>([]);
  const [selectedFormulaId, setSelectedFormulaId] = useState<string>('');
  const [mediaPreview, setMediaPreview] = useState<string | null>(mediaUrl);
  const [scheduleError, setScheduleError] = useState<string | null>(null);
  const [trialEnabled, setTrialEnabled] = useState(false);
  const [trialGraduation, setTrialGraduation] = useState<TrialGraduation>('MANUAL');
  const trialPayload = format === 'reel' && trialEnabled ? trialGraduation : null;

  useEffect(() => {
    contentApi
      .getHookFormulas(strategyMode)
      .then(setFormulas)
      .catch(() => {});
  }, [strategyMode]);

  useEffect(() => {
    if (mediaFile) {
      const reader = new FileReader();
      reader.onloadend = () => setMediaPreview(reader.result as string);
      reader.readAsDataURL(mediaFile);
    } else {
      setMediaPreview(mediaUrl);
    }
  }, [mediaFile, mediaUrl]);

  const handleApplyHook = (formulaIdStr: string) => {
    setSelectedFormulaId(formulaIdStr);
    if (!formulaIdStr) return;
    const formula = formulas.find((f) => String(f.id) === formulaIdStr);
    if (!formula) return;

    if (!caption || caption.trim() === '') {
      onCaptionChange(formula.template);
    } else {
      const lines = caption.split('\n');
      lines[0] = formula.template;
      onCaptionChange(lines.join('\n'));
    }
  };

  const handleScheduleClick = () => {
    setScheduleError(null);
    if (!scheduledAt) {
      setScheduleError('Por favor selecciona una fecha y hora futura para programar.');
      return;
    }
    const schedDate = new Date(fromDatetimeLocalValue(scheduledAt, tz));
    if (isNaN(schedDate.getTime()) || schedDate <= new Date()) {
      setScheduleError('La fecha programada debe ser en el futuro.');
      return;
    }
    if (!mediaFile && !mediaUrl) {
      setScheduleError('Añade una imagen o vídeo para poder programar la publicación.');
      return;
    }

    onSave({
      status: 'scheduled',
      scheduledAt: schedDate.toISOString(),
      notifyTelegram: false,
      trialGraduation: trialPayload,
    });
  };

  const handleDraftClick = () => {
    setScheduleError(null);
    onSave({
      status: 'draft',
      scheduledAt: scheduledAt ? fromDatetimeLocalValue(scheduledAt, tz) : null,
      notifyTelegram: false,
      trialGraduation: trialPayload,
    });
  };

  const handleReviewClick = () => {
    setScheduleError(null);
    onSave({
      status: 'draft',
      scheduledAt: scheduledAt ? fromDatetimeLocalValue(scheduledAt, tz) : null,
      notifyTelegram: true,
      trialGraduation: trialPayload,
    });
  };

  return (
    <div className="format-editor">
      {/* Selector de formato */}
      <div className="mb-3">
        <label className="form-label text-secondary small d-block">
          <i className="bi bi-grid me-1 text-primary"></i>Formato de publicación
        </label>
        <div className="format-radios d-flex gap-2">
          <button
            type="button"
            className={`format-radio-btn ${format === 'post' ? 'active' : ''}`}
            onClick={() => onFormatChange('post')}
          >
            <i className="bi bi-image me-1"></i>
            Post
          </button>
          <button
            type="button"
            className={`format-radio-btn ${format === 'reel' ? 'active' : ''}`}
            onClick={() => onFormatChange('reel')}
          >
            <i className="bi bi-camera-video me-1"></i>
            Reel
          </button>
          <button
            type="button"
            className={`format-radio-btn ${format === 'carousel' ? 'active' : ''}`}
            onClick={() => onFormatChange('carousel')}
          >
            <i className="bi bi-collection me-1"></i>
            Carrusel
          </button>
        </div>
      </div>

      {/* Catálogo de Ganchos (HookPicker) */}
      <div className="mb-3">
        <label htmlFor="hook-formula-select" className="form-label text-secondary small d-block">
          <i className="bi bi-lightning-charge me-1 text-warning"></i>Fórmula de gancho (HookPicker)
        </label>
        <select
          id="hook-formula-select"
          className="form-select form-select-sm bg-dark text-light border-secondary"
          value={selectedFormulaId}
          onChange={(e) => handleApplyHook(e.target.value)}
        >
          <option value="">Selecciona una fórmula de gancho (opcional)...</option>
          {formulas.map((f) => (
            <option key={f.id} value={String(f.id)}>
              #{f.id} {f.name} — "{f.template.slice(0, 45)}..."
            </option>
          ))}
        </select>
      </div>

      {/* Imagen / Video */}
      <div className="mb-3">
        <label className="form-label text-secondary small d-block">
          <i className="bi bi-image me-1 text-primary"></i>Imagen o Video
        </label>
        {mediaPreview && (
          <div className="media-preview-container mb-2 position-relative">
            <img src={mediaPreview} alt="Preview" className="media-preview-img rounded" />
            <button
              type="button"
              className="btn btn-sm btn-danger position-absolute top-0 end-0 m-2"
              onClick={() => {
                onMediaFileChange(null);
                setMediaPreview(null);
              }}
              aria-label="Eliminar imagen"
            >
              <i className="bi bi-x"></i>
            </button>
          </div>
        )}
        <input
          type="file"
          accept="image/*,video/*"
          className="form-control form-control-sm bg-dark text-light border-secondary"
          onChange={(e) => onMediaFileChange(e.target.files?.[0] || null)}
        />
      </div>

      {/* Editor de Caption */}
      <div className="mb-3">
        <div className="d-flex justify-content-between align-items-center mb-1">
          <label htmlFor="caption-editor" className="form-label text-secondary small m-0">
            <i className="bi bi-pencil-square me-1 text-primary"></i>Texto del Caption
          </label>
          <span className="text-secondary small">{caption.length} caracteres</span>
        </div>
        <textarea
          id="caption-editor"
          className="form-control bg-dark text-light border-secondary font-monospace"
          rows={6}
          placeholder="Escribe o genera tu caption aquí..."
          value={caption}
          onChange={(e) => onCaptionChange(e.target.value)}
        />
      </div>

      {/* Trial Reel (AD-10): solo Reels */}
      {format === 'reel' && (
        <div className="format-editor-trial mb-3">
          <div className="form-check form-switch">
            <input
              className="form-check-input"
              type="checkbox"
              id="trial-reel-toggle"
              checked={trialEnabled}
              onChange={(e) => setTrialEnabled(e.target.checked)}
            />
            <label className="form-check-label small" htmlFor="trial-reel-toggle">
              Publicar como prueba (solo no seguidores)
            </label>
          </div>
          {trialEnabled && (
            <select
              aria-label="Graduación del Reel de prueba"
              className="form-select form-select-sm bg-dark text-light border-secondary mt-2"
              value={trialGraduation}
              onChange={(e) => setTrialGraduation(e.target.value as TrialGraduation)}
            >
              <option value="MANUAL">Graduación manual (la decides tú desde Instagram)</option>
              <option value="SS_PERFORMANCE">Graduación automática si rinde bien</option>
            </select>
          )}
        </div>
      )}

      {/* Fecha programada */}
      <div className="mb-3">
        <label htmlFor="scheduled-date-input" className="form-label text-secondary small d-block">
          <i className="bi bi-calendar me-1 text-primary"></i>Fecha y hora programada
        </label>
        <input
          id="scheduled-date-input"
          type="datetime-local"
          className="form-control form-control-sm bg-dark text-light border-secondary"
          value={scheduledAt}
          onChange={(e) => {
            setScheduleError(null);
            onScheduledAtChange(e.target.value);
          }}
        />
        <ScheduleZoneHint value={scheduledAt} timezone={tz} secondaryTimezone={secondaryTimezone} />
        {scheduleError && (
          <div className="text-danger small mt-1">
            <i className="bi bi-exclamation-triangle me-1"></i>
            {scheduleError}
          </div>
        )}
      </div>

      {/* Footer Actions (AD-11) */}
      <div className="format-editor-footer d-flex flex-wrap gap-2 pt-3 border-top border-secondary">
        <button
          type="button"
          className="btn btn-sm btn-outline-secondary"
          onClick={handleDraftClick}
          disabled={loading}
        >
          <i className="bi bi-file-earmark me-1"></i>Guardar borrador
        </button>

        <button
          type="button"
          className="btn btn-sm btn-primary"
          onClick={handleScheduleClick}
          disabled={loading}
        >
          <i className="bi bi-calendar-check me-1"></i>Programar
        </button>

        <button
          type="button"
          className="btn btn-sm btn-outline-info"
          onClick={handleReviewClick}
          disabled={loading || !hasTelegram}
          title={!hasTelegram ? 'Vincula Telegram para enviar a revisión' : undefined}
        >
          <i className="bi bi-send me-1"></i>Enviar a revisión en Telegram
        </button>
      </div>
      {!hasTelegram && (
        <small className="text-secondary d-block mt-1" style={{ fontSize: '0.75rem' }}>
          * Enviar a revisión requiere una cuenta con Telegram vinculado.
        </small>
      )}
    </div>
  );
};

export default FormatEditor;
