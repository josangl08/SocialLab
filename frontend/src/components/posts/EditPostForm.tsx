import React, { useState, useEffect } from 'react';
import type { FormEvent } from 'react';
import { useAuth } from '../../context/AuthContext';
import './CreatePost.css';

interface Post {
  id: number;
  user_id: string;
  content: string;
  media_url: string | null;
  post_type: string;
  status: string;
  scheduled_at: string | null;
  created_at: string;
  instagram_account_id?: number | null;
}

interface InstagramAccount {
  id: number;
  username: string;
  account_name: string;
}

interface EditPostFormProps {
  post: Post;
  onSave: () => void;
  onCancel: () => void;
}

const POST_TYPES = [
  { value: 'post',     label: 'Post',     icon: 'bi-image' },
  { value: 'reel',     label: 'Reel',     icon: 'bi-camera-video' },
  { value: 'carousel', label: 'Carrusel', icon: 'bi-collection' },
];

const isImageUrl = (url: string) => /\.(jpeg|jpg|gif|png|webp|svg)(\?.*)?$/i.test(url);

const EditPostForm: React.FC<EditPostFormProps> = ({ post, onSave, onCancel }) => {
  const { token } = useAuth();
  const [content, setContent]               = useState(post.content);
  const [mediaFile, setMediaFile]           = useState<File | null>(null);
  const [mediaPreview, setMediaPreview]     = useState<string | null>(null);
  const [currentMediaUrl]                   = useState<string | null>(post.media_url);
  const [postType, setPostType]             = useState(post.post_type);
  const [status, setStatus]                 = useState(post.status === 'published' || post.status === 'failed' ? 'draft' : post.status);
  const [scheduledAt, setScheduledAt]       = useState(
    post.scheduled_at ? new Date(post.scheduled_at).toISOString().slice(0, 16) : ''
  );
  const [selectedAccountId, setSelectedAccountId] = useState(
    post.instagram_account_id ? String(post.instagram_account_id) : ''
  );
  const [instagramAccounts, setInstagramAccounts] = useState<InstagramAccount[]>([]);
  const [loading, setLoading]   = useState(false);
  const [message, setMessage]   = useState('');
  const [isError, setIsError]   = useState(false);

  useEffect(() => {
    if (!token) return;
    fetch('http://localhost:8000/instagram/accounts', {
      headers: { 'Authorization': `Bearer ${token}` },
    })
      .then(r => r.ok ? r.json() : [])
      .then(setInstagramAccounts)
      .catch(() => {});
  }, [token]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    setMediaFile(file);
    if (!file) { setMediaPreview(null); return; }
    const reader = new FileReader();
    reader.onloadend = () => setMediaPreview(reader.result as string);
    reader.readAsDataURL(file);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setMessage(''); setIsError(false); setLoading(true);

    if (!token) {
      setMessage('Sin token de autenticación.');
      setIsError(true); setLoading(false); return;
    }
    if (!currentMediaUrl && !mediaFile) {
      setMessage('Un archivo multimedia es obligatorio para Instagram.');
      setIsError(true); setLoading(false); return;
    }

    const formData = new FormData();
    formData.append('content', content);
    formData.append('post_type', postType);
    formData.append('status', status);
    if (scheduledAt) formData.append('scheduled_at', new Date(scheduledAt).toISOString());
    if (mediaFile) formData.append('media_file', mediaFile);
    if (selectedAccountId) formData.append('instagram_account_id', selectedAccountId);

    try {
      const res = await fetch(`http://localhost:8000/api/posts/${post.id}`, {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
      });
      if (res.ok) {
        setMessage('Publicación actualizada.');
        onSave();
      } else {
        const err = await res.json();
        const detail = err.detail;
        setMessage(Array.isArray(detail)
          ? detail.map((d: any) => d.msg).join('; ')
          : (detail ?? 'Error al actualizar'));
        setIsError(true);
      }
    } catch {
      setMessage('Error de red o servidor.'); setIsError(true);
    } finally {
      setLoading(false);
    }
  };

  // Displayed media: new file preview takes priority over current URL
  const displayPreview = mediaPreview ?? currentMediaUrl;
  const displayIsImage = displayPreview
    ? (mediaPreview ? mediaPreview.startsWith('data:image') : isImageUrl(displayPreview))
    : false;

  return (
    <div className="cp-wrap">
      <form onSubmit={handleSubmit}>

        {/* ── Media ─────────────────────────────────────── */}
        <div className="cp-field">
          <p className="cp-section-label">
            Imagen / Video
            {currentMediaUrl && !mediaFile && (
              <span style={{ marginLeft: 8, fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}>
                — haz clic para cambiar
              </span>
            )}
          </p>
          <div className="cp-upload-zone" style={{ maxHeight: 220 }}>
            <input
              type="file"
              accept="image/*,video/*"
              onChange={handleFileChange}
              disabled={loading}
            />
            {displayPreview ? (
              <div className="cp-upload-preview">
                {displayIsImage ? (
                  <img src={displayPreview} alt="preview" className="cp-upload-preview-img" />
                ) : (
                  <video src={displayPreview} className="cp-upload-preview-video" muted playsInline preload="auto" />
                )}
                <div className="cp-upload-preview-overlay">
                  <button type="button" className="cp-upload-change-btn">Cambiar</button>
                </div>
              </div>
            ) : (
              <>
                <i className="bi bi-cloud-arrow-up cp-upload-icon"></i>
                <span className="cp-upload-text">Arrastra tu archivo aquí</span>
                <span className="cp-upload-hint">o haz clic para seleccionar</span>
              </>
            )}
          </div>
        </div>

        {/* ── Caption ───────────────────────────────────── */}
        <div className="cp-field">
          <p className="cp-section-label">Caption</p>
          <textarea
            className="cp-textarea"
            placeholder="Texto de la publicación..."
            value={content}
            onChange={e => setContent(e.target.value)}
            rows={5}
            required
            disabled={loading}
          />
        </div>

        {/* ── Post type ─────────────────────────────────── */}
        <div className="cp-field">
          <p className="cp-section-label">Tipo</p>
          <div className="cp-type-grid">
            {POST_TYPES.map(t => (
              <button
                type="button"
                key={t.value}
                className={`cp-type-card${postType === t.value ? ' active' : ''}`}
                onClick={() => setPostType(t.value)}
                disabled={loading}
              >
                <i className={`bi ${t.icon}`}></i>
                <span>{t.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* ── Status ────────────────────────────────────── */}
        <div className="cp-field">
          <p className="cp-section-label">Estado</p>
          <div className="cp-status-toggle">
            <button
              type="button"
              className={`cp-status-btn${status === 'draft' ? ' active' : ''}`}
              onClick={() => setStatus('draft')}
              disabled={loading}
            >
              <i className="bi bi-pencil"></i>Borrador
            </button>
            <button
              type="button"
              className={`cp-status-btn${status === 'scheduled' ? ' active' : ''}`}
              onClick={() => setStatus('scheduled')}
              disabled={loading}
            >
              <i className="bi bi-clock"></i>Programado
            </button>
          </div>
        </div>

        {/* ── Schedule datetime ─────────────────────────── */}
        {status === 'scheduled' && (
          <div className="cp-field">
            <p className="cp-section-label">Fecha y hora</p>
            <input
              type="datetime-local"
              className="cp-input"
              value={scheduledAt}
              onChange={e => setScheduledAt(e.target.value)}
              disabled={loading}
            />
          </div>
        )}

        {/* ── Instagram account ─────────────────────────── */}
        {instagramAccounts.length > 0 && (
          <div className="cp-field">
            <p className="cp-section-label">Cuenta de Instagram</p>
            <select
              className="cp-select"
              value={selectedAccountId}
              onChange={e => setSelectedAccountId(e.target.value)}
              disabled={loading}
            >
              <option value="">Sin cuenta específica</option>
              {instagramAccounts.map(acc => (
                <option key={acc.id} value={acc.id}>
                  @{acc.username ?? acc.account_name}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* ── Feedback ──────────────────────────────────── */}
        {message && (
          <p className={`cp-msg ${isError ? 'cp-msg-error' : 'cp-msg-success'}`}>
            <i className={`bi ${isError ? 'bi-exclamation-circle' : 'bi-check-circle'}`}></i>
            {message}
          </p>
        )}

        {/* ── Actions ───────────────────────────────────── */}
        <div className="cp-actions" style={{ marginTop: 24 }}>
          <button type="button" className="cp-cancel-btn" onClick={onCancel} disabled={loading}>
            Cancelar
          </button>
          <button type="submit" className="cp-submit-btn" disabled={loading}>
            {loading
              ? <><div className="cp-spinner"></div>Guardando...</>
              : <><i className="bi bi-check-lg"></i>Guardar cambios</>
            }
          </button>
        </div>

      </form>
    </div>
  );
};

export default EditPostForm;
