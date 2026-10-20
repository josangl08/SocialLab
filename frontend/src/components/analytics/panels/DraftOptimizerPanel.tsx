import React, { useState } from 'react';

interface BestPostingTimeRaw {
  hour: string;
  day_of_week?: string | number | null;
  score: number;
  online_followers: number;
  avg_engagement: number;
  posts_count: number;
}

interface ContentTypeStats {
  count: number;
  total_likes: number;
  total_comments: number;
  total_engagement: number;
  avg_engagement: number;
  type_name: string;
}

interface DraftOptimizerPanelProps {
  bestPostingTimesRaw?: BestPostingTimeRaw[];
  byContentType?: Record<string, ContentTypeStats>;
}

export const DraftOptimizerPanel: React.FC<DraftOptimizerPanelProps> = ({
  bestPostingTimesRaw = [],
  byContentType = {}
}) => {
  const [isOpen, setIsOpen] = useState<boolean>(true);

  // Helper to translate weekday number to name
  const getDayName = (dayNum?: string | number | null): string => {
    if (dayNum === undefined || dayNum === null) return 'Día pico';
    const days = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];
    const idx = typeof dayNum === 'string' ? parseInt(dayNum, 10) : dayNum;
    return days[idx] || 'Día pico';
  };

  // 1. Calculate optimal posting slot (highest avg_engagement or score)
  const bestTime = bestPostingTimesRaw.length > 0 
    ? [...bestPostingTimesRaw].sort((a, b) => b.avg_engagement - a.avg_engagement)[0]
    : null;

  // 2. Calculate most common format (highest count)
  let mostCommonFormat = 'Reel';
  let maxCount = -1;
  Object.values(byContentType).forEach(stats => {
    if (stats.count > maxCount) {
      maxCount = stats.count;
      mostCommonFormat = stats.type_name;
    }
  });

  const recommendedDay = bestTime ? getDayName(bestTime.day_of_week) : 'Martes';
  const recommendedHour = bestTime ? bestTime.hour : '18:00';
  const estimatedDelta = bestTime ? Math.round(bestTime.avg_engagement) : 25;

  return (
    <div className="an-optimizer-panel">
      <div 
        className="an-optimizer-header" 
        onClick={() => setIsOpen(!isOpen)}
        role="button"
        aria-expanded={isOpen}
      >
        <h4 className="an-optimizer-title">
          <i className="bi bi-stars an-optimizer-icon-stars"></i>
          Asistente de Optimización de Borradores
        </h4>
        <i className={`bi bi-chevron-${isOpen ? 'up' : 'down'} text-muted`}></i>
      </div>

      {isOpen && (
        <div className="an-optimizer-body">
          <p className="small mb-2">
            Basado en tu historial de rendimiento y actividad de la audiencia, este es el mejor momento para tu próximo borrador:
          </p>
          <div className="d-flex align-items-center gap-3 flex-wrap">
            <div className="p-2 bg-dark rounded border border-secondary flex-fill">
              <div className="small text-muted">Horario Recomendado</div>
              <div className="fw-bold text-white">{recommendedDay} a las {recommendedHour}</div>
            </div>
            
            <div className="p-2 bg-dark rounded border border-secondary flex-fill">
              <div className="small text-muted">Formato Óptimo</div>
              <div className="fw-bold text-white">{mostCommonFormat}</div>
            </div>

            <div className="p-2 bg-dark rounded border border-secondary flex-fill">
              <div className="small text-muted">Engagement Estimado</div>
              <div className="fw-bold text-success">+{estimatedDelta}% de incremento</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DraftOptimizerPanel;
