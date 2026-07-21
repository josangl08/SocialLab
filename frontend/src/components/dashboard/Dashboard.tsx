import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import 'bootstrap-icons/font/bootstrap-icons.css';
import { apiClient } from '../../api/client';
import './Dashboard.css';

import { KPICard } from '../analytics/cards/KPICard';
import { AgentStatusCard } from '../../features/agent/AgentStatusCard';
import { CalendarProposalView } from '../../features/agent/CalendarProposalView';

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
  has_stats?: boolean;
}

interface ScheduledPost {
  id: number;
  content: string;
  post_type: string;
  scheduled_at: string | null;
  status: string;
  media_url: string | null;
}

interface EngagementTrendItem {
  date: string;
  likes: number;
  comments: number;
  engagement: number;
}

interface BestTimeSlot {
  hour: string;
  avg_engagement: number;
  posts_count: number;
}

interface BestTimesByWeekday {
  [weekday: string]: BestTimeSlot[];
}

const WEEKDAYS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];

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
  const [recentPostsData, setRecentPostsData] = useState<TopPost[]>([]);
  const [scheduledPosts, setScheduledPosts] = useState<ScheduledPost[]>([]);
  const [lastSyncAt, setLastSyncAt] = useState<string | null>(null);
  const [instagramAccountId, setInstagramAccountId] = useState<number | null>(null);
  const [accounts, setAccounts] = useState<Array<{
    id: number;
    username: string | null;
    account_name: string | null;
    profile_picture_url: string | null;
    connected: boolean;
    expired: boolean;
  }>>([]);
  const [engagementTrend, setEngagementTrend] = useState<EngagementTrendItem[]>([]);
  const [bestTimes, setBestTimes] = useState<BestTimeSlot[]>([]);
  const [bestTimesByWeekday, setBestTimesByWeekday] = useState<BestTimesByWeekday>({});
  const [selectedWeekday, setSelectedWeekday] = useState<number>(() => {
    const jsDay = new Date().getDay();
    return jsDay === 0 ? 6 : jsDay - 1; // JS Sunday(0) → Python 6, JS Mon(1) → Python 0
  });
  const hasInitialFetched = useRef(false);

  const checkInstagramStatus = useCallback(async (): Promise<{ connected: boolean; accountId: number | null }> => {
    const token = localStorage.getItem('authToken');
    if (!token) return { connected: false, accountId: null };

    try {
      const accountList = await apiClient.get<Array<{
        id: number; username: string | null; account_name: string | null;
        profile_picture_url: string | null; connected: boolean; expired: boolean;
      }>>('/instagram/status');
      setAccounts(accountList);

      const connectedAccounts = accountList.filter((a) => a.connected);
      const isConnected = connectedAccounts.length > 0;
      setInstagramConnected(isConnected);

      const resolvedAccountId = isConnected ? connectedAccounts[0].id : null;
      if (resolvedAccountId !== null) {
        setInstagramAccountId(resolvedAccountId);
      }

      const expiredAccounts = accountList.filter((a) => a.expired);
      if (expiredAccounts.length > 0) {
        alert('Uno o más tokens de Instagram han expirado. Por favor vuelve a conectar las cuentas afectadas.');
      }

      return { connected: isConnected, accountId: resolvedAccountId };
    } catch (error) {
      console.error('Error al verificar estado de Instagram:', error);
      return { connected: false, accountId: null };
    }
  }, [setInstagramConnected]);

  const fetchDashboardStats = useCallback(async (connected: boolean = false, resolvedAccountId?: number | null) => {
    const token = localStorage.getItem('authToken');
    if (!token) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);

      if (connected) {
        const effectiveAccountId = resolvedAccountId !== undefined ? resolvedAccountId : instagramAccountId;
        const accountParam = effectiveAccountId ? `&instagram_account_id=${effectiveAccountId}` : '';
        try {
          const data = await apiClient.get<{ success: boolean; data: any; last_sync_at: string | null }>(
            `/api/analytics/overview?days=3650${accountParam}`
          );

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
            setRecentPostsData(data.data.recent_posts || []);
            setLastSyncAt(data.last_sync_at);
            setEngagementTrend(data.data.engagement_trend || []);
            setBestTimes(data.data.best_posting_times || []);
            setBestTimesByWeekday(data.data.best_times_by_weekday || {});
          }
        } catch (error) {
          console.error('Error cargando analytics de Instagram:', error);
        }
      }

      try {
        const posts = await apiClient.get<ScheduledPost[]>('/api/posts');
        const upcoming = (posts || [])
          .filter((p) => p.status === 'scheduled')
          .slice(0, 5);
        setScheduledPosts(upcoming);
      } catch {
        console.error('Error cargando posts');
      }
    } catch (error) {
      console.error('Error cargando dashboard:', error);
    } finally {
      setLoading(false);
    }
  }, [instagramAccountId]); // instagramAccountId usado como fallback cuando resolvedAccountId no se pasa

  const handleSync = useCallback(async () => {
    if (isSyncing || (lastSync && new Date().getTime() - lastSync.getTime() < 5 * 60 * 1000)) {
      return;
    }

    const token = localStorage.getItem('authToken');
    if (!token || !instagramAccountId) return;

    setSyncing(true);
    try {
      const syncParam = instagramAccountId ? `?instagram_account_id=${instagramAccountId}` : '';
      try {
        await apiClient.get(`/instagram/sync${syncParam}`);
      } catch {
        console.error('Error al sincronizar posts de Instagram');
        setLastSync(new Date());
        return;
      }

      try {
        await apiClient.post(`/api/analytics/sync/${instagramAccountId}`);
        setLastSync(new Date());
        setSyncCompleted(0);
        setTimeout(() => {
          fetchDashboardStats(true);
        }, 2000);
      } catch {
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
      const { connected, accountId } = await checkInstagramStatus();
      await fetchDashboardStats(connected, accountId);
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
      window.location.href = apiClient.getUrl(`/instagram/login?token=${token}`);
    } catch (error) {
      console.error('Error en handleConnectInstagram:', error);
      alert('Ocurrió un error al intentar conectar con Instagram.');
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('es-ES', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
  };

  const formatNumber = (num: number | null | undefined): string => {
    if (num == null) return '0';
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

  const getPostTypeIcon = (postType: string): string => {
    if (postType === 'reel') return 'bi-camera-video';
    if (postType === 'carousel') return 'bi-collection';
    return 'bi-image';
  };

  const sparkline = engagementTrend.slice(-7).map(d => d.engagement);
  const currentAccount =
    accounts.find(a => a.id === instagramAccountId) ??
    accounts.find(a => a.connected);
  const totalInteractions = Math.round(stats.avg_interactions_per_post * stats.total_posts);

  return (
    <div className="dashboard-container">

      {/* ─── Zone 1: Profile Banner ─────────────────── */}
      <div className="sl-banner">
        {isInstagramConnected && currentAccount ? (
          <div className="sl-banner-inner">
            <div className="sl-banner-left">
              <div className="sl-avatar-ring">
                <div className="sl-avatar-inner">
                  {currentAccount.profile_picture_url ? (
                    <img
                      src={currentAccount.profile_picture_url}
                      alt="avatar"
                      className="sl-avatar-img"
                    />
                  ) : (
                    <div className="sl-avatar-initials">
                      {(currentAccount.username ?? currentAccount.account_name ?? 'U')[0].toUpperCase()}
                    </div>
                  )}
                </div>
              </div>
              <div className="sl-banner-info">
                <div className="sl-banner-username">
                  @{currentAccount.username ?? currentAccount.account_name ?? `Cuenta ${currentAccount.id}`}
                </div>
                {currentAccount.account_name && currentAccount.username && (
                  <div className="sl-banner-name">{currentAccount.account_name}</div>
                )}
                <div className="sl-connected-badge">
                  <span className="sl-connected-dot"></span>
                  Conectado
                </div>
              </div>
            </div>

            <div className="sl-banner-right">
              {accounts.length > 1 && (
                <select
                  className="sl-account-select"
                  value={instagramAccountId ?? ''}
                  onChange={(e) => setInstagramAccountId(Number(e.target.value))}
                >
                  {accounts.filter(a => a.connected).map(account => (
                    <option key={account.id} value={account.id}>
                      @{account.username ?? account.account_name ?? `Cuenta ${account.id}`}
                    </option>
                  ))}
                </select>
              )}
              {lastSyncAt && (
                <span className="sl-sync-time">
                  <i className="bi bi-clock-history"></i>
                  {formatTimeAgo(lastSyncAt)}
                </span>
              )}
              <button
                className={`sl-sync-btn${isSyncing ? ' syncing' : ''}`}
                onClick={handleSync}
                disabled={isSyncing}
              >
                <i className="bi bi-arrow-clockwise"></i>
                {isSyncing ? 'Sincronizando...' : 'Sincronizar'}
              </button>
            </div>
          </div>
        ) : (
          <div className="sl-connect-cta">
            <button className="sl-connect-btn" onClick={handleConnectInstagram}>
              <i className="bi bi-instagram me-2"></i>
              Conectar Instagram
            </button>
            <p className="sl-connect-hint">Conecta tu cuenta para ver analytics y programar contenido</p>
          </div>
        )}
      </div>

      {/* ─── Zone 2: KPI Grid ───────────────────────── */}
      <div className="sl-kpi-section">
        <div className="sl-kpi-grid">
          <KPICard
            title="Seguidores"
            value={formatNumber(stats.follower_count)}
            icon="people"
            color="primary"
            loading={loading}
            sparklineData={sparkline}
            sparklineColor="#a5b4fc"
          />
          <KPICard
            title="Alcance"
            value={formatNumber(stats.reach)}
            icon="broadcast"
            color="purple"
            loading={loading}
            sparklineData={sparkline}
            sparklineColor="#c4b5fd"
          />
          <KPICard
            title="Engagement"
            value={`${stats.engagement_rate.toFixed(1)}%`}
            icon="heart"
            color="danger"
            loading={loading}
            sparklineData={sparkline}
            sparklineColor="#fca5a5"
          />
          <KPICard
            title="Interacciones"
            value={formatNumber(totalInteractions)}
            icon="chat-dots"
            color="success"
            loading={loading}
            sparklineData={sparkline}
            sparklineColor="#6ee7b7"
          />
        </div>
      </div>

      {/* ─── Zone 3: Two-column content ─────────────── */}
      {isInstagramConnected && (
        loading ? (
          <div className="sl-loading">
            <div className="sl-spinner"></div>
            <p>Cargando datos de Instagram...</p>
          </div>
        ) : (
          <div className="sl-content">
            <div className="row g-4">

              {/* ── Left Column: AI & Planning ───────── */}
              <div className="col-12 col-lg-6">
                {instagramAccountId !== null && (
                  <>
                    <div className="mb-4">
                      <AgentStatusCard accountId={instagramAccountId} />
                    </div>
                    <div className="mb-4">
                      <CalendarProposalView accountId={instagramAccountId} />
                    </div>
                  </>
                )}

                <div className="sl-panel">
                  <div className="sl-panel-header">
                    <i className="bi bi-calendar-event"></i>
                    Próximas Publicaciones
                    {scheduledPosts.length > 0 && (
                      <span className="sl-panel-count">{scheduledPosts.length}</span>
                    )}
                  </div>
                  <div className="sl-panel-body sl-panel-body--compact">
                    {scheduledPosts.length > 0 ? (
                      <div className="sl-sched-list">
                        {scheduledPosts.map((post) => (
                          <div key={post.id} className="sl-sched-card">
                            <div className="sl-sched-thumb">
                              {post.media_url ? (
                                <img
                                  src={post.media_url}
                                  alt="preview"
                                  className="sl-sched-thumb-img"
                                />
                              ) : (
                                <div className="sl-sched-thumb-empty">
                                  <i className={`bi ${getPostTypeIcon(post.post_type)}`}></i>
                                </div>
                              )}
                              {(post.post_type === 'reel' || post.post_type === 'video') && (
                                <div className="sl-sched-play-badge">
                                  <i className="bi bi-play-fill"></i>
                                </div>
                              )}
                              {post.post_type === 'carousel' && (
                                <div className="sl-sched-play-badge">
                                  <i className="bi bi-collection"></i>
                                </div>
                              )}
                            </div>
                            <div className="sl-sched-info">
                              <div className="sl-sched-meta">
                                <span className="sl-sched-type">
                                  <i className={`bi ${getPostTypeIcon(post.post_type)}`}></i>
                                  {post.post_type}
                                </span>
                                <span className="sl-sched-status">Programado</span>
                              </div>
                              <p className="sl-sched-caption">
                                {post.content.substring(0, 80)}{post.content.length > 80 ? '…' : ''}
                              </p>
                              <span className="sl-sched-time">
                                <i className="bi bi-clock"></i>
                                {post.scheduled_at ? formatDate(post.scheduled_at) : 'Fecha no definida'}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="sl-empty">No hay publicaciones programadas</p>
                    )}
                  </div>
                </div>
              </div>

              {/* ── Right Column: Results ─────────────── */}
              <div className="col-12 col-lg-6">

                {/* Mejores Horarios */}
                <div className="sl-panel mb-4">
                  <div className="sl-panel-header">
                    <i className="bi bi-clock-history"></i>
                    Mejores Horarios para Publicar
                    <span className="sl-panel-header-sub">España (Madrid)</span>
                  </div>
                  <div className="sl-panel-body">
                    {Object.keys(bestTimesByWeekday).length > 0 ? (
                      <>
                        {/* TODO(human): Implementa el selector de días de la semana aquí.
                            Renderiza una fila de 7 botones usando WEEKDAYS (index 0=Lun..6=Dom).
                            Cada botón llama a setSelectedWeekday(i).
                            El botón activo es el que tiene i === selectedWeekday.
                            Si bestTimesByWeekday[String(i)] es undefined, el día no tiene datos
                            y puedes marcarlo visualmente (ej. opacidad reducida).
                            Usa las clases CSS: sl-day-tabs, sl-day-btn, active, no-data */}
                        <div className="sl-day-tabs mb-3">
                        </div>
                        {(bestTimesByWeekday[String(selectedWeekday)] ?? []).length > 0 ? (
                          (bestTimesByWeekday[String(selectedWeekday)] ?? []).map((slot, i) => {
                            const daySlots = bestTimesByWeekday[String(selectedWeekday)] ?? [];
                            const maxEngagement = daySlots[0]?.avg_engagement || 1;
                            const pct = Math.min(100, (slot.avg_engagement / maxEngagement) * 100);
                            return (
                              <div key={slot.hour} className="sl-time-slot">
                                <div className="sl-time-rank">#{i + 1}</div>
                                <div className="sl-time-label">{slot.hour}</div>
                                <div className="sl-time-bar-wrap">
                                  <div className="sl-time-bar" style={{ '--sl-bar-w': `${pct}%` } as React.CSSProperties}></div>
                                </div>
                                <div className="sl-time-score">{Math.round(slot.avg_engagement)}</div>
                              </div>
                            );
                          })
                        ) : (
                          <p className="sl-empty">Sin datos para este día — elige otro</p>
                        )}
                      </>
                    ) : bestTimes.length > 0 ? (
                      bestTimes.slice(0, 3).map((slot, i) => {
                        const maxEngagement = bestTimes[0]?.avg_engagement || 1;
                        const pct = Math.min(100, (slot.avg_engagement / maxEngagement) * 100);
                        return (
                          <div key={slot.hour} className="sl-time-slot">
                            <div className="sl-time-rank">#{i + 1}</div>
                            <div className="sl-time-label">{slot.hour}</div>
                            <div className="sl-time-bar-wrap">
                              <div className="sl-time-bar" style={{ '--sl-bar-w': `${pct}%` } as React.CSSProperties}></div>
                            </div>
                            <div className="sl-time-score">{Math.round(slot.avg_engagement)}</div>
                          </div>
                        );
                      })
                    ) : (
                      <p className="sl-empty">Datos insuficientes</p>
                    )}
                  </div>
                </div>

                {/* Carrusel Posts Recientes */}
                {recentPostsData.length > 0 && (
                  <div className="sl-panel mb-4">
                    <div className="sl-panel-header">
                      <i className="bi bi-grid-3x3"></i>
                      Posts Recientes
                    </div>
                    <div className="sl-panel-body">
                      <div className="sl-post-carousel">
                        {recentPostsData.map(post => (
                          <div key={post.id} className="sl-post-thumb">
                            {post.media_url ? (
                              <img
                                src={post.media_url}
                                alt="post reciente"
                                className="sl-post-thumb-img"
                              />
                            ) : (
                              <div className="sl-post-thumb-placeholder">
                                <i className="bi bi-image"></i>
                              </div>
                            )}
                            <div className="sl-post-thumb-overlay">
                              {post.has_stats !== false ? (
                                <>
                                  <span>
                                    <i className="bi bi-heart-fill"></i>
                                    {formatNumber(post.likes)}
                                  </span>
                                  <span>
                                    <i className="bi bi-chat-fill"></i>
                                    {formatNumber(post.comments)}
                                  </span>
                                </>
                              ) : (
                                <span className="sl-no-stats">Sin datos aún</span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* Post Destacado */}
                {topPosts.length > 0 && (
                  <div className="sl-panel">
                    <div className="sl-panel-header">
                      <i className="bi bi-trophy"></i>
                      Post Destacado
                    </div>
                    <div className="sl-panel-body">
                      <div className="sl-featured-post">
                        {topPosts[0].media_url && (
                          <img
                            src={topPosts[0].media_url}
                            alt="post destacado"
                            className="sl-featured-img"
                          />
                        )}
                        <p className="sl-featured-caption">
                          {topPosts[0].caption.substring(0, 120)}
                          {topPosts[0].caption.length > 120 ? '…' : ''}
                        </p>
                        <div className="sl-featured-metrics">
                          <span>
                            <i className="bi bi-heart-fill"></i>
                            {formatNumber(topPosts[0].likes)}
                          </span>
                          <span>
                            <i className="bi bi-chat-fill"></i>
                            {formatNumber(topPosts[0].comments)}
                          </span>
                          <span>
                            <i className="bi bi-eye-fill"></i>
                            {formatNumber(topPosts[0].impressions)}
                          </span>
                        </div>
                        <a
                          href={topPosts[0].permalink}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="sl-featured-link"
                        >
                          Ver en Instagram
                          <i className="bi bi-box-arrow-up-right"></i>
                        </a>
                      </div>
                    </div>
                  </div>
                )}

              </div>
            </div>
          </div>
        )
      )}
    </div>
  );
};

export default Dashboard;
