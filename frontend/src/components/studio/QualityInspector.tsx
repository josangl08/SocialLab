import React, { useState, useEffect, useRef } from 'react';
import { contentApi } from '../../api/content';
import type { QualityReport, BeatItemOutput } from '../../types';
import BeatSheet from './BeatSheet';
import './QualityInspector.css';

export interface QualityInspectorProps {
  caption: string;
  format?: 'post' | 'reel' | 'carousel';
  keywords?: string[];
  beats?: BeatItemOutput[];
  beatsTotalSeconds?: number;
  beatsLoopsToHook?: boolean;
  onReportChange?: (report: QualityReport | null) => void;
}

export const QualityInspector: React.FC<QualityInspectorProps> = ({
  caption,
  format = 'post',
  keywords,
  beats = [],
  beatsTotalSeconds,
  beatsLoopsToHook,
  onReportChange,
}) => {
  const [report, setReport] = useState<QualityReport | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Client-side 125 chars preview calculation for instant feedback
  const visiblePreviewText = caption ? caption.slice(0, 125) : '';
  const isTruncated = caption.length > 125;
  const clientVisibleCount = Math.min(caption.length, 125);

  useEffect(() => {
    if (!caption || caption.trim() === '') {
      setReport(null);
      setLoading(false);
      onReportChange?.(null);
      return;
    }

    setLoading(true);
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;

    const timer = setTimeout(async () => {
      try {
        const result = await contentApi.lintCaption(
          {
            caption,
            format,
            keywords,
          },
          { signal: controller.signal }
        );

        setReport(result);
        onReportChange?.(result);
      } catch (err: any) {
        if (err.name !== 'AbortError' && err.code !== 'ERR_CANCELED') {
          console.error('Error in lintCaption:', err);
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }, 400);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [caption, format, keywords]);

  const slopScore = report?.slop?.score ?? 0;
  const voicePurity = Math.max(0, 100 - slopScore);

  return (
    <div className="quality-inspector">
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h5 className="m-0 text-light fw-bold">
          <i className="bi bi-shield-check me-2 text-primary"></i>Inspector de calidad
        </h5>
        {loading && (
          <span className="badge bg-purple-subtle text-light small d-flex align-items-center gap-1">
            <span className="spinner-border spinner-border-sm" role="status"></span>
            Analizando...
          </span>
        )}
      </div>

      {/* Feed Preview (125 chars móvil) */}
      <div className="inspector-card preview-card mb-3">
        <div className="d-flex justify-content-between align-items-center mb-2">
          <span className="inspector-card-title text-secondary small fw-semibold">
            <i className="bi bi-phone me-1"></i>Vista previa en feed móvil
          </span>
          <span
            className={`badge ${isTruncated ? 'bg-warning text-dark' : 'bg-secondary'}`}
            data-testid="char-counter"
          >
            {clientVisibleCount}/125 chars
          </span>
        </div>
        <div className="feed-preview-bubble">
          {caption ? (
            <p className="feed-preview-text m-0">
              {visiblePreviewText}
              {isTruncated && <span className="feed-preview-more text-secondary"> … más</span>}
            </p>
          ) : (
            <p className="text-secondary small fst-italic m-0">
              Escribe un caption para ver cómo se mostrará en el feed...
            </p>
          )}
        </div>
        {isTruncated && (
          <small className="text-warning-emphasis d-block mt-1" style={{ fontSize: '0.75rem' }}>
            <i className="bi bi-info-circle me-1"></i>El texto posterior a 125 caracteres quedará oculto tras "... más".
          </small>
        )}
      </div>

      {/* Metrics Row */}
      <div className="row g-2 mb-3">
        {/* Hashtags */}
        <div className="col-4">
          <div className="metric-box text-center p-2 rounded">
            <div className="metric-label text-secondary small">Hashtags</div>
            <div
              className={`metric-value fs-5 fw-bold ${
                (report?.hashtag_count ?? 0) > 5 ? 'text-danger' : 'text-light'
              }`}
              data-testid="hashtag-count"
            >
              {report?.hashtag_count ?? 0}/5
            </div>
            {(report?.hashtag_count ?? 0) > 5 && (
              <span className="badge bg-danger small" style={{ fontSize: '0.65rem' }}>
                Exceso
              </span>
            )}
          </div>
        </div>

        {/* Pureza de voz (Anti-slop) */}
        <div className="col-4">
          <div className="metric-box text-center p-2 rounded">
            <div className="metric-label text-secondary small">Pureza voz</div>
            <div
              className={`metric-value fs-5 fw-bold ${
                voicePurity === 100 ? 'text-success' : voicePurity >= 70 ? 'text-warning' : 'text-danger'
              }`}
              data-testid="voice-purity"
            >
              {voicePurity}%
            </div>
            <span className="text-secondary" style={{ fontSize: '0.65rem' }}>
              {slopScore === 0 ? 'Sin slop' : `${report?.slop?.hits?.length ?? 0} términos`}
            </span>
          </div>
        </div>

        {/* Hook Score */}
        <div className="col-4">
          <div className="metric-box text-center p-2 rounded">
            <div className="metric-label text-secondary small">Gancho</div>
            <div
              className={`metric-value fs-5 fw-bold ${
                (report?.hook?.score ?? 0) >= 70
                  ? 'text-success'
                  : (report?.hook?.score ?? 0) >= 40
                  ? 'text-warning'
                  : 'text-secondary'
              }`}
              data-testid="hook-score"
            >
              {report?.hook?.score ?? 0}/100
            </div>
            <span
              className="text-secondary d-inline-block text-truncate"
              style={{ fontSize: '0.65rem', maxWidth: '100%' }}
              title={report?.hook?.formula_name ?? ''}
            >
              {report?.hook?.formula_name || 'Libre'}
            </span>
          </div>
        </div>
      </div>

      {/* Slop hits details */}
      {report?.slop && report.slop.hits.length > 0 && (
        <div className="slop-alerts alert alert-warning p-2 small mb-3">
          <strong className="d-block mb-1">
            <i className="bi bi-exclamation-triangle me-1"></i>Léxico sintético detectado:
          </strong>
          <ul className="m-0 ps-3">
            {report.slop.hits.map((hit, idx) => (
              <li key={idx}>
                <code>"{hit.term}"</code> → Sugerencia: <em>{hit.suggestion}</em>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Dealbreakers alert */}
      {report?.hook && report.hook.dealbreakers.length > 0 && (
        <div className="dealbreaker-alert alert alert-danger p-2 small mb-3">
          <strong className="d-block mb-1">
            <i className="bi bi-x-octagon me-1"></i>Gancho penalizado por dealbreaker:
          </strong>
          <span>Evita aperturas como: "{report.hook.dealbreakers.join(', ')}".</span>
        </div>
      )}

      {/* Warnings */}
      {report?.warnings && report.warnings.length > 0 && (
        <div className="warnings-section mb-3">
          <label className="text-secondary small fw-semibold d-block mb-1">Avisos de calidad</label>
          <div className="d-flex flex-column gap-1">
            {report.warnings.map((w, idx) => (
              <div key={idx} className="warning-item p-2 rounded small text-warning bg-warning bg-opacity-10 border border-warning border-opacity-25">
                <i className="bi bi-exclamation-circle me-1"></i>
                <span>{w.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* BeatSheet if Reel */}
      {format === 'reel' && (
        <BeatSheet
          beats={beats}
          totalSeconds={beatsTotalSeconds}
          loopsToHook={beatsLoopsToHook}
        />
      )}
    </div>
  );
};

export default QualityInspector;
