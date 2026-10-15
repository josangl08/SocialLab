import { render, screen, fireEvent } from '@testing-library/react';
import { describe, test, expect, vi } from 'vitest';
import MediaLightbox from '../components/media/MediaLightbox';
import type { Post } from '../types';

function post(id: number, overrides: Partial<Post> = {}): Post {
  return {
    id,
    user_id: 'u1',
    content: `Post ${id}`,
    media_url: `https://s.test/${id}.jpg`,
    post_type: 'post',
    status: 'scheduled',
    scheduled_at: '2030-06-27T12:30:00Z',
    created_at: '2030-06-01T10:00:00Z',
    ...overrides,
  };
}

const posts = [post(1), post(2, { status: 'published', content_format: 'reel' }), post(3)];

function setup(startIndex = 0) {
  const onClose = vi.fn();
  const onDetails = vi.fn();
  render(<MediaLightbox posts={posts} startIndex={startIndex} token="tok" onClose={onClose} onDetails={onDetails} />);
  return { onClose, onDetails };
}

const shownSrc = () => screen.getByAltText('publicación').getAttribute('src');

describe('MediaLightbox', () => {
  test('muestra el original, estado, formato y posición', () => {
    setup(1);
    expect(shownSrc()).toBe('https://s.test/2.jpg');
    expect(screen.getByText('Publicado')).toBeInTheDocument();
    expect(screen.getByText(/Reel/)).toBeInTheDocument();
    expect(screen.getByText('2 / 3')).toBeInTheDocument();
  });

  test('muestra la fecha y hora programadas en la zona de la cuenta', () => {
    render(
      <MediaLightbox posts={posts} startIndex={0} token="tok" onClose={vi.fn()} onDetails={vi.fn()}
        zonesFor={() => ({ primary: 'Europe/Madrid' })} />
    );
    // 2030-06-27T12:30Z = jueves 27, 14:30 en Madrid
    expect(screen.getByTestId('lightbox-date')).toHaveTextContent(/27 · 14:30/);
  });

  test('navega con los botones y con el teclado, en bucle', () => {
    setup(0);
    fireEvent.click(screen.getByLabelText('Siguiente'));
    expect(shownSrc()).toBe('https://s.test/2.jpg');
    fireEvent.keyDown(window, { key: 'ArrowRight' });
    expect(shownSrc()).toBe('https://s.test/3.jpg');
    fireEvent.keyDown(window, { key: 'ArrowRight' });
    expect(shownSrc()).toBe('https://s.test/1.jpg');
    fireEvent.keyDown(window, { key: 'ArrowLeft' });
    expect(shownSrc()).toBe('https://s.test/3.jpg');
    fireEvent.click(screen.getByLabelText('Anterior'));
    expect(shownSrc()).toBe('https://s.test/2.jpg');
  });

  test('Esc y clic fuera cierran; clic en el panel no', () => {
    const { onClose } = setup();
    fireEvent.click(screen.getByAltText('publicación'));
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.keyDown(window, { key: 'Escape' });
    fireEvent.click(screen.getByTestId('media-lightbox'));
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  test('Ver detalles entrega el post mostrado', () => {
    const { onDetails } = setup(2);
    fireEvent.click(screen.getByText('Ver detalles'));
    expect(onDetails).toHaveBeenCalledWith(posts[2]);
  });

  test('con una sola publicación no hay flechas', () => {
    render(<MediaLightbox posts={[post(1)]} startIndex={0} token="tok" onClose={() => {}} onDetails={() => {}} />);
    expect(screen.queryByLabelText('Siguiente')).not.toBeInTheDocument();
  });

  test('si el original de Drive no carga usa la miniatura grande', () => {
    render(
      <MediaLightbox
        posts={[post(1, { media_url: null, drive_file_id: 'file-1' })]}
        startIndex={0}
        token="tok"
        onClose={() => {}}
        onDetails={() => {}}
      />
    );
    expect(shownSrc()).toContain('/api/drive/files/file-1/image?token=tok');
    fireEvent.error(screen.getByAltText('publicación'));
    expect(shownSrc()).toContain('/api/posts/1/thumbnail?size=640');
  });
});
