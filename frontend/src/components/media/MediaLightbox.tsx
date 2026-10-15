import React, { useEffect, useState } from 'react';
import { isStorageVideo, postOriginalUrl, postThumbnailUrl } from '../../api/media';
import type { Post } from '../../types';
import { formatIcon } from '../calendar/DayMosaic';
import { formatInZones } from '../../utils/timezone';
import './MediaLightbox.css';

interface MediaLightboxProps {
  posts: Post[];
  startIndex: number;
  token: string | null;
  onClose: () => void;
  onDetails: (post: Post) => void;
  /** Zonas de la cuenta de cada post (AD-6); sin ellas, la del navegador */
  zonesFor?: (post: Post) => { primary?: string | null; secondary?: string | null };
}

const STATUS_LABELS: Record<string, string> = {
  draft:     'Borrador',
  scheduled: 'Programado',
  published: 'Publicado',
  failed:    'Fallido',
};

const FORMAT_LABELS: Record<string, string> = {
  post:     'Post',
  reel:     'Reel',
  carousel: 'Carrusel',
  story:    'Story',
};

function postDate(post: Post): Date {
  return new Date(post.publication_date ?? post.scheduled_at ?? post.created_at);
}

function statusLabel(post: Post): string {
  if (post.is_ai_generated && post.status === 'draft') return 'Propuesta IA';
  return STATUS_LABELS[post.status] ?? post.status;
}

/** Visor ampliado: imagen original de las publicaciones de un día, con navegación ←/→. */
const MediaLightbox: React.FC<MediaLightboxProps> = ({ posts, startIndex, token, onClose, onDetails, zonesFor }) => {
  const [index, setIndex] = useState(startIndex);
  // 0 = original, 1 = miniatura grande (el original no carga, p. ej. vídeo de Drive), 2 = icono
  const [fallback, setFallback] = useState(0);
  const post = posts[index];
  const multiple = posts.length > 1;

  useEffect(() => setFallback(0), [index]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      else if (e.key === 'ArrowRight' && multiple) setIndex(i => (i + 1) % posts.length);
      else if (e.key === 'ArrowLeft' && multiple) setIndex(i => (i - 1 + posts.length) % posts.length);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [multiple, posts.length, onClose]);

  if (!post) return null;

  const original = postOriginalUrl(post, token);
  // Sin original (vídeo de Instagram con audio con copyright) se ve su portada
  const src = fallback === 0 && original ? original : fallback <= 1 ? postThumbnailUrl(post, token, 640) : null;
  const format = post.content_format ?? post.post_type;
  const date = postDate(post);

  return (
    <div className="sl-lightbox-backdrop" data-testid="media-lightbox" onClick={onClose}>
      <div className="sl-lightbox-panel" onClick={e => e.stopPropagation()}>
        <button type="button" className="sl-lightbox-close" aria-label="Cerrar" onClick={onClose}>
          <i className="bi bi-x-lg" />
        </button>

        <div className="sl-lightbox-media">
          {original && isStorageVideo(post.media_url) ? (
            <video src={original} controls playsInline className="sl-lightbox-img" />
          ) : src ? (
            <img
              key={src}
              src={src}
              alt="publicación"
              className="sl-lightbox-img"
              onError={() => setFallback(f => f + 1)}
            />
          ) : (
            <i className={`bi ${formatIcon(post)} sl-lightbox-placeholder`} />
          )}

          {multiple && (
            <>
              <button
                type="button"
                className="sl-lightbox-nav sl-lightbox-prev"
                aria-label="Anterior"
                onClick={() => setIndex(i => (i - 1 + posts.length) % posts.length)}
              >
                <i className="bi bi-chevron-left" />
              </button>
              <button
                type="button"
                className="sl-lightbox-nav sl-lightbox-next"
                aria-label="Siguiente"
                onClick={() => setIndex(i => (i + 1) % posts.length)}
              >
                <i className="bi bi-chevron-right" />
              </button>
            </>
          )}
        </div>

        <div className="sl-lightbox-info">
          <div className="sl-lightbox-meta">
            <span className={`sl-lightbox-status sl-lightbox-status--${post.is_ai_generated && post.status === 'draft' ? 'proposal' : post.status}`}>
              {statusLabel(post)}
            </span>
            <span data-testid="lightbox-date">{formatInZones(date, zonesFor?.(post) ?? {})}</span>
            <span><i className={`bi ${formatIcon(post)}`} /> {FORMAT_LABELS[format] ?? format}</span>
            {multiple && <span className="sl-lightbox-count">{index + 1} / {posts.length}</span>}
          </div>
          <button type="button" className="sl-lightbox-details" onClick={() => onDetails(post)}>
            Ver detalles
          </button>
        </div>
      </div>
    </div>
  );
};

export default MediaLightbox;
