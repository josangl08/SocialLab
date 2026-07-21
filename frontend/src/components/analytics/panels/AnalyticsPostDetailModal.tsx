import React from 'react';
import ContentRadarChart from '../charts/ContentRadarChart';

interface AnalyticsPostDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  post: {
    id?: string;
    caption?: string;
    media_url?: string;
    permalink?: string;
    timestamp?: string;
    post_type?: string;
    likes?: number;
    comments?: number;
    saved?: number;
    saves?: number;
    views?: number;
    impressions?: number;
    reach?: number;
    avg_watch_time_ms?: number;
    total_watch_time_ms?: number;
  } | null;
}

export const AnalyticsPostDetailModal: React.FC<AnalyticsPostDetailModalProps> = ({
  isOpen,
  onClose,
  post
}) => {
  if (!isOpen || !post) return null;

  const isReel = post.post_type?.toLowerCase() === 'reel' || post.post_type?.toLowerCase() === 'video';

  const formatWatchTime = (ms?: number) => {
    if (!ms) return '0s';
    const seconds = ms / 1000;
    if (seconds < 60) {
      return `${seconds.toFixed(1)}s`;
    }
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds.toFixed(0)}s`;
  };

  const savedVal = post.saved ?? post.saves ?? 0;
  const commentsVal = post.comments ?? 0;
  const viewsVal = post.views ?? post.impressions ?? 0;
  const likesVal = post.likes ?? 0;

  return (
    <>
      {/* Backdrop */}
      <div 
        className="an-modal-backdrop" 
        onClick={onClose}
      />
      
      {/* Drawer Container */}
      <div className="an-modal-drawer animate-slide-in">
        <div className="an-modal-header d-flex align-items-center justify-content-between">
          <h5 className="an-modal-title">Detalle del Post</h5>
          <button 
            className="btn-close btn-close-white" 
            onClick={onClose}
            aria-label="Close"
          />
        </div>

        <div className="an-modal-body">
          {/* Post Media Preview */}
          {post.media_url && (
            <div className="an-post-preview-container mb-3">
              <img 
                src={post.media_url} 
                alt="Post preview" 
                className="an-post-preview-img img-fluid rounded" 
              />
            </div>
          )}

          {/* Caption */}
          {post.caption && (
            <p className="an-post-caption text-muted small mb-4">
              {post.caption}
            </p>
          )}

          {/* Numerical Metrics Grid */}
          <div className="an-metrics-grid mb-4">
            <div className="an-metric-box">
              <i className="bi bi-heart-fill text-danger me-2"></i>
              <div>
                <div className="an-metric-val">{likesVal}</div>
                <div className="an-metric-lbl">Likes</div>
              </div>
            </div>
            
            <div className="an-metric-box">
              <i className="bi bi-chat-fill text-primary me-2"></i>
              <div>
                <div className="an-metric-val">{commentsVal}</div>
                <div className="an-metric-lbl">Comments</div>
              </div>
            </div>

            <div className="an-metric-box">
              <i className="bi bi-bookmark-fill text-success me-2"></i>
              <div>
                <div className="an-metric-val">{savedVal}</div>
                <div className="an-metric-lbl">Saves</div>
              </div>
            </div>

            <div className="an-metric-box">
              <i className="bi bi-eye-fill text-info me-2"></i>
              <div>
                <div className="an-metric-val">{viewsVal}</div>
                <div className="an-metric-lbl">Views</div>
              </div>
            </div>
          </div>

          {/* Reel Watch Times */}
          {isReel && (
            <div className="an-reel-stats-container mb-4 p-3 rounded">
              <div className="small text-uppercase text-muted fw-bold mb-2">Reel Performance</div>
              <div className="row">
                <div className="col-6">
                  <div className="an-reel-stat-val text-violet fw-bold">
                    {formatWatchTime(post.avg_watch_time_ms)}
                  </div>
                  <div className="an-reel-stat-lbl text-muted small">Avg Watch Time</div>
                </div>
                <div className="col-6">
                  <div className="an-reel-stat-val text-violet fw-bold">
                    {formatWatchTime(post.total_watch_time_ms)}
                  </div>
                  <div className="an-reel-stat-lbl text-muted small">Total Watch Time</div>
                </div>
              </div>
            </div>
          )}

          {/* Radar Chart */}
          <div className="an-radar-section mb-3 text-center">
            <div className="small text-uppercase text-muted fw-bold mb-2">Perfil de Contenido</div>
            <ContentRadarChart post={post} />
          </div>

          {/* Permalink Link */}
          {post.permalink && (
            <div className="text-center mt-3 mb-2">
              <a 
                href={post.permalink} 
                target="_blank" 
                rel="noopener noreferrer" 
                className="btn btn-outline-light btn-sm w-100"
              >
                Ver en Instagram <i className="bi bi-box-arrow-up-right ms-1"></i>
              </a>
            </div>
          )}
        </div>
      </div>
    </>
  );
};

export default AnalyticsPostDetailModal;
