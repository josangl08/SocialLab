import React, { useState, useEffect } from 'react';
import type { FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import './CreatePost.css';

interface CreatePostProps {
  onPostCreated: () => void;
  onCancel?: () => void;
  initialDate?: string;
}

interface InstagramAccount {
  id: number;
  username: string;
  account_name: string;
}

const AI_ROLES = [
  { value: 'content_manager', label: 'Content Manager' },
  { value: 'marketing_expert', label: 'Experto en Marketing' },
  { value: 'casual_friend',   label: 'Tono Cercano' },
];

const POST_TYPES = [
  { value: 'post',     label: 'Post',     icon: 'bi-image' },
  { value: 'reel',     label: 'Reel',     icon: 'bi-camera-video' },
  { value: 'story',    label: 'Story',    icon: 'bi-layers' },
  { value: 'carousel', label: 'Carrusel', icon: 'bi-collection' },
];

const CreatePost: React.FC<CreatePostProps> = ({ onPostCreated, onCancel, initialDate }) => {
  const { token } = useAuth();
  const [searchParams] = useSearchParams();

  const [content, setContent]         = useState('');
  const [mediaFile, setMediaFile]     = useState<File | null>(null);
  const [mediaPreview, setMediaPreview] = useState<string | null>(null);
  const [isDragging, setIsDragging]   = useState(false);
  const [postType, setPostType]       = useState('post');
  const [status, setStatus]           = useState('draft');
  const [scheduledAt, setScheduledAt] = useState(() => {
    const raw = initialDate ?? searchParams.get('date') ?? '';
    if (!raw) return '';
    const parsed = new Date(raw);
    return isNaN(parsed.getTime()) ? '' : parsed.toISOString().slice(0, 16);
  });
  const [selectedAccountId, setSelectedAccountId] = useState('');
  const [instagramAccounts, setInstagramAccounts] = useState<InstagramAccount[]>([]);

  const [aiOpen, setAiOpen]     = useState(false);
  const [aiTopic, setAiTopic]   = useState('');
  const [aiRole, setAiRole]     = useState('content_manager');
  const [aiLoading, setAiLoading] = useState(false);
  const [aiMsg, setAiMsg]       = useState('');

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

  const applyFile = (file: File | null) => {
    setMediaFile(file);
    if (!file) { setMediaPreview(null); return; }
    const reader = new FileReader();
    reader.onloadend = () => setMediaPreview(reader.result as string);
    reader.readAsDataURL(file);
  };

  // TODO(human): implement drag-and-drop handlers on .cp-upload-zone
  // handleDrop should call e.preventDefault(), e.stopPropagation(), setIsDragging(false),
  // then extract e.dataTransfer.files[0] and pass it to applyFile().
  // handleDragOver / handleDragEnter should call e.preventDefault() and setIsDragging(true).
  // handleDragLeave should setIsDragging(false).
  // Wire them to the .cp-upload-zone div below: onDrop, onDragOver, onDragEnter, onDragLeave.

  const handleGenerateAI = async () => {
    if (!aiTopic) { setAiMsg('Introduce un tema para generar contenido.'); return; }
    setAiLoading(true); setAiMsg('');
    try {
      const res = await fetch('http://localhost:8000/ai/generate-post-content', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ topic: aiTopic, role: aiRole }),
      });
      if (res.ok) {
        const data = await res.json();
        setContent(data.generated_text);
        setAiMsg('Contenido generado correctamente.');
      } else {
        const err = await res.json();
        setAiMsg('Error: ' + (err.detail ?? 'No se pudo generar'));
      }
    } catch {
      setAiMsg('Error de conexión.');
    } finally {
      setAiLoading(false);
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setMessage(''); setIsError(false); setLoading(true);

    if (!token) { setMessage('Sin token de autenticación.'); setIsError(true); setLoading(false); return; }
    if (!mediaFile) { setMessage('La imagen o video es obligatorio para Instagram.'); setIsError(true); setLoading(false); return; }

    const formData = new FormData();
    formData.append('content', content);
    formData.append('post_type', postType);
    formData.append('status', status);
    if (scheduledAt) formData.append('scheduled_at', new Date(scheduledAt).toISOString());
    formData.append('media_file', mediaFile);
    if (selectedAccountId) formData.append('instagram_account_id', selectedAccountId);

    try {
      const res = await fetch('http://localhost:8000/api/posts', {
        method: 'POST', headers: { 'Authorization': `Bearer ${token}` }, body: formData,
      });
      if (res.ok) {
        setMessage('Publicación creada correctamente.');
        setContent(''); setAiTopic(''); setMediaFile(null); setMediaPreview(null);
        setPostType('post'); setStatus('draft'); setScheduledAt(''); setSelectedAccountId('');
        onPostCreated();
      } else {
        const err = await res.json();
        setMessage(Array.isArray(err.detail)
          ? err.detail.map((e: any) => e.msg).join('; ')
          : (err.detail ?? 'Error al crear la publicación'));
        setIsError(true);
      }
    } catch {
      setMessage('Error de red o servidor.'); setIsError(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="cp-wrap">
      <form onSubmit={handleSubmit}>

        {/* ── Media upload ───────────────────────────── */}
        <div className="cp-field">
          <p className="cp-section-label">Imagen / Video <span style={{ color: '#f87171' }}>*</span></p>
          <div className={`cp-upload-zone${isDragging ? ' dragging' : ''}`}>
            <input
              type="file"
              accept="image/*,video/*"
              required
              disabled={loading}
              onChange={e => applyFile(e.target.files?.[0] ?? null)}
            />
            {mediaPreview ? (
              <div className="cp-upload-preview">
                {mediaPreview.startsWith('data:image') ? (
                  <img src={mediaPreview} alt="preview" className="cp-upload-preview-img" />
                ) : (
                  <video src={mediaPreview} className="cp-upload-preview-video" />
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

        {/* ── AI assistant ───────────────────────────── */}
        <div className="cp-field">
          <button type="button" className="cp-ai-toggle" onClick={() => setAiOpen(o => !o)}>
            <span className="cp-ai-toggle-label">
              <i className="bi bi-stars"></i>
              Asistente IA
            </span>
            <i className={`bi bi-chevron-down cp-ai-toggle-chevron${aiOpen ? ' open' : ''}`}></i>
          </button>
          {aiOpen && (
            <div className="cp-ai-body">
              <div>
                <p className="cp-section-label">Tono</p>
                <select className="cp-select" value={aiRole} onChange={e => setAiRole(e.target.value)} disabled={aiLoading || loading}>
                  {AI_ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                </select>
              </div>
              <div>
                <p className="cp-section-label">Tema o idea</p>
                <textarea
                  className="cp-textarea"
                  style={{ minHeight: 72 }}
                  placeholder="ej. lanzamiento de zapatillas ecológicas..."
                  value={aiTopic}
                  onChange={e => setAiTopic(e.target.value)}
                  disabled={aiLoading || loading}
                />
              </div>
              <button type="button" className="cp-ai-generate-btn" onClick={handleGenerateAI} disabled={aiLoading || loading}>
                {aiLoading ? <><div className="cp-spinner"></div>Generando...</> : <><i className="bi bi-stars"></i>Generar caption</>}
              </button>
              {aiMsg && (
                <p className={`cp-msg ${aiMsg.startsWith('Error') ? 'cp-msg-error' : 'cp-msg-info'}`} style={{ marginTop: 0 }}>
                  {aiMsg}
                </p>
              )}
            </div>
          )}
        </div>

        {/* ── Caption ────────────────────────────────── */}
        <div className="cp-field">
          <p className="cp-section-label">Caption</p>
          <textarea
            className="cp-textarea"
            placeholder="Escribe el texto de tu publicación..."
            value={content}
            onChange={e => setContent(e.target.value)}
            rows={5}
            required
            disabled={loading}
          />
        </div>

        {/* ── Post type ──────────────────────────────── */}
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

        {/* ── Status ─────────────────────────────────── */}
        <div className="cp-field">
          <p className="cp-section-label">Estado</p>
          <div className="cp-status-toggle">
            <button
              type="button"
              className={`cp-status-btn${status === 'draft' ? ' active' : ''}`}
              onClick={() => setStatus('draft')}
              disabled={loading}
            >
              <i className="bi bi-pencil"></i>
              Borrador
            </button>
            <button
              type="button"
              className={`cp-status-btn${status === 'scheduled' ? ' active' : ''}`}
              onClick={() => setStatus('scheduled')}
              disabled={loading}
            >
              <i className="bi bi-clock"></i>
              Programar
            </button>
          </div>
        </div>

        {/* ── Schedule datetime (only when Programado) ── */}
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

        {/* ── Instagram account ──────────────────────── */}
        {instagramAccounts.length > 0 && (
          <div className="cp-field">
            <label htmlFor="instagram-account" className="cp-section-label">Cuenta de Instagram</label>
            <select
              id="instagram-account"
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

        {/* ── Feedback ───────────────────────────────── */}
        {message && (
          <p className={`cp-msg ${isError ? 'cp-msg-error' : 'cp-msg-success'}`}>
            <i className={`bi ${isError ? 'bi-exclamation-circle' : 'bi-check-circle'}`}></i>
            {message}
          </p>
        )}

        {/* ── Actions ────────────────────────────────── */}
        <div className="cp-actions" style={{ marginTop: 24 }}>
          {onCancel && (
            <button type="button" className="cp-cancel-btn" onClick={onCancel} disabled={loading}>
              Cancelar
            </button>
          )}
          <button type="submit" className="cp-submit-btn" disabled={loading}>
            {loading ? <><div className="cp-spinner"></div>Creando...</> : <><i className="bi bi-plus-lg"></i>Crear publicación</>}
          </button>
        </div>

      </form>
    </div>
  );
};

export default CreatePost;
