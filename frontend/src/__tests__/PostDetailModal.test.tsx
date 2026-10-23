import { render, screen, waitFor, within } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import PostDetailModal from '../components/posts/PostDetailModal';
import { apiClient } from '../api/client';
import { contentApi } from '../api/content';
import type { Post } from '../types';

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));

vi.mock('../api/client', () => ({
  apiClient: {
    get: vi.fn().mockImplementation(() => Promise.resolve(null)),
    post: vi.fn().mockImplementation(() => Promise.resolve({})),
    putForm: vi.fn().mockImplementation(() => Promise.resolve({})),
    delete: vi.fn().mockImplementation(() => Promise.resolve({})),
    getUrl: (p: string) => p,
  },
  ApiError: class ApiError extends Error {},
}));

vi.mock('../api/content', () => ({
  contentApi: {
    getCommentsTriage: vi.fn().mockImplementation(() => Promise.resolve({ source: 'api', comments: [] })),
    triageManualComments: vi.fn().mockImplementation(() => Promise.resolve({})),
    generateDmFunnel: vi.fn().mockImplementation(() => Promise.resolve({})),
  },
}));

const minutesAgo = (m: number) => new Date(Date.now() - m * 60_000).toISOString();

const baseStoryPost: Post = {
  id: 10,
  user_id: 'u1',
  content: '',
  media_url: 'https://cdn.instagram.com/story.jpg?oh=1',
  post_type: 'story',
  status: 'published',
  scheduled_at: null,
  created_at: minutesAgo(30),
  publication_date: minutesAgo(30),
  instagram_account_id: 1,
};

const metrics = {
  views: 282,
  reach: 228,
  likes: 24,
  replies: 4,
  link_clicks: 1,
  story_navigation: { tap_forward: 132, tap_back: 19, tap_exit: 93, swipe_forward: 18 },
};

const renderModal = (post: Post) =>
  render(<PostDetailModal show onHide={() => {}} post={post} />);

describe('PostDetailModal — Stories (AD-2, AD-2b)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.get).mockResolvedValue(null);
    vi.mocked(contentApi.getCommentsTriage).mockResolvedValue({ source: 'api', comments: [] });
  });

  test('muestra el rendimiento de una Story con métricas guardadas', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) =>
      Promise.resolve(url === '/api/posts/10' ? { ...baseStoryPost, story_metrics: metrics } : null));

    renderModal(baseStoryPost);

    const block = await screen.findByTestId('story-performance');
    expect(block).toHaveTextContent('Rendimiento de la Story');
    for (const [label, value] of [['Vistas', '282'], ['Alcance', '228'], ['Me gusta', '24'], ['Respuestas', '4'],
      ['Clics en enlace', '1'], ['Avances', '132'], ['Retrocesos', '19'], ['Salidas', '93']]) {
      expect(within(block).getByText(label).previousSibling).toHaveTextContent(value);
    }
  });

  test('Story recién publicada sin métricas muestra el aviso de próxima sincronización', async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) =>
      Promise.resolve(url === '/api/posts/10' ? { ...baseStoryPost, story_metrics: null } : null));

    renderModal(baseStoryPost);

    expect(await screen.findByText(/disponibles en la próxima sincronización/i)).toBeInTheDocument();
    expect(screen.queryByTestId('story-performance')).not.toBeInTheDocument();
  });

  test('Story caducada sin métricas no muestra el aviso', async () => {
    renderModal({ ...baseStoryPost, publication_date: minutesAgo(60 * 48) });

    await waitFor(() => expect(apiClient.get).toHaveBeenCalledWith('/api/posts/10'));
    expect(screen.queryByText(/disponibles en la próxima sincronización/i)).not.toBeInTheDocument();
  });

  test('un post que no es Story no pide métricas ni muestra el bloque', async () => {
    renderModal({ ...baseStoryPost, post_type: 'IMAGE' });

    await waitFor(() => expect(apiClient.get).toHaveBeenCalled());
    expect(apiClient.get).not.toHaveBeenCalledWith('/api/posts/10');
    expect(screen.queryByTestId('story-performance')).not.toBeInTheDocument();
  });

  test('una Story muestra su miniatura guardada en lugar de la media del CDN', async () => {
    const { container } = renderModal({
      ...baseStoryPost,
      media_url: 'https://cdn.instagram.com/story.mp4?oh=1',
      thumbnail_url_base: 'https://storage.test/thumbnails/u1/10/key',
    });

    expect(container.querySelector('video')).not.toBeInTheDocument();
    expect(container.querySelector('img.pdm-media-img')?.getAttribute('src'))
      .toBe('https://storage.test/thumbnails/u1/10/key_640.webp');
    await waitFor(() => expect(apiClient.get).toHaveBeenCalled());
  });
});

describe('PostDetailModal — días específicos (AD-3)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.get).mockResolvedValue(null);
  });

  test('avisa de que Hermes movió el post a un día permitido', () => {
    const post = {
      ...baseStoryPost, id: 11, post_type: 'post', status: 'draft', publication_date: null,
      scheduled_at: '2026-11-05T19:00:00Z',
      quality_report: {
        schedule_adjustment: { from: '2026-11-06T20:00:00+01:00', to: '2026-11-05T20:00:00+01:00', reason: 'fixed_days' },
      },
    } as unknown as Post;
    renderModal(post);
    const notice = screen.getByTestId('schedule-adjustment');
    expect(notice).toHaveTextContent(/viernes, 6 nov.*jueves, 5 nov/);
  });

  test('sin ajuste no muestra el aviso', () => {
    renderModal({ ...baseStoryPost, id: 12, post_type: 'post', status: 'draft', publication_date: null });
    expect(screen.queryByTestId('schedule-adjustment')).not.toBeInTheDocument();
  });
});
