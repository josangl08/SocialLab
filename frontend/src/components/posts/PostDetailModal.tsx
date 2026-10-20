import React, { useEffect, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { apiClient, ApiError } from '../../api/client';
import { postOriginalUrl, postThumbnailUrl } from '../../api/media';
import type { Post, StoryMetrics, StrategyMode } from '../../types';
import { getFirstOfDayOfMonth } from '../../features/agent/AgentStrategyDrawer';
import type { MonthlyCampaign } from '../../features/agent/AgentStrategyDrawer';
import CommentTriage from '../studio/CommentTriage';
import DmFunnel from '../studio/DmFunnel';
import ScheduleZoneHint from './ScheduleZoneHint';
import { browserTimezone, formatInZones, fromDatetimeLocalValue } from '../../utils/timezone';
import './PostDetailModal.css';

interface PostDetailModalProps {
  show: boolean;
  onHide: () => void;
  post: Post | null;
  onEdit?: () => void;
  onActionSuccess?: () => void;
  onViewProposal?: () => void;
  /** Zonas de la cuenta del post (AD-6); sin ellas, la del navegador */
  zones?: { primary?: string | null; secondary?: string | null };
}

const STATUS_LABELS: Record<string, string> = {
  draft:     'Draft',
  scheduled: 'Scheduled',
  published: 'Published',
  failed:    'Failed',
};

const STATUS_ICONS: Record<string, string> = {
  draft:     'bi-pencil',
  scheduled: 'bi-clock',
  published: 'bi-check-circle-fill',
  failed:    'bi-x-circle',
};

const TYPE_ICONS: Record<string, string> = {
  reel:     'bi-camera-video',
  carousel: 'bi-collection',
  story:    'bi-layers',
};

const STORY_TYPES = new Set(['story', 'stories']);
// Una Story sigue activa (y se sincronizará) durante 24 h
const STORY_LIFETIME_MS = 24 * 60 * 60 * 1000;

const STORY_METRICS: { label: string; value: (m: StoryMetrics) => number | null | undefined }[] = [
  { label: 'Vistas',          value: m => m.views },
  { label: 'Alcance',         value: m => m.reach },
  { label: 'Me gusta',        value: m => m.likes },
  { label: 'Respuestas',      value: m => m.replies },
  { label: 'Clics en enlace', value: m => m.link_clicks },
  { label: 'Avances',         value: m => m.story_navigation?.tap_forward },
  { label: 'Retrocesos',      value: m => m.story_navigation?.tap_back },
  { label: 'Salidas',         value: m => m.story_navigation?.tap_exit },
  { label: 'Siguiente historia', value: m => m.story_navigation?.swipe_forward },
];

const formatDate = (d: string) =>
  new Date(d).toLocaleDateString('es-ES', {
    day: 'numeric', month: 'long', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });

const PostDetailModal: React.FC<PostDetailModalProps> = ({
  show, onHide, post, onEdit, onActionSuccess, onViewProposal, zones,
}) => {
  const tz = zones?.primary || browserTimezone();
  const { token } = useAuth();
  const [actionStep, setActionStep]       = useState<'idle' | 'scheduling' | 'deleting'>('idle');
  const [scheduleDate, setScheduleDate]   = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError]     = useState('');
  const [strategyMode, setStrategyMode]   = useState<StrategyMode | null>(null);
  // Vista inicial con la miniatura; el original solo al hacer clic en la imagen
  const [showOriginal, setShowOriginal]   = useState(false);
  useEffect(() => setShowOriginal(false), [post?.id, post?.media_url, post?.drive_file_id]);

  useEffect(() => {
    setActionStep('idle');
    setActionError('');
    setScheduleDate('');
  }, [post?.id, show]);

  // Métricas de la Story guardadas por el job horario (solo vienen en el detalle del post)
  const isStory = !!post && STORY_TYPES.has(post.post_type.toLowerCase());
  const [storyMetrics, setStoryMetrics] = useState<StoryMetrics | null | undefined>(undefined);
  useEffect(() => {
    setStoryMetrics(undefined);
    if (!show || !isStory || post?.status !== 'published') return;
    let active = true;
    apiClient
      .get<Post>(`/api/posts/${post?.id}`)
      .then((detail) => { if (active) setStoryMetrics(detail?.story_metrics ?? null); })
      .catch(() => { if (active) setStoryMetrics(null); });
    return () => { active = false; };
  }, [show, isStory, post?.id, post?.status]);

  // Estrategia de la campaña del mes; sin campaña → personal (AD-2)
  const accountId = post?.instagram_account_id;
  useEffect(() => {
    setStrategyMode(null);
    if (!show || !accountId) return;
    let active = true;
    const monthDate = getFirstOfDayOfMonth(new Date());
    apiClient
      .get<MonthlyCampaign | null>(`/api/agent/campaign?account_id=${accountId}&month_date=${monthDate}`)
      .then((campaign) => { if (active) setStrategyMode(campaign?.strategy_mode ?? 'personal_storyline'); })
      .catch(() => { if (active) setStrategyMode('personal_storyline'); });
    return () => { active = false; };
  }, [accountId, show]);

  useEffect(() => {
    if (!show) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onHide(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [show, onHide]);

  useEffect(() => {
    document.body.style.overflow = show ? 'hidden' : '';
    return () => { document.body.style.overflow = ''; };
  }, [show]);

  const changeStatus = async (newStatus: string, scheduledAt?: string) => {
    if (!post || !token) return;
    setActionLoading(true);
    setActionError('');
    try {
      const formData = new FormData();
      formData.append('content', post.content);
      formData.append('post_type', post.post_type);
      formData.append('status', newStatus);
      if (scheduledAt) {
        formData.append('scheduled_at', scheduledAt);
      } else if (post.scheduled_at && newStatus === 'scheduled') {
        formData.append('scheduled_at', post.scheduled_at);
      }

      await apiClient.putForm(`/api/posts/${post.id}`, formData);
      onActionSuccess?.();
      onHide();
    } catch (error) {
      setActionError(error instanceof ApiError ? error.detail : 'Error de conexión');
    } finally {
      setActionLoading(false);
    }
  };

  const deletePost = async () => {
    if (!post || !token) return;
    setActionLoading(true);
    setActionError('');
    try {
      await apiClient.delete(`/api/posts/${post.id}`);
      onActionSuccess?.();
      onHide();
    } catch (error) {
      setActionError(error instanceof ApiError ? error.detail : 'Error de conexión');
      setActionStep('idle');
    } finally {
      setActionLoading(false);
    }
  };

  const confirmSchedule = () => {
    if (!scheduleDate) return;
    changeStatus('scheduled', fromDatetimeLocalValue(scheduleDate, tz));
  };

  if (!show || !post) return null;

  const typeIcon    = TYPE_ICONS[post.post_type] ?? 'bi-image';
  const statusLabel = STATUS_LABELS[post.status] ?? post.status;
  const statusIcon  = STATUS_ICONS[post.status]  ?? 'bi-circle';
  const isImage = post.media_url?.match(/\.(jpeg|jpg|gif|png|webp|svg)(\?.*)?$/i);
  const isVideo = post.post_type === 'reel' ||
    !!post.media_url?.match(/\.(mp4|webm|ogg|mov)(\?.*)?$/i);
  // La media de una Story en el CDN de Instagram caduca: se muestra su miniatura guardada
  const storyThumbnail = isStory ? postThumbnailUrl(post, token, 640) : null;
  const storyIsLive = !!post.publication_date &&
    Date.now() - new Date(post.publication_date).getTime() < STORY_LIFETIME_MS;

  // ── Shared action fragments ─────────────────────────
  const editBtn = onEdit ? (
    <button
      className="pdm-btn pdm-btn-edit"
      onClick={() => { onHide(); onEdit(); }}
      disabled={actionLoading}
    >
      <i className="bi bi-pencil"></i>Edit
    </button>
  ) : null;

  const deleteBtn = (
    <button
      className="pdm-btn pdm-btn-delete"
      onClick={() => setActionStep('deleting')}
      disabled={actionLoading}
    >
      <i className="bi bi-trash"></i>Delete
    </button>
  );

  // ── Footer builder ──────────────────────────────────
  const renderFooter = () => {
    // Delete confirmation step
    if (actionStep === 'deleting') {
      return (
        <div className="pdm-footer">
          <p className="pdm-confirm-msg">
            <i className="bi bi-exclamation-triangle"></i>
            This action will permanently delete the post.
          </p>
          <div className="pdm-footer-row">
            <button
              className="pdm-btn pdm-btn-secondary"
              onClick={() => setActionStep('idle')}
              disabled={actionLoading}
            >
              Cancel
            </button>
            <button
              className="pdm-btn pdm-btn-delete-confirm"
              onClick={deletePost}
              disabled={actionLoading}
            >
              {actionLoading
                ? <span className="pdm-spinner"></span>
                : <><i className="bi bi-trash"></i>Delete</>
              }
            </button>
          </div>
        </div>
      );
    }

    // Scheduling / rescheduling step
    if (actionStep === 'scheduling') {
      return (
        <div className="pdm-footer">
          <div className="pdm-footer-row">
            <input
              type="datetime-local"
              className="pdm-schedule-input"
              value={scheduleDate}
              onChange={e => setScheduleDate(e.target.value)}
              autoFocus
            />
            <button
              className="pdm-btn pdm-btn-confirm"
              onClick={confirmSchedule}
              disabled={!scheduleDate || actionLoading}
            >
              {actionLoading
                ? <span className="pdm-spinner"></span>
                : <><i className="bi bi-check-lg"></i>Confirm</>
              }
            </button>
            <button
              className="pdm-btn pdm-btn-cancel-step"
              onClick={() => setActionStep('idle')}
              disabled={actionLoading}
              aria-label="Cancel"
            >
              <i className="bi bi-x-lg"></i>
            </button>
          </div>
          <ScheduleZoneHint value={scheduleDate} timezone={tz} secondaryTimezone={zones?.secondary} />
        </div>
      );
    }

    // Status-specific idle footers
    switch (post.status) {
      case 'draft':
        // AI proposal: show "Ver en propuestas" to access all proposal actions
        if (post.is_ai_generated && onViewProposal) {
          return (
            <div className="pdm-footer">
              <p className="pdm-confirm-msg" style={{ fontSize: '12px', marginBottom: '8px' }}>
                <i className="bi bi-stars"></i>
                This post is part of an AI proposal
              </p>
              <div className="pdm-footer-row">
                <button
                  className="pdm-btn pdm-btn-schedule"
                  onClick={() => { onHide(); onViewProposal(); }}
                >
                  <i className="bi bi-layout-text-window"></i>See in proposals
                </button>
              </div>
            </div>
          );
        }
        return (
          <div className="pdm-footer">
            <div className="pdm-footer-row">
              <button
                className="pdm-btn pdm-btn-schedule"
                onClick={() => { setScheduleDate(''); setActionStep('scheduling'); }}
                disabled={actionLoading}
              >
                <i className="bi bi-clock"></i>Schedule
              </button>
            </div>
            <div className="pdm-footer-row">
              {editBtn}
              {deleteBtn}
            </div>
          </div>
        );

      case 'scheduled':
        return (
          <div className="pdm-footer">
            <div className="pdm-footer-row">
              <button
                className="pdm-btn pdm-btn-reschedule"
                onClick={() => { setScheduleDate(''); setActionStep('scheduling'); }}
                disabled={actionLoading}
              >
                <i className="bi bi-calendar-event"></i>Change date
              </button>
              <button
                className="pdm-btn pdm-btn-cancel-pub"
                onClick={() => changeStatus('draft')}
                disabled={actionLoading}
              >
                {actionLoading
                  ? <span className="pdm-spinner"></span>
                  : <><i className="bi bi-x-circle"></i>Cancel</>
                }
              </button>
            </div>
            <div className="pdm-footer-row">
              {editBtn}
              {deleteBtn}
            </div>
          </div>
        );

      case 'published':
        return (
          <div className="pdm-footer">
            <div className="pdm-footer-row">
              {editBtn}
              {deleteBtn}
            </div>
          </div>
        );

      case 'failed':
        return (
          <div className="pdm-footer">
            <div className="pdm-footer-row">
              <button
                className="pdm-btn pdm-btn-retry"
                onClick={() => changeStatus('scheduled')}
                disabled={actionLoading}
              >
                {actionLoading
                  ? <span className="pdm-spinner"></span>
                  : <><i className="bi bi-arrow-clockwise"></i>Retry</>
                }
              </button>
              <button
                className="pdm-btn pdm-btn-reschedule"
                onClick={() => { setScheduleDate(''); setActionStep('scheduling'); }}
                disabled={actionLoading}
              >
                <i className="bi bi-calendar-event"></i>Change date
              </button>
            </div>
            <div className="pdm-footer-row">
              {editBtn}
              {deleteBtn}
            </div>
          </div>
        );

      default:
        return (
          <div className="pdm-footer">
            <div className="pdm-footer-row">
              {editBtn}
              {deleteBtn}
            </div>
          </div>
        );
    }
  };

  return (
    <div className="pdm-backdrop" onClick={onHide}>
      <div className="pdm-panel" onClick={e => e.stopPropagation()}>

        {/* ── Media zone ─────────────────────────── */}
        <div className="pdm-media">
          {storyThumbnail ? (
            <img src={storyThumbnail} alt="story" className="pdm-media-img" loading="lazy" />
          ) : post.media_url ? (
            isImage ? (
              <img
                src={showOriginal ? post.media_url : postThumbnailUrl(post, token, 640) ?? post.media_url}
                alt="publicación"
                className={`pdm-media-img${showOriginal ? '' : ' pdm-media-zoomable'}`}
                loading="lazy"
                onClick={() => setShowOriginal(true)}
              />
            ) : isVideo ? (
              <video
                src={post.media_url}
                className="pdm-media-video"
                controls
                playsInline
                preload="auto"
                onLoadedMetadata={e => { (e.target as HTMLVideoElement).currentTime = 0.001; }}
              />
            ) : null
          ) : post.drive_file_id ? (
            <img
              src={(showOriginal ? postOriginalUrl(post, token) : postThumbnailUrl(post, token, 640)) ?? undefined}
              alt="publicación"
              className={`pdm-media-img${showOriginal ? '' : ' pdm-media-zoomable'}`}
              loading="lazy"
              onClick={() => setShowOriginal(true)}
              onError={(e) => {
                const el = e.currentTarget as HTMLImageElement;
                el.style.display = 'none';
                el.parentElement?.querySelector<HTMLDivElement>('.pdm-media-none')?.style.setProperty('display', 'flex');
              }}
            />
          ) : (
            <div className="pdm-media-none">
              <i className="bi bi-image"></i>
            </div>
          )}

          <div className="pdm-topbar">
            <div className="pdm-topbar-chips">
              <span className="pdm-chip pdm-chip-type">
                <i className={`bi ${typeIcon}`}></i>
                {post.post_type}
              </span>
              <span className={`pdm-chip pdm-chip-${post.status}`}>
                <i className={`bi ${statusIcon}`}></i>
                {statusLabel}
              </span>
            </div>
            <button className="pdm-close-btn" onClick={onHide} aria-label="Cerrar">
              <i className="bi bi-x-lg"></i>
            </button>
          </div>
        </div>

        {/* ── Body ───────────────────────────────── */}
        <div className="pdm-body">
          <p className="pdm-caption">{post.content}</p>

          <div className="pdm-meta">
            <div className="pdm-meta-row">
              <i className="bi bi-clock-history"></i>
              <span className="pdm-meta-label">Created</span>
              <span className="pdm-meta-value">{formatDate(post.created_at)}</span>
            </div>
            {post.scheduled_at && (
              <div className="pdm-meta-row">
                <i className="bi bi-calendar-event"></i>
                <span className="pdm-meta-label">Scheduled</span>
                <span className="pdm-meta-value">{formatInZones(post.scheduled_at, zones ?? {})}</span>
              </div>
            )}
            {post.publication_date && (
              <div className="pdm-meta-row">
                <i className="bi bi-check2-circle"></i>
                <span className="pdm-meta-label">Published</span>
                <span className="pdm-meta-value">{formatDate(post.publication_date)}</span>
              </div>
            )}
          </div>

          {isStory && storyMetrics && (
            <div className="pdm-story-performance" data-testid="story-performance">
              <h6 className="pdm-story-title">Rendimiento de la Story</h6>
              <div className="pdm-story-grid">
                {STORY_METRICS.map(({ label, value }) => (
                  <div key={label} className="pdm-story-metric">
                    <span className="pdm-story-value">{(value(storyMetrics) ?? 0).toLocaleString('es-ES')}</span>
                    <span className="pdm-story-label">{label}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {isStory && storyMetrics === null && storyIsLive && (
            <p className="pdm-story-pending">
              <i className="bi bi-hourglass-split"></i>Métricas disponibles en la próxima sincronización
            </p>
          )}

          {/* ── Comunidad (Fase F): solo sugerencias para copiar ── */}
          {post.status === 'published' && strategyMode && (
            <div className="pdm-community">
              <CommentTriage postId={post.id} strategyMode={strategyMode} />
            </div>
          )}
          {strategyMode === 'commercial_campaign' && accountId && (
            <div className="pdm-community">
              <DmFunnel strategyMode={strategyMode} accountId={accountId} />
            </div>
          )}
        </div>

        {/* ── Error strip ────────────────────────── */}
        {actionError && (
          <div className="pdm-error-strip">
            <i className="bi bi-exclamation-circle"></i>
            {actionError}
          </div>
        )}

        {/* ── Footer ─────────────────────────────── */}
        {renderFooter()}

      </div>
    </div>
  );
};

export default PostDetailModal;
