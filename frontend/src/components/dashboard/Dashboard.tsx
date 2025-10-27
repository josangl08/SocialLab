import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import 'bootstrap-icons/font/bootstrap-icons.css';
import './Dashboard.css';

// Import new analytics components
import { KPICard } from '../analytics/cards/KPICard';
import { FollowerGrowthChart } from '../analytics/charts/FollowerGrowthChart';
import { DemographicsChart } from '../analytics/charts/DemographicsChart';
import { ActivityHeatmap } from '../analytics/charts/ActivityHeatmap';
import { TopLocations } from '../analytics/charts/TopLocations';

interface DashboardStats {
  follower_count: number;
  profile_views: number;
  reach: number;
  impressions: number;
  avg_interactions_per_post: number;
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
  score: number;
  online_followers: number;
  avg_engagement: number;
  posts_count: number;
}

interface FollowerGrowthData {
  date: string;
  follower_count: number;
  change: number;
}

interface LocationData {
  country_code?: string;
  city_name?: string;
  audience_count: number;
  percentage: number;
}

interface AudienceData {
  follower_growth: FollowerGrowthData[];
  demographics: {
    audience_gender_age: Record<string, number>;
  };
  online_hours: Record<string, number>;
  top_locations: {
    countries: LocationData[];
    cities: LocationData[];
  };
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
    audience: AudienceData;
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
  const [loading, setLoading] = useState<boolean>(true);
  const [stats, setStats] = useState<DashboardStats>({
    follower_count: 0,
    profile_views: 0,
    reach: 0,
    impressions: 0,
    avg_interactions_per_post: 0,
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

  // New audience analytics state
  const [audienceData, setAudienceData] = useState<AudienceData>({
    follower_growth: [],
    demographics: { audience_gender_age: {} },
    online_hours: {},
    top_locations: { countries: [], cities: [] }
  });

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

      // Fetch Instagram analytics overview (all time - from cache, fast!)
      if (connected) {
        const instagramResponse = await fetch('http://localhost:8000/api/analytics/overview?days=3650', {
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
              avg_interactions_per_post: data.data.overview.avg_interactions_per_post || 0,
              engagement_rate: data.data.overview.engagement_rate || 0,
              total_posts: data.data.overview.total_posts || 0
            });
            setTopPosts(data.data.top_posts || []);
            setEngagementTrend(data.data.engagement_trend || []);
            setBestTimes(data.data.best_posting_times || []);
            setLastSyncAt(data.last_sync_at);

            // Set audience data
            if (data.data.audience) {
              setAudienceData({
                follower_growth: data.data.audience.follower_growth || [],
                demographics: data.data.audience.demographics || { audience_gender_age: {} },
                online_hours: data.data.audience.online_hours || {},
                top_locations: data.data.audience.top_locations || { countries: [], cities: [] }
              });
            }
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
                  <small className="dashboard-small-text" style={{ marginRight: '12px' }}>
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

        {/* KPI Cards Grid */}
        <div className="kpi-grid">
          <KPICard
            title="Seguidores"
            value={formatNumber(stats.follower_count)}
            icon="bi-people"
            color="primary"
            loading={loading}
          />
          <KPICard
            title="Vistas Perfil"
            value={formatNumber(stats.profile_views)}
            icon="bi-eye"
            color="info"
            loading={loading}
          />
          <KPICard
            title="Alcance"
            value={formatNumber(stats.reach)}
            icon="bi-broadcast"
            color="purple"
            loading={loading}
          />
          <KPICard
            title="Engagement"
            value={`${stats.engagement_rate.toFixed(1)}%`}
            icon="bi-heart"
            color="danger"
            loading={loading}
          />
          <KPICard
            title="Avg. Interacciones"
            value={formatNumber(stats.avg_interactions_per_post)}
            icon="bi-chat-dots"
            color="success"
            loading={loading}
          />
          <KPICard
            title="Total Posts"
            value={stats.total_posts}
            icon="bi-grid-3x3"
            color="warning"
            loading={loading}
          />
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
          {/* Section 1: Follower Growth */}
          <div className="analytics-section">
            <div className="section-header">
              <h3><i className="bi bi-graph-up-arrow me-2"></i>Crecimiento de Seguidores</h3>
            </div>
            <div className="section-content">
              <FollowerGrowthChart
                data={audienceData.follower_growth}
                loading={loading}
              />
            </div>
          </div>

          {/* Section 2: Audience Analytics - Two Columns */}
          <div className="analytics-section-row">
            {/* Demographics */}
            <div className="analytics-section">
              <div className="section-header">
                <h3><i className="bi bi-people me-2"></i>Demografía de Audiencia</h3>
              </div>
              <div className="section-content">
                <DemographicsChart
                  data={audienceData.demographics}
                  loading={loading}
                />
              </div>
            </div>

            {/* Top Locations */}
            <div className="analytics-section">
              <div className="section-header">
                <h3><i className="bi bi-geo-alt me-2"></i>Ubicaciones Principales</h3>
              </div>
              <div className="section-content">
                <TopLocations
                  countries={audienceData.top_locations.countries}
                  cities={audienceData.top_locations.cities}
                  loading={loading}
                />
              </div>
            </div>
          </div>

          {/* Section 3: Activity Heatmap */}
          <div className="analytics-section">
            <div className="section-header">
              <h3><i className="bi bi-clock-history me-2"></i>Actividad de Seguidores</h3>
            </div>
            <div className="section-content">
              <ActivityHeatmap
                onlineHours={audienceData.online_hours}
                bestPostingTimes={bestTimes}
                loading={loading}
              />
            </div>
          </div>

          {/* Section 4: Top Posts & Scheduled - Two Columns */}
          <div className="analytics-section-row">
            {/* Top Post */}
            <div className="analytics-section">
              <div className="section-header">
                <h3><i className="bi bi-trophy me-2"></i>Post Destacado</h3>
              </div>
              <div className="section-content">
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
                  <p className="dashboard-empty-state">No hay posts disponibles</p>
                )}
              </div>
            </div>

            {/* Upcoming Posts */}
            <div className="analytics-section">
              <div className="section-header">
                <h3><i className="bi bi-calendar-event me-2"></i>Próximas Publicaciones</h3>
              </div>
              <div className="section-content">
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
                  <p className="dashboard-empty-state">No hay publicaciones programadas</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
