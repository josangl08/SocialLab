import { describe, test, expect } from 'vitest';
import { driveThumbnailUrl, isStorageVideo, postOriginalUrl, postThumbnailUrl } from '../api/media';

describe('api/media', () => {
  const token = 'tok';

  test('postThumbnailUrl incluye size, v y token', () => {
    const url = postThumbnailUrl({ id: 42, media_url: null, drive_file_id: 'file-1' }, token, 160)!;
    expect(url).toMatch(/\/api\/posts\/42\/thumbnail\?size=160&v=[a-z0-9]+&token=tok$/);
  });

  test('la versión cambia cuando cambia la imagen del post', () => {
    const a = postThumbnailUrl({ id: 42, drive_file_id: 'file-1' }, token);
    const b = postThumbnailUrl({ id: 42, drive_file_id: 'file-2' }, token);
    const c = postThumbnailUrl({ id: 42, media_url: 'https://s.test/a.jpg', drive_file_id: 'file-1' }, token);
    expect(new Set([a, b, c]).size).toBe(3);
  });

  test('la versión no cambia si solo cambia la firma de la URL de Instagram', () => {
    const a = postThumbnailUrl({ id: 42, media_url: 'https://cdn.test/v/1_n.jpg?oh=a&oe=1' }, token);
    const b = postThumbnailUrl({ id: 42, media_url: 'https://cdn.test/v/1_n.jpg?oh=b&oe=2' }, token);
    expect(a).toBe(b);
  });

  test('sin imagen, sin token o vídeo de Storage no hay miniatura', () => {
    expect(postThumbnailUrl({ id: 1 }, token)).toBeNull();
    expect(postThumbnailUrl({ id: 1, drive_file_id: 'f' }, null)).toBeNull();
    expect(postThumbnailUrl({ id: 1, media_url: 'https://s.test/reel.MP4' }, token)).toBeNull();
    expect(isStorageVideo('https://s.test/a.mov?x=1')).toBe(true);
  });

  test('con miniatura guardada usa Storage directamente, sin token ni backend', () => {
    const base = 'https://p.supabase.co/storage/v1/object/public/thumbnails/u1/42/abc';
    const post = { id: 42, drive_file_id: 'file-1', thumbnail_url_base: base };
    expect(postThumbnailUrl(post, token, 160)).toBe(`${base}_160.webp`);
    expect(postThumbnailUrl(post, null, 640)).toBe(`${base}_640.webp`);
  });

  test('sin miniatura guardada pide el endpoint, que la genera', () => {
    const url = postThumbnailUrl({ id: 42, drive_file_id: 'file-1', thumbnail_url_base: null }, token, 320)!;
    expect(url).toContain('/api/posts/42/thumbnail?size=320');
  });

  test('driveThumbnailUrl pide el tamaño indicado', () => {
    expect(driveThumbnailUrl('file-abc', token, 160)).toContain('/api/drive/files/file-abc/image?size=160&token=tok');
  });

  test('postOriginalUrl: Storage directo, Drive por el proxy sin size', () => {
    expect(postOriginalUrl({ id: 1, media_url: 'https://s.test/a.jpg', drive_file_id: 'f' }, token)).toBe('https://s.test/a.jpg');
    expect(postOriginalUrl({ id: 1, drive_file_id: 'f' }, token)).toContain('/api/drive/files/f/image?token=tok');
    expect(postOriginalUrl({ id: 1 }, token)).toBeNull();
  });
});
