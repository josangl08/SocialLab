import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { ProspectComments } from '../components/studio/ProspectComments';
import { contentApi } from '../api/content';

vi.mock('../api/content', () => ({
  contentApi: { generateProspectComments: vi.fn() },
}));

const suggestions = Array.from({ length: 9 }, (_, i) => ({
  type: i + 1,
  type_name: `Tipo ${i + 1}`,
  text: `Comentario ${i + 1}`,
}));

describe('ProspectComments', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });
  });

  test('plegado por defecto; al abrir pide sugerencias con la estrategia del Studio', async () => {
    vi.mocked(contentApi.generateProspectComments).mockResolvedValue({ suggestions });
    render(<ProspectComments accountId={3} strategyMode="commercial_campaign" />);

    expect(screen.queryByLabelText(/Pega el texto/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Comentarios de prospección/i }));

    fireEvent.change(screen.getByLabelText(/Pega el texto/i), { target: { value: 'Cómo escalar una agencia' } });
    fireEvent.click(screen.getByRole('button', { name: /Sugerir comentarios/i }));

    await waitFor(() =>
      expect(contentApi.generateProspectComments).toHaveBeenCalledWith({
        target_post_text: 'Cómo escalar una agencia',
        strategy_mode: 'commercial_campaign',
        account_id: 3,
      })
    );
    expect(await screen.findAllByRole('listitem')).toHaveLength(9);
    expect(screen.getByText('Tipo 1')).toBeInTheDocument();
  });

  test('copiar un comentario usa el portapapeles sin publicar nada', async () => {
    vi.mocked(contentApi.generateProspectComments).mockResolvedValue({ suggestions });
    render(<ProspectComments accountId={null} strategyMode="personal_storyline" />);

    fireEvent.click(screen.getByRole('button', { name: /Comentarios de prospección/i }));
    fireEvent.change(screen.getByLabelText(/Pega el texto/i), { target: { value: 'Post ajeno' } });
    fireEvent.click(screen.getByRole('button', { name: /Sugerir comentarios/i }));

    await waitFor(() =>
      expect(contentApi.generateProspectComments).toHaveBeenCalledWith({
        target_post_text: 'Post ajeno',
        strategy_mode: 'personal_storyline',
      })
    );
    fireEvent.click(await screen.findByRole('button', { name: 'Copiar comentario Tipo 4' }));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('Comentario 4');
    expect(await screen.findByText('Copiado')).toBeInTheDocument();
  });
});
