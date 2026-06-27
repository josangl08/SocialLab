import React, { useEffect, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import './PostDetailModal.css';

interface Post {
  id: number;
  user_id: string;
  content: string;
  media_url: string | null;
  post_type: string;
  status: string;
  scheduled_at: string | null;
  created_at: string;
  publication_date?: string | null;
}

interface PostDetailModalProps {
  show: boolean;
  onHide: () => void;
  post: Post | null;
  onEdit?: () => void;
  onActionSuccess?: () => void;
}

const STATUS_LABELS: Record<string, string> = {
  draft:     'Borrador',
  scheduled: 'Programado',
  published: 'Publicado',
  failed:    'Fallido',
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

const formatDate = (d: string) =>
  new Date(d).toLocaleDateString('es-ES', {
    day: 'numeric', month: 'long', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });

const PostDetailModal: React.FC<PostDetailModalProps> = ({
  show, onHide, post, onEdit, onActionSuccess,
}) => {
  const { token } = useAuth();
  const [actionStep, setActionStep]       = useState<'idle' | 'scheduling' | 'deleting'>('idle');
  const [scheduleDate, setScheduleDate]   = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError]     = useState('');

  useEffect(() => {
    setActionStep('idle');
    setActionError('');
    setScheduleDate('');
  }, [post?.id, show]);

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

      const res = await fetch(`http://localhost:8000/api/posts/${post.id}`, {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
      });

      if (res.ok) {
        onActionSuccess?.();
        onHide();
      } else {
        const err = await res.json();
        setActionError(err.detail ?? 'Error al actualizar el estado');
      }
    } catch {
      setActionError('Error de conexión');
    } finally {
      setActionLoading(false);
    }
  };

  const deletePost = async () => {
    if (!post || !token) return;
    setActionLoading(true);
    setActionError('');
    try {
      const res = await fetch(`http://localhost:8000/api/posts/${post.id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok) {
        onActionSuccess?.();
        onHide();
      } else {
        const err = await res.json();
        setActionError(err.detail ?? 'Error al eliminar');
        setActionStep('idle');
      }
    } catch {
      setActionError('Error de conexión');
      setActionStep('idle');
    } finally {
      setActionLoading(false);
    }
  };

  const confirmSchedule = () => {
    if (!scheduleDate) return;
    changeStatus('scheduled', new Date(scheduleDate).toISOString());
  };

  if (!show || !post) return null;

  const typeIcon    = TYPE_ICONS[post.post_type] ?? 'bi-image';
  const statusLabel = STATUS_LABELS[post.status] ?? post.status;
  const statusIcon  = STATUS_ICONS[post.status]  ?? 'bi-circle';
  const isImage = post.media_url?.match(/\.(jpeg|jpg|gif|png|webp|svg)(\?.*)?$/i);
  const isVideo = post.post_type === 'reel' ||
    !!post.media_url?.match(/\.(mp4|webm|ogg|mov)(\?.*)?$/i);

  // ── Shared action fragments ─────────────────────────
  const editBtn = onEdit ? (
    <button
      className="pdm-btn pdm-btn-edit"
      onClick={() => { onHide(); onEdit(); }}
      disabled={actionLoading}
    >
      <i className="bi bi-pencil"></i>Editar
    </button>
  ) : null;

  const deleteBtn = (
    <button
      className="pdm-btn pdm-btn-delete"
      onClick={() => setActionStep('deleting')}
      disabled={actionLoading}
    >
      <i className="bi bi-trash"></i>Eliminar
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
            Esta acción eliminará la publicación permanentemente.
          </p>
          <div className="pdm-footer-row">
            <button
              className="pdm-btn pdm-btn-secondary"
              onClick={() => setActionStep('idle')}
              disabled={actionLoading}
            >
              Cancelar
            </button>
            <button
              className="pdm-btn pdm-btn-delete-confirm"
              onClick={deletePost}
              disabled={actionLoading}
            >
              {actionLoading
                ? <span className="pdm-spinner"></span>
                : <><i className="bi bi-trash"></i>Eliminar</>
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
                : <><i className="bi bi-check-lg"></i>Confirmar</>
              }
            </button>
            <button
              className="pdm-btn pdm-btn-cancel-step"
              onClick={() => setActionStep('idle')}
              disabled={actionLoading}
              aria-label="Cancelar"
            >
              <i className="bi bi-x-lg"></i>
            </button>
          </div>
        </div>
      );
    }

    // Status-specific idle footers
    switch (post.status) {
      case 'draft':
        return (
          <div className="pdm-footer">
            <div className="pdm-footer-row">
              <button
                className="pdm-btn pdm-btn-schedule"
                onClick={() => { setScheduleDate(''); setActionStep('scheduling'); }}
                disabled={actionLoading}
              >
                <i className="bi bi-clock"></i>Programar
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
                <i className="bi bi-calendar-event"></i>Cambiar fecha
              </button>
              <button
                className="pdm-btn pdm-btn-cancel-pub"
                onClick={() => changeStatus('draft')}
                disabled={actionLoading}
              >
                {actionLoading
                  ? <span className="pdm-spinner"></span>
                  : <><i className="bi bi-x-circle"></i>Cancelar</>
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
                  : <><i className="bi bi-arrow-clockwise"></i>Reintentar</>
                }
              </button>
              <button
                className="pdm-btn pdm-btn-reschedule"
                onClick={() => { setScheduleDate(''); setActionStep('scheduling'); }}
                disabled={actionLoading}
              >
                <i className="bi bi-calendar-event"></i>Cambiar fecha
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
          {post.media_url ? (
            isImage ? (
              <img src={post.media_url} alt="publicación" className="pdm-media-img" />
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
              <span className="pdm-meta-label">Creado</span>
              <span className="pdm-meta-value">{formatDate(post.created_at)}</span>
            </div>
            {post.scheduled_at && (
              <div className="pdm-meta-row">
                <i className="bi bi-calendar-event"></i>
                <span className="pdm-meta-label">Programado</span>
                <span className="pdm-meta-value">{formatDate(post.scheduled_at)}</span>
              </div>
            )}
            {post.publication_date && (
              <div className="pdm-meta-row">
                <i className="bi bi-check2-circle"></i>
                <span className="pdm-meta-label">Publicado</span>
                <span className="pdm-meta-value">{formatDate(post.publication_date)}</span>
              </div>
            )}
          </div>
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
