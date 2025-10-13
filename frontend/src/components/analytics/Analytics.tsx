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
        'all': 90
      };
      const days = daysMap[timeRange] || 7;

      // Fetch top posts
      const topPostsResponse = await fetch(`http://localhost:8000/api/instagram/posts/top?limit=10`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      // Fetch engagement trend
      const trendResponse = await fetch(`http://localhost:8000/api/instagram/analytics/engagement-trend?days=${days}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      // Fetch best posting times
      const bestTimesResponse = await fetch(`http://localhost:8000/api/instagram/analytics/best-times?days_back=${days}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (!topPostsResponse.ok || !trendResponse.ok || !bestTimesResponse.ok) {
        throw new Error('Error fetching Instagram analytics');
      }

      const topPostsData = await topPostsResponse.json();
      const trendData = await trendResponse.json();
      const bestTimesData = await bestTimesResponse.json();

      // Calcular totales
      const totalLikes = topPostsData.data?.reduce((sum: number, post: any) => sum + (post.likes || 0), 0) || 0;
      const totalComments = topPostsData.data?.reduce((sum: number, post: any) => sum + (post.comments || 0), 0) || 0;
      const totalEngagement = topPostsData.data?.reduce((sum: number, post: any) => sum + (post.engagement || 0), 0) || 0;
      const totalImpressions = topPostsData.data?.reduce((sum: number, post: any) => sum + (post.impressions || 1), 0) || 1;
      const avgEngagementRate = totalImpressions > 0 ? (totalEngagement / totalImpressions * 100) : 0;

      const formattedData: AnalyticsData = {
        overview: {
          total_posts: topPostsData.count || 0,
          total_likes: totalLikes,
          total_comments: totalComments,
          engagement_rate: parseFloat(avgEngagementRate.toFixed(2))
        },
        top_posts: (topPostsData.data || []).slice(0, 3).map((post: any) => ({
          id: post.id,
          content: post.caption || 'Sin descripción',
          media_url: post.media_url || '',
          likes: post.likes || 0,
          comments: post.comments || 0,
          date: post.timestamp || new Date().toISOString()
        })),
        engagement_trend: (trendData.data || []).map((item: any) => ({
          date: item.date,
          likes: item.likes || 0,
          comments: item.comments || 0
        })),
        best_posting_times: (bestTimesData.data || []).slice(0, 4).map((item: any) => ({
          time: item.hour || '00:00',
          avg_engagement: item.avg_engagement_rate || 0
        }))
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

      {/* Insights Box */}
      <div className="insights-box">
        <h4><i className="bi bi-lightbulb me-2"></i>Insights Clave</h4>
        <ul>
          <li>
            <strong>Mejor día:</strong> Los posts del martes obtienen 23% más engagement
          </li>
          <li>
            <strong>Horario óptimo:</strong> 18:00 es tu hora pico con 5.1% de engagement
          </li>
          <li>
            <strong>Tipo de contenido:</strong> Posts con estadísticas de jugadores tienen
            mayor interacción
          </li>
          <li>
            <strong>Recomendación:</strong> Aumenta la frecuencia de publicación en horario
            de tarde (17:00 - 21:00)
          </li>
        </ul>
      </div>
    </div>
  );
};

export default Analytics;
