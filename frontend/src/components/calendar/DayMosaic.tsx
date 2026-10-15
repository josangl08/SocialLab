import React, { useState } from 'react';
import { postThumbnailUrl } from '../../api/media';
import type { Post } from '../../types';
import './DayMosaic.css';

/** Publicación del día con la clase de estado del calendario (event-status-*, event-proposal…). */
export interface MosaicItem {
  post: Post;
  className: string;
  /** Fecha en la zona secundaria cuando cae en otro día (AD-10) */
  secondaryNote?: string;
}

interface DayMosaicProps {
  items: MosaicItem[];
  token: string | null;
  onOpen: (index: number) => void;
}

/** Tipo MIME propio para que solo las miniaturas del calendario sean soltables en un día. */
export const POST_DRAG_TYPE = 'application/x-sociallab-post';

const MAX_TILES = 4;

// El sync de métricas guarda el media_type de Instagram (VIDEO, CAROUSEL_ALBUM) en post_type
const FORMAT_ICONS: Record<string, string> = {
  reel:           'bi-camera-video',
  video:          'bi-camera-video',
  carousel:       'bi-collection',
  carousel_album: 'bi-collection',
  story:          'bi-layers',
};

export function formatIcon(post: Post): string {
  return FORMAT_ICONS[(post.content_format ?? post.post_type ?? '').toLowerCase()] ?? 'bi-image';
}

function layoutClass(count: number): string {
  if (count === 1) return 'sl-mosaic--1';
  if (count === 2) return 'sl-mosaic--2';
  return 'sl-mosaic--4';
}

const MosaicTile: React.FC<{
  item: MosaicItem;
  index: number;
  src: string | null;
  onOpen: (index: number) => void;
}> = ({ item, index, src, onOpen }) => {
  const [failed, setFailed] = useState(false);
  const { post, className, secondaryNote } = item;
  return (
    <div
      className={`sl-mosaic-tile ${className}`}
      data-testid={`mosaic-tile-${post.id}`}
      data-post-id={post.id}
      title={post.content.substring(0, 80)}
      draggable
      onDragStart={e => {
        e.dataTransfer.setData(POST_DRAG_TYPE, String(post.id));
        e.dataTransfer.effectAllowed = 'move';
      }}
      onClick={e => { e.stopPropagation(); onOpen(index); }}
    >
      {src && !failed ? (
        <img src={src} alt="" loading="lazy" draggable={false} onError={() => setFailed(true)} />
      ) : (
        <i className={`bi ${formatIcon(post)} sl-mosaic-placeholder`} data-testid={`mosaic-placeholder-${post.id}`} />
      )}
      {secondaryNote && (
        <span className="sl-mosaic-tz-mark" title={secondaryNote} data-testid={`mosaic-tz-mark-${post.id}`}>
          <i className="bi bi-globe2" />
        </span>
      )}
    </div>
  );
};

/** Mosaico de miniaturas de un día en la vista de mes: 1 → celda, 2 → mitades,
 *  3–4 → 2×2, más de 4 → 3 miniaturas + "+N". Cada foto se ve completa dentro de su hueco. */
const DayMosaic: React.FC<DayMosaicProps> = ({ items, token, onOpen }) => {
  const overflow = items.length > MAX_TILES;
  const shown = overflow ? items.slice(0, MAX_TILES - 1) : items;

  return (
    <div className={`sl-mosaic ${layoutClass(items.length)}`} data-testid="day-mosaic">
      {shown.map((item, i) => (
        <MosaicTile
          key={item.post.id}
          item={item}
          index={i}
          src={postThumbnailUrl(item.post, token, 160)}
          onOpen={onOpen}
        />
      ))}
      {overflow && (
        <button
          type="button"
          className="sl-mosaic-tile sl-mosaic-more"
          onClick={e => { e.stopPropagation(); onOpen(MAX_TILES - 1); }}
        >
          +{items.length - (MAX_TILES - 1)}
        </button>
      )}
    </div>
  );
};

export default DayMosaic;
