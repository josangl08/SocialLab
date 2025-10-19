import React, { useState, useEffect, useRef } from 'react';
import 'bootstrap-icons/font/bootstrap-icons.css';
import './Analytics.css';

interface AnalyticsData {
  overview: {
    total_posts: number;
    total_likes: number;
    total_comments: number;
    engagement_rate: number;
  };
  top_posts: Array<{
    id: number;
    content: string;
    media_url: string;
    likes: number;
    comments: number;
    date: string;
  }>;
  engagement_trend: Array<{
    date: string;
    likes: number;
    comments: number;
  }>;
  best_posting_times: Array<{
    time: string;
    avg_engagement: number;
  }>;
  insights?: Array<{
    type: string;
    title: string;
    description: string;
    icon: string;
  }>;
}

const Analytics: React.FC = () => {
  const [loading, setLoading] = useState<boolean>(true);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [timeRange, setTimeRange] = useState<string>('7days');
  const isFetchingRef = useRef<boolean>(false);

  useEffect(() => {
    // Prevenir fetch duplicado si ya hay uno en progreso
    if (isFetchingRef.current) {
      return;
    }
    fetchAnalytics();
  }, [timeRange]);

  const fetchAnalytics = async () => {
    const token = localStorage.getItem('authToken');
    if (!token) {
      setLoading(false);
      return;
    }

    // Marcar que estamos fetching
    if (isFetchingRef.current) {
      return;
    }
    isFetchingRef.current = true;

    setLoading(true);
    try {
      // Determinar días según el rango
      const daysMap: { [key: string]: number } = {
        '7days': 7,
        '30days': 30,
        '90days': 90,
        'all': 3650  // 10 años de historia
      };
      const days = daysMap[timeRange] || 365;  // Default: 1 año

      // Usar un solo endpoint con parámetro days
      const response = await fetch(`http://localhost:8000/api/analytics/cached-overview?days=${days}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (!response.ok) {
        throw new Error('Error fetching Instagram analytics');
      }

      const data = await response.json();

      if (!data.success || !data.data) {
        throw new Error('No data available');
      }

      // Mapear datos del backend al formato del frontend
      const formattedData: AnalyticsData = {
        overview: {
          total_posts: data.data.overview.total_posts || 0,
          total_likes: data.data.overview.total_interactions || 0,
          total_comments: 0, // Se incluye en total_interactions
          engagement_rate: data.data.overview.engagement_rate || 0
        },
        top_posts: (data.data.top_posts || []).map((post: any) => ({
          id: post.id,
          content: post.caption || 'Sin descripción',
          media_url: post.media_url || '',
          likes: post.likes || 0,
          comments: post.comments || 0,
          date: post.timestamp || new Date().toISOString()
        })),
        engagement_trend: (data.data.engagement_trend || []).map((item: any) => ({
          date: item.date,
          likes: item.likes || 0,
          comments: item.comments || 0
        })),
        best_posting_times: (data.data.best_posting_times || []).map((item: any) => ({
          time: item.hour || '00:00',
          avg_engagement: item.avg_engagement_rate || 0
        })),
        insights: data.data.insights || []
      };

      setAnalytics(formattedData);
    } catch (error) {
      console.error('Error cargando analytics:', error);
      setAnalytics(null);
    } finally {
      setLoading(false);
      isFetchingRef.current = false; // Resetear flag al terminar
    }
  };

  if (loading) {
    return (
      <div className="analytics-loading">
        <div className="spinner"></div>
        <p>Cargando analytics...</p>
      </div>
    );
  }

  if (!analytics) {
    return (
      <div className="analytics-empty">
        <p><i className="bi bi-bar-chart-line me-2"></i>No hay datos de analytics disponibles</p>
        <p className="text-muted">Conecta tu cuenta de Instagram para ver métricas</p>
      </div>
    );
  }

  return (
    <div className="analytics-container">
      <div className="analytics-header">
        <div>
          <h2><i className="bi bi-bar-chart-line me-2"></i>Analytics & Insights</h2>
          <p className="analytics-description">
            Métricas de rendimiento de tus publicaciones
          </p>
        </div>
        <div className="time-range-selector">
          <select value={timeRange} onChange={(e) => setTimeRange(e.target.value)}>
            <option value="7days">Últimos 7 días</option>
            <option value="30days">Últimos 30 días</option>
            <option value="90days">Últimos 90 días</option>
            <option value="all">Todo el tiempo</option>
          </select>
        </div>
      </div>

      {/* Overview Stats */}
      <div className="overview-grid">
        <div className="stat-card-analytics">
          <div className="stat-icon-analytics"><i className="bi bi-file-text"></i></div>
          <div className="stat-content-analytics">
            <span className="stat-value-analytics">{analytics.overview.total_posts}</span>
            <span className="stat-label-analytics">Posts Publicados</span>
          </div>
        </div>

        <div className="stat-card-analytics">
          <div className="stat-icon-analytics"><i className="bi bi-heart-fill"></i></div>
          <div className="stat-content-analytics">
            <span className="stat-value-analytics">
              {analytics.overview.total_likes.toLocaleString()}
            </span>
            <span className="stat-label-analytics">Total Likes</span>
          </div>
        </div>

        <div className="stat-card-analytics">
          <div className="stat-icon-analytics"><i className="bi bi-chat-dots"></i></div>
          <div className="stat-content-analytics">
            <span className="stat-value-analytics">{analytics.overview.total_comments}</span>
            <span className="stat-label-analytics">Comentarios</span>
          </div>
        </div>

        <div className="stat-card-analytics">
          <div className="stat-icon-analytics"><i className="bi bi-graph-up"></i></div>
          <div className="stat-content-analytics">
            <span className="stat-value-analytics">{analytics.overview.engagement_rate}%</span>
            <span className="stat-label-analytics">Engagement Rate</span>
          </div>
        </div>
      </div>

      {/* Engagement Trend */}
      <div className="analytics-section">
        <h3><i className="bi bi-graph-up me-2"></i>Tendencia de Engagement</h3>
        <div className="trend-chart">
          {analytics.engagement_trend.map((day, index) => {
            const maxLikes = Math.max(...analytics.engagement_trend.map(d => d.likes));
            const height = (day.likes / maxLikes) * 100;

            return (
              <div key={index} className="chart-bar-container">
                <div className="chart-bar-wrapper">
                  <div className="chart-bar" style={{ height: `${height}%` }}>
                    <div className="bar-tooltip">
                      <strong>{day.likes}</strong> likes<br />
                      <strong>{day.comments}</strong> comments
                    </div>
                  </div>
                </div>
                <div className="chart-label">
                  {new Date(day.date).toLocaleDateString('es-ES', {
                    day: 'numeric',
                    month: 'short'
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Two Column Layout */}
      <div className="analytics-columns">
        {/* Top Posts */}
        <div className="analytics-section">
          <h3><i className="bi bi-trophy me-2"></i>Posts Más Exitosos</h3>
          <div className="top-posts-list">
            {analytics.top_posts.map((post, index) => (
              <div key={post.id} className="top-post-item">
                <div className="post-rank">#{index + 1}</div>
                <div className="post-info">
                  <p className="post-content">{post.content}</p>
                  <div className="post-metrics">
                    <span><i className="bi bi-heart-fill me-1"></i>{post.likes}</span>
                    <span><i className="bi bi-chat-dots me-1"></i>{post.comments}</span>
                    <span className="post-date">
                      {new Date(post.date).toLocaleDateString('es-ES')}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Best Posting Times */}
        <div className="analytics-section">
          <h3><i className="bi bi-clock me-2"></i>Mejores Horarios para Publicar</h3>
          <div className="best-times-list">
            {analytics.best_posting_times.map((time, index) => (
              <div key={index} className="time-item">
                <div className="time-label"><i className="bi bi-clock me-1"></i>{time.time}</div>
                <div className="time-bar-container">
                  <div
                    className="time-bar"
                    style={{
                      width: `${(time.avg_engagement / 6) * 100}%`
                    }}
                  ></div>
                </div>
                <div className="time-value">{time.avg_engagement}% engagement</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Insights Box - Dinámicos */}
      {analytics.insights && analytics.insights.length > 0 && (
        <div className="insights-box">
          <h4><i className="bi bi-lightbulb me-2"></i>Insights Clave</h4>
          <ul>
            {analytics.insights.map((insight, index) => (
              <li key={index}>
                <strong>{insight.title}:</strong> {insight.description}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default Analytics;
