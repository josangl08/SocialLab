import { apiClient } from './client';

// Lado mayor en px. Para imágenes recortadas en cuadrado (object-fit: cover), el lado
// corto (~3/4 del mayor en fotos verticales) debe cubrir el tamaño pintado × devicePixelRatio
export type ThumbnailSize = 160 | 320 | 480 | 640;

/** Lo mínimo de un post para resolver su imagen. */
export interface PostMediaRef {
  id: number;
  media_url?: string | null;
  drive_file_id?: string | null;
}

const VIDEO_URL = /\.(mp4|mov|webm|ogg|m4v)(\?.*)?$/i;

export function isStorageVideo(mediaUrl: string | null | undefined): boolean {
  return !!mediaUrl && VIDEO_URL.test(mediaUrl);
}

// Hash corto del origen de la imagen: cambia la URL (y salta la caché del navegador)
// cuando el post cambia de imagen
function sourceVersion(source: string): string {
  let hash = 5381;
  for (let i = 0; i < source.length; i++) hash = ((hash << 5) + hash + source.charCodeAt(i)) | 0;
  return (hash >>> 0).toString(36);
}

/** Miniatura JPEG del post (Storage o Drive); null si no hay imagen previsualizable. */
export function postThumbnailUrl(
  post: PostMediaRef,
  token: string | null,
  size: ThumbnailSize = 320,
): string | null {
  const source = post.media_url || post.drive_file_id;
  if (!source || !token || isStorageVideo(post.media_url)) return null;
  const params = new URLSearchParams({ size: String(size), v: sourceVersion(source), token });
  return apiClient.getUrl(`/api/posts/${post.id}/thumbnail?${params}`);
}

/** Miniatura de un archivo de Drive (selector de imágenes, slots sin post). */
export function driveThumbnailUrl(fileId: string, token: string | null, size: ThumbnailSize = 320): string {
  const params = new URLSearchParams({ size: String(size), token: token ?? '' });
  return apiClient.getUrl(`/api/drive/files/${encodeURIComponent(fileId)}/image?${params}`);
}

/** Imagen original (solo para ampliar). */
export function postOriginalUrl(post: PostMediaRef, token: string | null): string | null {
  if (post.media_url) return post.media_url;
  if (post.drive_file_id && token) {
    return apiClient.getUrl(
      `/api/drive/files/${encodeURIComponent(post.drive_file_id)}/image?token=${encodeURIComponent(token)}`,
    );
  }
  return null;
}
