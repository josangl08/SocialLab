import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import ContentStudio from '../components/studio/ContentStudio';
import { useAuth } from '../context/AuthContext';
import { apiClient } from '../api/client';
import { contentApi } from '../api/content';
import { RedirectWithQuery } from '../App';

vi.mock('../context/AuthContext', () => ({
  useAuth: vi.fn(),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock('../api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    postForm: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    status: number;
    detail: string;
    constructor(status: number, detail: string) {
      super(detail);
      this.status = status;
      this.detail = detail;
    }
  },
}));

vi.mock('../api/content', () => ({
  contentApi: {
    lintCaption: vi.fn(),
    getHookFormulas: vi.fn(),
    generateRepurpose: vi.fn(),
    generateReel: vi.fn(),
    generateCarousel: vi.fn(),
  },
}));

describe('ContentStudio Component', () => {
  const mockToken = 'mock-token-123';
  const mockAccounts = [
    {
      id: 1,
      username: 'test_user_1',
      account_name: 'Cuenta Deportes',
      sector: 'deportes',
      telegram_chat_id: 'chat-101',
    },
    {
      id: 2,
      username: 'test_user_2',
      account_name: 'Cuenta Moda',
      sector: 'moda',
      telegram_chat_id: null,
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    (useAuth as any).mockReturnValue({
      token: mockToken,
      isAuthenticated: true,
      user: { id: 'usr-1' },
      logout: vi.fn(),
    });

    (apiClient.get as any).mockImplementation((url: string) => {
      if (url.includes('/instagram/accounts')) {
        return Promise.resolve(mockAccounts);
      }
      if (url.includes('/api/drive/exports')) {
        return Promise.resolve([]);
      }
      return Promise.resolve([]);
    });

    (apiClient.postForm as any).mockResolvedValue({ id: 10 });

    (contentApi.getHookFormulas as any).mockResolvedValue([
      { id: 1, name: 'Pregunta directa', template: '¿Sabías que...?', best_for: ['commercial_campaign'] },
    ]);

    (contentApi.lintCaption as any).mockResolvedValue({
      visible_text: '',
      visible_length: 0,
      truncated: false,
      hashtag_count: 0,
      hashtag_limit: 5,
      hashtags_over_limit: [],
      keywords_missing_in_visible: [],
      slop: { score: 0, hits: [], invisible_chars: 0, em_dash_count: 0 },
      hook: { formula_id: null, formula_name: null, score: 0, dealbreakers: [] },
      warnings: [],
    });
  });

  // --- Casos migrados de CreatePost.test.tsx ---

  test('renders Instagram account selector option lists', async () => {
    render(
      <MemoryRouter>
        <ContentStudio />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Cuenta de Instagram/i)).toBeInTheDocument();
    });

    const selector = screen.getByLabelText(/Cuenta de Instagram/i) as HTMLSelectElement;
    expect(selector).toBeInTheDocument();

    const options = within(selector).getAllByRole('option');
    expect(options[0]).toHaveValue('');
    expect(options[1]).toHaveValue('1');
    expect(options[2]).toHaveValue('2');
    expect(options[1].textContent).toContain('@test_user_1');
    expect(options[2].textContent).toContain('@test_user_2');
  });

  test('allows selecting an Instagram account', async () => {
    render(
      <MemoryRouter>
        <ContentStudio />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Cuenta de Instagram/i)).toBeInTheDocument();
    });

    const selector = screen.getByLabelText(/Cuenta de Instagram/i) as HTMLSelectElement;
    fireEvent.change(selector, { target: { value: '2' } });
    expect(selector.value).toBe('2');
  });

  // --- Requisitos específicos de ContentStudio ---

  test('muestra origen P1 solo cuando la cuenta es de sector deportes', async () => {
    render(
      <MemoryRouter>
        <ContentStudio />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Cuenta de Instagram/i)).toBeInTheDocument();
    });

    // La cuenta 1 es de deportes por defecto
    expect(screen.getByRole('button', { name: /Estadísticas deportivas/i })).toBeInTheDocument();

    // Cambiar a la cuenta 2 (sector: 'moda')
    const selector = screen.getByLabelText(/Cuenta de Instagram/i);
    fireEvent.change(selector, { target: { value: '2' } });

    // "Estadísticas deportivas" ya no debe aparecer
    expect(screen.queryByRole('button', { name: /Estadísticas deportivas/i })).not.toBeInTheDocument();
  });

  test('guarda borrador con notify_telegram=false', async () => {
    render(
      <MemoryRouter>
        <ContentStudio />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Texto del Caption/i)).toBeInTheDocument();
    });

    const textarea = screen.getByLabelText(/Texto del Caption/i);
    fireEvent.change(textarea, { target: { value: 'Borrador de prueba' } });

    const draftBtn = screen.getByRole('button', { name: /Guardar borrador/i });
    fireEvent.click(draftBtn);

    await waitFor(() => {
      expect(apiClient.postForm).toHaveBeenCalledTimes(1);
    });

    const [endpoint, formData] = (apiClient.postForm as any).mock.calls[0];
    expect(endpoint).toBe('/api/posts');
    expect(formData.get('content')).toBe('Borrador de prueba');
    expect(formData.get('status')).toBe('draft');
    expect(formData.get('notify_telegram')).toBe('false');
  });

  test('no programa sin imagen o vídeo', async () => {
    render(
      <MemoryRouter>
        <ContentStudio />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Fecha y hora programada/i)).toBeInTheDocument();
    });

    const futureDate = new Date();
    futureDate.setDate(futureDate.getDate() + 5);
    fireEvent.change(screen.getByLabelText(/Fecha y hora programada/i), {
      target: { value: futureDate.toISOString().slice(0, 16) },
    });
    fireEvent.click(screen.getByRole('button', { name: /Programar/i }));

    expect(await screen.findByText(/Añade una imagen o vídeo/i)).toBeInTheDocument();
    expect(apiClient.postForm).not.toHaveBeenCalled();
  });

  test('origen P1 visible con sector deportivo en texto libre', async () => {
    (apiClient.get as any).mockImplementation((url: string) => {
      if (url.includes('/instagram/accounts')) {
        return Promise.resolve([{ id: 3, username: 'viajes', sector: 'Contenido Visual Deportivo y Viajes' }]);
      }
      return Promise.resolve(null);
    });

    render(
      <MemoryRouter>
        <ContentStudio />
      </MemoryRouter>
    );

    expect(await screen.findByRole('button', { name: /Estadísticas deportivas/i })).toBeInTheDocument();
  });

  test('usa la estrategia de la campaña activa del mes', async () => {
    (apiClient.get as any).mockImplementation((url: string) => {
      if (url.includes('/instagram/accounts')) return Promise.resolve(mockAccounts);
      if (url.includes('/api/agent/campaign')) {
        return Promise.resolve({ account_id: 1, strategy_mode: 'commercial_campaign' });
      }
      return Promise.resolve([]);
    });

    render(
      <MemoryRouter>
        <ContentStudio />
      </MemoryRouter>
    );

    expect(await screen.findByRole('button', { name: /Campaña comercial/i })).toBeInTheDocument();
  });

  test('programa publicación con fecha futura y notify_telegram=false', async () => {
    const { container } = render(
      <MemoryRouter>
        <ContentStudio />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Fecha y hora programada/i)).toBeInTheDocument();
    });

    const textarea = screen.getByLabelText(/Texto del Caption/i);
    fireEvent.change(textarea, { target: { value: 'Post para programar' } });

    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(fileInput, {
      target: { files: [new File(['img'], 'foto.png', { type: 'image/png' })] },
    });

    const dateInput = screen.getByLabelText(/Fecha y hora programada/i);
    const futureDate = new Date();
    futureDate.setDate(futureDate.getDate() + 5);
    const futureStr = futureDate.toISOString().slice(0, 16);

    fireEvent.change(dateInput, { target: { value: futureStr } });

    const scheduleBtn = screen.getByRole('button', { name: /Programar/i });
    fireEvent.click(scheduleBtn);

    await waitFor(() => {
      expect(apiClient.postForm).toHaveBeenCalledTimes(1);
    });

    const [endpoint, formData] = (apiClient.postForm as any).mock.calls[0];
    expect(endpoint).toBe('/api/posts');
    expect(formData.get('status')).toBe('scheduled');
    expect(formData.get('notify_telegram')).toBe('false');
    expect(formData.get('scheduled_at')).toBeTruthy();
    expect((formData.get('media_file') as File).name).toBe('foto.png');
  });

  test('sube la imagen generada por P1 cuando llega como URL pública', async () => {
    (apiClient.get as any).mockImplementation((url: string) => {
      if (url.includes('/instagram/accounts')) return Promise.resolve(mockAccounts);
      if (url.includes('/api/drive/exports')) {
        return Promise.resolve([
          { id: 'exp-1', export_type: 'player', player: { name: 'Messi' }, stats: { goals: 12 } },
        ]);
      }
      return Promise.resolve(null);
    });
    (apiClient.post as any).mockResolvedValue({
      caption: 'Caption P1',
      preview_url: 'https://storage.test/templates/p1.png',
    });
    (global.fetch as any).mockResolvedValue({
      blob: () => Promise.resolve(new Blob(['png'], { type: 'image/png' })),
    });

    render(
      <MemoryRouter>
        <ContentStudio />
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole('button', { name: /Estadísticas deportivas/i }));
    fireEvent.click(await screen.findByText(/Messi/));
    fireEvent.click(screen.getByRole('button', { name: /Generar publicación/i }));
    await screen.findByText(/Estadísticas deportivas convertidas/i);

    fireEvent.click(screen.getByRole('button', { name: /Guardar borrador/i }));

    await waitFor(() => {
      expect(apiClient.postForm).toHaveBeenCalledTimes(1);
    });
    const [, formData] = (apiClient.postForm as any).mock.calls[0];
    expect(global.fetch).toHaveBeenCalledWith('https://storage.test/templates/p1.png');
    expect(formData.get('content')).toBe('Caption P1');
    expect(formData.get('media_file')).toBeInstanceOf(Blob);
  });

  test('botón de revisión deshabilitado sin Telegram y habilitado con Telegram', async () => {
    render(
      <MemoryRouter>
        <ContentStudio />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Cuenta de Instagram/i)).toBeInTheDocument();
    });

    // Cuenta 1 tiene telegram_chat_id: 'chat-101' -> habilitado
    const reviewBtn = screen.getByRole('button', { name: /Enviar a revisión en Telegram/i });
    expect(reviewBtn).not.toBeDisabled();

    // Cambiar a cuenta 2 (telegram_chat_id: null) -> deshabilitado
    const selector = screen.getByLabelText(/Cuenta de Instagram/i);
    fireEvent.change(selector, { target: { value: '2' } });

    expect(reviewBtn).toBeDisabled();
  });

  test('precarga fecha desde query ?date= y redirige /create-post a /generate', async () => {
    const testDate = '2026-10-15T10:00';
    render(
      <MemoryRouter initialEntries={[`/create-post?date=${encodeURIComponent(testDate)}`]}>
        <Routes>
          <Route path="/create-post" element={<RedirectWithQuery to="/generate" />} />
          <Route path="/generate" element={<ContentStudio />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      const dateInput = screen.getByLabelText(/Fecha y hora programada/i) as HTMLInputElement;
      expect(dateInput.value).toBe(testDate);
    });
  });

  // --- Fase C: origen Reciclar ---

  const quality = {
    visible_text: '', visible_length: 0, truncated: false, hashtag_count: 0, hashtag_limit: 5,
    hashtags_over_limit: [], keywords_missing_in_visible: [],
    slop: { score: 0, hits: [], invisible_chars: 0, em_dash_count: 0 },
    hook: { formula_id: null, formula_name: null, score: 0, dealbreakers: [] }, warnings: [],
  };
  const reelPiece = (n: number) => ({
    hooks: [
      { text: `Gancho A${n}`, score: 70, formula_id: 1 },
      { text: `Gancho B${n}`, score: 55, formula_id: 2 },
    ],
    beats: { beats: [{ label: 'Gancho', start_s: 0, end_s: 2, duration_s: 2, alert: null }], total_s: 2, loops_to_hook: false },
    on_screen_text: [],
    caption: `Gancho A${n}\nCuerpo del reel ${n}`,
    report: quality,
  });
  const carouselPiece = (n: number) => ({
    slides: [
      { index: 1, role: 'cover', text: `Portada ${n}`, word_count: 2 },
      { index: 2, role: 'stake', text: 'Por qué importa', word_count: 3 },
    ],
    caption: `Caption carrusel ${n}`,
    report: quality,
  });

  const openRepurpose = async () => {
    render(
      <MemoryRouter>
        <ContentStudio />
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByLabelText(/Cuenta de Instagram/i)).toHaveValue('1'));
    fireEvent.click(screen.getByRole('button', { name: /Reciclar contenido/i }));
  };

  test('reciclar muestra 5 piezas y abre un carrusel en el editor', async () => {
    (contentApi.generateRepurpose as any).mockResolvedValue({
      reels: [reelPiece(1), reelPiece(2), reelPiece(3)],
      carousels: [carouselPiece(1), carouselPiece(2)],
    });
    await openRepurpose();

    fireEvent.change(screen.getByLabelText(/Transcripción o texto largo/i), { target: { value: 'Transcripción del podcast' } });
    fireEvent.click(screen.getByRole('button', { name: /Generar 5 piezas/i }));

    const list = await screen.findByRole('list', { name: /Piezas recicladas/i });
    expect(within(list).getAllByRole('listitem')).toHaveLength(5);
    expect(contentApi.generateRepurpose).toHaveBeenCalledWith(
      expect.objectContaining({ account_id: 1, transcript: 'Transcripción del podcast' })
    );

    fireEvent.click(screen.getByRole('button', { name: /Abrir Carrusel 2/i }));
    expect(screen.getByTestId('carousel-editor')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Portada 2')).toBeInTheDocument();
    expect(screen.getByLabelText(/Texto del Caption/i)).toHaveValue('Caption carrusel 2');
  });

  test('abrir un reel reciclado permite alternar el gancho', async () => {
    (contentApi.generateRepurpose as any).mockResolvedValue({
      reels: [reelPiece(1), reelPiece(2), reelPiece(3)],
      carousels: [carouselPiece(1), carouselPiece(2)],
    });
    await openRepurpose();

    fireEvent.change(screen.getByLabelText(/Transcripción o texto largo/i), { target: { value: 'Texto' } });
    fireEvent.click(screen.getByRole('button', { name: /Generar 5 piezas/i }));
    fireEvent.click(await screen.findByRole('button', { name: /Abrir Reel 1/i }));

    const caption = screen.getByLabelText(/Texto del Caption/i);
    expect(caption).toHaveValue('Gancho A1\nCuerpo del reel 1');

    fireEvent.click(screen.getByRole('button', { name: /Gancho B1/i }));
    expect(caption).toHaveValue('Gancho B1\nCuerpo del reel 1');
  });

  test('reciclar bloquea textos de más de 30 000 caracteres', async () => {
    await openRepurpose();
    fireEvent.change(screen.getByLabelText(/Transcripción o texto largo/i), { target: { value: 'x'.repeat(30001) } });

    expect(screen.getByText(/Acorta el texto/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Generar 5 piezas/i })).toBeDisabled();
  });

  // --- Generar desde idea libre ---

  const renderStudio = async () => {
    render(
      <MemoryRouter>
        <ContentStudio />
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByLabelText(/Cuenta de Instagram/i)).toHaveValue('1'));
  };

  test('idea libre: sin generador en formato Post', async () => {
    await renderStudio();
    expect(screen.queryByRole('button', { name: /Generar con IA/i })).not.toBeInTheDocument();
  });

  test('idea libre: genera un Reel con la estrategia activa y lo abre con sus ganchos', async () => {
    (contentApi.generateReel as any).mockResolvedValue(reelPiece(9));
    await renderStudio();

    fireEvent.click(screen.getByRole('button', { name: /^Reel$/i }));
    fireEvent.change(screen.getByLabelText(/Tema del Reel/i), { target: { value: 'Rutina de mañana' } });
    fireEvent.click(screen.getByRole('button', { name: /Generar con IA/i }));

    await waitFor(() => expect(screen.getByLabelText(/Texto del Caption/i)).toHaveValue('Gancho A9\nCuerpo del reel 9'));
    expect(contentApi.generateReel).toHaveBeenCalledWith(
      expect.objectContaining({ account_id: 1, topic: 'Rutina de mañana', strategy_mode: 'personal_storyline' })
    );
    expect(screen.getByRole('group', { name: /Ganchos candidatos/i })).toBeInTheDocument();
  });

  test('idea libre: genera un carrusel con el nº de diapositivas elegido', async () => {
    (contentApi.generateCarousel as any).mockResolvedValue(carouselPiece(4));
    await renderStudio();

    fireEvent.click(screen.getByRole('button', { name: /^Carrusel$/i }));
    fireEvent.change(screen.getByLabelText(/Tema del carrusel/i), { target: { value: 'Errores al empezar' } });
    fireEvent.change(screen.getByLabelText(/Número de diapositivas/i), { target: { value: '9' } });
    fireEvent.click(screen.getByRole('button', { name: /Generar con IA/i }));

    expect(await screen.findByTestId('carousel-editor')).toBeInTheDocument();
    expect(contentApi.generateCarousel).toHaveBeenCalledWith(expect.objectContaining({ slides: 9, topic: 'Errores al empezar' }));
  });

  // --- Persistencia de la estructura ---

  const savedForm = () => (apiClient.postForm as any).mock.calls[0][1] as FormData;

  test('guardar un carrusel generado envía las diapositivas editadas', async () => {
    (contentApi.generateCarousel as any).mockResolvedValue(carouselPiece(1));
    await renderStudio();

    fireEvent.click(screen.getByRole('button', { name: /^Carrusel$/i }));
    fireEvent.change(screen.getByLabelText(/Tema del carrusel/i), { target: { value: 'Tema' } });
    fireEvent.click(screen.getByRole('button', { name: /Generar con IA/i }));
    fireEvent.change(await screen.findByDisplayValue('Portada 1'), { target: { value: 'Portada editada' } });
    fireEvent.click(screen.getByRole('button', { name: /Guardar borrador/i }));

    await waitFor(() => expect(apiClient.postForm).toHaveBeenCalled());
    expect(savedForm().get('content_format')).toBe('carousel');
    const structure = JSON.parse(savedForm().get('content_structure') as string);
    expect(structure.slides[0].text).toBe('Portada editada');
  });

  test('guardar un reel generado envía ganchos y beats', async () => {
    (contentApi.generateReel as any).mockResolvedValue(reelPiece(1));
    await renderStudio();

    fireEvent.click(screen.getByRole('button', { name: /^Reel$/i }));
    fireEvent.change(screen.getByLabelText(/Tema del Reel/i), { target: { value: 'Tema' } });
    fireEvent.click(screen.getByRole('button', { name: /Generar con IA/i }));
    await screen.findByRole('group', { name: /Ganchos candidatos/i });
    fireEvent.click(screen.getByRole('button', { name: /Guardar borrador/i }));

    await waitFor(() => expect(apiClient.postForm).toHaveBeenCalled());
    const structure = JSON.parse(savedForm().get('content_structure') as string);
    expect(structure.hooks).toHaveLength(2);
    expect(structure.beats.total_s).toBe(2);
  });

  test('un post escrito a mano no envía estructura', async () => {
    await renderStudio();
    fireEvent.change(screen.getByLabelText(/Texto del Caption/i), { target: { value: 'Hola' } });
    fireEvent.click(screen.getByRole('button', { name: /Guardar borrador/i }));

    await waitFor(() => expect(apiClient.postForm).toHaveBeenCalled());
    expect(savedForm().get('content_format')).toBe('post');
    expect(savedForm().has('content_structure')).toBe(false);
  });

  // --- Estrategia aplicada ---

  const mockCampaign = (campaign: object | null) => {
    (apiClient.get as any).mockImplementation((url: string) => {
      if (url.includes('/instagram/accounts')) return Promise.resolve(mockAccounts);
      if (url.includes('/api/agent/campaign')) return Promise.resolve(campaign);
      return Promise.resolve([]);
    });
  };

  test('sin campaña activa arranca con la estrategia personal', async () => {
    mockCampaign(null);
    await renderStudio();

    expect(await screen.findByRole('button', { name: /Historia personal/i })).toBeInTheDocument();
    expect(apiClient.get).toHaveBeenCalledWith(expect.stringContaining('/api/agent/campaign?account_id=1'));
  });

  test('cambiar la estrategia afecta a la generación y no modifica la campaña', async () => {
    mockCampaign({ account_id: 1, strategy_mode: 'commercial_campaign' });
    (contentApi.generateReel as any).mockResolvedValue(reelPiece(1));
    await renderStudio();

    fireEvent.click(await screen.findByRole('button', { name: /Campaña comercial/i }));
    expect(screen.getByRole('button', { name: /Historia personal/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /^Reel$/i }));
    fireEvent.change(screen.getByLabelText(/Tema del Reel/i), { target: { value: 'Tema' } });
    fireEvent.click(screen.getByRole('button', { name: /Generar con IA/i }));

    await waitFor(() =>
      expect(contentApi.generateReel).toHaveBeenCalledWith(expect.objectContaining({ strategy_mode: 'personal_storyline' }))
    );
    expect(apiClient.post).not.toHaveBeenCalled();
  });

  // --- Acciones de salida ---

  test('no programa sin fecha ni con fecha pasada', async () => {
    await renderStudio();

    fireEvent.click(screen.getByRole('button', { name: /Programar/i }));
    expect(await screen.findByText(/selecciona una fecha y hora futura/i)).toBeInTheDocument();

    const pastDate = new Date();
    pastDate.setDate(pastDate.getDate() - 1);
    fireEvent.change(screen.getByLabelText(/Fecha y hora programada/i), {
      target: { value: pastDate.toISOString().slice(0, 16) },
    });
    fireEvent.click(screen.getByRole('button', { name: /Programar/i }));

    expect(await screen.findByText(/debe ser en el futuro/i)).toBeInTheDocument();
    expect(apiClient.postForm).not.toHaveBeenCalled();
  });

  test('permite guardar aunque haya avisos de calidad', async () => {
    (contentApi.lintCaption as any).mockResolvedValue({
      visible_text: '', visible_length: 0, truncated: false, hashtag_count: 6, hashtag_limit: 5,
      hashtags_over_limit: ['#f'], keywords_missing_in_visible: [],
      slop: { score: 0, hits: [], invisible_chars: 0, em_dash_count: 0 },
      hook: { formula_id: null, formula_name: null, score: 0, dealbreakers: [] },
      warnings: [{ code: 'HASHTAGS_OVER_LIMIT', message: 'Más de 5 hashtags' }],
    });
    await renderStudio();

    fireEvent.change(screen.getByLabelText(/Texto del Caption/i), { target: { value: 'Hola #a #b #c #d #e #f' } });
    expect(await screen.findByText(/Más de 5 hashtags/i, {}, { timeout: 2000 })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Guardar borrador/i }));

    await waitFor(() => expect(apiClient.postForm).toHaveBeenCalled());
    expect(savedForm().get('content')).toBe('Hola #a #b #c #d #e #f');
  });
});
