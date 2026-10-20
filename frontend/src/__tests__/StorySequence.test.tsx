import { render, screen, fireEvent, within } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import StorySequence from '../components/studio/StorySequence';
import { contentApi } from '../api/content';

vi.mock('../api/content', () => ({
  contentApi: { generateStory: vi.fn() },
}));

vi.mock('../api/client', () => ({
  ApiError: class ApiError extends Error {
    detail: string;
    constructor(_status: number, detail: string) {
      super(detail);
      this.detail = detail;
    }
  },
}));

describe('StorySequence', () => {
  beforeEach(() => vi.clearAllMocks());

  test('genera y muestra los frames en orden con su sticker', async () => {
    (contentApi.generateStory as any).mockResolvedValue({
      frames: [
        { index: 1, role: 'warmup', text: '¿Café o té?', sticker: 'poll', sticker_payload: { question: '¿Qué tomas?', options: ['Café', 'Té'] } },
        { index: 2, role: 'questions', text: 'Pregúntame lo que quieras', sticker: 'question' },
        { index: 3, role: 'dm', text: 'Escríbeme RUTINA por DM', sticker: 'dm_cta' },
      ],
    });
    render(<StorySequence accountId={7} />);

    fireEvent.change(screen.getByLabelText(/Tema de las Stories/i), { target: { value: 'Mañanas' } });
    fireEvent.click(screen.getByRole('button', { name: /Generar Stories del día/i }));

    const list = await screen.findByRole('list', { name: /Secuencia de Stories/i });
    const items = within(list).getAllByRole('listitem');
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent('Encuesta');
    expect(items[0]).toHaveTextContent('¿Qué tomas? · Café / Té');
    expect(items[1]).toHaveTextContent('Caja de preguntas');
    expect(items[2]).toHaveTextContent('Llamada al DM');
    expect(contentApi.generateStory).toHaveBeenCalledWith({ account_id: 7, topic: 'Mañanas' });
  });

  test('sin tema no envía topic (el backend usa la campaña del mes)', async () => {
    (contentApi.generateStory as any).mockResolvedValue({ frames: [] });
    render(<StorySequence accountId={7} />);
    fireEvent.click(screen.getByRole('button', { name: /Generar Stories del día/i }));
    expect(contentApi.generateStory).toHaveBeenCalledWith({ account_id: 7, topic: undefined });
    expect(await screen.findByRole('button', { name: /Generar Stories del día/i })).toBeEnabled();
  });

  test('deshabilitado sin cuenta', () => {
    render(<StorySequence accountId={null} />);
    expect(screen.getByRole('button', { name: /Generar Stories del día/i })).toBeDisabled();
  });
});
