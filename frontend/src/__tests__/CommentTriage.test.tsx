import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { CommentTriage } from '../components/studio/CommentTriage';
import { contentApi } from '../api/content';

vi.mock('../api/content', () => ({
  contentApi: {
    getCommentsTriage: vi.fn(),
    triageManualComments: vi.fn(),
  },
}));

describe('CommentTriage Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
  });

  test('carga y muestra comentarios clasificados con etiquetas y respuestas sugeridas (cuenta profesional)', async () => {
    vi.mocked(contentApi.getCommentsTriage).mockResolvedValue({
      source: 'api',
      comments: [
        {
          id: 'c1',
          text: '¿Cuánto cuesta el curso completo?',
          username: 'juan_perez',
          label: 'question',
          suggested_reply: 'Hola Juan, el curso cuesta 49€. Tienes el enlace en la bio.',
        },
        {
          id: 'c2',
          text: 'Me interesa contratar vuestra consultoría ya mismo',
          username: 'laura_biz',
          label: 'lead',
          suggested_reply: 'Genial Laura, te he enviado un DM con los detalles para agendar llamada.',
        },
        {
          id: 'c3',
          text: '¡Brutal este post! Muchísimas gracias.',
          username: 'carlos_dev',
          label: 'support',
          suggested_reply: '¡Muchas gracias Carlos! Me alegra que te sirva.',
        },
      ],
    });

    render(<CommentTriage postId={10} strategyMode="commercial_campaign" />);

    expect(await screen.findByText('Triaje de Comentarios')).toBeInTheDocument();

    // Verify items rendered
    expect(await screen.findByText('@juan_perez')).toBeInTheDocument();
    expect(screen.getByText('¿Cuánto cuesta el curso completo?')).toBeInTheDocument();
    expect(screen.getByText('Pregunta')).toBeInTheDocument();
    expect(
      screen.getByText('Hola Juan, el curso cuesta 49€. Tienes el enlace en la bio.')
    ).toBeInTheDocument();

    expect(screen.getByText('@laura_biz')).toBeInTheDocument();
    expect(screen.getByText('Lead')).toBeInTheDocument();

    expect(screen.getByText('@carlos_dev')).toBeInTheDocument();
    expect(screen.getByText('Soporte')).toBeInTheDocument();
  });

  test('copiar respuesta sugerida utiliza el portapapeles y no realiza ninguna llamada de publicación', async () => {
    vi.mocked(contentApi.getCommentsTriage).mockResolvedValue({
      source: 'api',
      comments: [
        {
          id: 'c1',
          text: '¿Tenéis soporte?',
          username: 'ana',
          label: 'question',
          suggested_reply: 'Sí Ana, soporte 24/7.',
        },
      ],
    });

    render(<CommentTriage postId={10} />);

    expect(await screen.findByText('@ana')).toBeInTheDocument();

    const copyBtn = screen.getByRole('button', { name: /Copiar respuesta sugerida/i });
    fireEvent.click(copyBtn);

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('Sí Ana, soporte 24/7.');
    expect(await screen.findByText('Copiado')).toBeInTheDocument();
  });

  test('muestra aviso de permisos y formulario manual cuando source es unavailable', async () => {
    vi.mocked(contentApi.getCommentsTriage).mockResolvedValue({
      source: 'unavailable',
      comments: [],
    });

    render(<CommentTriage postId={10} />);

    const notice = await screen.findByTestId('unavailable-notice');
    expect(notice).toHaveTextContent(/instagram_business_manage_comments/i);
    expect(
      screen.getByPlaceholderText(/¿Cuánto cuesta el servicio\?/i)
    ).toBeInTheDocument();
  });

  test('permite enviar comentarios pegados manualmente y visualiza los resultados', async () => {
    vi.mocked(contentApi.getCommentsTriage).mockResolvedValue({
      source: 'unavailable',
      comments: [],
    });

    vi.mocked(contentApi.triageManualComments).mockResolvedValue({
      source: 'manual',
      comments: [
        {
          id: 'm1',
          text: '¿Hacen envíos internacionales?',
          label: 'question',
          suggested_reply: 'Sí, enviamos a todo el mundo.',
        },
      ],
    });

    render(<CommentTriage postId={10} strategyMode="commercial_campaign" />);

    const textarea = await screen.findByPlaceholderText(/¿Cuánto cuesta el servicio\?/i);
    fireEvent.change(textarea, {
      target: { value: '¿Hacen envíos internacionales?' },
    });

    const submitBtn = screen.getByRole('button', { name: /Analizar comentarios/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(contentApi.triageManualComments).toHaveBeenCalledWith({
        comments: ['¿Hacen envíos internacionales?'],
        strategy_mode: 'commercial_campaign',
      });
    });

    expect(await screen.findByText('¿Hacen envíos internacionales?')).toBeInTheDocument();
    expect(screen.getByText('Pregunta')).toBeInTheDocument();
    expect(screen.getByText('Sí, enviamos a todo el mundo.')).toBeInTheDocument();
  });

  test('muestra advertencia clara de que nada se publica automáticamente en Instagram', async () => {
    vi.mocked(contentApi.getCommentsTriage).mockResolvedValue({
      source: 'api',
      comments: [],
    });

    render(<CommentTriage postId={10} />);

    expect(
      await screen.findByText(/Las respuestas son sugerencias\. Nada se publica de forma automática en Instagram\./i)
    ).toBeInTheDocument();
  });
});
