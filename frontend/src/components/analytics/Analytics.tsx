import React, { useState, useEffect, useRef } from 'react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';
import 'bootstrap-icons/font/bootstrap-icons.css';
import './Analytics.css';

interface ContentTypeStats {
  count: number;
  total_likes: number;
  total_comments: number;
  total_engagement: number;
  avg_engagement: number;
  type_name: string;
}

interface GrowthData {
  posts: number;
  likes: number;
  comments: number;
  engagement: number;
}

interface AnalyticsData {
  overview: {
    total_posts: number;
    total_likes: number;
    total_comments: number;
    engagement_rate: number;
    growth?: GrowthData;
  };
  by_content_type?: { [key: string]: ContentTypeStats };
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
    engagement?: number;
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
  const [timeRange, setTimeRange] = useState<string>('30days');
  const [showComparison, setShowComparison] = useState<boolean>(false);
  const isFetchingRef = useRef<boolean>(false);

  useEffect(() => {
    if (isFetchingRef.current) {
      return;
    }
    fetchAnalytics();
  }, [timeRange, showComparison]);

  const fetchAnalytics = async () => {
    const token = localStorage.getItem('authToken');
    if (!token) {
      setLoading(false);
      return;
    }

    if (isFetchingRef.current) {
      return;
    }
    isFetchingRef.current = true;

    setLoading(true);
    try {
      const daysMap: { [key: string]: number } = {
        '7days': 7,
        '30days': 30,
        '90days': 90,
        'all': 3650
      };
      const days = daysMap[timeRange] || 365;

      // Usar el endpoint optimizado con parámetro compare
      const response = await fetch(
        `http://localhost:8000/api/analytics/overview?days=${days}&compare=${showComparison}`,
        {
          headers: { 'Authorization': `Bearer ${token}` }
        }
      );

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
          total_comments: 0,
          engagement_rate: data.data.overview.engagement_rate || 0,
          growth: data.data.overview.growth
        },
        by_content_type: data.data.by_content_type || {},
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
          comments: item.comments || 0,
          engagement: item.engagement || 0
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
      isFetchingRef.current = false;
    }
  };

  const formatGrowth = (value: number): string => {
    const sign = value >= 0 ? '+' : '';
    return `${sign}${value.toFixed(1)}%`;
  };

  const getGrowthColor = (value: number): string => {
    return value >= 0 ? '#10b981' : '#ef4444';
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

  // Preparar datos para gráfico de tipos de contenido
  const contentTypeChartData = analytics.by_content_type
    ? Object.entries(analytics.by_content_type).map(([, stats]) => ({
        name: stats.type_name,
        engagement: stats.avg_engagement,
        posts: stats.count
      }))
    : [];

  // Colores para el gráfico de tipos de contenido
  const COLORS = ['#6366f1', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981'];

  return (
    <div className="analytics-container">
      <div className="analytics-header">
        <div>
          <h2><i className="bi bi-bar-chart-line me-2"></i>Analytics & Insights</h2>
          <p className="analytics-description">
            Métricas de rendimiento de tus publicaciones
          </p>
        </div>
        <div className="analytics-controls">
          <div className="time-range-selector">
            <select value={timeRange} onChange={(e) => setTimeRange(e.target.value)}>
              <option value="7days">Últimos 7 días</option>
              <option value="30days">Últimos 30 días</option>
              <option value="90days">Últimos 90 días</option>
              <option value="all">Todo el tiempo</option>
            </select>
          </div>
          <label className="comparison-toggle">
            <input
              type="checkbox"
              checked={showComparison}
              onChange={(e) => setShowComparison(e.target.checked)}
            />
            <span>Mostrar crecimiento</span>
          </label>
        </div>
      </div>

      {/* Overview Stats con Crecimiento */}
      <div className="overview-grid">
        <div className="stat-card-analytics">
          <div className="stat-icon-analytics"><i className="bi bi-file-text"></i></div>
          <div className="stat-content-analytics">
            <span className="stat-value-analytics">{analytics.overview.total_posts}</span>
            <span className="stat-label-analytics">Posts Publicados</span>
            {analytics.overview.growth && (
              <span
                className="stat-growth"
                style={{ color: getGrowthColor(analytics.overview.growth.posts) }}
              >
                {formatGrowth(analytics.overview.growth.posts)}
              </span>
            )}
          </div>
        </div>

        <div className="stat-card-analytics">
          <div className="stat-icon-analytics"><i className="bi bi-heart-fill"></i></div>
          <div className="stat-content-analytics">
            <span className="stat-value-analytics">
              {analytics.overview.total_likes.toLocaleString()}
            </span>
            <span className="stat-label-analytics">Total Interacciones</span>
            {analytics.overview.growth && (
              <span
                className="stat-growth"
                style={{ color: getGrowthColor(analytics.overview.growth.likes) }}
              >
                {formatGrowth(analytics.overview.growth.likes)}
              </span>
            )}
          </div>
        </div>

        <div className="stat-card-analytics">
          <div className="stat-icon-analytics"><i className="bi bi-chat-dots"></i></div>
          <div className="stat-content-analytics">
            <span className="stat-value-analytics">
              {analytics.overview.total_comments.toLocaleString()}
            </span>
            <span className="stat-label-analytics">Comentarios</span>
            {analytics.overview.growth && (
              <span
                className="stat-growth"
                style={{ color: getGrowthColor(analytics.overview.growth.comments) }}
              >
                {formatGrowth(analytics.overview.growth.comments)}
              </span>
            )}
          </div>
        </div>

        <div className="stat-card-analytics">
          <div className="stat-icon-analytics"><i className="bi bi-graph-up"></i></div>
          <div className="stat-content-analytics">
            <span className="stat-value-analytics">{analytics.overview.engagement_rate}%</span>
            <span className="stat-label-analytics">Engagement Rate</span>
            {analytics.overview.growth && (
              <span
                className="stat-growth"
                style={{ color: getGrowthColor(analytics.overview.growth.engagement) }}
              >
                {formatGrowth(analytics.overview.growth.engagement)}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Engagement Trend - Recharts */}
      <div className="analytics-section">
        <h3><i className="bi bi-graph-up me-2"></i>Tendencia de Engagement</h3>
        <div className="chart-container">
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={analytics.engagement_trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis
                dataKey="date"
                tickFormatter={(value) => {
                  const date = new Date(value);
                  return date.toLocaleDateString('es-ES', {
                    day: 'numeric',
                    month: 'short'
                  });
                }}
                stroke="#6b7280"
                style={{ fontSize: '12px' }}
              />
              <YAxis stroke="#6b7280" style={{ fontSize: '12px' }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#fff',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px'
                }}
                labelFormatter={(value) => {
                  const date = new Date(value);
                  return date.toLocaleDateString('es-ES', {
                    weekday: 'long',
                    day: 'numeric',
                    month: 'long'
                  });
                }}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="likes"
                stroke="#ec4899"
                strokeWidth={2}
                name="Likes"
                dot={{ fill: '#ec4899', r: 4 }}
                activeDot={{ r: 6 }}
              />
              <Line
                type="monotone"
                dataKey="comments"
                stroke="#8b5cf6"
                strokeWidth={2}
                name="Comentarios"
                dot={{ fill: '#8b5cf6', r: 4 }}
                activeDot={{ r: 6 }}
              />
              <Line
                type="monotone"
                dataKey="engagement"
                stroke="#6366f1"
                strokeWidth={2}
                name="Engagement Total"
                dot={{ fill: '#6366f1', r: 4 }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Análisis por Tipo de Contenido */}
      {contentTypeChartData.length > 0 && (
        <div className="analytics-section">
          <h3><i className="bi bi-collection me-2"></i>Análisis por Tipo de Contenido</h3>
          <div className="content-type-analysis">
            <div className="chart-container" style={{ height: '300px' }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={contentTypeChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis
                    dataKey="name"
                    stroke="#6b7280"
                    style={{ fontSize: '12px' }}
                  />
                  <YAxis stroke="#6b7280" style={{ fontSize: '12px' }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#fff',
                      border: '1px solid #e5e7eb',
                      borderRadius: '8px'
                    }}
                  />
                  <Legend />
                  <Bar
                    dataKey="engagement"
                    fill="#6366f1"
                    name="Engagement Promedio"
                    radius={[8, 8, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="content-type-stats">
              {contentTypeChartData.map((item, index) => (
                <div key={index} className="content-type-item">
                  <div
                    className="type-indicator"
                    style={{ backgroundColor: COLORS[index % COLORS.length] }}
                  ></div>
                  <div className="type-info">
                    <span className="type-name">{item.name}</span>
                    <span className="type-details">
                      {item.posts} posts · {item.engagement.toFixed(1)} engagement promedio
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

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
          <h3><i className="bi bi-clock me-2"></i>Mejores Horarios</h3>
          <div className="chart-container" style={{ height: '250px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={analytics.best_posting_times}
                layout="vertical"
                margin={{ left: 20, right: 20 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis type="number" stroke="#6b7280" style={{ fontSize: '12px' }} />
                <YAxis
                  type="category"
                  dataKey="time"
                  stroke="#6b7280"
                  style={{ fontSize: '12px' }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#fff',
                    border: '1px solid #e5e7eb',
                    borderRadius: '8px'
                  }}
                />
                <Bar
                  dataKey="avg_engagement"
                  fill="#10b981"
                  name="Engagement Promedio"
                  radius={[0, 8, 8, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Insights Box */}
      {analytics.insights && analytics.insights.length > 0 && (
        <div className="insights-box">
          <h4><i className="bi bi-lightbulb me-2"></i>Insights Clave</h4>
          <ul>
            {analytics.insights.map((insight, index) => (
              <li key={index}>
                <i className={`bi bi-${insight.icon} me-2`}></i>
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
