import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import EditPostForm from '../components/posts/EditPostForm';
import { apiClient } from '../api/client';
import type { Post } from '../types';

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ token: 'tok' }),
}));

vi.mock('../api/client', () => ({
  apiClient: { get: vi.fn(), putForm: vi.fn() },
  ApiError: class ApiError extends Error {
    detail = '';
  },
}));

const basePost: Post = {
  id: 5,
  user_id: 'u1',
  content: 'Caption',
  media_url: 'https://mock.storage.test/drafts/a.png',
  post_type: 'carousel',
  status: 'draft',
  scheduled_at: null,
  created_at: '2026-10-01T10:00:00',
  content_format: 'carousel',
  content_structure: {
    slides: [
      { index: 1, role: 'cover', text: 'Portada guardada', word_count: 2 },
      { index: 2, role: 'stake', text: 'Por qué importa', word_count: 3 },
    ],
  },
};

const sentForm = () => (apiClient.putForm as any).mock.calls[0][1] as FormData;

describe('EditPostForm con estructura', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (apiClient.get as any).mockResolvedValue([]);
    (apiClient.putForm as any).mockResolvedValue({});
  });

  test('muestra y guarda las diapositivas editadas de un carrusel', async () => {
    const onSave = vi.fn();
    render(<EditPostForm post={basePost} onSave={onSave} onCancel={vi.fn()} />);

    fireEvent.change(screen.getByDisplayValue('Portada guardada'), { target: { value: 'Nueva portada' } });
    fireEvent.click(screen.getByRole('button', { name: /Guardar cambios/i }));

    await waitFor(() => expect(onSave).toHaveBeenCalled());
    expect(sentForm().get('content_format')).toBe('carousel');
    const structure = JSON.parse(sentForm().get('content_structure') as string);
    expect(structure.slides[0].text).toBe('Nueva portada');
    expect(structure.slides).toHaveLength(2);
  });

  test('si deja de ser carrusel no reenvía la estructura', async () => {
    const onSave = vi.fn();
    render(<EditPostForm post={basePost} onSave={onSave} onCancel={vi.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: /^Post$/i }));
    expect(screen.queryByTestId('carousel-editor')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Guardar cambios/i }));

    await waitFor(() => expect(onSave).toHaveBeenCalled());
    expect(sentForm().has('content_structure')).toBe(false);
  });

  test('un reel muestra su beat sheet guardado', async () => {
    const reelPost: Post = {
      ...basePost,
      post_type: 'reel',
      content_format: 'reel',
      content_structure: {
        beats: {
          beats: [{ label: 'Gancho', text: 'Hola', start_s: 0, end_s: 5, duration_s: 5, alert: 'OVER_4S' }],
          total_s: 5,
          loops_to_hook: false,
        },
      },
    };
    render(<EditPostForm post={reelPost} onSave={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByText(/Beat Sheet/i)).toBeInTheDocument();
    await waitFor(() => expect(apiClient.get).toHaveBeenCalledWith('/instagram/accounts'));
  });

  test('un post sin estructura no muestra editor ni la envía', async () => {
    const onSave = vi.fn();
    const plain: Post = { ...basePost, post_type: 'post', content_format: null, content_structure: null };
    render(<EditPostForm post={plain} onSave={onSave} onCancel={vi.fn()} />);

    expect(screen.queryByTestId('carousel-editor')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Guardar cambios/i }));
    await waitFor(() => expect(onSave).toHaveBeenCalled());
    expect(sentForm().has('content_structure')).toBe(false);
  });
});

describe('EditPostForm en la zona de la cuenta', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (apiClient.get as any).mockResolvedValue([
      { id: 7, username: 'acc', primary_timezone: 'Europe/Madrid', secondary_timezone: 'Asia/Kuching' },
    ]);
    (apiClient.putForm as any).mockResolvedValue({});
  });

  test('muestra la hora en la zona de la cuenta y guarda el instante UTC', async () => {
    const post: Post = {
      ...basePost, post_type: 'post', content_format: 'post', content_structure: null,
      status: 'scheduled', scheduled_at: '2026-10-14T18:00:00Z', instagram_account_id: 7,
    };
    const onSave = vi.fn();
    render(<EditPostForm post={post} onSave={onSave} onCancel={vi.fn()} />);

    const input = await screen.findByDisplayValue('2026-10-14T20:00');
    expect(screen.getByTestId('schedule-zone-hint')).toHaveTextContent('Hora de Madrid');
    expect(screen.getByTestId('schedule-zone-hint')).toHaveTextContent('Jue 15 · 02:00 Kuching');

    fireEvent.change(input, { target: { value: '2026-10-15T18:00' } });
    fireEvent.click(screen.getByRole('button', { name: /Guardar cambios/i }));

    await waitFor(() => expect(onSave).toHaveBeenCalled());
    expect(sentForm().get('scheduled_at')).toBe('2026-10-15T16:00:00.000Z');
  });
});
