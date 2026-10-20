import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import PostDetailModal from '../components/posts/PostDetailModal';
import { DmFunnel } from '../components/studio/DmFunnel';
import { apiClient } from '../api/client';
import { contentApi } from '../api/content';
import type { Post } from '../types';

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));

vi.mock('../api/client', () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), putForm: vi.fn(), delete: vi.fn(), getUrl: (p: string) => p },
  ApiError: class ApiError extends Error {},
}));

vi.mock('../api/content', () => ({
  contentApi: {
    getCommentsTriage: vi.fn(),
    triageManualComments: vi.fn(),
    generateDmFunnel: vi.fn(),
  },
}));

const basePost: Post = {
  id: 7,
  user_id: 'u1',
  content: 'Comenta GUIA y te la envío',
  media_url: null,
  post_type: 'image',
  status: 'published',
  scheduled_at: null,
  created_at: '2026-10-01T10:00:00Z',
  instagram_account_id: 3,
};

const renderModal = (post: Post) =>
  render(<PostDetailModal show onHide={() => {}} post={post} />);

describe('PostDetailModal — comunidad (Fase F)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(contentApi.getCommentsTriage).mockResolvedValue({ source: 'api', comments: [] });
  });

  test('cuenta comercial: post publicado muestra triaje y embudo de DM', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ strategy_mode: 'commercial_campaign' });
    renderModal(basePost);

    expect(await screen.findByTestId('comment-triage-panel')).toBeInTheDocument();
    expect(screen.getByTestId('dm-funnel-panel')).toBeInTheDocument();
    expect(contentApi.getCommentsTriage).toHaveBeenCalledWith(7);
  });

  test('cuenta personal (sin campaña): triaje sí, embudo de DM no', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(null);
    renderModal(basePost);

    expect(await screen.findByTestId('comment-triage-panel')).toBeInTheDocument();
    expect(screen.queryByTestId('dm-funnel-panel')).not.toBeInTheDocument();
  });

  test('post no publicado: no se piden comentarios', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ strategy_mode: 'commercial_campaign' });
    renderModal({ ...basePost, status: 'draft' });

    expect(await screen.findByTestId('dm-funnel-panel')).toBeInTheDocument();
    expect(screen.queryByTestId('comment-triage-panel')).not.toBeInTheDocument();
    expect(contentApi.getCommentsTriage).not.toHaveBeenCalled();
  });
});

describe('DmFunnel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });
  });

  test('no se renderiza en cuentas personales', () => {
    const { container } = render(<DmFunnel strategyMode="personal_storyline" accountId={3} />);
    expect(container).toBeEmptyDOMElement();
  });

  test('genera el DM de entrega y 2 seguimientos y los copia sin enviar nada', async () => {
    vi.mocked(contentApi.generateDmFunnel).mockResolvedValue({
      delivery_dm: 'Gracias por comentar GUIA: [ENLACE]',
      follow_ups: ['¿Te sirvió?', '¿Cómo te fue?'],
    });
    render(<DmFunnel strategyMode="commercial_campaign" accountId={3} />);

    fireEvent.change(screen.getByPlaceholderText(/GUIA, SISTEMA/i), { target: { value: 'GUIA' } });
    fireEvent.change(screen.getByPlaceholderText(/Plantilla de Notion/i), { target: { value: 'Guía PDF' } });
    fireEvent.click(screen.getByRole('button', { name: /Generar mensajes/i }));

    await waitFor(() =>
      expect(contentApi.generateDmFunnel).toHaveBeenCalledWith({
        keyword: 'GUIA', resource_description: 'Guía PDF', account_id: 3,
      })
    );
    expect(await screen.findByText('Gracias por comentar GUIA: [ENLACE]')).toBeInTheDocument();
    expect(screen.getByText('¿Te sirvió?')).toBeInTheDocument();
    expect(screen.getByText('¿Cómo te fue?')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Copiar seguimiento 2' }));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('¿Cómo te fue?');
    expect(await screen.findByText('Copiado')).toBeInTheDocument();
  });
});
