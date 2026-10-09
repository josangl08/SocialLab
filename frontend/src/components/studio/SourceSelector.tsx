import React from 'react';
import './SourceSelector.css';

export type ContentSource = 'idea' | 'repurpose' | 'sports';

export interface SourceSelectorProps {
  source: ContentSource;
  onSelectSource: (source: ContentSource) => void;
  isSportsSector: boolean;
}

export const SourceSelector: React.FC<SourceSelectorProps> = ({
  source,
  onSelectSource,
  isSportsSector,
}) => {
  return (
    <div className="source-selector mb-4">
      <label className="source-selector-label text-secondary small d-block mb-2">
        <i className="bi bi-compass me-1 text-primary"></i>Origen del contenido
      </label>
      <div className="source-tabs d-flex gap-2">
        <button
          type="button"
          className={`source-tab-btn ${source === 'idea' ? 'active' : ''}`}
          onClick={() => onSelectSource('idea')}
        >
          <i className="bi bi-lightbulb me-2"></i>
          Idea libre
        </button>

        <button
          type="button"
          className={`source-tab-btn ${source === 'repurpose' ? 'active' : ''}`}
          onClick={() => onSelectSource('repurpose')}
        >
          <i className="bi bi-recycle me-2"></i>
          Reciclar contenido
        </button>

        {isSportsSector && (
          <button
            type="button"
            className={`source-tab-btn ${source === 'sports' ? 'active' : ''}`}
            onClick={() => onSelectSource('sports')}
          >
            <i className="bi bi-graph-up me-2"></i>
            Estadísticas deportivas
          </button>
        )}
      </div>
    </div>
  );
};

export default SourceSelector;
