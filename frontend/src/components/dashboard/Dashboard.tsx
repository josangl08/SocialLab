import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import 'bootstrap-icons/font/bootstrap-icons.css';
import './Dashboard.css';

interface DashboardStats {
  follower_count: number;
  profile_views: number;
  reach: number;
  impressions: number;
  engagement_rate: number;
  total_posts: number;
}

interface TopPost {
  id: string;
  caption: string;
  media_url: string;
  permalink: string;
  timestamp: string;
  likes: number;
  comments: number;
  engagement: number;
  impressions: number;
}

interface EngagementTrendItem {
  date: string;
  likes: number;
  comments: number;
  engagement: number;
  posts_count: number;
}

interface BestPostingTime {
  hour: string;
  avg_engagement_rate: number;
  posts_count: number;
}

interface ScheduledPost {
  id: number;
  content: string;
  post_type: string;
  scheduled_at: string | null;
  status: string;
}

interface AnalyticsData {
  success: boolean;
  data: {
    overview: DashboardStats;
    top_posts: TopPost[];
    engagement_trend: EngagementTrendItem[];
    best_posting_times: BestPostingTime[];
  };
  last_sync_at: string | null;
}

const Dashboard: React.FC = () => {
  const {
    isInstagramConnected,
    setInstagramConnected,
    isSyncing,
    setSyncing,
    lastSync,
    setLastSync,
    setSyncCompleted
  } = useAuth();

  const location = useLocation();
  const navigate = useNavigate();
  const [loading, setLoading] = useState<boolean>(true);
  const [stats, setStats] = useState<DashboardStats>({
    follower_count: 0,
    profile_views: 0,
    reach: 0,
    impressions: 0,
    engagement_rate: 0,
    total_posts: 0
  });
  const [topPosts, setTopPosts] = useState<TopPost[]>([]);
  const [engagementTrend, setEngagementTrend] = useState<EngagementTrendItem[]>([]);
  const [bestTimes, setBestTimes] = useState<BestPostingTime[]>([]);
  const [scheduledPosts, setScheduledPosts] = useState<ScheduledPost[]>([]);
  const [lastSyncAt, setLastSyncAt] = useState<string | null>(null);
  const [instagramAccountId, setInstagramAccountId] = useState<number | null>(null);
  const hasInitialFetched = useRef(false);

  const checkInstagramStatus = useCallback(async (): Promise<boolean> => {
    const token = localStorage.getItem('authToken');
    if (!token) return false;

    try {
      const response = await fetch('http://localhost:8000/instagram/status', {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.ok) {
        const data = await response.json();
        setInstagramConnected(data.connected);

        // Guardar instagram_account_id para usarlo en sync
        if (data.instagram_account_id) {
          setInstagramAccountId(data.instagram_account_id);
        }

        if (data.expired) {
          alert('Tu token de Instagram ha expirado. Por favor vuelve a conectar tu cuenta.');
        }

        return data.connected; // ← Retornar el valor
      }
      return false;
    } catch (error) {
      console.error('Error al verificar estado de Instagram:', error);
      return false;
    }
  }, [setInstagramConnected]);

  const fetchDashboardStats = useCallback(async (connected: boolean = false) => {
    const token = localStorage.getItem('authToken');
    if (!token) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);

      // Fetch Instagram analytics overview (from cache - fast!)
      if (connected) {
        const instagramResponse = await fetch('http://localhost:8000/api/analytics/cached-overview', {
          headers: { 'Authorization': `Bearer ${token}` }
        });

        if (instagramResponse.ok) {
          const data = await instagramResponse.json();

          if (data.success && data.data) {
            setStats({
              follower_count: data.data.overview.follower_count || 0,
              profile_views: data.data.overview.profile_views || 0,
              reach: data.data.overview.reach || 0,
              impressions: data.data.overview.impressions || 0,
              engagement_rate: data.data.overview.engagement_rate || 0,
              total_posts: data.data.overview.total_posts || 0
            });
            setTopPosts(data.data.top_posts || []);
            setEngagementTrend(data.data.engagement_trend || []);
            setBestTimes(data.data.best_posting_times || []);
            setLastSyncAt(data.last_sync_at); // Guardar timestamp de última sincronización
          }
        } else {
          console.error('Error cargando analytics de Instagram:', instagramResponse.status);
        }
      }

      // Fetch scheduled posts from local database
      const postsResponse = await fetch('http://localhost:8000/posts', {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (postsResponse.ok) {
        const posts = await postsResponse.json();
        const upcoming = (posts || [])
          .filter((p: any) => p.status === 'scheduled')
          .slice(0, 5);
        setScheduledPosts(upcoming);
      } else {
        console.error('Error cargando posts');
      }
    } catch (error) {
      console.error('Error cargando dashboard:', error);
    } finally {
      setLoading(false);
    }
  }, []); // Sin dependencias, ahora recibe `connected` como parámetro

  const handleSync = useCallback(async () => {
    if (isSyncing || (lastSync && new Date().getTime() - lastSync.getTime() < 5 * 60 * 1000)) {
      return;
    }

    const token = localStorage.getItem('authToken');
    if (!token || !instagramAccountId) return;

    setSyncing(true);
    try {
      // 1. Sincronizar posts básicos + datos del perfil (followers, username, etc.)
      const postsResponse = await fetch(`http://localhost:8000/instagram/sync`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (!postsResponse.ok) {
        console.error('Error al sincronizar posts de Instagram');
        setLastSync(new Date());
        return;
      }

      // 2. Sincronizar métricas de performance (likes, comments, reach, etc.)
      const metricsResponse = await fetch(`http://localhost:8000/api/analytics/sync/${instagramAccountId}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (metricsResponse.ok) {
        setLastSync(new Date());
        setSyncCompleted(0);
        // Esperar un momento para que el background task procese los datos
        setTimeout(() => {
          fetchDashboardStats(true); // Refresh stats after sync
        }, 2000);
      } else {
        console.error('Error al sincronizar métricas de Instagram');
        setLastSync(new Date());
      }
    } catch (error) {
      console.error('Error en la sincronización:', error);
      setLastSync(new Date());
    } finally {
      setSyncing(false);
    }
  }, [isSyncing, lastSync, setSyncing, setLastSync, setSyncCompleted, fetchDashboardStats, instagramAccountId]);

  useEffect(() => {
    if (hasInitialFetched.current) return;
    hasInitialFetched.current = true;

    const initDashboard = async () => {
      const connected = await checkInstagramStatus(); // Obtener el valor
      await fetchDashboardStats(connected);  // Pasarlo como parámetro
    };

    initDashboard();
  }, [checkInstagramStatus, fetchDashboardStats]);

  useEffect(() => {
    const queryParams = new URLSearchParams(location.search);
    if (queryParams.get('instagram_connected') === 'true') {
      setInstagramConnected(true);
      handleSync();
    }
  }, [location, setInstagramConnected, handleSync]);

  const handleConnectInstagram = async () => {
    const token = localStorage.getItem('authToken');
    if (!token) {
      alert('Debes iniciar sesión en SocialLab primero para conectar Instagram.');
      return;
    }
    try {
      window.location.href = `http://localhost:8000/instagram/login?token=${token}`;
    } catch (error) {
      console.error('Error en handleConnectInstagram:', error);
      alert('Ocurrió un error al intentar conectar con Instagram.');
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('es-ES', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
  };

  const formatNumber = (num: number) => {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
  };

  const formatTimeAgo = (dateStr: string | null): string => {
    if (!dateStr) return 'Nunca';

    const now = new Date();
    const syncDate = new Date(dateStr);
    const diffMs = now.getTime() - syncDate.getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffMins < 1) return 'Hace unos segundos';
    if (diffMins === 1) return 'Hace 1 minuto';
    if (diffMins < 60) return `Hace ${diffMins} minutos`;
    if (diffHours === 1) return 'Hace 1 hora';
    if (diffHours < 24) return `Hace ${diffHours} horas`;
    if (diffDays === 1) return 'Hace 1 día';
    return `Hace ${diffDays} días`;
  };

  return (
    <div className="dashboard-container">
      {/* Header with Stats */}
      <div className="dashboard-header">
        <div className="header-top">
          <h1>Dashboard - SocialLab</h1>
          <div className="header-actions">
            {!isInstagramConnected ? (
              <button className="btn-connect-instagram" onClick={handleConnectInstagram}>
                <i className="bi bi-instagram me-2"></i>
                Conectar Instagram
              </button>
            ) : (
              <div className="sync-section">
                {lastSyncAt && (
                  <small className="text-muted" style={{ marginRight: '12px' }}>
                    <i className="bi bi-clock-history"></i> {formatTimeAgo(lastSyncAt)}
                  </small>
                )}
                <button
                  className="btn-sync"
                  onClick={handleSync}
                  disabled={isSyncing}
                >
                  <i className={`bi ${isSyncing ? 'bi-arrow-repeat' : 'bi-arrow-clockwise'} me-2`}></i>
                  {isSyncing ? 'Sincronizando...' : 'Sincronizar'}
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="dashboard-stats">
          <div className="stat-card">
            <div className="stat-icon">
              <i className="bi bi-people"></i>
            </div>
            <div className="stat-content">
              <span className="stat-value">{formatNumber(stats.follower_count)}</span>
              <span className="stat-label">Seguidores</span>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon">
              <i className="bi bi-eye"></i>
            </div>
            <div className="stat-content">
              <span className="stat-value">{formatNumber(stats.profile_views)}</span>
              <span className="stat-label">Vistas Perfil</span>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon">
              <i className="bi bi-broadcast"></i>
            </div>
            <div className="stat-content">
              <span className="stat-value">{formatNumber(stats.reach)}</span>
              <span className="stat-label">Alcance</span>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon">
              <i className="bi bi-heart"></i>
            </div>
            <div className="stat-content">
              <span className="stat-value">{stats.engagement_rate.toFixed(1)}%</span>
              <span className="stat-label">Engagement</span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Dashboard Content */}
      {!isInstagramConnected ? (
        <div className="dashboard-content">
          <div className="alert alert-info">
            <i className="bi bi-info-circle me-2"></i>
            Conecta tu cuenta de Instagram para ver insights y análisis detallados
          </div>
        </div>
      ) : loading ? (
        <div className="dashboard-loading">
          <div className="spinner"></div>
          <p>Cargando datos de Instagram...</p>
        </div>
      ) : (
        <div className="dashboard-content">
          {/* Two Column Layout */}
          <div className="dashboard-grid">
            {/* Left Column */}
            <div className="dashboard-column">
              {/* Engagement Trend */}
              <div className="dashboard-section">
                <h3><i className="bi bi-graph-up me-2"></i>Tendencia de Engagement (último año)</h3>
                <div className="trend-mini-chart">
                  {engagementTrend.length > 0 ? (
                    engagementTrend.map((item, index) => (
                      <div key={index} className="trend-bar-container">
                        <div
                          className="trend-bar"
                          style={{
                            height: `${(item.engagement / Math.max(...engagementTrend.map(t => t.engagement))) * 100}%`
                          }}
                          title={`${item.date}: ${item.engagement} engagement`}
                        ></div>
                        <span className="trend-label">{new Date(item.date).getDate()}</span>
                      </div>
                    ))
                  ) : (
                    <p className="text-muted">No hay datos de tendencia disponibles</p>
                  )}
                </div>
              </div>

              {/* Top Post */}
              <div className="dashboard-section">
                <h3><i className="bi bi-trophy me-2"></i>Post Destacado</h3>
                {topPosts.length > 0 ? (
                  <div className="top-post-card">
                    {topPosts[0].media_url && (
                      <img src={topPosts[0].media_url} alt="Top post" className="top-post-image" />
                    )}
                    <div className="top-post-content">
                      <p className="top-post-caption">
                        {topPosts[0].caption.substring(0, 120)}{topPosts[0].caption.length > 120 ? '...' : ''}
                      </p>
                      <div className="top-post-metrics">
                        <span><i className="bi bi-heart-fill"></i> {formatNumber(topPosts[0].likes)}</span>
                        <span><i className="bi bi-chat-fill"></i> {formatNumber(topPosts[0].comments)}</span>
                        <span><i className="bi bi-eye-fill"></i> {formatNumber(topPosts[0].impressions)}</span>
                      </div>
                      <a href={topPosts[0].permalink} target="_blank" rel="noopener noreferrer" className="btn-view-post">
                        Ver en Instagram <i className="bi bi-box-arrow-up-right"></i>
                      </a>
                    </div>
                  </div>
                ) : (
                  <p className="text-muted">No hay posts disponibles</p>
                )}
              </div>
            </div>

            {/* Right Column */}
            <div className="dashboard-column">
              {/* Best Posting Time */}
              <div className="dashboard-section">
                <h3><i className="bi bi-clock me-2"></i>Mejor Horario para Publicar</h3>
                {bestTimes.length > 0 ? (
                  <div className="best-time-highlight">
                    <div className="best-time-value">{bestTimes[0].hour}</div>
                    <p className="best-time-label">
                      {bestTimes[0].avg_engagement_rate.toFixed(1)}% engagement promedio
                    </p>
                    <small className="text-muted">Basado en {bestTimes[0].posts_count} posts</small>
                  </div>
                ) : (
                  <p className="text-muted">No hay suficientes datos para análisis</p>
                )}
              </div>

              {/* Upcoming Posts */}
              <div className="dashboard-section">
                <h3><i className="bi bi-calendar-event me-2"></i>Próximas Publicaciones</h3>
                {scheduledPosts.length > 0 ? (
                  <div className="upcoming-posts-list">
                    {scheduledPosts.map((post) => (
                      <div key={post.id} className="upcoming-post-item">
                        <div className="upcoming-post-icon">
                          <i className="bi bi-instagram"></i>
                        </div>
                        <div className="upcoming-post-info">
                          <p className="upcoming-post-content">
                            {post.content.substring(0, 60)}{post.content.length > 60 ? '...' : ''}
                          </p>
                          <span className="upcoming-post-date">
                            <i className="bi bi-clock"></i> {post.scheduled_at ? formatDate(post.scheduled_at) : 'Fecha no definida'}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-muted">No hay publicaciones programadas</p>
                )}
              </div>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="dashboard-section">
            <h3><i className="bi bi-lightning me-2"></i>Acciones Rápidas</h3>
            <div className="quick-actions-grid">
              <button className="quick-action-btn" onClick={() => navigate('/create-post')}>
                <i className="bi bi-plus-circle"></i>
                <span>Crear Post</span>
              </button>
              <button className="quick-action-btn" onClick={() => navigate('/generate')}>
                <i className="bi bi-stars"></i>
                <span>Generar Contenido</span>
              </button>
              <button className="quick-action-btn" onClick={() => navigate('/calendar')}>
                <i className="bi bi-calendar-event"></i>
                <span>Ver Calendario</span>
              </button>
              <button className="quick-action-btn" onClick={() => navigate('/analytics')}>
                <i className="bi bi-bar-chart-line"></i>
                <span>Analytics Completo</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
