import React from 'react';
import './ActivityHeatmap.css';

interface OnlineHoursData {
  [hour: string]: number;
}

interface BestPostingTime {
  hour: string;
  score: number;
  online_followers: number;
  avg_engagement: number;
  posts_count: number;
}

interface ActivityHeatmapProps {
  onlineHours: OnlineHoursData;
  bestPostingTimes: BestPostingTime[];
  loading?: boolean;
}

export const ActivityHeatmap: React.FC<ActivityHeatmapProps> = ({
  onlineHours,
  bestPostingTimes,
  loading = false
}) => {
  if (loading) {
    return (
      <div className="chart-loading">
        <div className="spinner"></div>
        <p>Cargando datos de actividad...</p>
      </div>
    );
  }

  if (!onlineHours || Object.keys(onlineHours).length === 0) {
    return (
      <div className="chart-empty">
        <i className="bi bi-clock" style={{ fontSize: '48px', color: '#d1d5db' }}></i>
        <p>No hay datos de actividad disponibles</p>
      </div>
    );
  }

  // Normalizar valores de online hours (0-100)
  const values = Object.values(onlineHours);
  const maxValue = Math.max(...values);
  const minValue = Math.min(...values);

  const normalizeValue = (value: number) => {
    if (maxValue === minValue) return 50;
    return ((value - minValue) / (maxValue - minValue)) * 100;
  };

  // Obtener color basado en intensidad
  const getColor = (hour: string) => {
    const hourNum = parseInt(hour);
    const value = onlineHours[hour] || 0;
    const normalized = normalizeValue(value);

    // Verificar si es un horario recomendado (top 5)
    const isRecommended = bestPostingTimes.some(
      t => parseInt(t.hour.split(':')[0]) === hourNum
    );

    if (isRecommended) {
      // Verde brillante para horarios recomendados
      if (normalized > 66) return '#10b981';  // green-500
      if (normalized > 33) return '#34d399';  // green-400
      return '#6ee7b7';                       // green-300
    }

    // Azul para actividad normal
    if (normalized > 66) return '#3b82f6';    // blue-500
    if (normalized > 33) return '#60a5fa';    // blue-400
    return '#93c5fd';                         // blue-300
  };

  const getBorderColor = (hour: string) => {
    const hourNum = parseInt(hour);
    const isTopRecommended = bestPostingTimes.findIndex(
      t => parseInt(t.hour.split(':')[0]) === hourNum
    );

    if (isTopRecommended === 0) return '#059669';  // Mejor horario
    if (isTopRecommended > 0 && isTopRecommended < 3) return '#10b981';  // Top 3
    return 'transparent';
  };

  // Formatear hora
  const formatHour = (hour: string | number) => {
    const h = typeof hour === 'string' ? parseInt(hour) : hour;
    return `${h.toString().padStart(2, '0')}:00`;
  };

  return (
    <div className="activity-heatmap">
      <div className="heatmap-legend">
        <div className="legend-item">
          <div className="legend-dot" style={{ background: '#3b82f6' }}></div>
          <span>Seguidores online</span>
        </div>
        <div className="legend-item">
          <div className="legend-dot" style={{ background: '#10b981' }}></div>
          <span>Mejor horario</span>
        </div>
        <div className="legend-item">
          <div className="legend-star">⭐</div>
          <span>Top 3 horarios</span>
        </div>
      </div>

      <div className="heatmap-grid">
        {Array.from({ length: 24 }, (_, i) => {
          const hour = i.toString();
          const value = onlineHours[hour] || 0;
          const normalized = normalizeValue(value);
          const color = getColor(hour);
          const borderColor = getBorderColor(hour);

          return (
            <div
              key={i}
              className="heatmap-cell"
              style={{
                background: color,
                border: `2px solid ${borderColor}`,
                opacity: 0.3 + (normalized / 100) * 0.7
              }}
              title={`${formatHour(i)}: ${value} seguidores online`}
            >
              <span className="cell-hour">{formatHour(i)}</span>
              <span className="cell-value">{value}</span>
            </div>
          );
        })}
      </div>

      {/* Top Posting Times */}
      <div className="best-times-list">
        <h4>🎯 Mejores Horarios para Publicar</h4>
        <div className="best-times-items">
          {bestPostingTimes.slice(0, 5).map((time, index) => (
            <div key={index} className="best-time-item">
              <div className="best-time-rank">
                {index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : `#${index + 1}`}
              </div>
              <div className="best-time-info">
                <span className="best-time-hour">{time.hour}</span>
                <div className="best-time-stats">
                  <span className="stat">
                    Score: <strong>{time.score}</strong>
                  </span>
                  <span className="stat">
                    {time.online_followers} online
                  </span>
                  {time.posts_count > 0 && (
                    <span className="stat">
                      {time.avg_engagement.toFixed(1)}% engagement
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default ActivityHeatmap;
