import React, { useEffect, useState, useRef } from 'react';
import { useAuth } from '../../context/AuthContext';
import EditPostForm from './EditPostForm';
import PostDetailModal from './PostDetailModal';
import './PostList.css';

interface Post {
  id: number;
  user_id: string;
  content: string;
  media_url: string | null;
  post_type: string;
  status: string;
  scheduled_at: string | null;
  created_at: string;
}

interface PostListProps {
  refresh?: boolean;
}

const TYPE_ICONS: Record<string, string> = {
  reel: 'bi-camera-video', carousel: 'bi-collection', story: 'bi-layers',
};

// ── Self-contained video cell with play/pause toggle ─────
const VideoCell: React.FC<{ src: string }> = ({ src }) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);

  const handlePlayToggle = (e: React.MouseEvent) => {
    e.stopPropagation(); // prevent opening the detail modal
    const video = videoRef.current;
    if (!video) return;
    if (isPlaying) {
      video.pause();
    } else {
      video.play().catch(() => {});
    }
  };

  return (
    <>
      <video
        ref={videoRef}
        src={src}
        className="sl-post-cell-img"
        muted
        playsInline
        preload="auto"
        onLoadedMetadata={e => { (e.target as HTMLVideoElement).currentTime = 0.001; }}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onEnded={() => setIsPlaying(false)}
      />
      <button
        className={`sl-cell-play-btn${isPlaying ? ' is-playing' : ''}`}
        onClick={handlePlayToggle}
        aria-label={isPlaying ? 'Pausar' : 'Reproducir'}
      >
        <i className={`bi ${isPlaying ? 'bi-pause-fill' : 'bi-play-fill'}`}></i>
      </button>
    </>
  );
};

const PostList: React.FC<PostListProps> = ({ refresh }) => {
  const { token } = useAuth();
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [alert, setAlert] = useState<{ text: string; ok: boolean } | null>(null);
  const [selectedPost, setSelectedPost] = useState<Post | null>(null);
  const [editingPost, setEditingPost] = useState<Post | null>(null);

  const fetchPosts = async () => {
    if (!token) { setError('No hay token de autenticación.'); setLoading(false); return; }
    try {
      const res = await fetch('http://localhost:8000/api/posts', {
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
      });
      if (res.ok) setPosts(await res.json());
      else {
        const err = await res.json();
        setError('Error al cargar publicaciones: ' + (err.detail ?? 'Error desconocido'));
      }
    } catch {
      setError('Error de red o servidor');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchPosts(); }, [token, refresh]);

  const handleDelete = async (postId: number) => {
    if (!window.confirm('¿Eliminar esta publicación?')) return;
    setAlert(null);
    try {
      const res = await fetch(`http://localhost:8000/api/posts/${postId}`, {
        method: 'DELETE', headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok) {
        setAlert({ text: 'Publicación eliminada.', ok: true });
        fetchPosts();
      } else {
        const err = await res.json();
        setAlert({ text: 'Error: ' + (err.detail ?? 'Error desconocido'), ok: false });
      }
    } catch {
      setAlert({ text: 'Error de red o servidor', ok: false });
    }
  };

  if (loading) return (
    <div className="sl-post-list">
      <div className="sl-post-empty"><i className="bi bi-hourglass-split"></i>Cargando publicaciones...</div>
    </div>
  );

  if (error) return (
    <div className="sl-post-list">
      <div className="sl-post-alert sl-post-alert-error"><i className="bi bi-exclamation-circle"></i>{error}</div>
    </div>
  );

  if (editingPost) return (
    <EditPostForm
      post={editingPost}
      onSave={() => { setEditingPost(null); fetchPosts(); }}
      onCancel={() => setEditingPost(null)}
    />
  );

  const isImage = (url: string) => /\.(jpeg|jpg|gif|png|webp|svg)(\?.*)?$/i.test(url);
  const isVideoMedia = (post: Post) =>
    post.post_type === 'reel' ||
    (!!post.media_url && /\.(mp4|webm|ogg|mov)(\?.*)?$/i.test(post.media_url));

  return (
    <div className="sl-post-list">
      {alert && (
        <div className={`sl-post-alert ${alert.ok ? 'sl-post-alert-success' : 'sl-post-alert-error'}`}>
          <i className={`bi ${alert.ok ? 'bi-check-circle' : 'bi-exclamation-circle'}`}></i>
          {alert.text}
        </div>
      )}

      {posts.length === 0 ? (
        <div className="sl-post-empty">
          <i className="bi bi-inbox"></i>
          No tienes publicaciones aún
        </div>
      ) : (
        <>
          <div className="sl-grid-header">
            <span className="sl-grid-count">{posts.length} publicación{posts.length !== 1 ? 'es' : ''}</span>
          </div>

          <div className="sl-post-grid">
            {posts.map(post => (
              <div key={post.id} className="sl-post-cell" onClick={() => setSelectedPost(post)}>
                {/* Media fill */}
                {post.media_url && isImage(post.media_url) ? (
                  <img src={post.media_url} alt="" className="sl-post-cell-img" />
                ) : isVideoMedia(post) && post.media_url ? (
                  <VideoCell src={post.media_url} />
                ) : (
                  <div className={`sl-post-cell-text status-${post.status}`}>
                    {post.content}
                  </div>
                )}

                {/* Status dot */}
                <span className={`sl-cell-status-dot ${post.status}`}></span>

                {/* Type badge — top-right corner, always visible */}
                {post.post_type !== 'post' && (
                  <span className="sl-cell-type-badge">
                    <i className={`bi ${TYPE_ICONS[post.post_type] ?? 'bi-image'}`}></i>
                  </span>
                )}

                {/* Hover overlay */}
                <div className="sl-post-cell-overlay">
                  <span className={`sl-overlay-status ${post.status}`}>
                    {post.status === 'draft' ? 'Borrador' :
                     post.status === 'scheduled' ? 'Programado' :
                     post.status === 'published' ? 'Publicado' : post.status}
                  </span>
                  <p className="sl-overlay-caption">{post.content}</p>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      <PostDetailModal
        show={selectedPost !== null}
        onHide={() => setSelectedPost(null)}
        post={selectedPost}
        onEdit={() => {
          const post = selectedPost;
          setSelectedPost(null);
          if (post) setEditingPost(post);
        }}
        onActionSuccess={fetchPosts}
      />
    </div>
  );
};

export default PostList;
