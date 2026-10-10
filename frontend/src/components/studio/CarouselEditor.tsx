import React, { useState } from 'react';
import type { CarouselSlide, CarouselSlideRole } from '../../types';
import './CarouselEditor.css';

export interface CarouselEditorProps {
  slides: CarouselSlide[];
  onSlidesChange?: (slides: CarouselSlide[]) => void;
  caption?: string;
  onCaptionChange?: (caption: string) => void;
  readOnly?: boolean;
}

const ROLE_LABELS: Record<CarouselSlideRole, string> = {
  cover: 'Portada (≤ 6 palabras)',
  stake: 'Problema / Stake',
  idea: 'Idea clave (≤ 25 palabras)',
  recap: 'Resumen',
  cta: 'Llamada a la acción',
};

export const countWords = (text: string): number => {
  const trimmed = text.trim();
  if (!trimmed) return 0;
  return trimmed.split(/\s+/).length;
};

export const getSlideWarning = (slide: CarouselSlide): string | null => {
  const words = countWords(slide.text);
  if (slide.role === 'cover' && words > 6) {
    return `La portada no debería superar 6 palabras (actual: ${words}).`;
  }
  if (slide.role === 'idea' && words > 25) {
    return `La idea principal no debería superar 25 palabras (actual: ${words}).`;
  }
  return null;
};

export const CarouselEditor: React.FC<CarouselEditorProps> = ({
  slides = [],
  onSlidesChange,
  caption,
  onCaptionChange,
  readOnly = false,
}) => {
  const [activeIndex, setActiveIndex] = useState<number>(0);

  if (!slides || slides.length === 0) {
    return (
      <div className="carousel-editor text-muted text-center py-4">
        No hay diapositivas para mostrar.
      </div>
    );
  }

  const safeIndex = Math.min(Math.max(0, activeIndex), slides.length - 1);
  const currentSlide = slides[safeIndex];
  const currentWords = countWords(currentSlide.text);
  const warning = getSlideWarning(currentSlide);

  const handleTextChange = (newText: string) => {
    if (!onSlidesChange) return;
    const updated = slides.map((s, idx) => {
      if (idx === safeIndex) {
        return {
          ...s,
          text: newText,
          word_count: countWords(newText),
        };
      }
      return s;
    });
    onSlidesChange(updated);
  };

  const handlePrev = () => {
    if (safeIndex > 0) setActiveIndex(safeIndex - 1);
  };

  const handleNext = () => {
    if (safeIndex < slides.length - 1) setActiveIndex(safeIndex + 1);
  };

  return (
    <div className="carousel-editor" data-testid="carousel-editor">
      <div className="carousel-editor-header">
        <h6 className="mb-0 text-white">
          <i className="bi bi-collection me-2 text-primary"></i>
          Editor de Carrusel ({slides.length} diapositivas)
        </h6>
        <div className="d-flex gap-2">
          <button
            type="button"
            className="btn btn-sm btn-outline-secondary"
            onClick={handlePrev}
            disabled={safeIndex === 0}
            aria-label="Slide anterior"
          >
            <i className="bi bi-chevron-left me-1"></i> Anterior
          </button>
          <button
            type="button"
            className="btn btn-sm btn-outline-secondary"
            onClick={handleNext}
            disabled={safeIndex === slides.length - 1}
            aria-label="Siguiente slide"
          >
            Siguiente <i className="bi bi-chevron-right ms-1"></i>
          </button>
        </div>
      </div>

      {/* Navegación por chips de diapositivas */}
      <div className="carousel-slide-nav" role="tablist" aria-label="Lista de diapositivas">
        {slides.map((s, idx) => {
          const hasWarn = Boolean(getSlideWarning(s));
          const isActive = idx === safeIndex;
          return (
            <button
              key={idx}
              type="button"
              className={`carousel-slide-chip ${isActive ? 'active' : ''} ${hasWarn ? 'has-warning' : ''}`}
              onClick={() => setActiveIndex(idx)}
              role="tab"
              aria-selected={isActive}
              aria-label={`Diapositiva ${idx + 1}`}
            >
              #{idx + 1} {s.role}
              {hasWarn && <i className="bi bi-exclamation-triangle-fill ms-1 text-warning" title="Aviso de palabras"></i>}
            </button>
          );
        })}
      </div>

      {/* Tarjeta de la diapositiva actual */}
      <div className="carousel-slide-card">
        <div className="d-flex justify-content-between align-items-center mb-2">
          <div className="d-flex align-items-center gap-2">
            <span className="badge bg-secondary">Diapositiva {safeIndex + 1} de {slides.length}</span>
            <span className="badge bg-primary carousel-slide-role-badge">
              {ROLE_LABELS[currentSlide.role] || currentSlide.role}
            </span>
          </div>
          <span className="text-muted small" data-testid="slide-word-count">
            {currentWords} {currentWords === 1 ? 'palabra' : 'palabras'}
          </span>
        </div>

        <div className="mb-2">
          <label htmlFor={`slide-text-${safeIndex}`} className="form-label small text-muted">
            Texto de la diapositiva
          </label>
          <textarea
            id={`slide-text-${safeIndex}`}
            className="form-control"
            rows={4}
            value={currentSlide.text}
            onChange={(e) => handleTextChange(e.target.value)}
            disabled={readOnly}
            placeholder="Escribe el contenido de esta diapositiva..."
          />
        </div>

        {warning && (
          <div className="carousel-word-warning" role="alert" data-testid="slide-warning">
            <i className="bi bi-exclamation-circle-fill"></i>
            <span>{warning}</span>
          </div>
        )}
      </div>

      {/* Editor opcional de caption general */}
      {caption !== undefined && (
        <div className="mt-3 pt-3 border-top border-secondary">
          <label htmlFor="carousel-caption" className="form-label small text-muted">
            Caption acompañante
          </label>
          <textarea
            id="carousel-caption"
            className="form-control"
            rows={3}
            value={caption}
            onChange={(e) => onCaptionChange?.(e.target.value)}
            disabled={readOnly}
            placeholder="Caption para acompañar el carrusel..."
          />
        </div>
      )}
    </div>
  );
};

export default CarouselEditor;
