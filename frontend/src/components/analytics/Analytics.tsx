import React, { useState, useEffect } from 'react';
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
import { apiClient } from '../../api/client';
import './Analytics.css';
import { FollowerGrowthChart } from './charts/FollowerGrowthChart';
import { AccountGrowthChart, type AccountGrowth } from './charts/AccountGrowthChart';
import { DemographicsChart } from './charts/DemographicsChart';
import { ActivityHeatmap } from './charts/ActivityHeatmap';
import { TopLocations } from './charts/TopLocations';
import { KPIStrip } from './cards/KPIStrip';
import { AnalyticsPostDetailModal } from './panels/AnalyticsPostDetailModal';
import { DraftOptimizerPanel } from './panels/DraftOptimizerPanel';

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

interface BestPostingTimeRaw {
  hour: string;
  day_of_week?: string | number | null;
  score: number;
  online_followers: number;
  avg_engagement: number;
  posts_count: number;
}

interface AudienceData {
  follower_growth: FollowerGrowthData[];
  demographics: { audience_gender_age?: Record<string, number>; [key: string]: unknown };
  engaged_demographics?: { audience_gender_age?: Record<string, number>; [key: string]: unknown };
  online_hours: Record<string, number>;
  top_locations: { countries: LocationData[]; cities: LocationData[] };
  best_posting_times_raw: BestPostingTimeRaw[];
}

interface ContentTypeStats {
  count: number;
  total_likes: number;
  total_comments: number;
  total_engagement: number;
  avg_engagement: number;
  type_name: string;
}

interface TopPost {
  id: string;
  content: string;
  media_url: string;
  permalink: string;
  post_type: string;
  likes: number;
  comments: number;
  saved: number;
  views: number;
  reach: number;
  avg_watch_time_ms: number;
  total_watch_time_ms: number;
  date: string;
  outlier_multiple: number | null;
  sends_per_reach: number | null;
}

interface AnalyticsData {
  overview: {
    total_posts: number;
    follower_count: number;
    total_likes: number;
    total_comments: number;
    total_saves: number;
    reach: number;
    views: number;
    total_interactions: number;
    engagement_rate: number;
    avg_sends_per_reach: number | null;
    median_views: number | null;
    contact_button_taps: number;
    strategy_mode: 'commercial_campaign' | 'personal_storyline';
    follower_growth: AccountGrowth | null;
    growth?: {
      posts: number;
      likes: number;
      comments: number;
      engagement: number;
    };
  };
  by_content_type?: Record<string, ContentTypeStats>;
  top_posts: TopPost[];
  top_posts_by_outlier: TopPost[];
  engagement_trend: Array<{ date: string; likes: number; comments: number; engagement?: number }>;
  best_posting_times: Array<{ time: string; avg_engagement: number }>;
  best_posting_times_raw?: BestPostingTimeRaw[];
  insights?: Array<{ type: string; title: string; description: string; icon: string }>;
  audience?: AudienceData;
}

type InnerTab = 'rendimiento' | 'audiencia' | 'contenido';
type DemographicsMode = 'followers' | 'engaged';
type TimeRange = '7days' | '30days' | '90days' | 'all';
type TopPostsSort = 'engagement' | 'outlier';

const mapTopPost = (post: Record<string, any>): TopPost => ({
  id: post.id ?? '',
  content: post.caption ?? 'Sin descripción',
  media_url: post.media_url ?? '',
  permalink: post.permalink ?? '',
  post_type: post.post_type ?? 'IMAGE',
  likes: post.likes ?? 0,
  comments: post.comments ?? 0,
  saved: post.saved ?? 0,
  views: post.impressions ?? 0,
  reach: post.reach ?? 0,
  avg_watch_time_ms: post.avg_watch_time_ms ?? 0,
  total_watch_time_ms: post.total_watch_time_ms ?? 0,
  date: post.timestamp ?? new Date().toISOString(),
  outlier_multiple: post.outlier_multiple ?? null,
  sends_per_reach: post.sends_per_reach ?? null,
});

const formatPercent = (ratio: number | null) =>
  ratio == null ? '—' : `${(ratio * 100).toFixed(1).replace('.', ',')} %`;

const COLORS = ['#833ab4', '#fd1d1d', '#fcb045', '#818cf8', '#6ee7b7'];
const DAYS_MAP: Record<TimeRange, number> = { '7days': 7, '30days': 30, '90days': 90, 'all': 3650 };

const TOOLTIP_STYLE = {
  backgroundColor: 'rgba(8, 12, 24, 0.95)',
  border: '1px solid rgba(255, 255, 255, 0.08)',
  borderRadius: '10px',
  color: '#f0f2f8',
};

const Analytics: React.FC = () => {
  const [loading, setLoading] = useState<boolean>(true);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [timeRange, setTimeRange] = useState<TimeRange>('30days');
  const [activeTab, setActiveTab] = useState<InnerTab>('rendimiento');
  const [demographicsMode, setDemographicsMode] = useState<DemographicsMode>('followers');
  const [selectedPost, setSelectedPost] = useState<TopPost | null>(null);
  const [topPostsSort, setTopPostsSort] = useState<TopPostsSort>('engagement');

  useEffect(() => {
    const token = localStorage.getItem('authToken');
    if (!token) { setLoading(false); return; }

    const controller = new AbortController();
    setLoading(true);

    async function load() {
      try {
        const days = DAYS_MAP[timeRange];
        const data = await apiClient.get<{ success: boolean; data: Record<string, any> }>(
          `/api/analytics/overview?days=${days}&compare=true`,
          { signal: controller.signal }
        );

        if (!data.success || !data.data) throw new Error('No data available');

        const raw = data.data;
        const ov = raw.overview ?? {};

        setAnalytics({
          overview: {
            total_posts: ov.total_posts ?? 0,
            follower_count: ov.follower_count ?? 0,
            total_likes: ov.total_likes ?? 0,
            total_comments: ov.total_comments ?? 0,
            total_saves: ov.total_saves ?? 0,
            reach: ov.reach ?? 0,
            views: ov.views ?? ov.impressions ?? 0,
            total_interactions: ov.total_interactions ?? 0,
            engagement_rate: ov.engagement_rate ?? 0,
            avg_sends_per_reach: ov.avg_sends_per_reach ?? null,
            median_views: ov.median_views ?? null,
            contact_button_taps: ov.contact_button_taps ?? 0,
            strategy_mode: ov.strategy_mode ?? 'personal_storyline',
            follower_growth: ov.follower_growth ?? null,
            growth: ov.growth,
          },
          by_content_type: raw.by_content_type ?? {},
          top_posts: (raw.top_posts ?? []).map(mapTopPost),
          top_posts_by_outlier: (raw.top_posts_by_outlier ?? []).map(mapTopPost),
          engagement_trend: (raw.engagement_trend ?? []).map((item: Record<string, unknown>) => ({
            date: item.date as string,
            likes: (item.likes as number) ?? 0,
            comments: (item.comments as number) ?? 0,
            engagement: (item.engagement as number) ?? 0,
          })),
          best_posting_times: (raw.best_posting_times ?? []).map((item: Record<string, unknown>) => ({
            time: (item.hour as string) ?? '00:00',
            avg_engagement: (item.avg_engagement as number) ?? 0,
          })),
          best_posting_times_raw: raw.best_posting_times ?? [],
          insights: raw.insights ?? [],
          audience: raw.audience ? {
            follower_growth: raw.audience.follower_growth ?? [],
            demographics: raw.audience.demographics ?? { audience_gender_age: {} },
            engaged_demographics: raw.audience.engaged_demographics ?? {},
            online_hours: raw.audience.online_hours ?? {},
            top_locations: raw.audience.top_locations ?? { countries: [], cities: [] },
            best_posting_times_raw: raw.best_posting_times ?? [],
          } : undefined,
        });
      } catch (error) {
        if ((error as Error).name === 'AbortError') return;
        console.error('Error cargando analytics:', error);
        setAnalytics(null);
      } finally {
        setLoading(false);
      }
    }

    load();
    return () => controller.abort();
  }, [timeRange]);

  if (loading) {
    return (
      <div className="an-container">
        <div className="an-state-center" style={{ minHeight: '60vh' }}>
          <div className="an-spinner"></div>
          <p className="an-state-label">Cargando analytics...</p>
        </div>
      </div>
    );
  }

  if (!analytics) {
    return (
      <div className="an-container">
        <div className="an-state-center" style={{ minHeight: '60vh' }}>
          <i className="bi bi-bar-chart-line an-state-icon"></i>
          <p className="an-state-label">No hay datos de analytics disponibles</p>
          <p className="an-state-hint">Conecta tu cuenta de Instagram para ver métricas</p>
        </div>
      </div>
    );
  }

  // X-axis helpers — ~7 ticks visible for any range
  const effectiveDays = timeRange === 'all' ? 365 : DAYS_MAP[timeRange];
  const xAxisInterval = Math.max(0, Math.floor(effectiveDays / 7) - 1);
  const xAxisFormatter = (v: string) => {
    const d = new Date(v + 'T12:00:00');
    if (timeRange === '7days')
      return d.toLocaleDateString('es-ES', { weekday: 'short', day: 'numeric' });
    if (timeRange === 'all')
      return d.toLocaleDateString('es-ES', { month: 'short', year: '2-digit' });
    return d.toLocaleDateString('es-ES', { day: 'numeric', month: 'short' });
  };

  const kpiCards = [
    { title: 'Seguidores',     value: analytics.overview.follower_count.toLocaleString('es-ES'),     icon: 'people-fill',    color: 'primary' as const },
    { title: 'Alcance',        value: analytics.overview.reach.toLocaleString('es-ES'),              icon: 'broadcast',      color: 'info' as const },
    { title: 'Visualizaciones',value: analytics.overview.views.toLocaleString('es-ES'),             icon: 'eye-fill',       color: 'purple' as const },
    { title: 'Engagement',     value: `${analytics.overview.engagement_rate}%`,                     icon: 'graph-up-arrow', color: 'success' as const },
    { title: 'Interacciones',  value: analytics.overview.total_interactions.toLocaleString('es-ES'), icon: 'heart-fill',     color: 'warning' as const },
    { title: 'Guardados',      value: analytics.overview.total_saves.toLocaleString('es-ES'),        icon: 'bookmark-fill',  color: 'success' as const },
    { title: 'Sends / Reach',  value: formatPercent(analytics.overview.avg_sends_per_reach),         icon: 'send-fill',      color: 'info' as const },
    ...(analytics.overview.strategy_mode === 'commercial_campaign'
      ? [{ title: 'Toques en contacto', value: analytics.overview.contact_button_taps.toLocaleString('es-ES'), icon: 'telephone-fill', color: 'warning' as const }]
      : []),
  ];

  const shownTopPosts = topPostsSort === 'outlier' ? analytics.top_posts_by_outlier : analytics.top_posts;

  const contentTypeChartData = analytics.by_content_type
    ? Object.entries(analytics.by_content_type).map(([, stats]) => ({
        name: stats.type_name,
        engagement: stats.avg_engagement,
        posts: stats.count,
      }))
    : [];

  const periodLabel = timeRange === 'all'
    ? 'todos los tiempos'
    : `últimos ${DAYS_MAP[timeRange]} días`;

  return (
    <div className="an-container">
      {/* ── Header ──────────────────────────────────────── */}
      <div className="an-header">
        <div className="an-header-info">
          <h2 className="an-header-title">
            <i className="bi bi-bar-chart-line"></i>
            Analytics
          </h2>
          <p className="an-header-sub">
            Métricas de rendimiento · {analytics.overview.total_posts} publicaciones · {periodLabel}
          </p>
        </div>
        <div className="an-time-range">
          {(['7days', '30days', '90days', 'all'] as TimeRange[]).map((range) => (
            <button
              key={range}
              className={`an-time-btn${timeRange === range ? ' active' : ''}`}
              onClick={() => setTimeRange(range)}
            >
              {range === '7days' ? '7d' : range === '30days' ? '30d' : range === '90days' ? '90d' : 'Todo'}
            </button>
          ))}
        </div>
      </div>

      {/* ── KPI Strip ───────────────────────────────────── */}
      <div className="an-kpi-area">
        <KPIStrip cards={kpiCards} />
      </div>

      {analytics.overview.total_posts === 0 && (
        <div className="an-notice">
          <i className="bi bi-info-circle"></i>
          {timeRange === 'all'
            ? 'No hay publicaciones registradas — los datos de audiencia y seguidores siguen disponibles abajo.'
            : `No hay publicaciones en los últimos ${DAYS_MAP[timeRange]} días — los datos de audiencia y seguidores siguen disponibles abajo.`}
        </div>
      )}

      {/* ── Inner Tab Navigation ────────────────────────── */}
      <div className="an-inner-tabs-container">
        <div className="an-inner-tabs">
          {([
            { key: 'rendimiento', label: 'Rendimiento', icon: 'graph-up' },
            { key: 'audiencia',   label: 'Audiencia',   icon: 'people' },
            { key: 'contenido',   label: 'Contenido',   icon: 'collection' },
          ] as { key: InnerTab; label: string; icon: string }[]).map(({ key, label, icon }) => (
            <button
              key={key}
              className={`an-inner-tab${activeTab === key ? ' active' : ''}`}
              onClick={() => setActiveTab(key)}
            >
              <i className={`bi bi-${icon}`}></i>
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Tab: Rendimiento ────────────────────────────── */}
      {activeTab === 'rendimiento' && (
        <div className="an-content animate-fade-in">
          <div className="an-section">
            <div className="an-section-title">
              <i className="bi bi-activity"></i>
              Tendencia de Engagement
            </div>
            <div className="an-chart-body">
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={analytics.engagement_trend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={xAxisFormatter}
                    interval={xAxisInterval}
                    stroke="rgba(255,255,255,0.08)"
                    tick={{ fill: 'rgba(240,242,248,0.45)', fontSize: 11 }}
                  />
                  <YAxis
                    stroke="rgba(255,255,255,0.08)"
                    tick={{ fill: 'rgba(240,242,248,0.45)', fontSize: 11 }}
                  />
                  <Tooltip
                    contentStyle={TOOLTIP_STYLE}
                    labelFormatter={(v) => new Date(v).toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long' })}
                  />
                  <Legend />
                  <Line type="monotone" dataKey="likes"      stroke="#fd1d1d" strokeWidth={2} name="Likes"        dot={false} activeDot={{ r: 5 }} />
                  <Line type="monotone" dataKey="comments"   stroke="#833ab4" strokeWidth={2} name="Comentarios"  dot={false} activeDot={{ r: 5 }} />
                  <Line type="monotone" dataKey="engagement" stroke="#fcb045" strokeWidth={2} name="Engagement"   dot={false} activeDot={{ r: 5 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {analytics.audience && (
            <>
              <div className="an-section">
                <div className="an-section-title">
                  <i className="bi bi-person-lines-fill"></i>
                  Crecimiento de Seguidores
                </div>
                <div className="an-chart-body">
                  <FollowerGrowthChart
                    data={analytics.audience.follower_growth}
                    loading={loading}
                    timeRange={timeRange}
                  />
                </div>
              </div>

              <div className="an-section">
                <div className="an-section-title">
                  <i className="bi bi-arrow-down-up"></i>
                  Altas y Bajas de Seguidores
                </div>
                <div className="an-chart-body">
                  <AccountGrowthChart growth={analytics.overview.follower_growth} />
                </div>
              </div>

              <div className="an-section">
                <div className="an-section-title">
                  <i className="bi bi-clock"></i>
                  Actividad de Seguidores
                </div>
                <ActivityHeatmap
                  onlineHours={analytics.audience.online_hours}
                  bestPostingTimes={analytics.audience.best_posting_times_raw}
                  loading={loading}
                />
              </div>
            </>
          )}
        </div>
      )}

      {/* ── Tab: Audiencia ──────────────────────────────── */}
      {activeTab === 'audiencia' && analytics.audience && (
        <div className="an-content animate-fade-in">
          <div className="an-section">
            <div className="an-section-title-row">
              <div className="an-section-title">
                <i className="bi bi-bar-chart-steps"></i>
                Demografía
              </div>
              <div className="an-demographics-toggle">
                <button
                  className={`an-demographics-pill${demographicsMode === 'followers' ? ' active' : ''}`}
                  onClick={() => setDemographicsMode('followers')}
                >
                  Seguidores
                </button>
                <button
                  className={`an-demographics-pill${demographicsMode === 'engaged' ? ' active' : ''}`}
                  onClick={() => setDemographicsMode('engaged')}
                >
                  Audiencia Activa
                </button>
              </div>
            </div>
            <div className="an-section-body">
              <DemographicsChart
                data={
                  demographicsMode === 'followers'
                    ? analytics.audience.demographics as { audience_gender_age: Record<string, number> }
                    : (analytics.audience.engaged_demographics as { audience_gender_age: Record<string, number> } | null) ?? null
                }
                loading={loading}
                emptyMessage={
                  demographicsMode === 'engaged'
                    ? 'Datos de audiencia activa no disponibles — sincroniza para ver'
                    : undefined
                }
              />
            </div>
          </div>

          <div className="an-section">
            <div className="an-section-title">
              <i className="bi bi-geo-alt"></i>
              Ubicaciones Principales
            </div>
            <div className="an-section-body">
              <TopLocations
                countries={analytics.audience.top_locations.countries}
                cities={analytics.audience.top_locations.cities}
                loading={loading}
              />
            </div>
          </div>
        </div>
      )}

      {/* ── Tab: Contenido ──────────────────────────────── */}
      {activeTab === 'contenido' && (
        <div className="an-content animate-fade-in">
          {contentTypeChartData.length > 0 && (
            <div className="an-section">
              <div className="an-section-title">
                <i className="bi bi-layers"></i>
                Rendimiento por Tipo de Contenido
              </div>
              <div className="an-dashboard-grid">
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={contentTypeChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                    <XAxis dataKey="name" stroke="rgba(255,255,255,0.08)" tick={{ fill: 'rgba(240,242,248,0.45)', fontSize: 11 }} />
                    <YAxis stroke="rgba(255,255,255,0.08)" tick={{ fill: 'rgba(240,242,248,0.45)', fontSize: 11 }} />
                    <Tooltip contentStyle={TOOLTIP_STYLE} />
                    <Bar dataKey="engagement" fill="#833ab4" name="Engagement Promedio" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
                <div style={{ padding: '20px 0' }}>
                  {contentTypeChartData.map((item, index) => (
                    <div key={index} style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
                      <div style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: COLORS[index % COLORS.length], flexShrink: 0 }}></div>
                      <div>
                        <div style={{ color: '#f0f2f8', fontSize: '0.85rem', fontWeight: 600 }}>{item.name}</div>
                        <div style={{ color: 'rgba(240,242,248,0.45)', fontSize: '0.75rem' }}>
                          {item.posts} posts · {item.engagement.toFixed(1)} engagement
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          <div className="an-section">
            <div className="an-section-title-row">
              <div className="an-section-title">
                <i className="bi bi-trophy"></i>
                Posts Más Exitosos
              </div>
              <div className="an-demographics-toggle" aria-label="Ordenar posts">
                <button
                  className={`an-demographics-pill${topPostsSort === 'engagement' ? ' active' : ''}`}
                  onClick={() => setTopPostsSort('engagement')}
                >
                  Engagement
                </button>
                <button
                  className={`an-demographics-pill${topPostsSort === 'outlier' ? ' active' : ''}`}
                  onClick={() => setTopPostsSort('outlier')}
                >
                  Outlier Multiple
                </button>
              </div>
            </div>
            <div className="an-top-posts-grid">
              {shownTopPosts.map((post) => (
                <div
                  key={post.id}
                  className="an-post-card"
                  onClick={() => setSelectedPost(post)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && setSelectedPost(post)}
                >
                  {post.media_url ? (
                    <img src={post.media_url} alt="Post" className="an-post-card-thumb" />
                  ) : (
                    <div className="an-post-card-thumb" style={{ background: 'rgba(255,255,255,0.04)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <i className="bi bi-image" style={{ color: 'rgba(255,255,255,0.2)', fontSize: '2rem' }}></i>
                    </div>
                  )}
                  <div className="an-post-card-body">
                    <p className="an-post-card-caption">{post.content || 'Sin descripción'}</p>
                    <div className="an-post-card-stats">
                      <span><i className="bi bi-heart-fill me-1" style={{ color: '#fd1d1d' }}></i>{post.likes}</span>
                      <span><i className="bi bi-chat-fill me-1" style={{ color: '#833ab4' }}></i>{post.comments}</span>
                      <span><i className="bi bi-bookmark-fill me-1" style={{ color: '#6ee7b7' }}></i>{post.saved}</span>
                    </div>
                    <div className="an-post-card-stats an-post-card-metrics">
                      <span title="Vistas frente a la mediana de 90 días">
                        {post.outlier_multiple != null
                          ? `${post.outlier_multiple.toString().replace('.', ',')}×`
                          : 'Datos insuficientes'}
                      </span>
                      <span title="Sends per Reach">
                        <i className="bi bi-send-fill me-1"></i>{formatPercent(post.sends_per_reach)}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {analytics.best_posting_times.length > 0 && (
            <div className="an-section">
              <div className="an-section-title">
                <i className="bi bi-alarm"></i>
                Mejores Horarios para Publicar
              </div>
              <div className="an-chart-body">
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={analytics.best_posting_times} layout="vertical" margin={{ left: 10, right: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                    <XAxis type="number" stroke="rgba(255,255,255,0.08)" tick={{ fill: 'rgba(240,242,248,0.45)', fontSize: 11 }} />
                    <YAxis type="category" dataKey="time" stroke="rgba(255,255,255,0.08)" tick={{ fill: 'rgba(240,242,248,0.45)', fontSize: 11 }} />
                    <Tooltip contentStyle={TOOLTIP_STYLE} />
                    <Bar dataKey="avg_engagement" fill="#6ee7b7" name="Engagement Promedio" radius={[0, 6, 6, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Draft Optimizer ─────────────────────────────── */}
      <DraftOptimizerPanel
        bestPostingTimesRaw={analytics.best_posting_times_raw}
        byContentType={analytics.by_content_type}
      />

      {/* ── Post Detail Modal ───────────────────────────── */}
      <AnalyticsPostDetailModal
        isOpen={selectedPost !== null}
        onClose={() => setSelectedPost(null)}
        post={selectedPost ? {
          id: selectedPost.id,
          caption: selectedPost.content,
          media_url: selectedPost.media_url,
          permalink: selectedPost.permalink,
          post_type: selectedPost.post_type,
          likes: selectedPost.likes,
          comments: selectedPost.comments,
          saved: selectedPost.saved,
          views: selectedPost.views,
          reach: selectedPost.reach,
          avg_watch_time_ms: selectedPost.avg_watch_time_ms,
          total_watch_time_ms: selectedPost.total_watch_time_ms,
        } : null}
      />
    </div>
  );
};

export default Analytics;
