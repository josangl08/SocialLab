import { render, screen, fireEvent } from '@testing-library/react';
import { describe, test, expect, vi } from 'vitest';
import DayMosaic, { POST_DRAG_TYPE, type MosaicItem } from '../components/calendar/DayMosaic';
import type { Post } from '../types';

function item(id: number, overrides: Partial<Post> = {}, className = 'event-status-scheduled'): MosaicItem {
  return {
    post: {
      id,
      user_id: 'u1',
      content: `Post ${id}`,
      media_url: null,
      drive_file_id: `file-${id}`,
      post_type: 'post',
      status: 'scheduled',
      scheduled_at: '2030-06-27T12:00:00Z',
      created_at: '2030-06-01T10:00:00Z',
      ...overrides,
    },
    className,
  };
}

const items = (n: number) => Array.from({ length: n }, (_, i) => item(i + 1));

describe('DayMosaic', () => {
  test.each([
    [1, 'sl-mosaic--1', 1],
    [2, 'sl-mosaic--2', 2],
    [3, 'sl-mosaic--4', 3],
    [4, 'sl-mosaic--4', 4],
  ])('%i publicaciones → disposición %s con %i miniaturas', (n, layout, tiles) => {
    render(<DayMosaic items={items(n)} token="tok" onOpen={() => {}} />);
    expect(screen.getByTestId('day-mosaic')).toHaveClass(layout);
    expect(screen.getAllByTestId(/^mosaic-tile-/)).toHaveLength(tiles);
    expect(screen.queryByText(/^\+\d+$/)).not.toBeInTheDocument();
  });

  test('6 publicaciones → 3 miniaturas y casilla +3 que abre la 4.ª', () => {
    const onOpen = vi.fn();
    render(<DayMosaic items={items(6)} token="tok" onOpen={onOpen} />);
    expect(screen.getByTestId('day-mosaic')).toHaveClass('sl-mosaic--4');
    expect(screen.getAllByTestId(/^mosaic-tile-/)).toHaveLength(3);
    fireEvent.click(screen.getByText('+3'));
    expect(onOpen).toHaveBeenCalledWith(3);
  });

  test('cada miniatura lleva la clase de su estado', () => {
    render(
      <DayMosaic
        items={[item(1, { status: 'draft' }, 'event-post event-status-draft'), item(2, { status: 'published' }, 'event-post event-status-published')]}
        token="tok"
        onOpen={() => {}}
      />
    );
    expect(screen.getByTestId('mosaic-tile-1')).toHaveClass('event-status-draft');
    expect(screen.getByTestId('mosaic-tile-2')).toHaveClass('event-status-published');
  });

  test('una publicación ocupa la celda con miniatura de 160 y carga diferida', () => {
    const { container } = render(<DayMosaic items={items(1)} token="tok" onOpen={() => {}} />);
    const img = container.querySelector('img')!;
    expect(img.getAttribute('src')).toContain('/api/posts/1/thumbnail?size=160');
    expect(img).toHaveAttribute('loading', 'lazy');
  });

  test('sin imagen o con vídeo de Storage muestra el icono del formato', () => {
    render(
      <DayMosaic
        items={[
          item(1, { drive_file_id: null }),
          item(2, { drive_file_id: null, media_url: 'https://s.test/reel.mp4', content_format: 'reel' }),
        ]}
        token="tok"
        onOpen={() => {}}
      />
    );
    expect(screen.getByTestId('mosaic-placeholder-1')).toHaveClass('bi-image');
    expect(screen.getByTestId('mosaic-placeholder-2')).toHaveClass('bi-camera-video');
    expect(screen.getByTestId('day-mosaic')).toHaveClass('sl-mosaic--2');
  });

  test('si la miniatura falla se muestra el icono', () => {
    const { container } = render(<DayMosaic items={items(1)} token="tok" onOpen={() => {}} />);
    fireEvent.error(container.querySelector('img')!);
    expect(screen.getByTestId('mosaic-placeholder-1')).toBeInTheDocument();
  });

  test('clic en una miniatura abre su índice; arrastrar transporta el post_id', () => {
    const onOpen = vi.fn();
    render(<DayMosaic items={items(2)} token="tok" onOpen={onOpen} />);
    fireEvent.click(screen.getByTestId('mosaic-tile-2'));
    expect(onOpen).toHaveBeenCalledWith(1);

    const setData = vi.fn();
    fireEvent.dragStart(screen.getByTestId('mosaic-tile-2'), { dataTransfer: { setData, effectAllowed: '' } });
    expect(setData).toHaveBeenCalledWith(POST_DRAG_TYPE, '2');
  });
});
